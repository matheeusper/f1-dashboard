"""Modo treino com metas (so no Time Trial).

- Voce escolhe uma curva para treinar (tecla T no painel ou botao 9): a cada
  volta o engenheiro diz quanto ficou do seu melhor trecho, onde voce freou
  contra o alvo, e cobra consistencia (variacao nas ultimas 5 voltas).
- No comeco do Time Trial ele propoe metas para o dia (tempo de volta, voltas
  seguidas sem travar, constancia, o seu vicio) e acompanha o progresso.
- Meta cumprida vira conquista no historico (pagina Evolucao).
"""
import statistics

from analise import HABITO, TRAVA, fala_dif, fala_volta

TIME_TRIAL = 18


def fmt_meta(ms):
    decimos = int(ms // 100)
    m, resto = divmod(decimos, 600)
    s, d = divmod(resto, 10)
    return "%d:%02d.%d" % (m, s, d)


def fala_cent(seg):
    c = int(round(abs(seg) * 100))
    if c >= 10:
        return fala_dif(seg)
    if c == 0:
        return "menos de um centésimo"
    return "um centésimo" if c == 1 else "%d centésimos" % c


class TreinoMixin:
    def _tr_reset(self):
        self.tr_curva = None
        self.tr_metas = []
        self.tr_metas_ok = False
        self.tr_seg = []             # [(trecho_ms, frenagem_m)] da curva treinada
        self.tr_melhor_sessao = {}   # curva -> melhor trecho nesta sessao (ms)

    def tr_disponivel(self):
        s = self.d.session
        return bool(s and s["typeId"] == TIME_TRIAL)

    def _tr_melhor(self, n):
        cand = [v for v in ((self.resumo or {}).get("melhores_seg", {}).get(n), self.tr_melhor_sessao.get(n)) if v]
        return min(cand) if cand else None

    # ---------------------------------------------------------------- escolher a curva
    def tr_alternar(self, n=None):
        if not self.tr_disponivel():
            self.responde("O modo treino só funciona no Time Trial.")
            return
        if not self.corners:
            self.responde("Ainda não mapeei as curvas. Faz uma volta limpa primeiro.")
            return
        if n is None and self.tr_curva is not None or n is not None and n == self.tr_curva:
            antiga = self.tr_curva
            self.tr_curva = None
            self.tr_metas = [m for m in self.tr_metas if m["id"] != "curva"]
            self.responde("Treino da curva %d encerrado." % antiga, chamar=False)
            return
        if n is None:   # sem escolha: a curva onde voce mais perde
            n = (self.resumo or {}).get("fraca")
            if not n and self.report and self.report["corners"]:
                n = max((c for c in self.report["corners"] if c.get("loss") is not None),
                        key=lambda c: c["loss"], default={"n": 1})["n"]
            n = n or 1
        c = next((c for c in self.corners if c["n"] == n), None)
        if c is None:
            return
        self.tr_curva = n
        self.tr_seg = []
        self.tr_metas = [m for m in self.tr_metas if m["id"] != "curva"]
        self.tr_metas.append({"id": "curva", "curva": n, "meta": 5, "prog": 0, "feito": False,
                              "texto": "Curva %d: 5 voltas seguidas a menos de 5 centésimos do seu melhor" % n})
        partes = ["Treino na curva %d. Vou cobrar consistência nela." % n]
        alvo = self._alvo_frenagem(c)
        if alvo:
            partes.append("Alvo de frenagem: %d metros." % (5 * round(alvo / 5)))
            self._define_dica(c, "freie a %d metros" % (5 * round(alvo / 5)), self.lap_no or 0)
        partes.append("Meta: 5 voltas seguidas a menos de 5 centésimos do seu melhor trecho.")
        self.responde(" ".join(partes))

    # ---------------------------------------------------------------- metas do dia
    def _tr_gerar_metas(self, ms_volta=None):
        if self.tr_metas_ok or not self.corners:
            return
        self.tr_metas_ok = True
        r = self.resumo or {}
        rec, ideal = self.recorde_ms, r.get("ideal", 0)
        metas = []
        base = rec or ms_volta
        if base:
            ganho = max(100, (rec - ideal) * 0.5) if rec and ideal and rec > ideal else (100 if rec else 500)
            alvo = int((base - ganho) // 100 * 100)
            metas.append({"id": "tempo", "alvo": alvo, "meta": 1, "prog": 0, "feito": False,
                          "texto": "Bater %s hoje" % fmt_meta(alvo)})
        metas.append({"id": "sem_trava", "meta": 5, "prog": 0, "feito": False,
                      "texto": "5 voltas seguidas sem travar"})
        metas.append({"id": "constante", "meta": 3, "prog": 0, "feito": False,
                      "texto": "3 voltas seguidas a menos de 3 décimos do recorde"})
        hab = r.get("habitos") or {}
        if hab:
            n, h = max(hab.items(), key=lambda kv: kv[1][1])
            metas.append({"id": "vicio", "curva": n, "motivo": h[0], "meta": 5, "prog": 0, "feito": False,
                          "texto": "Curva %d: 5 voltas seguidas sem %s" % (n, HABITO.get(h[0], h[0]))})
        self.tr_metas = metas + [m for m in self.tr_metas if m["id"] == "curva"]
        lista = ", ".join(m["texto"][:1].lower() + m["texto"][1:] for m in metas)
        if metas and metas[0]["id"] == "tempo":
            lista = lista.replace(fmt_meta(metas[0]["alvo"]), fala_volta(metas[0]["alvo"]))
        self.say("Time Trial. Metas de hoje: %s. Aperte T no painel para treinar uma curva." % lista,
                 pri=3, ttl=60, tom="calmo", show="Metas de hoje: " + " · ".join(m["texto"] for m in metas))

    def _tr_conquista(self, meta):
        meta["feito"] = True
        meta["prog"] = meta["meta"]
        self.say("Meta cumprida%s: %s!" % (self.vn(), meta["texto"].lower() if meta["id"] != "tempo"
                                           else "bateu " + fala_volta(meta["alvo"])),
                 pri=2, tom="animado", chamar=False, show="🏆 Meta cumprida: " + meta["texto"])
        if self.hist and self.chave:
            self._seguro(self.hist.salvar_conquista, self.chave, self.sess_id, meta["texto"])

    def _tr_conta(self, meta, ok, aviso):
        if meta["feito"]:
            return
        meta["prog"] = meta["prog"] + 1 if ok else 0
        if meta["prog"] >= meta["meta"]:
            self._tr_conquista(meta)
        elif ok and meta["prog"] == meta["meta"] - 1 and meta["meta"] > 2:
            self.say(aviso, pri=3, ttl=20, chamar=False)

    # ---------------------------------------------------------------- fim de volta
    def _tr_fim_volta(self, num, ms, valida, resultado):
        if not self.tr_disponivel():
            return
        for x in resultado:
            n = x["c"]["n"]
            seg = x["m"]["seg"]
            if valida and (n not in self.tr_melhor_sessao or seg < self.tr_melhor_sessao[n]):
                self.tr_melhor_sessao[n] = seg
        self._tr_gerar_metas(ms)
        por_curva = {x["c"]["n"]: x for x in resultado}
        travou = any(x["m"]["lock"] >= TRAVA for x in resultado)
        for meta in self.tr_metas:
            if meta["feito"]:
                continue
            if meta["id"] == "tempo":
                if valida and ms <= meta["alvo"]:
                    self._tr_conquista(meta)
            elif meta["id"] == "sem_trava":
                self._tr_conta(meta, valida and not travou, "Mais uma volta sem travar e a meta está batida.")
            elif meta["id"] == "constante":
                ok = valida and self.recorde_ms and ms - self.recorde_ms <= 300
                self._tr_conta(meta, ok, "Mais uma volta nesse ritmo e a meta de constância está batida.")
            elif meta["id"] == "vicio":
                x = por_curva.get(meta["curva"])
                ok = valida and x is not None and meta["motivo"] not in [k for k, _ in x["motivos"]]
                self._tr_conta(meta, ok, "Curva %d: mais uma volta sem o vício e a meta está batida." % meta["curva"])
            elif meta["id"] == "curva":
                x = por_curva.get(meta["curva"])
                melhor = self._tr_melhor(meta["curva"])
                ok = valida and x is not None and melhor and x["m"]["seg"] - melhor <= 50
                self._tr_conta(meta, ok, "Curva %d: mais uma e a meta está batida." % meta["curva"])
        self._tr_feedback(por_curva, valida)

    def _tr_feedback(self, por_curva, valida):
        n = self.tr_curva
        if n is None:
            return
        x = por_curva.get(n)
        if x is None:
            return
        seg = x["m"]["seg"]
        bp = x["dist"][0] if x.get("dist") else None
        self.tr_seg.append((seg, bp))
        del self.tr_seg[:-5]
        melhor = self._tr_melhor(n)
        partes = []
        if melhor and seg <= melhor + 5:
            partes.append("Curva %d: melhor trecho seu nessa curva!" % n)
        elif melhor:
            partes.append("Curva %d: %s do seu melhor." % (n, fala_cent((seg - melhor) / 1000)))
        if bp is not None and x.get("dist"):
            alvo = x["dist"][1]
            partes.append("Frenagem a %d metros, alvo %d." % (bp, 5 * round(alvo / 5)))
        if len(self.tr_seg) >= 3:
            segs = [s for s, _ in self.tr_seg]
            bps = [b for _, b in self.tr_seg if b is not None]
            var = "Variação de %s" % fala_cent(statistics.pstdev(segs) / 1000)
            if len(bps) >= 3:
                var += " e %d metros na frenagem" % round(statistics.pstdev(bps))
            partes.append(var + " nas últimas %d." % len(segs))
        if not valida:
            partes.append("Volta inválida, não conta para as metas.")
        self.say(" ".join(partes), pri=2, ttl=30, tom="calmo", chamar=False)
        # dica fixa da curva treinada para a proxima volta
        c = x["c"]
        alvo_m = self._alvo_frenagem(c)
        self._define_dica(c, "freie a %d metros" % (5 * round(alvo_m / 5)) if alvo_m else "foco total",
                          (self.lap_no or 0) + 1)

    # ---------------------------------------------------------------- botao 9 e tela
    def _r_metas(self):
        if not self.tr_disponivel():
            self.responde("Metas e treino só no Time Trial.")
            return
        if not self.tr_metas:
            self.responde("As metas aparecem depois da primeira volta limpa.")
            return
        partes = []
        for m in self.tr_metas:
            partes.append("%s: %s" % (m["texto"], "feita" if m["feito"] else "%d de %d" % (m["prog"], m["meta"])))
        if self.tr_curva:
            partes.append("Treinando a curva %d" % self.tr_curva)
        self.responde(". ".join(partes) + ".")

    def tr_view(self):
        cons = None
        if len(self.tr_seg) >= 2:
            segs = [s for s, _ in self.tr_seg]
            bps = [b for _, b in self.tr_seg if b is not None]
            cons = {"seg": round(statistics.pstdev(segs) / 1000, 3),
                    "bp": round(statistics.pstdev(bps), 1) if len(bps) >= 2 else None, "n": len(segs)}
        return {"tt": self.tr_disponivel(), "curva": self.tr_curva, "cons": cons,
                "metas": [{"texto": m["texto"], "prog": m["prog"], "meta": m["meta"], "feito": m["feito"]}
                          for m in self.tr_metas]}
