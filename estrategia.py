"""Estrategista de pit (o "pit wall" do engenheiro).

- Aprende quanto se perde num pit stop em cada pista, medindo as paradas de
  todos os carros (volta de entrada + saida contra o ritmo normal) e guardando
  no historico.
- Preve onde voce volta se parar agora: posicao, quem fica na frente e atras.
- Safety car/VSC: avisa quando o pit fica barato.
- Undercut e overcut, e pneus dos rivais (mais novos ou mais velhos que os seus).
"""
import statistics
import time

from analise import fala_gap
from idioma import N_, tx

PERDA_PADRAO = 22.0          # segundos, ate aprender a pista
FATOR_SC = {1: 0.55, 2: 0.7}  # o pit custa menos com safety car / VSC
COMPOSTO = {16: N_("macios"), 17: N_("médios"), 18: N_("duros"), 7: N_("intermediários"), 8: N_("de chuva")}


def cap(s):
    return s[:1].upper() + s[1:]


def atras_lider(lv):
    """Tempo atras do lider (ms) de um carro, pelo pacote Lap Data."""
    return lv[9] * 60000 + lv[8]


class EstrategiaMixin:
    def _es_reset(self):
        self.es_perdas = []          # perdas medidas nesta sessao (s)
        self.es_perdas_hist = []     # perdas guardadas desta pista
        self.es_meus_tempos = []
        self.es_sc_visto = 0.0
        self.es_sc_prev = 0
        self.es_janela_sc = False

    def _es_pista(self):
        if self.hist and self.chave:
            self.es_perdas_hist = self._seguro(self.hist.perdas_pit, self.chave) or []

    # ================================================================ perda no pit
    def perda_pit(self):
        amostras = self.es_perdas + self.es_perdas_hist
        return statistics.median(amostras) if amostras else PERDA_PADRAO

    def _es_aprende(self, tempos):
        """tempos: [(ms, parou_nessa_volta, teve_sc)] de um carro. Mede a perda quando ele volta ao ritmo."""
        if len(tempos) < 4 or tempos[-1][1] or not tempos[-2][1]:
            return
        k = 0
        while k + 1 < len(tempos) and tempos[-2 - k][1]:
            k += 1
        antes = [ms for ms, pit, sc in tempos[:-1 - k] if not pit and not sc][-3:]
        voltas_pit = tempos[-1 - k:-1]
        if len(antes) < 2 or any(sc for _ms, _p, sc in voltas_pit):
            return
        base = statistics.median(antes)
        perda = (sum(ms for ms, _p, _s in voltas_pit) - k * base) / 1000.0
        if 8 <= perda <= 45:
            self.es_perdas.append(perda)
            if self.hist and self.chave:
                self._seguro(self.hist.salvar_perda_pit, self.chave, perda)

    def _es_volta_carro(self, car, ms, parou):
        sc = time.monotonic() - self.es_sc_visto < self.lap_sec * 1.2
        t = car.setdefault("tempos", [])
        t.append((ms, parou, sc))
        del t[:-8]
        self._es_aprende(t)

    # ================================================================ previsao
    def previsao_pit(self):
        """(posicao, (idx_frente, gap_ms), (idx_atras, gap_ms), perda_s) se parar agora."""
        d = self.d
        al, v, s = d.all_lap, d.lap, d.session
        if not al or v is None or v[13] <= 0:
            return None
        perda = self.perda_pit() * FATOR_SC.get(s["safetyCar"] if s else 0, 1.0)
        alvo = atras_lider(v) + perda * 1000
        outros = [(atras_lider(lv), i) for i, lv in enumerate(al)
                  if i != d.player and lv[26] == 2 and lv[13] > 0]
        frente = [x for x in outros if x[0] <= alvo]
        tras = [x for x in outros if x[0] > alvo]
        f = max(frente) if frente else None
        t = min(tras) if tras else None
        return (len(frente) + 1,
                (f[1], alvo - f[0]) if f else None,
                (t[1], t[0] - alvo) if t else None,
                perda)

    def texto_previsao(self, prefixo=None):
        prefixo = prefixo or tx("Se parar agora, volta em")
        p = self.previsao_pit()
        if not p:
            return ""
        pos, f, t, _perda = p
        partes = ["%s P%d" % (prefixo, pos)]
        if f:   # "1,2 segundo atrás do Pérez"
            partes.append(tx("%s atrás %s") % (fala_gap(f[1]), self.de(f[0])) if f[1] < 3000
                          else tx("atrás %s") % self.de(f[0]))
        if t and t[1] < 3000:   # "com o Sainz 0,8 segundo atrás"
            partes.append(tx("com %s %s atrás") % (self.quem(t[0]), fala_gap(t[1])))
        return ", ".join(partes) + "."

    # ================================================================ 2x por segundo (corrida)
    def _es_tick(self):
        d = self.d
        s, v, st = d.session, d.lap, d.status
        if not s or not s["isRace"] or v is None:
            return
        sc = s["safetyCar"]
        if sc in (1, 2):
            self.es_sc_visto = time.monotonic()
        # safety car / VSC acabou de entrar: o pit fica barato
        if sc in (1, 2) and self.es_sc_prev not in (1, 2) and not v[15] and st:
            restantes = (s["totalLaps"] - v[14]) if s["totalLaps"] else 99
            recente = v[14] - self.cr_ultimo_pit_volta <= 5
            janela = s["pitIdeal"] and v[14] >= s["pitIdeal"] - 4
            precisa = len(self.cr_compostos) < 2 and all(c in (16, 17, 18) for c in self.cr_compostos)
            if not recente and restantes > 2 and (st["tyreAge"] >= 6 or janela or precisa):
                perda = self.perda_pit() * FATOR_SC[sc]
                self.say(tx("%s na pista! Box, box: o pit custa só uns %d segundos agora. %s")
                         % (tx("Safety car") if sc == 1 else "VSC", round(perda),
                            self.texto_previsao(tx("Você volta em"))),
                         pri=1, ttl=20, tom="urgente", chave="sc_box", cool=60)
        self.es_sc_prev = sc

    # ================================================================ fim de volta (corrida)
    def _es_fim_volta(self, num):
        d = self.d
        v, s, st, al, sts = d.lap, d.session, d.status, d.all_lap, d.all_status
        if v is None or not s or not st or not al or not sts:
            return
        pos = v[13]
        minha_idade = st["tyreAge"]
        janela = bool(s["pitIdeal"]) and s["pitIdeal"] - 2 <= num <= max(s["pitLatest"], s["pitIdeal"])
        sem_parar = num - self.cr_ultimo_pit_volta > 5
        # carro da frente
        fi = self.idx_pos(pos - 1) if pos > 1 else None
        if fi is not None and fi < len(sts):
            gap = v[7] * 60000 + v[6]
            idade = sts[fi][1]
            if 0 < gap < 3000 and idade - minha_idade >= 8:
                self.say(tx("%s está com pneus %d voltas mais velhos. Ele vai cair, pressiona.")
                         % (cap(self.quem(fi)), idade - minha_idade), pri=3, chave="pneu_frente", cool=self.voltas(4))
            elif 0 < gap < 2000 and janela and sem_parar and not al[fi][15]:
                self.say(tx("Chance de undercut %s, a %s. Se pararmos nesta volta, o pneu novo pode te colocar na frente.")
                         % (self.de(fi), fala_gap(gap)), pri=2, chave="undercut_eu", cool=self.voltas(3))
        # carro de tras
        ti = self.idx_pos(pos + 1)
        if ti is not None and ti < len(sts):
            lt = al[ti]
            gap_t = lt[7] * 60000 + lt[6]
            idade = sts[ti][1]
            if 0 < gap_t < 3000 and minha_idade - idade >= 8:
                self.say(tx("%s tem pneus %d voltas mais novos, vai vir forte.") % (cap(self.quem(ti)), minha_idade - idade),
                         pri=3, chave="pneu_tras", cool=self.voltas(4))
            elif 0 < gap_t < 2500 and janela and sem_parar:
                self.say(tx("Atenção ao undercut %s, a %s. Se ele parar, a gente responde na volta seguinte.")
                         % (self.de(ti), fala_gap(gap_t)), pri=2, chave="undercut_ele", cool=self.voltas(3))

    def _es_minha_volta(self, ms, parou):
        sc = time.monotonic() - self.es_sc_visto < self.lap_sec * 1.2
        self.es_meus_tempos.append((ms, parou, sc))
        del self.es_meus_tempos[:-8]
        self._es_aprende(self.es_meus_tempos)

    # ================================================================ botao 8
    def _r_estrategia(self):
        d = self.d
        s, v, st, sts = d.session, d.lap, d.status, d.all_status
        if not s or v is None or not st:
            return False
        if not s["isRace"]:
            self.responde(tx("Estratégia de pit só na corrida."))
            return
        partes = [tx("O pit aqui custa uns %d segundos.") % round(self.perda_pit())]
        prev = self.texto_previsao()
        if prev:
            partes.append(prev)
        comp = tx(COMPOSTO.get(st["visual"]))
        partes.append(tx("Seus %s têm %d voltas.") % (comp, st["tyreAge"]) if comp else
                      tx("Seus pneus têm %d voltas.") % st["tyreAge"])
        for p, onde in ((v[13] - 1, tx("frente")), (v[13] + 1, tx("trás"))):
            i = self.idx_pos(p) if p >= 1 else None
            if i is not None and sts and i < len(sts):
                c = tx(COMPOSTO.get(sts[i][0]))
                if c:
                    partes.append(tx("%s, %s, está de %s com %d voltas.") % (cap(self.quem(i)), onde, c, sts[i][1]))
        if s["pitIdeal"] and v[14] <= max(s["pitLatest"], s["pitIdeal"]):
            partes.append(tx("Janela de pit: volta %d%s.") % (s["pitIdeal"], tx(" a %d") % s["pitLatest"]
                                                        if s["pitLatest"] and s["pitLatest"] != s["pitIdeal"] else ""))
        self.responde(" ".join(partes))

    def es_view(self):
        p = self._seguro(self.previsao_pit) if self.d.session and self.d.session["isRace"] else None
        if not p:
            return None
        pos, f, t, perda = p
        return {"pos": pos, "perda": round(perda, 1),
                "frente": [self.piloto(f[0]) or "P%d" % self._pos_de(f[0]), round(f[1] / 1000, 1)] if f else None,
                "tras": [self.piloto(t[0]) or "P%d" % self._pos_de(t[0]), round(t[1] / 1000, 1)] if t else None}
