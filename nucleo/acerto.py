"""Analise do acerto do carro.

Mede o equilibrio do carro em cada fase da curva (entrada, meio e saida) pela
diferenca de deriva entre os pneus dianteiros e traseiros (pacote Motion Ex):
dianteiros escorregando mais = subesterco; traseiros escorregando mais =
sobresterco. Junta isso com as patinadas na saida e a diferenca de temperatura
entre dianteiros e traseiros, e so aponta um padrao quando ele se repete em
pelo menos 3 voltas.

Sugestoes:
- uma mudanca por vez, a do problema que aparece em mais curvas. Vale a maioria: pelo menos 2
  curvas e o dobro do lado contrario; curvas divididas nao geram sugestao;
- no meio da curva, asa nas curvas rapidas e barra estabilizadora nas lentas;
- dentro dos limites do jogo, e so o que da para mudar na sessao (em parc ferme, so o que muda
  pelo MFD: balanco de freio e diferencial no acelerador);
- depois que o acerto muda, compara as voltas antes e depois e diz se melhorou ou se e melhor voltar.
  O que piorou nao e sugerido de novo.
"""
import bisect
import statistics
import time
from collections import deque

from analise import ponto_entrada
from idioma import N_, ingles, tx

LIMIAR = 0.012        # rad (~0,7 grau) de diferenca de deriva para contar como sub/sobresterco
PATINA_SAIDA = 0.15   # escorregamento medio dos traseiros com acelerador na saida
DIF_TEMP = 8.0        # graus entre dianteiros e traseiros
RAPIDA = 170          # km/h no apice: daqui para cima quem manda no meio da curva e a asa; abaixo, a barra
FASES = {"e": N_("na entrada"), "m": N_("no meio"), "s": N_("na saída")}

# item do acerto: (nome, unidade, minimo, maximo, passo, {sentido: como fica}) - limites do F1 25
ITENS = {
    "brakeBias": (N_("balanço de freio"), "%", 50, 70, 1, {1: N_("mais para frente"), -1: N_("mais para trás")}),
    "diffOff": (N_("diferencial sem acelerador"), "%", 10, 100, 5, {1: N_("mais fechado"), -1: N_("mais aberto")}),
    "diffOn": (N_("diferencial no acelerador"), "%", 10, 100, 5, {1: N_("mais fechado"), -1: N_("mais aberto")}),
    "frontWing": (N_("asa dianteira"), "", 0, 50, 1, {1: N_("mais asa"), -1: N_("menos asa")}),
    "rearWing": (N_("asa traseira"), "", 0, 50, 1, {1: N_("mais asa"), -1: N_("menos asa")}),
    "frontARB": (N_("barra estabilizadora dianteira"), "", 1, 21, 1, {1: N_("mais dura"), -1: N_("mais macia")}),
    "rearARB": (N_("barra estabilizadora traseira"), "", 1, 21, 1, {1: N_("mais dura"), -1: N_("mais macia")}),
}
MFD = ("brakeBias", "diffOn")    # muda andando, pelo MFD: vale tambem em parc ferme
PARC_FERME = range(5, 18)        # classificacao, sprint e corrida (typeId 5 a 17)

# problema (fase, tipo) -> o que resolve, em ordem. "mr"/"ml" = meio das curvas rapidas/lentas
OPCOES = {
    ("e", "sub"): [("brakeBias", -1), ("diffOff", -1)],
    ("e", "sobre"): [("brakeBias", 1), ("diffOff", 1)],
    ("mr", "sub"): [("frontWing", 1), ("rearWing", -1)],
    ("mr", "sobre"): [("rearWing", 1), ("frontWing", -1)],
    ("ml", "sub"): [("frontARB", -1), ("rearARB", 1)],
    ("ml", "sobre"): [("rearARB", -1), ("frontARB", 1)],
    ("s", "sobre"): [("diffOn", -1)],     # sobresterco ou patinada na saida
}
NOME_PROB = {
    ("e", "sub"): N_("subesterço na entrada"), ("e", "sobre"): N_("sobresterço na entrada"),
    ("mr", "sub"): N_("subesterço no meio das curvas rápidas"),
    ("mr", "sobre"): N_("sobresterço no meio das curvas rápidas"),
    ("ml", "sub"): N_("subesterço no meio das curvas lentas"),
    ("ml", "sobre"): N_("sobresterço no meio das curvas lentas"),
    ("s", "sobre"): N_("sobresterço ou patinada na saída"), ("s", "sub"): N_("subesterço na saída"),
}


def _lista(ns):
    """'da curva 2' / 'das curvas 3 e 7'."""
    ns = sorted(ns)
    if len(ns) == 1:
        return tx("da curva %d") % ns[0]
    return tx("das curvas ") + ", ".join(str(n) for n in ns[:-1]) + tx(" e ") + str(ns[-1])


def _num(x):
    return ("%g" % x) if ingles() else ("%g" % x).replace(".", ",")


def _seg(s):
    return ("%.2f" % s) if ingles() else ("%.2f" % s).replace(".", ",")


class AcertoMixin:
    ac_chave = None          # acerto (so o que muda na garagem) das voltas analisadas: sobrevive a troca de sessao
    ac_chave_nova = None     # (chave, desde) enquanto o acerto lido for diferente
    ac_novo = False          # a analise recomecou por causa de um acerto novo
    # medir se a mudanca ajudou (sobrevive ao recomeco da analise)
    ac_bloco = None          # voltas com o mesmo acerto: {"valores", "mfd", "tempos"}
    ac_antes = None          # resumo do ultimo bloco completo: {"valores", "cont", "tempo", "sugerida"}
    ac_comparar = False      # tem um acerto anterior para comparar quando o atual juntar 3 voltas
    ac_comparacao = None     # {"texto", "veredito"} da ultima comparacao
    ac_sugerida = None       # a sugestao em vigor neste bloco
    ac_evitar = frozenset()  # (item, sentido, valor) que ja piorou: nao sugere de novo

    def _ac_setup_check(self):
        """Mudou o acerto na garagem? Recomeca a analise (as voltas antigas eram de outro carro)."""
        su = self.d.setup
        chave = su.get("chave") if su else None
        if chave is None:
            return
        if self.ac_chave is None:
            self.ac_chave = chave
            return
        if chave == self.ac_chave:
            self.ac_chave_nova = None
            return
        agora = time.monotonic()
        if self.ac_chave_nova is None or self.ac_chave_nova[0] != chave:
            self.ac_chave_nova = (chave, agora)   # espera parar de mexer nos valores
            return
        if agora - self.ac_chave_nova[1] < 3:
            return
        self.ac_chave, self.ac_chave_nova = chave, None
        self._ac_fecha_bloco()
        if self.ac_voltas or self.ac_hist or self.ac_temp:
            self._ac_reset()
            self.ac_novo = True
            self.ac_cache = self.ac_view()
            self.say(tx("Acerto novo. Recomeço a análise do equilíbrio: preciso de 3 voltas lançadas."),
                     pri=3, ttl=30, tom="calmo", chave="acerto_novo", cool=20)

    def _ac_reset(self):
        self.ac_hist = {}                 # curva -> fase -> ultimas medias
        self.ac_temp = deque(maxlen=6)    # (dianteiros - traseiros) por volta
        self.ac_acc = [0.0, 0.0, 0]
        self.ac_voltas = 0
        self.ac_vapex = {}                # curva -> velocidade no apice (km/h)
        self.ac_falado = None
        self.ac_ultima_fala = 0
        self.ac_novo = False

    # ---------------------------------------------------------------- valores do acerto
    def _ac_valores(self):
        """Valores atuais dos itens que o engenheiro sabe mudar (o balanco de freio vem do MFD)."""
        su, st = self.d.setup, self.d.status
        v = {k: su[k] for k in ITENS if su and k in su}
        if st:
            v["brakeBias"] = st["brakeBias"]
        return v

    def _ac_mfd(self):
        st, su = self.d.status, self.d.setup
        return (st["brakeBias"] if st else None, su["diffOn"] if su else None)

    # ---------------------------------------------------------------- coleta
    def _ac_amostra(self, tel):
        if tel["speed"] > 120:
            s = tel["tyreSurf"]
            self.ac_acc[0] += (s[2] + s[3]) / 2
            self.ac_acc[1] += (s[0] + s[1]) / 2
            self.ac_acc[2] += 1

    def _ac_volta(self, num, tr, ms=0, valida=False):
        """Chamado no fim de cada volta lancada."""
        mfd = self._ac_mfd()
        if self.ac_bloco is not None and self.ac_bloco["mfd"] != mfd:
            # mudou o balanco de freio ou o diferencial pelo MFD: outro acerto. Esta volta foi meio a meio
            self._ac_fecha_bloco()
            self._ac_reset()
            self.ac_novo = True
            self.ac_bloco = {"valores": self._ac_valores(), "mfd": mfd, "tempos": []}
            return
        if self.ac_bloco is None:
            self.ac_bloco = {"valores": self._ac_valores(), "mfd": mfd, "tempos": []}
        if valida and 40000 < ms < 240000:
            self.ac_bloco["tempos"].append(ms)

        if self.ac_acc[2] > 300:
            self.ac_temp.append(self.ac_acc[0] / self.ac_acc[2] - self.ac_acc[1] / self.ac_acc[2])
        self.ac_acc = [0.0, 0.0, 0]
        if not self.corners or not tr.completo or not any(tr.bal):
            return
        D = tr.d
        ref = self.recorde_tr or tr
        for c in self.corners:
            tin, apex = ponto_entrada(ref, c), c["apex"]
            ia = min(bisect.bisect_left(ref.d, apex), len(ref.v) - 1)
            self.ac_vapex[c["n"]] = ref.v[ia]
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
        if self.ac_voltas >= 3:
            self.ac_novo = False
            if self.ac_comparar and self.ac_antes:
                self.ac_comparar = False
                self.ac_comparacao = self._ac_compara()
                if self.ac_comparacao:
                    self.say(self.ac_comparacao["texto"], pri=3, ttl=40, tom="calmo", chave="acerto_comp", cool=20)
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

    def _ac_por_problema(self, achados):
        """Curvas por problema, com o meio da curva separado em rapidas e lentas."""
        c = {(f, t): set(ns) for f, t, ns in achados if f != "temp"}

        def g(k):
            return c.get(k, set())

        def rap(ns):
            return {n for n in ns if self.ac_vapex.get(n, 0) >= RAPIDA}

        ms, mo = g(("m", "sub")), g(("m", "sobre"))
        so = g(("s", "sobre")) | g(("s", "patina"))
        return {("e", "sub"): g(("e", "sub")), ("e", "sobre"): g(("e", "sobre")),
                ("mr", "sub"): rap(ms), ("mr", "sobre"): rap(mo),
                ("ml", "sub"): ms - rap(ms), ("ml", "sobre"): mo - rap(mo),
                ("s", "sobre"): so, ("s", "sub"): g(("s", "sub")) - so}

    def _ac_votos(self, pp):
        """Problemas em que a maioria das curvas concorda: [(n curvas, problema)], o maior primeiro."""
        grupos = []
        for fase in ("e", "mr", "ml", "s"):
            sub, sobre = pp[(fase, "sub")], pp[(fase, "sobre")]
            for a, b, tipo in ((sub, sobre, "sub"), (sobre, sub, "sobre")):
                if (fase, tipo) in OPCOES and len(a) >= 2 and len(a) >= 2 * len(b):
                    grupos.append((len(a), (fase, tipo)))
        grupos.sort(key=lambda x: -x[0])
        return grupos

    def _ac_ajuste(self, item, sentido, valores):
        """Um passo do item no sentido pedido, dentro do limite. None se nao der (no limite, ou ja piorou)."""
        _, _, lo, hi, passo, _ = ITENS[item]
        atual = valores.get(item)
        if atual is None:
            return {"item": item, "sentido": sentido, "de": None, "para": None}
        novo = min(hi, max(lo, passo * round((atual + sentido * passo) / passo)))
        if (novo - atual) * sentido <= 0 or (item, sentido, atual) in self.ac_evitar:
            return None
        return {"item": item, "sentido": sentido, "de": atual, "para": novo}

    @staticmethod
    def _ac_texto_ajuste(a):
        nome, un, _, _, _, sentidos = ITENS[a["item"]]
        if a["de"] is None:
            return "%s %s" % (tx(nome), tx(sentidos[a["sentido"]]))
        return tx("%s de %d para %d%s (%s)") % (tx(nome), a["de"], a["para"], un, tx(sentidos[a["sentido"]]))

    def ac_sugestao(self, achados):
        """{"ajuste", "texto", "motivo", "proxima"} ou {"aviso"} quando nao da para sugerir nada."""
        pp = self._ac_por_problema(achados)
        grupos = self._ac_votos(pp)
        if not grupos:
            # misto = a mesma fase com curvas pedindo coisas opostas (subesterco na saida sozinho fica so no diagnostico)
            if any(pp[(f, "sub")] and pp[(f, "sobre")] for f in ("e", "mr", "ml", "s")):
                return {"aviso": tx("Equilíbrio misto: cada curva pede uma coisa, então não mexo no acerto; "
                                    "vale trabalhar a pilotagem nelas.")}
            return {}
        s = self.d.session
        parc = bool(s and s.get("typeId") in PARC_FERME)
        valores = self._ac_valores()
        escolhas, bloqueado = [], False
        for n, prob in grupos:
            for item, sentido in OPCOES[prob]:
                if parc and item not in MFD:
                    bloqueado = True
                    continue
                a = self._ac_ajuste(item, sentido, valores)
                if a:
                    a.update(prob=prob, n=n)
                    escolhas.append(a)
                    break
        if not escolhas:
            return {"aviso": tx("Em parc fermé só dá para mudar o balanço de freio e o diferencial no acelerador, "
                                "e eles não resolvem o que eu vi.") if bloqueado else
                    tx("O que resolveria isso já está no limite do jogo.")}
        a = escolhas[0]
        out = {"ajuste": a, "texto": self._ac_texto_ajuste(a),
               "motivo": tx("%s em %d curvas") % (tx(NOME_PROB[a["prob"]]), a["n"])}
        if len(escolhas) > 1:
            out["proxima"] = self._ac_texto_ajuste(escolhas[1])
        return out

    # ---------------------------------------------------------------- antes e depois
    def _ac_resumo(self):
        """Fotografia do bloco atual (so com a analise completa: 3 voltas)."""
        if self.ac_voltas < 3 or not self.ac_bloco:
            return None
        pp = self._ac_por_problema(self.ac_achados())
        t = self.ac_bloco["tempos"]
        return {"valores": self.ac_bloco["valores"], "cont": {k: len(v) for k, v in pp.items()},
                "tempo": statistics.median(t) if len(t) >= 2 else None, "sugerida": self.ac_sugerida}

    def _ac_fecha_bloco(self):
        """O acerto mudou: guarda o bloco que termina para comparar com o proximo."""
        r = self._ac_resumo()
        if r:
            self.ac_antes = r
        if self.ac_antes:
            self.ac_comparar = True
        self.ac_bloco = None
        self.ac_sugerida = None

    def _ac_compara(self):
        antes, depois = self.ac_antes, self._ac_resumo()
        if not depois:
            return None
        va, vd = antes["valores"], depois["valores"]
        mud = [(k, va[k], vd[k]) for k in ITENS if k in va and k in vd and va[k] != vd[k]]
        ca, cd = antes["cont"], depois["cont"]
        sug = antes["sugerida"]
        seguiu = bool(sug and any(k == sug["item"] and (d - a) * sug["sentido"] > 0 for k, a, d in mud))
        partes, veredito = [], None
        if seguiu:
            prob = sug["prob"]
            oposto = (prob[0], "sobre" if prob[1] == "sub" else "sub")
            n0, n1, o0, o1 = ca.get(prob, 0), cd.get(prob, 0), ca.get(oposto, 0), cd.get(oposto, 0)
            partes.append(tx("%s: de %d para %d curvas") % (tx(NOME_PROB[prob]), n0, n1))
            if n1 < n0 and o1 >= o0 + 2:
                veredito = "passou"
            elif n1 != n0:
                veredito = "melhor" if n1 < n0 else "pior"
        else:
            t0, t1 = sum(ca.values()), sum(cd.values())
            partes.append(tx("curvas com problema de equilíbrio: de %d para %d") % (t0, t1))
            if abs(t1 - t0) >= 2:
                veredito = "melhor" if t1 < t0 else "pior"
        dt = (depois["tempo"] - antes["tempo"]) / 1000 if antes["tempo"] and depois["tempo"] else None
        if dt is not None:
            if abs(dt) < 0.05:
                partes.append(tx("mesmo tempo de volta"))
            else:
                partes.append((tx("volta %s s mais rápida") if dt < 0 else tx("volta %s s mais lenta")) % _seg(abs(dt)))
        so_tempo = veredito is None   # o equilibrio ficou igual: decide pelo tempo, com folga para a pilotagem
        if so_tempo:
            veredito = "igual" if dt is None or abs(dt) < 0.2 else ("melhor" if dt < 0 else "pior")

        def volta():
            return ", ".join("%s %s%s" % (tx(ITENS[k][0]), _num(a), ITENS[k][1]) for k, a, _ in mud)

        if so_tempo and veredito == "melhor":
            fim = tx("Equilíbrio igual, mas pelo tempo parece melhor: mantém.")
        elif so_tempo and veredito == "pior":
            fim = (tx("Equilíbrio igual, mas pelo tempo parece pior. Se confirmar, volte para: %s.") % volta()) if mud \
                else tx("Equilíbrio igual, mas pelo tempo parece pior.")
        elif veredito == "melhor":
            fim = tx("Melhorou: mantém.")
        elif veredito == "igual":
            fim = tx("Sem diferença clara.")
        elif veredito == "passou":
            fim = tx("Passou do ponto: agora apareceu %s. Volte para: %s.") % (tx(NOME_PROB[oposto]), volta())
        else:
            fim = (tx("Piorou. Volte para: %s.") % volta()) if mud else tx("Piorou: vale voltar ao acerto anterior.")
        if seguiu and veredito in ("pior", "passou"):
            self.ac_evitar = self.ac_evitar | {(sug["item"], sug["sentido"], sug["de"])}
        quais = ", ".join("%s %s→%s%s" % (tx(ITENS[k][0]), _num(a), _num(d), ITENS[k][1]) for k, a, d in mud) \
            or tx("outros ajustes")
        texto = tx("Comparando com o acerto anterior (%s): ") % quais + "; ".join(partes) + ". " + fim
        return {"texto": texto, "veredito": veredito}

    # ---------------------------------------------------------------- texto
    def ac_texto(self):
        """(texto, achados, sugestao); texto None enquanto faltam voltas."""
        achados = self.ac_achados()
        if self.ac_voltas < 3:
            return None, achados, {}
        if not achados:
            return tx("Carro equilibrado nas últimas voltas: nada de subesterço ou sobresterço que se repita."), achados, {}
        partes = []
        for fase, tipo, ns in achados:
            if fase == "temp":
                partes.append(tx("dianteiros %d graus mais quentes que os traseiros") % round(statistics.median(self.ac_temp))
                              if tipo == "frente" else
                              tx("traseiros %d graus mais quentes que os dianteiros") % round(-statistics.median(self.ac_temp)))
            elif tipo == "patina":
                partes.append(tx("patinando na saída %s") % _lista(ns))
            else:
                partes.append("%s %s %s" % (tx("subesterço") if tipo == "sub" else tx("sobresterço"), tx(FASES[fase]), _lista(ns)))
        texto = tx("Acerto: ") + "; ".join(partes) + "."
        sug = self.ac_sugestao(achados)
        if sug.get("texto"):
            texto += tx(" Sugestão: %s, por causa de %s. Mude uma coisa por vez: depois eu comparo as voltas.") % (
                sug["texto"], sug["motivo"])
        elif sug.get("aviso"):
            texto += " " + sug["aviso"]
        return texto, achados, sug

    def _ac_fala_periodica(self, num):
        s = self.d.session
        if not s or s["isRace"] or self.ac_voltas < 3 or num - self.ac_ultima_fala < 4:
            return
        texto, achados, _ = self.ac_texto()
        chave = tuple((f, t, tuple(ns or ())) for f, t, ns in achados)
        if texto and achados and chave != self.ac_falado:
            self.ac_falado = chave
            self.ac_ultima_fala = num
            self.say(texto, pri=3, ttl=40, tom="calmo")

    # ---------------------------------------------------------------- botao 10 e tela
    def _r_acerto(self):
        texto, _, _ = self.ac_texto()
        if texto is None:
            falta = max(1, 3 - self.ac_voltas)
            self.responde(tx("Acerto novo: ainda preciso de %d voltas lançadas para analisar o equilíbrio.") % falta
                          if self.ac_novo else
                          tx("Ainda preciso de %d voltas lançadas para analisar o equilíbrio do carro.") % falta)
        else:
            self.responde(texto)

    def ac_view(self):
        texto, achados, sug = self.ac_texto()
        if texto is not None:
            self.ac_sugerida = sug.get("ajuste")
        itens = []
        for fase, tipo, ns in achados:
            if fase == "temp":
                itens.append(tx("Pneus dianteiros mais quentes") if tipo == "frente" else tx("Pneus traseiros mais quentes"))
            elif tipo == "patina":
                itens.append(tx("Patinando na saída %s") % _lista(ns))
            else:
                itens.append("%s %s %s" % (tx("Subesterço") if tipo == "sub" else tx("Sobresterço"), tx(FASES[fase]), _lista(ns)))
        return {"voltas": self.ac_voltas, "achados": itens, "sugestao": sug.get("texto"), "motivo": sug.get("motivo"),
                "proxima": sug.get("proxima"), "aviso": sug.get("aviso"), "comparacao": self.ac_comparacao,
                "ok": texto is not None, "novo": self.ac_novo}
