"""Voz do engenheiro e ajustes do painel.

- Ajustes: idioma, nome do piloto, voz, velocidade e volume (dados/config.json).
- Voz: gera a fala com as vozes neurais da Microsoft (pacote edge-tts, precisa
  de internet). Cada mensagem e preparada assim que o engenheiro a cria, para
  ja estar pronta quando chegar a hora de falar. Sem internet, o painel usa a
  voz do Windows.
"""
import asyncio
import hashlib
import json
import os
import queue
import threading
import time
from collections import OrderedDict

try:
    import edge_tts
except ImportError:  # pacote nao instalado: o painel usa a voz do Windows
    edge_tts = None

import idioma
from caminhos import DADOS
from idioma import N_, tx

PASTA = DADOS
ARQUIVO = os.path.join(PASTA, "config.json")

VOZES = [
    {"id": "pt-BR-AntonioNeural", "lang": "pt", "nome": "Antonio", "tipo": N_("masculina, natural")},
    {"id": "pt-BR-FranciscaNeural", "lang": "pt", "nome": "Francisca", "tipo": N_("feminina, natural")},
    {"id": "pt-BR-ThalitaMultilingualNeural", "lang": "pt", "nome": "Thalita", "tipo": N_("feminina, natural")},
    {"id": "en-GB-RyanNeural", "lang": "en", "nome": "Ryan", "tipo": N_("masculina, britânica")},
    {"id": "en-GB-SoniaNeural", "lang": "en", "nome": "Sonia", "tipo": N_("feminina, britânica")},
    {"id": "en-US-AndrewNeural", "lang": "en", "nome": "Andrew", "tipo": N_("masculina, americana")},
    {"id": "en-AU-WilliamNeural", "lang": "en", "nome": "William", "tipo": N_("masculina, australiana")},
    {"id": "windows", "lang": None, "nome": N_("Voz do Windows"), "tipo": N_("robótica, funciona sem internet")},
]
IDS = {v["id"] for v in VOZES}
LANG_VOZ = {v["id"]: v["lang"] for v in VOZES}
VOZ_PADRAO = {"pt": "pt-BR-AntonioNeural", "en": "en-GB-RyanNeural"}


def vozes(lang):
    """Vozes do idioma (e a do Windows), com a descricao traduzida."""
    return [dict(v, tipo=tx(v["tipo"]), nome=tx(v["nome"])) for v in VOZES if v["lang"] in (lang, None)]
# tom da mensagem -> (ajuste de velocidade em %, ajuste de tom em Hz)
TONS = {"normal": (0, 0), "calmo": (-5, -2), "animado": (8, 4), "urgente": (14, 1)}

PADRAO = {"idioma": None, "nome": "", "nome_jogo": True, "voz": None, "velocidade": 6, "volume": 100,
          "radio": True, "chiado": 35}


class Ajustes:
    def __init__(self, caminho=ARQUIVO):
        self.caminho = caminho
        self.lock = threading.Lock()
        self.dados = dict(PADRAO)
        try:
            with open(caminho, encoding="utf-8") as f:
                self.dados.update(self._valida(json.load(f)))
        except (OSError, ValueError):
            pass
        self._coerente()

    def _coerente(self):
        """Idioma (o do Windows na primeira vez) e uma voz que fale esse idioma."""
        d = self.dados
        if d["idioma"] not in idioma.IDIOMAS:
            d["idioma"] = idioma.detectar()
        if d["voz"] not in IDS or LANG_VOZ[d["voz"]] not in (d["idioma"], None):
            d["voz"] = VOZ_PADRAO[d["idioma"]]
        idioma.definir(d["idioma"])

    @staticmethod
    def _valida(d):
        out = {}
        if isinstance(d.get("nome"), str):
            out["nome"] = d["nome"].strip()[:24]
        if d.get("voz") in IDS:
            out["voz"] = d["voz"]
        if d.get("idioma") in idioma.IDIOMAS:
            out["idioma"] = d["idioma"]
        for k in ("radio", "nome_jogo"):
            if isinstance(d.get(k), bool):
                out[k] = d[k]
        for k, lo, hi in (("velocidade", -20, 30), ("volume", 0, 100), ("chiado", 0, 100)):
            try:
                out[k] = max(lo, min(hi, int(d[k])))
            except (KeyError, TypeError, ValueError):
                pass
        return out

    def get(self):
        with self.lock:
            return dict(self.dados)

    def atualiza(self, novos):
        with self.lock:
            self.dados.update(self._valida(novos))
            self._coerente()
            os.makedirs(os.path.dirname(self.caminho), exist_ok=True)
            tmp = self.caminho + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.dados, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.caminho)
            return dict(self.dados)


class Voz:
    TRABALHADORES = 2

    def __init__(self, ajustes):
        self.ajustes = ajustes
        self.cache = OrderedDict()
        self.pendentes = {}
        self.lock = threading.Lock()
        self.fila = queue.Queue()
        self.falhas_seguidas = 0
        self.pausa_ate = 0.0
        self.ultimo_erro = None
        self.ultimo_ok = 0.0
        if edge_tts is not None:
            for _ in range(self.TRABALHADORES):
                threading.Thread(target=self._trabalha, daemon=True).start()

    # ------------------------------------------------------------ estado
    def neural(self):
        """True se a voz natural esta escolhida e funcionando."""
        return (edge_tts is not None and self.ajustes.get()["voz"] != "windows"
                and time.monotonic() >= self.pausa_ate)

    def status(self):
        if edge_tts is None:
            return tx("pacote edge-tts não instalado: usando a voz do Windows")
        if self.ajustes.get()["voz"] == "windows":
            return tx("voz do Windows")
        if time.monotonic() < self.pausa_ate:
            return tx("sem conexão com o serviço de voz: usando a voz do Windows por enquanto")
        if self.ultimo_ok:
            return tx("voz natural conectada")
        return tx("voz natural pronta")

    # ------------------------------------------------------------ sintese
    def _chave(self, texto, tom):
        a = self.ajustes.get()
        base = "%s|%s|%s|%s" % (a["voz"], a["velocidade"], tom, texto)
        return hashlib.sha1(base.encode("utf-8")).hexdigest(), a

    def preparar(self, texto, tom="normal"):
        """Comeca a gerar o audio em segundo plano (se ainda nao existe)."""
        if not self.neural() or not texto:
            return
        k, a = self._chave(texto, tom)
        with self.lock:
            if k in self.cache or k in self.pendentes:
                return
            self.pendentes[k] = threading.Event()
        self.fila.put((k, texto[:600], tom if tom in TONS else "normal", a["voz"], a["velocidade"]))

    def obter(self, texto, tom="normal", espera=8.0):
        """Audio MP3 da fala, ou None se nao der (o painel usa a voz do Windows)."""
        if not self.neural() or not texto:
            return None
        self.preparar(texto, tom)
        k, _ = self._chave(texto, tom)
        with self.lock:
            if k in self.cache:
                self.cache.move_to_end(k)
                return self.cache[k]
            ev = self.pendentes.get(k)
        if ev is not None:
            ev.wait(espera)
        with self.lock:
            return self.cache.get(k)

    def _trabalha(self):
        loop = asyncio.new_event_loop()
        while True:
            k, texto, tom, voz, vel = self.fila.get()
            try:
                dados = loop.run_until_complete(asyncio.wait_for(self._sintetiza(texto, tom, voz, vel), 12))
                if not dados:
                    raise RuntimeError(tx("serviço de voz não devolveu áudio"))
                with self.lock:
                    self.cache[k] = dados
                    while len(self.cache) > 200:
                        self.cache.popitem(last=False)
                self.falhas_seguidas = 0
                self.ultimo_ok = time.monotonic()
            except Exception as exc:
                self.falhas_seguidas += 1
                self.ultimo_erro = "%s: %s" % (type(exc).__name__, exc)
                if self.falhas_seguidas >= 3:   # sem internet? tenta de novo em 1 minuto
                    self.pausa_ate = time.monotonic() + 60
                    self.falhas_seguidas = 0
                    print("Voz natural indisponivel (%s). Usando a voz do Windows por 1 minuto." % self.ultimo_erro)
            finally:
                with self.lock:
                    ev = self.pendentes.pop(k, None)
                if ev:
                    ev.set()

    @staticmethod
    async def _sintetiza(texto, tom, voz, vel):
        dv, dp = TONS.get(tom, (0, 0))
        com = edge_tts.Communicate(texto, voz, rate="%+d%%" % (vel + dv), pitch="%+dHz" % dp)
        dados = bytearray()
        async for parte in com.stream():
            if parte["type"] == "audio":
                dados += parte["data"]
        return bytes(dados)
