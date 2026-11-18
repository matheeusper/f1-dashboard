"""Analise do acerto do carro.

Mede o equilibrio do carro em cada fase da curva (entrada, meio e saida) pela
diferenca de deriva entre os pneus dianteiros e traseiros (pacote Motion Ex):
dianteiros escorregando mais = subesterco; traseiros escorregando mais =
sobresterco. Junta isso com as patinadas na saida e a diferenca de temperatura
entre dianteiros e traseiros, e so aponta um padrao quando ele se repete em
pelo menos 3 voltas. As sugestoes usam os valores atuais do seu acerto.
"""
import bisect
import statistics
from collections import deque

from analise import ponto_entrada

LIMIAR = 0.012        # rad (~0,7 grau) de diferenca de deriva para contar como sub/sobresterco
PATINA_SAIDA = 0.15   # escorregamento medio dos traseiros com acelerador na saida
DIF_TEMP = 8.0        # graus entre dianteiros e traseiros
FASES = {"e": "na entrada", "m": "no meio", "s": "na saída"}


def _lista(ns):
    """'da curva 2' / 'das curvas 3 e 7'."""
    ns = sorted(ns)
    if len(ns) == 1:
        return "da curva %d" % ns[0]
    return "das curvas " + ", ".join(str(n) for n in ns[:-1]) + " e %d" % ns[-1]


class AcertoMixin:
    def _ac_reset(self):
        self.ac_hist = {}                 # curva -> fase -> ultimas medias
        self.ac_temp = deque(maxlen=6)    # (dianteiros - traseiros) por volta
        self.ac_acc = [0.0, 0.0, 0]
        self.ac_voltas = 0
        self.ac_falado = None
        self.ac_ultima_fala = 0

    # ---------------------------------------------------------------- coleta
    def _ac_amostra(self, tel):
        if tel["speed"] > 120:
            s = tel["tyreSurf"]
            self.ac_acc[0] += (s[2] + s[3]) / 2
            self.ac_acc[1] += (s[0] + s[1]) / 2
            self.ac_acc[2] += 1

    def _ac_volta(self, num, tr):
        """Chamado no fim de cada volta lancada."""
        if self.ac_acc[2] > 300:
            self.ac_temp.append(self.ac_acc[0] / self.ac_acc[2] - self.ac_acc[1] / self.ac_acc[2])
        self.ac_acc = [0.0, 0.0, 0]
        if not self.corners or not tr.completo or not any(tr.bal):
            return
        D = tr.d
        ref = self.recorde_tr or tr
        for c in self.corners:
            tin, apex = ponto_entrada(ref, c), c["apex"]
            faixas = {"e": (tin - 20, apex - 25), "m": (apex - 25, apex + 25), "s": (apex + 25, c["exit"] + 60)}
            h = self.ac_hist.setdefault(c["n"], {"e": deque(maxlen=5), "m": deque(maxlen=5), "s": deque(maxlen=5),
                                                 "spin": deque(maxlen=5)})
            for fase, (a, b) in faixas.items():
                if b <= a:
                    continue
                i0, i1 = bisect.bisect_left(D, a), bisect.bisect_right(D, b)
                vals = [tr.bal[k] for k in range(i0, i1)
                        if tr.v[k] > 60 and abs(tr.steer[k]) > 0.05 and (fase != "s" or tr.thr[k] > 0.3)]
                if len(vals) >= 5:
                    h[fase].append(sum(vals) / len(vals))
            a, b = faixas["s"]
            i0, i1 = bisect.bisect_left(D, a), bisect.bisect_right(D, b)
            sp = [tr.spin[k] for k in range(i0, i1) if tr.thr[k] > 0.5]
            if len(sp) >= 5:
                h["spin"].append(sum(sp) / len(sp))
        self.ac_voltas += 1
        self._ac_fala_periodica(num)

    # ---------------------------------------------------------------- conclusoes
    def ac_achados(self):
        """[(fase, 'sub'|'sobre'|'patina', [curvas])] + ('temp', 'frente'|'tras', None)."""
        por = {}
        for n, h in self.ac_hist.items():
            for fase in ("e", "m", "s"):
                if len(h[fase]) >= 3:
                    med = statistics.median(h[fase])
                    if med >= LIMIAR:
                        por.setdefault((fase, "sub"), []).append(n)
                    elif med <= -LIMIAR:
                        por.setdefault((fase, "sobre"), []).append(n)
            if len(h["spin"]) >= 3 and statistics.median(h["spin"]) >= PATINA_SAIDA:
                por.setdefault(("s", "patina"), []).append(n)
        out = [(f, t, sorted(ns)) for (f, t), ns in sorted(por.items())]
        if len(self.ac_temp) >= 3:
            dt = statistics.median(self.ac_temp)
            if dt >= DIF_TEMP:
                out.append(("temp", "frente", None))
            elif dt <= -DIF_TEMP:
                out.append(("temp", "tras", None))
        return out

    def ac_sugestoes(self, achados):
        st, su = self.d.status, self.d.setup
        bias = st["brakeBias"] if st else None
        fw, rw = (su["frontWing"], su["rearWing"]) if su else (None, None)
        don, doff = (su["diffOn"], su["diffOff"]) if su else (None, None)

        def de_para(nome, atual, novo, unid=""):
            if atual is None:
                return nome
            return "%s de %d para %d%s" % (nome, atual, novo, unid)

        sug = []
        tipos = {(f, t) for f, t, _ in achados}
        if ("e", "sub") in tipos:
            sug.append(de_para("balanço de freio mais para trás", bias, (bias or 0) - 1, "%"))
            sug.append(de_para("diferencial sem acelerador mais aberto", doff, max(10, (doff or 0) - 5), "%"))
        if ("e", "sobre") in tipos:
            sug.append(de_para("balanço de freio mais para frente", bias, (bias or 0) + 1, "%"))
            sug.append(de_para("diferencial sem acelerador mais fechado", doff, min(100, (doff or 0) + 5), "%"))
        if ("m", "sub") in tipos:
            sug.append(de_para("mais asa dianteira", fw, (fw or 0) + 1))
        if ("m", "sobre") in tipos:
            sug.append(de_para("mais asa traseira", rw, (rw or 0) + 1))
        if ("s", "sub") in tipos or ("s", "sobre") in tipos or ("s", "patina") in tipos:
            sug.append(de_para("diferencial no acelerador mais aberto", don, max(10, (don or 0) - 5), "%"))
        if ("s", "sobre") in tipos or ("s", "patina") in tipos:
            sug.append("acelerador mais progressivo na saída")
        if ("temp", "frente") in tipos:
            sug.append("pressão dos dianteiros um pouco menor")
        if ("temp", "tras") in tipos:
            sug.append("pressão dos traseiros um pouco menor")
        return sug

    def ac_texto(self):
        achados = self.ac_achados()
        if self.ac_voltas < 3:
            return None, achados
        if not achados:
            return "Carro equilibrado nas últimas voltas: nada de subesterço ou sobresterço que se repita.", achados
        partes = []
        for fase, tipo, ns in achados:
            if fase == "temp":
                partes.append("dianteiros %d graus mais quentes que os traseiros" % round(statistics.median(self.ac_temp))
                              if tipo == "frente" else
                              "traseiros %d graus mais quentes que os dianteiros" % round(-statistics.median(self.ac_temp)))
            elif tipo == "patina":
                partes.append("patinando na saída %s" % _lista(ns))
            else:
                partes.append("%s %s %s" % ("subesterço" if tipo == "sub" else "sobresterço", FASES[fase], _lista(ns)))
        texto = "Acerto: " + "; ".join(partes) + "."
        sug = self.ac_sugestoes(achados)
        if sug:
            texto += " Sugestão: " + "; ".join(sug) + "."
        return texto, achados

    def _ac_fala_periodica(self, num):
        s = self.d.session
        if not s or s["isRace"] or self.ac_voltas < 3 or num - self.ac_ultima_fala < 4:
            return
        texto, achados = self.ac_texto()
        chave = tuple((f, t, tuple(ns or ())) for f, t, ns in achados)
        if texto and achados and chave != self.ac_falado:
            self.ac_falado = chave
            self.ac_ultima_fala = num
            self.say(texto, pri=3, ttl=40, tom="calmo")

    # ---------------------------------------------------------------- botao 10 e tela
    def _r_acerto(self):
        texto, _ = self.ac_texto()
        if texto is None:
            self.responde("Ainda preciso de %d voltas lançadas para analisar o equilíbrio do carro."
                          % max(1, 3 - self.ac_voltas))
        else:
            self.responde(texto)

    def ac_view(self):
        texto, achados = self.ac_texto()
        itens = []
        for fase, tipo, ns in achados:
            if fase == "temp":
                itens.append("Pneus dianteiros mais quentes" if tipo == "frente" else "Pneus traseiros mais quentes")
            elif tipo == "patina":
                itens.append("Patinando na saída %s" % _lista(ns))
            else:
                itens.append("%s %s %s" % ("Subesterço" if tipo == "sub" else "Sobresterço", FASES[fase], _lista(ns)))
        return {"voltas": self.ac_voltas, "achados": itens, "sugestoes": self.ac_sugestoes(achados) if achados else [],
                "ok": texto is not None}
