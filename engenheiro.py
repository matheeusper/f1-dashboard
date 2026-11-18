"""Engenheiro de corrida do painel F1 25.

A cada volta compara cada curva com a sua referencia (recorde na pista ou a
melhor volta da sessao), grava tudo no historico, aprende seus vicios por
curva e gera mensagens curtas que o painel fala em voz alta.
"""
import bisect
import random
import struct
import time
from collections import deque

from analise import (DICA, HABITO, Trace, deltas, detectar_curvas, diagnostico, fala_dif, fala_gap,
                     fala_volta, frenagem, metricas, ponto_entrada, texto_meu, texto_outro)
from analise import num as numero
from acerto import AcertoMixin
from corrida import CorridaMixin
from estrategia import EstrategiaMixin
from treino import TreinoMixin

SECOS = (16, 17, 18)
COMPOSTOS = {16: "macios", 17: "médios", 18: "duros", 7: "intermediários", 8: "de chuva"}
PNEU = ["traseiro esquerdo", "traseiro direito", "dianteiro esquerdo", "dianteiro direito"]
MISTURA = ["pobre", "padrão", "rica", "máxima"]
# botoes "UDP Action N" do jogo (mapeie no volante): o que cada um pergunta ao engenheiro
BOTOES = {1: "Pneus", 2: "Gaps", 3: "Combustível e bateria", 4: "Onde estou perdendo",
          5: "Clima e pit", 6: "Repetir a última", 7: "Silêncio (só o essencial)", 8: "Estratégia de pit",
          9: "Metas e treino", 10: "Acerto do carro"}
PECAS = {"fwL": "na asa dianteira esquerda", "fwR": "na asa dianteira direita",
         "rearWing": "na asa traseira", "floor": "no assoalho", "diffuser": "no difusor",
         "sidepod": "na lateral", "gearbox": "no câmbio", "engine": "no motor"}


def fmt_volta(ms):
    if not ms or ms <= 0:
        return "—"
    return "%d:%06.3f" % (ms // 60000, (ms % 60000) / 1000.0)


def fmt_dif(s):
    return ("+" if s >= 0 else "−") + ("%.3f" % abs(s)).replace(".", ",")


def cap(s):
    return s[:1].upper() + s[1:]


def motivo_outro(motivo, valor):
    return "" if motivo == "geral" else ": " + texto_outro(motivo, valor)


class Engenheiro(CorridaMixin, EstrategiaMixin, TreinoMixin, AcertoMixin):
    def __init__(self, dec):
        self.d = dec
        self.msgs = deque(maxlen=10)
        self.seq = 0
        self.map_ver = 0
        self.voz = None        # voz.Voz (definida pelo servidor)
        self.ajustes = None    # voz.Ajustes: nome do piloto, voz...
        self.rng = random.Random()
        self._ultima_frase = {}
        self.btn_prev = 0
        self.ptt = 0             # conta os apertos de botao (o painel toca o "clique" do radio)
        self.silencio = False    # botao 7: so o essencial
        try:
            from historico import Historico
            self.hist = Historico()
        except Exception as exc:
            print("Historico indisponivel:", exc)
            self.hist = None
        self.reset()

    # ================================================================ estado
    def reset(self):
        self.cur = Trace()
        self.lap_no = None
        self.chave = None
        self.corners = []
        self.entradas = []
        self.lap_len = 0.0
        self.recorde_ms, self.recorde_tr = 0, None
        self.sess_ms, self.sess_tr = 0, None
        self.sess_id = None
        self.resumo = None
        self.report = None
        self.cue = None
        self.cue_lap = -1
        self.cool = {}
        self.persist = {}
        self.base = None
        self.cars = {}
        self.best_other = None
        self.gaps = []
        self.desgaste = []
        self.stint = None
        self.talk = True
        self.last_rules = 0.0
        self.lap_sec = 90.0
        self.saudou = False
        self.voltas_sessao = []
        self.voltas_desde_resumo = 0
        self.map_ver += 1
        self._cr_reset()
        self._es_reset()
        self._ms_reset()
        self._tr_reset()
        self._ac_reset()
        self.ac_cache = {"voltas": 0, "achados": [], "sugestoes": [], "ok": False}
        self.rep_tr = self.rep_ref = None
        self.rep_ref_ms = self.rep_ms = 0

    def _seguro(self, fn, *args):
        try:
            return fn(*args)
        except Exception as exc:  # o engenheiro nunca pode derrubar o painel
            print("Engenheiro:", type(exc).__name__, exc)
            return None

    # ================================================================ mensagens
    def nome(self):
        """Primeiro nome do piloto (ex.: 'Max'), ou vazio."""
        n = self.ajustes.get()["nome"] if self.ajustes else ""
        return n.split()[0] if n.split() else ""

    def vn(self):
        """', Max' para encaixar no meio da frase ('Isso, Max!'), ou vazio."""
        n = self.nome()
        return ", " + n if n else ""

    def chama(self, texto):
        n = self.nome()
        if not n:
            return texto
        primeira = texto.split()[0] if texto.split() else ""
        sigla = (len(primeira) > 1 and primeira.isupper()) or any(ch.isdigit() for ch in primeira)
        pilotos = {self.piloto(i) for i in range(len(self.d.names))} if self.d.names else set()
        if primeira.strip(",.!?:") in pilotos:   # nome de piloto continua com maiuscula
            sigla = True
        if primeira and not sigla:   # "O P5 se aproxima" -> "Max, o P5 se aproxima"
            texto = texto[0].lower() + texto[1:]
        return "%s, %s" % (n, texto)

    def escolhe(self, chave, opcoes):
        """Varia a frase para nao soar como gravacao (nunca repete a ultima)."""
        ops = [o for o in opcoes if o != self._ultima_frase.get(chave)] or list(opcoes)
        o = self.rng.choice(ops)
        self._ultima_frase[chave] = o
        return o

    def say(self, texto, pri=3, ttl=20, chave=None, cool=0, show=None, tom=None, chamar=None, resp=False):
        agora = time.monotonic()
        if self.silencio and pri >= 3 and not resp:
            return False
        if chave:
            if agora < self.cool.get(chave, 0):
                return False
            self.cool[chave] = agora + cool
        tom = tom or ("urgente" if pri == 1 else "normal")
        tela = show or texto
        if chamar is None:   # de vez em quando chama pelo nome, como no radio de verdade
            chamar = self.rng.random() < {1: 0.85, 2: 0.3}.get(pri, 0.12)
        if chamar:
            texto = self.chama(texto)
        self.seq += 1
        self.msgs.append({"seq": self.seq, "text": texto, "show": tela, "pri": pri,
                          "ttl": ttl, "t": agora, "tom": tom, "resp": resp})
        self.preparar(texto, tom)
        return True

    def preparar(self, texto, tom="normal"):
        if self.voz is not None:
            self._seguro(self.voz.preparar, texto, tom)

    def voltas(self, n):
        return n * self.lap_sec

    def _segura(self, chave, cond, segundos):
        agora = time.monotonic()
        if not cond:
            self.persist.pop(chave, None)
            return False
        ini = self.persist.setdefault(chave, agora)
        return agora - ini >= segundos

    # ================================================================ pista
    def _pista(self):
        s = self.d.session
        if s is None or self.d.uid is None:
            return
        chave = "%s-%s" % (s["trackId"], s["formula"])
        if chave == self.chave:
            return
        self.chave = chave
        self.lap_len = float(s["trackLength"] or 0)
        if self.hist:
            ref = self._seguro(self.hist.referencia, chave)
            if ref:
                self.corners = ref["curvas"]
                self.recorde_ms, self.recorde_tr = ref["tempo"], ref["traco"]
                self.lap_len = ref["comprimento"] or self.lap_len
            self.sess_id = self._seguro(self.hist.sessao, self.d.uid, chave, s["track"], s["type"],
                                        s["isRace"])
            self._atualiza_resumo()
            self._es_pista()
        self._entradas()
        self.map_ver += 1

    def _entradas(self):
        self.entradas = sorted(c["entry"] for c in self.corners)

    def _atualiza_resumo(self):
        if self.hist and self.chave:
            self.resumo = self._seguro(self.hist.resumo, self.chave, self.sess_id, len(self.corners))

    def _referencia(self):
        s = self.d.session
        seco = s is None or s["weatherId"] <= 2
        if (self.recorde_tr is not None and seco
                and (self.sess_ms == 0 or self.sess_ms <= self.recorde_ms * 1.025)):
            return self.recorde_tr, self.recorde_ms, "recorde"
        if self.sess_tr is not None:
            return self.sess_tr, self.sess_ms, "sessao"
        return None, 0, None

    # ================================================================ entrada (60 Hz)
    def on_lap(self):
        d = self.d
        v, tel = d.lap, d.tel
        if v is None or tel is None:
            return
        self._pista()
        lap_num, dist, cur = v[14], v[10], v[1]
        if self.lap_no is None:
            self.lap_no = lap_num
        if lap_num != self.lap_no:
            if lap_num == self.lap_no + 1 and v[0] > 0:
                self._seguro(self._volta_fechada, self.lap_no, v[0], self.cur)
            self.cur = Trace()
            self.lap_no = lap_num
            self._seguro(self._volta_nova, lap_num)
        if v[18]:
            self.cur.invalid = True
        if v[15]:
            self.cur.pit = True
        if v[25] in (0, 2, 3):
            self.cur.flying = False
        if dist >= 0:
            slip = d.slip
            if abs(slip[2]) >= abs(slip[3]):
                lock, roda = abs(slip[2]), 2
            else:
                lock, roda = abs(slip[3]), 3
            x, z = d.posxz
            ang = d.slip_ang
            bal = (abs(ang[2]) + abs(ang[3])) / 2 - (abs(ang[0]) + abs(ang[1])) / 2
            self.cur.add(dist, cur, tel["speed"], tel["throttle"], tel["brake"], tel["steer"], tel["gear"],
                         lock, roda, max(abs(slip[0]), abs(slip[1])), x, z, bal)
            self._ms_check(lap_num, dist)
            self._ac_amostra(tel)
        self._seguro(self._outros)
        self._fala_e_dica(dist, tel, lap_num)
        agora = time.monotonic()
        if agora - self.last_rules >= 0.5:
            self.last_rules = agora
            self._seguro(self._regras)

    # ---------------------------------------------------------------- outros carros
    def _outros(self):
        d = self.d
        if d.all_lap is None or d.all_tel is None:
            return
        corrida = bool(d.session and d.session["isRace"])
        for i, lv in enumerate(d.all_lap):
            if i == d.player or i >= len(d.all_tel) or lv[26] != 2:
                continue
            tv = d.all_tel[i]
            car = self.cars.get(i)
            if car is None:
                car = self.cars[i] = {"lap": lv[14], "cur": Trace(False), "last": None, "last_ms": 0,
                                      "last_lap": 0}
            if lv[14] != car["lap"]:
                tr = car["cur"]
                if corrida and lv[14] == car["lap"] + 1 and lv[0] > 0:
                    self._es_volta_carro(car, lv[0], tr.pit)   # aprende quanto custa o pit nesta pista
                if lv[14] == car["lap"] + 1 and lv[0] > 0 and tr.ok():
                    car["last"], car["last_ms"], car["last_lap"] = tr, lv[0], car["lap"]
                    if (not corrida and not tr.invalid
                            and (self.best_other is None or lv[0] < self.best_other[2])):
                        self.best_other = (i, tr, lv[0])
                car["cur"] = Trace(False)
                car["lap"] = lv[14]
            tr = car["cur"]
            if lv[18]:
                tr.invalid = True
            if lv[15]:
                tr.pit = True
            if lv[10] >= 0:
                tr.add(lv[10], lv[1], tv[0], tv[1], tv[3])

    # ---------------------------------------------------------------- quando falar
    def _fala_e_dica(self, dist, tel, lap_num):
        vel, freio, vol = tel["speed"], tel["brake"], abs(tel["steer"])
        tt = None
        if self.entradas and dist >= 0 and vel > 30:
            i = bisect.bisect_right(self.entradas, dist)
            prox = self.entradas[i] if i < len(self.entradas) else self.entradas[0] + self.lap_len
            tt = (prox - dist) / (vel / 3.6)
        dentro = any(c["entry"] - 10 <= dist <= c["exit"] for c in self.corners)
        if vel < 90 or (self.d.lap and self.d.lap[15]):
            self.talk = True
        elif freio > 0.05 or vol > 0.25 or dentro:
            self.talk = False
        elif tt is not None:
            self.talk = tt >= 3.2
        else:
            self.talk = tel["throttle"] > 0.8 and vol < 0.15
        # dica antes da curva onde voce mais perdeu (ou do seu vicio)
        if self.cue and lap_num == self.cue_lap and dist >= 0 and vel > 100 and freio < 0.05:
            c, texto = self.cue
            falta = c["entry"] - dist
            if falta > 0:
                t = falta / (vel / 3.6)
                if 3.0 <= t <= 6.5:
                    self.say(texto, pri=3, ttl=3, tom="calmo", chamar=False)
                    self.cue = None
            elif dist > c["exit"]:
                self.cue = None

    # ================================================================ volta fechada
    def _volta_nova(self, num):
        d = self.d
        s = d.session
        if not s:
            return
        if s["isRace"] and s["totalLaps"] and num == s["totalLaps"]:
            self.say(self.escolhe("ultima", ["Última volta%s! Traz pra casa." % self.vn(),
                                             "Última volta. Foco total, traz pra casa.",
                                             "Bandeira branca%s, última volta!" % self.vn()]),
                     pri=2, chave="ultima", cool=600, tom="animado", chamar=False)
        if s["isRace"] and d.lap and num - self.cr_ultimo_pit_volta > 5:   # estrategia do jogo
            ideal, ultima = s["pitIdeal"], s["pitLatest"]
            if ideal and num == ideal - 1:
                self.say("Box na próxima volta.", pri=2, chave="box_prox_%d" % ideal, cool=99999)
            elif ideal and num == ideal:
                volta = " " + (self._seguro(self.texto_previsao) or
                               ("Se parar agora, deve voltar em P%d." % s["pitRejoin"] if s["pitRejoin"] else ""))
                volta = volta.rstrip()
                self.say("Box, box. Box nesta volta." + volta, pri=1, tom="urgente",
                         chave="box_%d" % ideal, cool=99999, show="BOX, BOX · box nesta volta." + volta)
            elif ultima and num == ultima and ultima != ideal:
                self.say("Última volta da janela de pit. Box, box.", pri=1, chave="box_ultima_%d" % ultima,
                         cool=99999)
        # sem erro recente para lembrar? lembra o vicio mais forte a cada 4 voltas
        if self.cue is None and self.resumo and self.resumo["habitos"] and num % 4 == 0:
            n, (motivo, pct, _q, _t) = max(self.resumo["habitos"].items(), key=lambda kv: kv[1][1])
            c = next((c for c in self.corners if c["n"] == n), None)
            if c and DICA.get(motivo):
                dica = DICA[motivo]
                alvo = self._alvo_frenagem(c) if motivo in ("cedo", "tarde") else None
                if alvo:
                    dica = "o recorde freia a %d metros" % (5 * round(alvo / 5))
                self._define_dica(c, dica, num, lembrete=True)

    def _alvo_frenagem(self, c):
        """Onde a sua referencia freia nessa curva, em metros antes da entrada."""
        ref, ref_ms, _t = self._referencia()
        if ref is None:
            return None
        r = metricas(ref, c, ref_ms)
        f = frenagem(r) if r else None
        if f is None:
            return None
        d = ponto_entrada(self.recorde_tr or ref, c) - f
        return d if d > 5 else None

    def _texto_motivo(self, x, tipo):
        """(fala, tela) do motivo principal; frenagem com os metros da referencia."""
        motivo, valor = x["motivos"][0]
        alvo = "o recorde" if tipo == "recorde" else "a sua melhor"
        if motivo in ("cedo", "tarde") and x["dist"]:
            eu, ref = x["dist"]
            extra = " e passou do ponto" if motivo == "tarde" else ""
            return ("freou a %d metros%s, %s freia a %d" % (eu, extra, alvo, ref),
                    "freou a %d m%s (ref. %d m)" % (eu, extra, ref))
        t = texto_meu(motivo, valor)
        return t, t

    def _define_dica(self, c, dica, volta, lembrete=False):
        n = c["n"]
        if lembrete:
            texto = self.escolhe("lembrete", ["Curva %d: lembra, %s." % (n, dica),
                                              "Na %d, lembra: %s." % (n, dica)])
        else:
            texto = self.escolhe("dica", ["Curva %d, %s." % (n, dica), "Atenção na %d: %s." % (n, dica),
                                          cap("%s na %d." % (dica, n))])
        self.cue = (c, texto)
        self.cue_lap = volta
        self.preparar(texto, "calmo")

    # ================================================================ minissetores ao vivo
    def _ms_reset(self):
        self.ms_lap = None
        self.ms_lista = []       # [{n, d}] curvas ja feitas nesta volta (d = ganho/perda em s)
        self.ms_prox = 0         # proxima curva a fechar
        self.ms_flash = None     # ultima curva fechada, para o painel piscar
        self.ms_seq = getattr(self, "ms_seq", 0)
        self.ms_ref_id = None
        self.ms_ref_seg = {}

    def _ms_ref(self):
        """Tempo de cada trecho na referencia (recorde ou melhor da sessao), em ms."""
        ref, ref_ms, _tipo = self._referencia()
        if ref is None or not self.corners:
            return None
        if id(ref) != self.ms_ref_id:
            self.ms_ref_id = id(ref)
            self.ms_ref_seg = {}
            for c in self.corners:
                t0 = 0.0 if c["b0"] <= 0 else ref.interp(ref.t, c["b0"])
                t1 = float(ref_ms) if c["last"] else ref.interp(ref.t, c["b1"])
                self.ms_ref_seg[c["n"]] = t1 - t0
        return self.ms_ref_seg

    def _ms_registra(self, n, dif):
        dif = round(dif, 3)
        self.ms_lista.append({"n": n, "d": dif})
        self.ms_seq += 1
        self.ms_flash = {"seq": self.ms_seq, "n": n, "d": dif}

    def _ms_check(self, lap_num, dist):
        if self.ms_lap != lap_num:
            self.ms_lap, self.ms_lista, self.ms_prox = lap_num, [], 0
        cs, tr = self.corners, self.cur
        if not cs or len(tr) < 5 or tr.d[0] > 200 or not tr.flying or tr.pit:
            return
        while self.ms_prox < len(cs) - 1 and dist >= cs[self.ms_prox]["b1"]:
            c = cs[self.ms_prox]
            self.ms_prox += 1
            ref = self._ms_ref()
            if not ref:
                continue
            t0 = 0.0 if c["b0"] <= 0 else tr.interp(tr.t, c["b0"])
            self._ms_registra(c["n"], (tr.interp(tr.t, c["b1"]) - t0 - ref[c["n"]]) / 1000.0)

    def _ms_fim_volta(self, num, ms, tr):
        """A ultima curva fecha na linha de chegada (antes de a volta virar referencia)."""
        cs = self.corners
        if not cs or self.ms_lap != num or self.ms_prox != len(cs) - 1 or not tr.ok():
            return
        ref = self._ms_ref()
        c = cs[-1]
        if ref:
            t0 = 0.0 if c["b0"] <= 0 else tr.interp(tr.t, c["b0"])
            self._ms_registra(c["n"], (ms - t0 - ref[c["n"]]) / 1000.0)
        self.ms_prox += 1

    def ms_view(self):
        return {"lap": self.ms_lap, "corners": self.ms_lista, "flash": self.ms_flash}

    def _volta_fechada(self, num, ms, tr):
        d = self.d
        self._ms_fim_volta(num, ms, tr)
        if 40 < ms / 1000 < 240:
            self.lap_sec = ms / 1000.0
        lancada = tr.ok()
        valida = lancada and not tr.invalid
        if lancada:
            self._analisa_volta(num, ms, tr, valida)
        if d.session and d.session["isRace"]:
            self._es_minha_volta(ms, tr.pit)
            self._fim_volta_corrida(num, tr, ms if lancada else 0)
            self._seguro(self._es_fim_volta, num)
        self._desgaste(num)

    def _analisa_volta(self, num, ms, tr, valida):
        d = self.d
        primeira_ref = False
        if not self.corners and valida:
            comp = self.lap_len or tr.d[-1]
            self.corners = detectar_curvas(tr, comp)
            self.lap_len = comp
            self._entradas()
            primeira_ref = True
            self.map_ver += 1
        ref, ref_ms, tipo = self._referencia()
        resultado = []
        linhas = []
        for c in self.corners:
            m = metricas(tr, c, ms)
            if m is None:
                continue
            r = metricas(ref, c, ref_ms) if ref is not None else None
            perda = (m["seg"] - r["seg"]) / 1000.0 if r else None
            motivos = diagnostico(m, r) if r and perda >= 0.04 else []
            # pontos de frenagem medidos a partir da entrada da curva (como as placas de 100/50 m)
            dist = None
            if r:
                tin = ponto_entrada(self.recorde_tr or ref, c)
                fe, fr = frenagem(m), frenagem(r)
                if fe is not None and fr is not None and tin - fe > 5 and tin - fr > 5:
                    dist = (round(tin - fe), round(tin - fr))
            resultado.append({"c": c, "m": m, "r": r, "perda": perda, "motivos": motivos, "dist": dist})
            linhas.append((c["n"], m["seg"], None if perda is None else perda * 1000,
                           ",".join(k for k, _ in motivos)))
        composto = d.status["visual"] if d.status else 0
        if self.hist and self.sess_id:
            self._seguro(self.hist.salvar_volta, self.sess_id, num, ms, valida, composto, linhas)
        self.voltas_sessao.append((num, ms, valida))

        novo_sess = valida and (self.sess_ms == 0 or ms < self.sess_ms)
        if novo_sess:
            self.sess_ms, self.sess_tr = ms, tr
        recorde_ant = self.recorde_ms
        novo_rec = valida and bool(self.corners) and (self.recorde_ms == 0 or ms < self.recorde_ms)
        if novo_rec:
            self.recorde_ms, self.recorde_tr = ms, tr
            if self.hist and self.chave:
                self._seguro(self.hist.salvar_referencia, self.chave, ms, self.corners, tr, self.lap_len)
            self.map_ver += 1

        # ------------- relatorio da volta (tela)
        habitos = (self.resumo or {}).get("habitos", {})
        cs = []
        for x in resultado:
            item = {"n": x["c"]["n"], "loss": None if x["perda"] is None else round(x["perda"], 3)}
            if x["r"]:
                item.update(deltas(x["m"], x["r"]))
            if x["dist"]:
                item["bpEu"], item["bpRef"] = x["dist"]
            if x["motivos"] and x["motivos"][0][0] != "geral":
                item["tip"] = self._texto_motivo(x, tipo)[1]
            h = habitos.get(x["c"]["n"])
            if h:
                item["habit"] = HABITO.get(h[0])
            cs.append(item)
        self.report = {"lap": num, "ms": ms, "ref": ref_ms, "kind": tipo, "valid": valida, "corners": cs}

        # ------------- relatorio falado (estilo radio: curto e variado)
        vn = self.vn()
        t = fala_volta(ms)
        tela = ["V%d %s" % (num, fmt_volta(ms))]
        pri, tom, chamar = 3, "normal", None
        piores = sorted((x for x in resultado if x["perda"] is not None and x["perda"] >= 0.08
                         and x["motivos"]), key=lambda x: -x["perda"])[:2]
        if novo_rec and recorde_ant:
            ganho = fala_dif((recorde_ant - ms) / 1000)
            fala = [self.escolhe("recorde", [
                "Isso%s! %s, novo recorde pessoal! %s mais rápido." % (vn, t, cap(ganho)),
                "Que volta%s! %s. Recorde pessoal, %s melhor que o anterior." % (vn, t, ganho),
                "%s! É recorde%s! Tiramos %s." % (t, vn, ganho),
            ])]
            tela.append("RECORDE PESSOAL " + fmt_dif((ms - recorde_ant) / 1000))
            pri, tom, chamar = 2, "animado", False
        elif novo_rec:
            fala = ["%s." % t, "Referência salva. A partir de agora eu comparo cada curva com ela."
                    if primeira_ref else "Primeiro recorde salvo nesta pista."]
            tela.append("referência salva")
        elif novo_sess and ref_ms:
            fala = [self.escolhe("melhor_sessao", [
                "%s, melhor volta da sessão. Boa%s." % (t, vn),
                "Melhor da sessão: %s. Continua assim." % t,
                "%s. Essa foi a melhor de hoje." % t,
            ])]
            tela.append("melhor da sessão")
            tom = "animado"
        else:
            fala = [self.escolhe("abre_volta", ["%s." % t, "%s nessa." % t, "Volta %d, %s." % (num, t)])]
            if ref_ms:
                dif = (ms - ref_ms) / 1000
                alvo = "do recorde" if tipo == "recorde" else "da sua melhor"
                if dif < 0.05:
                    fala.append(self.escolhe("no_ritmo", ["Em cima %s." % alvo, "No ritmo %s." % alvo,
                                                          "Mesmo tempo %s." % alvo]))
                else:
                    d_ = fala_dif(dif)
                    fala.append(self.escolhe("dif", ["Mais %s %s." % (d_, alvo), cap("%s %s." % (d_, alvo)),
                                                     cap("%s atrás %s." % (d_, alvo))]))
                tela.append(fmt_dif(dif))
        if not valida:
            fala.append(self.escolhe("invalida", ["Volta inválida.", "Essa foi invalidada."]))
            tela.append("inválida")
        for i, x in enumerate(piores):
            motivo, valor = x["motivos"][0]
            n = x["c"]["n"]
            oque, tela_oque = self._texto_motivo(x, tipo)
            quanto = fala_dif(x["perda"])
            if motivo == "geral":
                frase = "Mais %s na curva %d." % (quanto, n)
            else:
                frase = self.escolhe("curva%d" % i, [
                    "Curva %d: %s, %s." % (n, oque, quanto),
                    "Perdemos %s na %d: %s." % (quanto, n, oque),
                    "Na %d você %s, %s." % (n, oque, quanto),
                ])
            h = habitos.get(n)
            if h and h[0] == motivo:
                frase += " " + self.escolhe("vicio", ["De novo: é o seu vício nessa curva.",
                                                      "Esse erro de novo, é o seu vício ali.",
                                                      "Mesmo erro de sempre nessa curva."])
            fala.append(frase)
            tela.append("C%d %s %s" % (n, fmt_dif(x["perda"]), tela_oque))
        ganhos = [x for x in resultado if x["perda"] is not None and x["perda"] <= -0.08]
        if (novo_sess or novo_rec) and ganhos and recorde_ant:
            g = min(ganhos, key=lambda x: x["perda"])
            fala.append("O ganho maior foi na curva %d." % g["c"]["n"])
        if ref_ms and not piores and not novo_rec and not novo_sess and valida:
            fala.append(self.escolhe("boa", ["Sem perdas grandes, boa volta.", "Volta limpa, mantém.",
                                             "Muito bom%s, consistente." % vn, "Tudo certo por curva."]))
        self.say(" ".join(fala), pri=pri, ttl=40, show=" · ".join(tela), tom=tom, chamar=chamar)

        # ------------- dica para a proxima volta (ja deixa o audio pronto)
        if piores:
            x = piores[0]
            motivo = x["motivos"][0][0]
            if DICA.get(motivo) and x["perda"] >= 0.1:
                dica = DICA[motivo]
                if motivo in ("cedo", "tarde") and x["dist"]:   # numero concreto para mirar
                    dica = "freie a %d metros" % (5 * round(x["dist"][1] / 5))
                self._define_dica(x["c"], dica, num + 1)

        # guarda a volta para o grafico de telemetria comparada
        self.rep_tr, self.rep_ref, self.rep_ref_ms, self.rep_ms = tr, ref, ref_ms, ms
        # modo treino/metas (Time Trial) e analise do acerto
        self._seguro(self._tr_fim_volta, num, ms, valida, resultado)
        self._seguro(self._ac_volta, num, tr)
        self.ac_cache = self._seguro(self.ac_view) or self.ac_cache

        self.voltas_desde_resumo += 1
        if self.voltas_desde_resumo >= 5 or primeira_ref:
            self.voltas_desde_resumo = 0
            self._atualiza_resumo()
        self._compara_rival(num, tr, ms)

    # ---------------------------------------------------------------- outros pilotos
    def _compara(self, meu, meu_ms, outro, outro_ms):
        melhor = None
        for c in self.corners:
            m = metricas(meu, c, meu_ms)
            r = metricas(outro, c, outro_ms)
            if not m or not r:
                continue
            ganho = (m["seg"] - r["seg"]) / 1000.0
            if ganho >= 0.1 and (melhor is None or ganho > melhor[0]):
                melhor = (ganho, c, m, r)
        return melhor

    def _compara_rival(self, num, tr, ms):
        d = self.d
        if not self.corners or d.all_lap is None or d.lap is None:
            return
        if d.session and d.session["isRace"]:
            pos = d.lap[13]
            gap = d.lap[7] * 60000 + d.lap[6]
            if pos <= 1 or gap > 3000 or time.monotonic() < self.cool.get("rival", 0):
                return
            frente = next((i for i, lv in enumerate(d.all_lap) if lv[13] == pos - 1), None)
            car = self.cars.get(frente)
            if not car or car["last"] is None or abs(car["last_lap"] - num) > 1:
                return
            res = self._compara(tr, ms, car["last"], car["last_ms"])
            if res:
                ganho, c, m, r = res
                motivo, valor = diagnostico(m, r)[0]
                self.say("%s é %s mais rápido na curva %d%s." % (self.rotulo(pos - 1), fala_dif(ganho), c["n"],
                                                                 motivo_outro(motivo, valor)),
                         pri=3, ttl=30, chave="rival", cool=self.voltas(2))
        elif self.best_other and time.monotonic() >= self.cool.get("melhor_outro", 0):
            i, otr, oms = self.best_other
            minha = self.sess_ms or ms
            if oms >= minha:
                return
            res = self._compara(tr, ms, otr, oms)
            if res:
                ganho, c, m, r = res
                motivo, valor = diagnostico(m, r)[0]
                self.say("Contra a volta mais rápida da sessão, a maior diferença é na curva %d, %s%s."
                         % (c["n"], fala_dif(ganho), motivo_outro(motivo, valor)),
                         pri=3, ttl=30, chave="melhor_outro", cool=self.voltas(2))

    # ---------------------------------------------------------------- corrida
    def _fim_volta_corrida(self, num, tr, ms):
        d = self.d
        v, st, s = d.lap, d.status, d.session
        if v is None:
            return
        pos = v[13]
        gap_f = v[7] * 60000 + v[6] if pos > 1 else None
        gap_t = None
        if d.all_lap:
            atras = next((lv for lv in d.all_lap if lv[13] == pos + 1 and lv[26] == 2), None)
            if atras:
                gap_t = atras[7] * 60000 + atras[6]
        self.gaps.append((num, pos, gap_f, gap_t))
        self.gaps = self.gaps[-6:]
        ult = [g for g in self.gaps[-4:] if g[1] == pos]
        if len(ult) >= 4:
            if all(g[2] for g in ult):
                ritmo = (ult[-1][2] - ult[0][2]) / 3.0
                if ritmo <= -150 and gap_f > 1000:
                    voltas = max(1, round((gap_f - 500) / -ritmo))
                    self.say("Você tira %s por volta %s. Alcança em %d voltas."
                             % (fala_dif(ritmo / 1000), self.de(self.idx_pos(pos - 1)), voltas), pri=2,
                             chave="alcanca", cool=self.voltas(3))
                elif ritmo >= 250:
                    self.say("%s está abrindo %s por volta." % (self.rotulo(pos - 1), fala_dif(ritmo / 1000)),
                             pri=3, chave="abrindo", cool=self.voltas(5))
            if all(g[3] for g in ult):
                ritmo_t = (ult[-1][3] - ult[0][3]) / 3.0
                if ritmo_t <= -150 and gap_t < 4000:
                    self.say("%s se aproxima %s por volta, está a %s."
                             % (self.rotulo(pos + 1), fala_dif(ritmo_t / 1000), fala_gap(gap_t)), pri=2,
                             chave="aproxima", cool=self.voltas(3))
        if gap_t is not None and 0 < gap_t < 1000:
            self.say("%s a %s, dentro do DRS. Defenda nas retas." % (self.rotulo(pos + 1), fala_gap(gap_t)),
                     pri=2, chave="drs_atras", cool=self.voltas(2))
        if gap_f is not None and 0 < gap_f < 1000 and st:
            if d.t2 and d.t2.get("regs2026"):
                dica = "Use o overtake na reta." if d.t2.get("otAvail") else "Fique no vácuo."
            elif st["ersStore"] >= 0.5 * 4e6:
                dica = "Bateria em %d por cento, use o modo overtake na reta." % (st["ersStore"] / 4e4)
            else:
                dica = "Carregue a bateria e ataque na próxima."
            self.say("A %s %s. %s" % (fala_gap(gap_f), self.de(self.idx_pos(pos - 1)), dica), pri=2,
                     chave="ataque", cool=self.voltas(2))
        if st and s and s["totalLaps"] and num >= 2:
            sobra = st["fuelLaps"]
            restantes = s["totalLaps"] - num
            if sobra < -0.25 and restantes > 0:
                lc = sorted(self.corners, key=lambda c: -c["vin"])[:2]
                onde = (" antes das curvas %s" % " e ".join(str(c["n"]) for c in sorted(lc, key=lambda c: c["n"]))
                        if lc else "")
                self.say("Combustível negativo, %s volta. Faça lift and coast%s." % (numero(sobra), onde),
                         pri=1 if sobra < -1 else 2, chave="comb", cool=self.voltas(3))
            elif sobra > 1.2 and 0 < restantes <= 6 and st["fuelMix"] < 2:
                self.say("Combustível sobrando, pode usar a mistura rica.", pri=3, chave="comb_rica",
                         cool=99999)

    def _desgaste(self, num):
        d = self.d
        if not d.damage or not d.status:
            return
        idade, composto = d.status["tyreAge"], d.status["visual"]
        stint = (composto,)
        if self.stint != stint or (self.desgaste and idade < self.desgaste[-1][2]):
            self.stint = stint
            self.desgaste = []
        w = max(d.damage["wear"])
        self.desgaste.append((num, w, idade))
        if len(self.desgaste) < 3:
            return
        taxa = (self.desgaste[-1][1] - self.desgaste[-3][1]) / 2.0
        if taxa <= 0.3:
            return
        s = d.session
        if w >= 70:
            self.say("Pneus com %d por cento de desgaste, perdendo rendimento. Box quando puder." % w,
                     pri=1, chave="pneu70", cool=self.voltas(3))
            return
        ate70 = (70 - w) / taxa
        if ate70 <= 3:
            self.say("Pneus com %d por cento. No ritmo atual chegam a 70 em %d voltas. Pense no pit."
                     % (w, max(1, round(ate70))), pri=2, chave="pneu_proj", cool=self.voltas(3))
        elif s and s["isRace"] and s["totalLaps"]:
            restantes = s["totalLaps"] - num
            if 0 < restantes <= 8 and ate70 > restantes + 1:
                self.say("Os pneus aguentam até o fim.", pri=3, chave="pneu_fim_%s" % composto, cool=99999)

    # ================================================================ regras (2x por segundo)
    def _regras(self):
        d = self.d
        tel, st, v, s, dmg = d.tel, d.status, d.lap, d.session, d.damage
        if tel is None or v is None:
            return
        self._seguro(self._cr_tick)
        self._seguro(self._es_tick)
        estado = {"warn": v[20], "pen": v[19], "dt": v[22], "sg": v[23],
                  "dmg": {k: dmg[k] for k in PECAS} if dmg else None,
                  "sc": s["safetyCar"] if s else 0, "flag": st["flag"] if st else 0}
        if self.base is None:
            self.base = estado
            return
        b = self.base
        corrida = bool(s and s["isRace"])

        if not self.saudou and self.talk and self.resumo is not None and s:
            self.saudou = True
            self._saudacao()

        # punicoes e avisos
        if estado["pen"] > b["pen"]:
            self.say("Punição de %d segundos. Total %d." % (estado["pen"] - b["pen"], estado["pen"]), pri=1)
        if estado["dt"] > b["dt"]:
            self.say("Drive-through para cumprir.", pri=1)
        if estado["sg"] > b["sg"]:
            self.say("Stop and go para cumprir.", pri=1)
        if estado["warn"] > b["warn"]:
            extra = " Cuidado, os avisos viram punição." if estado["warn"] >= 2 else ""
            self.say("Aviso de limite de pista, já são %d.%s" % (estado["warn"], extra), pri=2,
                     show="Aviso de limite de pista (%d)" % estado["warn"])
        # danos
        if estado["dmg"] and b["dmg"]:
            for k, nome in PECAS.items():
                novo, velho = estado["dmg"][k], b["dmg"][k]
                if novo >= velho + 8:
                    texto = "Dano %s, %d por cento." % (nome, novo)
                    if k in ("fwL", "fwR") and novo >= 40:
                        texto += " Recomendo parar e trocar o bico."
                    self.say(texto, pri=1)
        # safety car e bandeiras
        if estado["sc"] != b["sc"]:
            sc = estado["sc"]
            if sc == 1:
                self.say("Safety car na pista. Diminua e respeite o delta.", pri=1)
            elif sc == 2:
                self.say("Virtual safety car. Respeite o delta.", pri=1)
            elif sc == 0 and b["sc"] in (1, 2):
                self.say("Bandeira verde, corrida liberada!", pri=1)
        if estado["flag"] != b["flag"]:
            if estado["flag"] == 3:
                self.say("Bandeira amarela, cuidado.", pri=1, chave="amarela", cool=20)
            elif estado["flag"] == 2:
                self.say("Bandeira azul, deixe passar.", pri=2, chave="azul", cool=30)
        self.base = estado

        if st is None:
            return
        rapido = tel["speed"] > 120
        vis = st["visual"]
        quente, frio = (105, 78) if vis in SECOS or vis == 0 else (95, 55)
        sup = tel["tyreSurf"]
        tras, diant = (sup[0] + sup[1]) / 2, (sup[2] + sup[3]) / 2
        if self._segura("tras_quente", rapido and tras > quente, 8):
            self.say("Pneus traseiros superaquecendo, %d graus. Cuidado na tração." % tras, pri=2,
                     chave="tras_quente", cool=120)
        if self._segura("diant_quente", rapido and diant > quente, 8):
            self.say("Dianteiros superaquecendo, %d graus. Menos volante na entrada." % diant, pri=2,
                     chave="diant_quente", cool=120)
        sc_ativo = s and s["safetyCar"] in (1, 2)
        if self._segura("frio", tel["speed"] > 150 and max(sup) < frio and not sc_ativo
                        and (v[14] >= 2 or not corrida), 15):
            self.say("Pneus frios, %d graus. Aqueça os pneus." % max(sup), pri=3, chave="frio", cool=180)
        if self._segura("freio", max(tel["brakeTemp"]) > 1050, 3):
            self.say("Freios muito quentes.", pri=2, chave="freio", cool=120)
        if self._segura("motor", tel["engineTemp"] >= 128, 5):
            self.say("Motor esquentando, %d graus." % tel["engineTemp"], pri=2, chave="motor", cool=180)
        bat = st["ersStore"] / 4e6
        if corrida and self._segura("bateria", (st["ersMode"] >= 2 and bat < 0.15) or bat < 0.05, 5):
            self.say("Bateria baixa. Mude para o modo médio e recarregue.", pri=2, chave="bateria",
                     cool=self.voltas(2))
        # clima
        if s:
            if vis in SECOS:
                chuva = [r for r in s["rain"] if 0 < r[0] <= 15 and r[1] >= 60]
                agora = s["rain"][0][1] if s["rain"] else 0
                if chuva and agora < 40:
                    # so avisa de novo quando a previsao mudar
                    self.say("Chuva forte prevista em %d minutos, %d por cento." % (chuva[0][0], chuva[0][1]),
                             pri=2, chave="chuva_%d_%d" % (chuva[0][0], chuva[0][1]), cool=99999)
                if s["weatherId"] >= 3:
                    self.say("Está chovendo e você está de pneu liso.", pri=1, chave="chuva_liso", cool=120)
            elif vis in (7, 8) and s["weatherId"] <= 1 and s["rain"] and s["rain"][0][1] < 10:
                self.say("Pista secando, considere pneus de pista seca.", pri=2, chave="secando", cool=240)

    # ================================================================ memoria
    def _saudacao(self):
        s, r = self.d.session, self.resumo
        vn = self.vn()
        abre = self.escolhe("saudacao", ["Rádio check%s. Me ouve bem?" % vn,
                                         "Oi%s, rádio funcionando." % vn,
                                         "Fala%s, tô contigo no rádio." % vn])
        partes = [abre, "%s." % s["track"]]
        if not r or not r["voltas"]:
            partes.append("Primeira vez aqui. Faz uma volta limpa pra eu montar sua referência.")
        else:
            # curto como no radio: recorde, o que da pra buscar e o ponto de atencao do dia
            if self.recorde_ms:
                partes.append("Recorde: %s." % fala_volta(self.recorde_ms))
            if r["ideal"] and self.recorde_ms and self.recorde_ms - r["ideal"] >= 100:
                partes.append("Tem %s pra buscar." % fala_dif((self.recorde_ms - r["ideal"]) / 1000))
            if r["habitos"]:
                n, h = max(r["habitos"].items(), key=lambda kv: kv[1][1])
                partes.append("Atenção na %d: você costuma %s." % (n, HABITO.get(h[0], h[0])))
            elif r["fraca"] and r["fraca_ganho"] >= 80:
                partes.append("Foco na curva %d hoje." % r["fraca"])
            partes.append(self.escolhe("bora", ["Bora.", "Vamos nessa.", "Bom trabalho hoje."]))
        self.say(" ".join(partes), pri=3, ttl=90, tom="calmo", chamar=False,
                 show="Rádio check · " + " ".join(partes[1:]))

    def end_session(self):
        """Resumo falado quando a sessao acaba (ou o jogo troca de sessao)."""
        validas = [ms for _n, ms, ok in self.voltas_sessao if ok]
        if len(validas) < 3:
            return
        from historico import _media_limpa
        media, desvio = _media_limpa(validas)
        partes = ["Resumo da sessão: %d voltas válidas, melhor %s, média %s, variação de %s."
                  % (len(validas), fala_volta(min(validas)), fala_volta(media), fala_dif(desvio / 1000))]
        tela = ["Sessão: %d voltas · melhor %s · média %s · ±%s"
                % (len(validas), fmt_volta(min(validas)), fmt_volta(int(media)), numero(desvio / 1000, 2))]
        r = self.resumo
        if r and r.get("anterior") and self.hist and self.sess_id:
            ant = r["anterior"]
            dif = (media - ant["media"]) / 1000
            partes.append("A média ficou %s %s que na sessão anterior."
                          % (fala_dif(dif), "mais rápida" if dif < 0 else "mais lenta"))
            atual, antes = self._seguro(self.hist.comparar_sessoes, self.sess_id, ant["id"]) or ({}, {})
            evol = {n: atual[n] - antes[n] for n in atual if n in antes}
            if evol:
                n = min(evol, key=evol.get)
                if evol[n] <= -50:
                    partes.append("Evoluiu mais na curva %d, %s por volta." % (n, fala_dif(evol[n] / 1000)))
        self._atualiza_resumo()
        r = self.resumo
        if r and r.get("fraca") and r.get("fraca_ganho", 0) >= 80:
            partes.append("Para a próxima: trabalhe a curva %d, ainda tem %s nela."
                          % (r["fraca"], fala_dif(r["fraca_ganho"] / 1000)))
        self.say(" ".join(partes), pri=2, ttl=120, show=" · ".join(tela), tom="calmo", chamar=False)

    # ================================================================ botoes do volante
    def pergunta(self, n):
        """Botao 'UDP Action n' (ou tecla n no painel): responde na hora."""
        self.ptt += 1
        fn = {1: self._r_pneus, 2: self._r_gaps, 3: self._r_combustivel, 4: self._r_perdendo,
              5: self._r_clima, 6: self._r_repetir, 7: self._r_silencio, 8: self._r_estrategia,
              9: self._r_metas, 10: self._r_acerto}.get(n)
        if fn is None:
            self.responde("Botão %d ainda sem função." % n)
        elif self._seguro(fn) is False:
            self.responde("Ainda sem dados pra isso. Entra na pista que eu te passo.")

    def responde(self, texto, show=None, tom="normal", chamar=None):
        self.say(texto, pri=2, ttl=15, show=show, tom=tom, resp=True, chamar=chamar)

    def _r_pneus(self):
        d = self.d
        st, dmg, tel = d.status, d.damage, d.tel
        if not st or not dmg or not tel:
            return False
        comp = COMPOSTOS.get(st["visual"])
        partes = ["Pneus %s com %d voltas." % (comp, st["tyreAge"]) if comp else
                  "Pneus com %d voltas." % st["tyreAge"]]
        w = dmg["wear"]
        pior = max(range(4), key=lambda k: w[k])
        partes.append("Desgaste de %d por cento, o pior é o %s com %d."
                      % (round(sum(w) / 4), PNEU[pior], round(w[pior])))
        quente, frio = (105, 78) if st["visual"] in SECOS or st["visual"] == 0 else (95, 55)
        sup = tel["tyreSurf"]
        tras, diant = (sup[0] + sup[1]) / 2, (sup[2] + sup[3]) / 2
        if diant > quente:
            partes.append("Dianteiros quentes, %d graus. Menos volante na entrada." % diant)
        elif tras > quente:
            partes.append("Traseiros quentes, %d graus. Cuidado na tração." % tras)
        elif max(sup) < frio:
            partes.append("Estão frios, %d graus." % max(sup))
        else:
            partes.append("Temperaturas na janela.")
        if len(self.desgaste) >= 3 and max(w) < 70:
            taxa = (self.desgaste[-1][1] - self.desgaste[-3][1]) / 2.0
            if taxa > 0.3:
                partes.append("No ritmo atual chegam a 70 por cento em umas %d voltas." % max(1, round((70 - max(w)) / taxa)))
        self.responde(" ".join(partes))

    def _r_gaps(self):
        d = self.d
        v = d.lap
        if v is None:
            return False
        pos = v[13]
        partes = ["P%d." % pos]
        hist = [g for g in self.gaps[-4:] if g[1] == pos]
        gap_f = v[7] * 60000 + v[6]
        if pos > 1 and gap_f > 0:
            frase = "%s, P%d, está a %s" % (self.rotulo(pos - 1), pos - 1, fala_gap(gap_f)) \
                if self.piloto(self.idx_pos(pos - 1)) else "O P%d está a %s" % (pos - 1, fala_gap(gap_f))
            if len(hist) >= 2 and all(g[2] for g in hist):
                ritmo = (hist[-1][2] - hist[0][2]) / (len(hist) - 1)
                if ritmo <= -80:
                    frase += ", você tira %s por volta" % fala_dif(ritmo / 1000)
                elif ritmo >= 80:
                    frase += ", ele abre %s por volta" % fala_dif(ritmo / 1000)
            partes.append(frase + ".")
        if d.all_lap:
            atras = next((lv for lv in d.all_lap if lv[13] == pos + 1 and lv[26] == 2), None)
            if atras:
                gap_t = atras[7] * 60000 + atras[6]
                if gap_t > 0:
                    frase = "%s, P%d, está a %s" % (self.rotulo(pos + 1), pos + 1, fala_gap(gap_t)) \
                        if self.piloto(self.idx_pos(pos + 1)) else "O P%d está a %s" % (pos + 1, fala_gap(gap_t))
                    if len(hist) >= 2 and all(g[3] for g in hist):
                        ritmo = (hist[-1][3] - hist[0][3]) / (len(hist) - 1)
                        if ritmo <= -80:
                            frase += ", vindo %s por volta" % fala_dif(ritmo / 1000)
                    partes.append(frase + ("" if gap_t >= 1000 else ", dentro do DRS") + ".")
        if len(partes) == 1 and self.sess_ms:
            partes.append("Sua melhor na sessão é %s." % fala_volta(self.sess_ms))
        self.responde(" ".join(partes))

    def _r_combustivel(self):
        d = self.d
        st = d.status
        if not st:
            return False
        sobra = st["fuelLaps"]
        partes = ["Combustível %s %s volta, mistura %s."
                  % ("mais" if sobra >= 0 else "menos", numero(abs(sobra)), MISTURA[st["fuelMix"]]
                     if 0 <= st["fuelMix"] < 4 else "padrão")]
        if sobra < -0.2 and self.corners:
            lc = sorted(sorted(self.corners, key=lambda c: -c["vin"])[:2], key=lambda c: c["n"])
            partes.append("Precisamos economizar: lift and coast antes da %s." % " e da ".join(str(c["n"]) for c in lc))
        elif sobra > 1.0:
            partes.append("Tem sobra, pode usar mistura rica.")
        partes.append("Bateria em %d por cento." % round(st["ersStore"] / 4e4))
        if d.t2 and d.t2.get("regs2026"):
            partes.append("Overtake disponível." if d.t2.get("otAvail") else "Overtake ainda não.")
        self.responde(" ".join(partes))

    def _r_perdendo(self):
        rep = self.report
        if not rep or not rep["corners"]:
            self.responde("Ainda não tenho volta pra comparar. Faz uma volta limpa e me pergunta de novo.")
            return
        piores = sorted((c for c in rep["corners"] if c.get("loss") and c["loss"] >= 0.05),
                        key=lambda c: -c["loss"])[:2]
        if not piores:
            partes = ["Na última volta você não perdeu nada relevante em nenhuma curva. Tá voando."]
        else:
            partes = ["Na última volta você perdeu mais"]
            for i, c in enumerate(piores):
                partes.append("%s %d, %s%s." % ("na" if i == 0 else "Depois na", c["n"], fala_dif(c["loss"]),
                                                ": " + c["tip"] if c.get("tip") else ""))
        hab = (self.resumo or {}).get("habitos") or {}
        if hab:
            n, h = max(hab.items(), key=lambda kv: kv[1][1])
            partes.append("E fica de olho na %d: você costuma %s." % (n, HABITO.get(h[0], h[0])))
        self.responde(" ".join(partes))

    def _r_clima(self):
        s = self.d.session
        if not s:
            return False
        partes = ["%s, pista a %d graus, ar a %d." % (s["weather"], s["trackTemp"], s["airTemp"])]
        prox = [r for r in s["rain"] if r[0] > 0]
        chuva = next((r for r in prox if r[1] >= 40), None)
        if chuva:
            partes.append("Chuva de %d por cento em %d minutos." % (chuva[1], chuva[0]))
        elif prox:
            partes.append("Sem chuva forte prevista.")
        if s["isRace"] and s["pitIdeal"]:
            if s["pitLatest"] and s["pitLatest"] != s["pitIdeal"]:
                partes.append("Janela de pit entre as voltas %d e %d." % (s["pitIdeal"], s["pitLatest"]))
            else:
                partes.append("Volta ideal pro pit: %d." % s["pitIdeal"])
        self.responde(" ".join(partes))

    def _r_repetir(self):
        ultima = next((m for m in reversed(self.msgs) if not m.get("resp")), None)
        if ultima is None:
            self.responde("Nada pra repetir ainda.")
        else:
            self.say(ultima["text"], pri=2, ttl=15, tom=ultima["tom"], chamar=False, resp=True, show=ultima["show"])

    def _r_silencio(self):
        self.silencio = not self.silencio
        if self.silencio:
            self.responde(self.escolhe("silencio_on", ["Entendido, só o essencial a partir de agora.",
                                                       "Copiado. Fico quieto, só o importante."]), chamar=False)
        else:
            self.responde(self.escolhe("silencio_off", ["Rádio normal de novo.", "Ok, voltei a falar tudo."]),
                          chamar=False)

    def on_event(self, code, data, player):
        vn = self.vn()
        if code == "BUTN":
            status = struct.unpack_from("<I", data, 33)[0]
            novos = status & ~self.btn_prev
            self.btn_prev = status
            for n in range(1, 13):
                if novos & (1 << (19 + n)):   # UDP Action 1 = bit 20 ... UDP Action 12 = bit 31
                    self.pergunta(n)
            return
        self._seguro(self._cr_evento, code, data)
        if code == "LGOT":
            self.say(self.escolhe("largada", ["Luzes apagadas! Vai%s!" % vn, "Vai, vai, vai!",
                                              "Largou! Boa corrida%s." % vn]),
                     pri=2, ttl=5, tom="animado", chamar=False)
        elif code == "CHQF" and self.d.lap:
            pos = self.d.lap[13]
            if pos == 1:
                texto = self.escolhe("vitoria", ["Vencemos%s! Que corrida! P1!" % vn,
                                                 "É P1! Vitória%s, que pilotagem!" % vn])
            elif pos <= 3:
                texto = "Pódio%s! P%d, grande corrida!" % (vn, pos)
            else:
                texto = self.escolhe("chegada", ["Bandeira quadriculada. P%d%s, bom trabalho." % (pos, vn),
                                                 "Fim de corrida, P%d. Valeu o esforço%s." % (pos, vn)])
            self.say(texto, pri=2, tom="animado" if pos <= 3 else "normal", chamar=False,
                     show="Bandeira quadriculada · P%d" % pos)
        elif code == "SEND":
            self._seguro(self._cr_fim_sessao)
            self._seguro(self.end_session)
            self.voltas_sessao = []

    # ================================================================ saida
    def view(self):
        agora = time.monotonic()
        ref_tr, ref_ms, tipo = self._referencia()
        r = self.resumo or {}
        return {
            "msgs": [{"seq": m["seq"], "text": m["text"], "show": m["show"], "pri": m["pri"],
                      "ttl": m["ttl"], "tom": m["tom"], "resp": m["resp"],
                      "age": int((agora - m["t"]) * 1000)} for m in self.msgs],
            "voice": self._voz_view(),
            "ptt": self.ptt, "silencio": self.silencio,
            "pit": self._seguro(self.es_view), "live": self.ms_view(),
            "treino": self.tr_view(), "acerto": self.ac_cache,
            "talk": self.talk, "report": self.report, "mapVer": self.map_ver,
            "nCorners": len(self.corners), "ref": ref_ms, "refKind": tipo,
            "record": self.recorde_ms, "ideal": r.get("ideal", 0),
            "habits": {str(k): HABITO.get(h[0], h[0]) for k, h in r.get("habitos", {}).items()},
        }

    def telemetria(self, n):
        """Velocidade, acelerador, freio e diferenca de tempo da ultima volta x referencia numa curva."""
        tr, ref = self.rep_tr, self.rep_ref
        c = next((c for c in self.corners if c["n"] == n), None)
        if c is None or tr is None:
            return {"n": n, "ok": False}
        a = max(c["b0"], c["entry"] - 250, tr.d[0])
        b = min(c["b1"], c["exit"] + 200, tr.d[-1])
        if b - a < 50:
            a, b = c["b0"], c["b1"]
        passo = max(2.0, (b - a) / 400)
        xs = [a + i * passo for i in range(int((b - a) / passo) + 1)]

        def serie(t):
            return {k: [round(t.interp(getattr(t, k), x), 3 if k != "v" else 1) for x in xs]
                    for k in ("v", "thr", "brk")}

        tin = ponto_entrada(self.recorde_tr or ref or tr, c)
        out = {"n": n, "ok": True, "d": [round(x - tin, 1) for x in xs], "eu": serie(tr), "lap": self.report and
               self.report["lap"], "kind": self.report and self.report["kind"]}
        m = metricas(tr, c, self.rep_ms)
        marcas = {"apex": round(c["apex"] - tin, 1)}
        if m and frenagem(m) is not None:
            marcas["eu"] = round(frenagem(m) - tin, 1)
        if ref is not None:
            out["ref"] = serie(ref)
            t0e, t0r = tr.interp(tr.t, a), ref.interp(ref.t, a)
            out["delta"] = [round((tr.interp(tr.t, x) - t0e - (ref.interp(ref.t, x) - t0r)) / 1000, 3) for x in xs]
            r = metricas(ref, c, self.rep_ref_ms)
            if r and frenagem(r) is not None:
                marcas["ref"] = round(frenagem(r) - tin, 1)
        out["marcas"] = marcas
        return out

    def _voz_view(self):
        a = self.ajustes.get() if self.ajustes else {}
        return {"neural": bool(self.voz and self.voz.neural()), "volume": a.get("volume", 100),
                "radio": a.get("radio", True), "chiado": a.get("chiado", 35)}

    def mapa(self):
        tr = self.recorde_tr or self.sess_tr
        pts, curvas = [], []
        if tr is not None and len(tr) and any(tr.x):
            ultimo = -1e9
            for i in range(len(tr)):
                if tr.d[i] - ultimo >= 10:
                    ultimo = tr.d[i]
                    pts.append([round(tr.x[i], 1), round(tr.z[i], 1)])
            for c in self.corners:
                curvas.append({"n": c["n"], "x": round(tr.interp(tr.x, c["apex"]), 1),
                               "z": round(tr.interp(tr.z, c["apex"]), 1)})
        return {"ver": self.map_ver, "pts": pts, "corners": curvas}
