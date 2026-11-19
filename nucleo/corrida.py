"""Avisos de corrida que o engenheiro do jogo daria.

Cobre posicao e ultrapassagens, pit stop (limitador, tempo da parada, volta a
pista), paradas dos rivais (undercut/overcut), regra dos dois compostos, furo,
abandonos, volta mais rapida dos outros, DRS, safety car, bandeira vermelha,
contato, volta de formacao e, na classificacao, tempo restante, zona de
eliminacao, trafego e volta de saida/entrada. Usa os nomes dos pilotos.
"""
import struct
import time
import unicodedata

from analise import fala_dif, fala_gap, fala_volta
from analise import num as numero
from idioma import N_, ingles, tx

SECOS = (16, 17, 18)
COMPOSTO = {16: N_("macios"), 17: N_("médios"), 18: N_("duros"), 7: N_("intermediários"), 8: N_("de chuva")}
PNEU = [N_("traseiro esquerdo"), N_("traseiro direito"), N_("dianteiro esquerdo"), N_("dianteiro direito")]
TREINO = (1, 2, 3, 4)
QUALI = tuple(range(5, 15))
QUALI_Q1 = (5, 10)     # Q1 e Sprint Shootout 1
QUALI_Q2 = (6, 11)     # Q2 e Sprint Shootout 2
MOTIVO_ABANDONO = {3: N_("batida"), 6: N_("bandeira preta"), 8: N_("falha mecânica")}
MOTIVO_DRS = {0: N_("pista molhada"), 1: N_("safety car"), 2: N_("bandeira vermelha")}
ALERTA_TEMPO = [(600, N_("Dez minutos restantes.")), (300, N_("Cinco minutos restantes.")),
                (120, N_("Dois minutos restantes.")), (60, N_("Último minuto!"))]


def nome_curto(bruto):
    """'Max VERSTAPPEN' -> 'Verstappen'. None para nomes genericos do online."""
    if not bruto:
        return None
    n = bruto.rstrip("…").strip()
    if not n or n.lower() in ("player", "driver", "jogador", "piloto"):
        return None
    w = n.split()[-1]
    return w.capitalize() if (w.isupper() or w.islower()) else w


# Sobrenome -> como o engenheiro chama no radio (o jogo costuma mandar so o sobrenome dos pilotos reais)
PRIMEIROS = {
    "verstappen": "Max", "tsunoda": "Yuki", "hamilton": "Lewis", "leclerc": "Charles", "norris": "Lando",
    "piastri": "Oscar", "russell": "George", "antonelli": "Kimi", "alonso": "Fernando", "stroll": "Lance",
    "gasly": "Pierre", "doohan": "Jack", "colapinto": "Franco", "ocon": "Esteban", "bearman": "Ollie",
    "albon": "Alex", "sainz": "Carlos", "hulkenberg": "Nico", "bortoleto": "Gabriel", "lawson": "Liam",
    "hadjar": "Isack", "lindblad": "Arvid", "ricciardo": "Daniel", "perez": "Checo", "bottas": "Valtteri",
    "zhou": "Zhou", "magnussen": "Kevin", "sargeant": "Logan", "schumacher": "Mick", "drugovich": "Felipe",
}


def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def primeiro_nome(bruto):
    """Como chamar o piloto no radio, pelo nome que o jogo manda.
    'Matheus SILVA' -> 'Matheus'; 'VERSTAPPEN' -> 'Max'; 'SILVA' -> 'Silva'; 'Player' -> None."""
    sobrenome = nome_curto(bruto)
    if not sobrenome:
        return None
    ws = bruto.rstrip("…").split()
    if len(ws) >= 2 and len(ws[0]) > 1 and not ws[0].endswith("."):   # veio o primeiro nome junto
        p = ws[0]
        return p.capitalize() if (p.isupper() or p.islower()) else p
    return PRIMEIROS.get(_sem_acento(sobrenome).lower(), sobrenome)


def cap(s):
    return s[:1].upper() + s[1:]


class CorridaMixin:
    # ================================================================ estado
    def _cr_reset(self):
        self.cr_pos_anunciada = None
        self.cr_pos_desde = (None, 0.0)
        self.cr_ovtk = None
        self.cr_pit_prev = 0
        self.cr_pit_max = (0, 0)
        self.cr_pits_prev = None
        self.cr_ultimo_pit_volta = -99
        self.cr_rivais = {}
        self.cr_compostos = set()
        self.cr_pneu_dmg = None
        self.cr_alertas_tempo = set()
        self.cr_formacao = False
        self.cr_driver_status = None
        self.cr_corte = None
        self.cr_torre_pits = {}   # carro -> (paradas, volta em que parou por ultimo)
        self.cr_torre_melhor = {}  # carro -> melhor volta vista (quando o jogo nao manda o historico)

    # ================================================================ nomes
    def piloto(self, i):
        nomes = self.d.names
        if nomes is None or i is None or not 0 <= i < len(nomes):
            return None
        return nome_curto(nomes[i])

    def _pos_de(self, i):
        al = self.d.all_lap
        return al[i][13] if al and i is not None and 0 <= i < len(al) else None

    def quem(self, i):
        """'o Norris' (ou 'o P3' se o nome nao vier). Em ingles, so 'Norris' / 'P3'."""
        n = self.piloto(i)
        if n:
            return n if ingles() else "o " + n
        p = self._pos_de(i)
        return tx("o P%d") % p if p else tx("o carro")

    def de(self, i):
        """'do Norris' / 'do P3' (em ingles, igual a quem)."""
        return self.quem(i) if ingles() else "d" + self.quem(i)

    def rotulo(self, pos):
        """Quem esta na posicao: 'Norris' (ou 'P3' sem nome), para comecar frases."""
        return self.piloto(self.idx_pos(pos)) or "P%d" % pos

    def idx_pos(self, pos):
        al = self.d.all_lap
        if not al:
            return None
        for i, lv in enumerate(al):
            if lv[13] == pos and lv[26] in (2, 3):
                return i
        return None

    # ================================================================ torre de tempos (tecla P)
    def torre_view(self):
        """O grid inteiro para a torre: gaps, pneus, paradas e voltas de cada carro."""
        d = self.d
        al, s = d.all_lap, d.session
        if not al or s is None:
            return None
        corrida = bool(s["isRace"])
        sts, hist = d.all_status or [], d.hist or {}
        carros = [i for i, lv in enumerate(al) if lv[26] >= 2 and lv[13] >= 1]
        if not carros:
            return None
        for i in carros:
            ult = al[i][0]
            if ult > 0 and ult < self.cr_torre_melhor.get(i, 1e12):
                self.cr_torre_melhor[i] = ult
        melhores = {i: hist[i][0] if i in hist and hist[i][0] > 0 else self.cr_torre_melhor.get(i, 0)
                    for i in carros}
        melhores = {i: m for i, m in melhores.items() if m > 0}
        pole = min(melhores.values()) if melhores else 0
        lider = next((i for i in carros if al[i][13] == 1), None)
        comp = s["trackLength"] or 0
        linhas = []
        for i in carros:
            lv = al[i]
            pits, volta = lv[16], lv[14]
            ant = self.cr_torre_pits.get(i)
            if ant is None or pits < ant[0]:
                self.cr_torre_pits[i] = (pits, -99)
            elif pits > ant[0]:
                self.cr_torre_pits[i] = (pits, volta)
            parou_em = self.cr_torre_pits[i][1]
            st = sts[i] if i < len(sts) else None
            atras = 0
            if corrida and lider is not None and comp > 0 and i != lider:
                atras = max(0, int((al[lider][11] - lv[11]) // comp))
            melhor = melhores.get(i, 0)
            linhas.append({
                "pos": lv[13], "nome": self.piloto(i) or "P%d" % lv[13], "eu": i == d.player,
                "gap": lv[9] * 60000 + lv[8], "int": lv[7] * 60000 + lv[6], "voltasAtras": atras,
                "comp": st[0] if st else 0, "idade": st[1] if st else None,
                "pits": pits, "noPit": lv[15] in (1, 2), "parou": 0 <= volta - parou_em <= 2,
                "ultima": lv[0], "melhor": melhor, "difPole": melhor - pole if melhor and pole else None,
                "roxo": bool(melhor and melhor == pole), "pen": lv[19], "fora": lv[26] >= 4,
            })
        linhas.sort(key=lambda x: (x["fora"], x["pos"]))
        return {"corrida": corrida, "volta": al[lider][14] if lider is not None else None,
                "total": s["totalLaps"] if corrida else None, "carros": linhas}

    # ================================================================ 2x por segundo
    def _cr_tick(self):
        d = self.d
        v, s, st = d.lap, d.session, d.status
        if v is None or s is None:
            return
        agora = time.monotonic()
        if s["isRace"]:
            if s["safetyCar"] == 3 and not self.cr_formacao:
                self.cr_formacao = True
                self.say(tx("Volta de formação. Aqueça pneus e freios e mantenha a posição. Você larga em P%d.")
                         % v[24], pri=2, ttl=40, tom="calmo")
            self._cr_posicao(v, s, agora)
            self._cr_pit(v, st, s)
            self._cr_rivais_pit(v)
            self._cr_compostos(v, st, s)
        else:
            self._cr_quali(v, s, agora)
            self._cr_trafego(v)
        self._cr_furo()

    # ---------------------------------------------------------------- posicao
    def _cr_posicao(self, v, s, agora):
        pos = v[13]
        if pos <= 0:
            return
        if v[15] or s["safetyCar"] == 3:      # no pit ou na formacao: so acompanha
            self.cr_pos_anunciada = pos if s["safetyCar"] == 3 else self.cr_pos_anunciada
            self.cr_pos_desde = (pos, agora)
            return
        if self.cr_pos_anunciada is None:
            self.cr_pos_anunciada = pos
            self.cr_pos_desde = (pos, agora)
            return
        if pos != self.cr_pos_desde[0]:
            self.cr_pos_desde = (pos, agora)
            return
        if pos == self.cr_pos_anunciada or agora - self.cr_pos_desde[1] < 1.5:
            return
        if agora < self.cool.get("posicao", 0):
            return
        ov = self.cr_ovtk if self.cr_ovtk and agora - self.cr_ovtk[2] < 8 else None
        ganhou = pos < self.cr_pos_anunciada
        if ganhou:
            if pos == 1:
                texto = tx("Você lidera! P1!")
            elif ov and ov[0] == "passou":
                q = self.quem(ov[1])
                texto = self.escolhe("passou", [tx("Passou %s! P%d.") % (q, pos),
                                                tx("Boa! %s ficou pra trás, P%d.") % (cap(q), pos),
                                                tx("Isso! Deixou %s pra trás, P%d.") % (q, pos)])
            else:
                texto = self.escolhe("ganhou", [tx("P%d, ganhou posição.") % pos, tx("Subiu pra P%d.") % pos])
        else:
            if ov and ov[0] == "perdeu":
                q = self.quem(ov[1])
                texto = self.escolhe("perdeu", [tx("%s passou. P%d.") % (cap(q), pos),
                                                tx("Perdemos a posição pr%s, P%d.") % (q, pos)])
            else:
                texto = tx("Perdeu posição, P%d.") % pos
        self.say(texto, pri=2, ttl=10, chave="posicao", cool=4, tom="animado" if ganhou else "normal")
        self.cr_pos_anunciada = pos
        self.cr_ovtk = None

    # ---------------------------------------------------------------- seu pit stop
    def _cr_pit(self, v, st, s):
        pit, tel = v[15], self.d.tel
        if st and tel and self._segura("limitador", pit >= 1 and st["pitLimiter"] == 0
                                       and tel["speed"] > s["pitLimit"] + 3, 0.3):
            self.say(tx("Limitador! Limitador!"), pri=1, ttl=4, chave="limitador", cool=15, tom="urgente",
                     chamar=False)
        if pit:
            self.cr_pit_max = (max(self.cr_pit_max[0], v[29]), max(self.cr_pit_max[1], v[28]))
        pits = v[16]
        if self.cr_pits_prev is None:
            self.cr_pits_prev = pits
        if self.cr_pit_prev and not pit:          # saiu do pit lane
            if pits > self.cr_pits_prev:
                parada = self.cr_pit_max[0]
                partes = []
                if parada:
                    partes.append(tx("Parada de %s segundos.") % numero(parada / 1000))
                partes.append(tx("Voltou em P%d.") % v[13])
                atras = self.idx_pos(v[13] + 1)
                if atras is not None:
                    lv = self.d.all_lap[atras]
                    gap = lv[7] * 60000 + lv[6]
                    if 0 < gap < 5000:
                        partes.append(tx("%s está %s atrás.") % (cap(self.quem(atras)), fala_gap(gap)))
                comp = tx(COMPOSTO.get(st["visual"])) if st else None
                partes.append(tx("Pneus %s frios, cuidado nas primeiras curvas.") % comp if comp else
                              tx("Pneus frios, cuidado nas primeiras curvas."))
                self.say(" ".join(partes), pri=2, ttl=25)
                self.cr_ultimo_pit_volta = v[14]
            self.cr_pit_max = (0, 0)
        self.cr_pits_prev = pits
        self.cr_pit_prev = pit

    # ---------------------------------------------------------------- pit dos rivais
    def _cr_rivais_pit(self, v):
        d = self.d
        al = d.all_lap
        if not al:
            return
        minha = v[13]
        for i, lv in enumerate(al):
            if i == d.player or lv[26] != 2:
                continue
            r = self.cr_rivais.get(i)
            if r is None:
                self.cr_rivais[i] = {"pits": lv[16], "pit": lv[15], "pos": lv[13]}
                continue
            if not lv[15] and r["pit"] and lv[16] > r["pits"]:   # acabou de sair do pit depois de parar
                antes = r["pos"]
                if abs(antes - minha) <= 3 or antes == 1:
                    comp = tx(COMPOSTO.get(d.all_status[i][0])) if d.all_status and i < len(d.all_status) else None
                    frase = tx("%s, que era P%d, parou%s.") % (cap(self.quem(i)), antes,
                                                           tx(", colocou pneus ") + comp if comp else "")
                    if v[15] == 0 and antes == minha - 1:
                        frase += tx(" Pista livre na frente: força agora pra ganhar no overcut.")
                    elif v[15] == 0 and antes == minha + 1:
                        frase += tx(" Cuidado com o undercut. Se pararmos na próxima, cobrimos.")
                    self.say(frase, pri=2 if abs(antes - minha) <= 1 else 3, ttl=25)
            r["pits"], r["pit"] = lv[16], lv[15]
            if not lv[15]:
                r["pos"] = lv[13]

    # ---------------------------------------------------------------- regra dos dois compostos
    def _cr_compostos(self, v, st, s):
        if not st or s["safetyCar"] == 3 or v[14] < 1:
            return
        self.cr_compostos.add(st["visual"])
        if not s["totalLaps"] or s["totalLaps"] < 10:
            return
        restantes = s["totalLaps"] - v[14]
        seco = all(c in SECOS for c in self.cr_compostos)
        if seco and len(self.cr_compostos) < 2 and 0 < restantes <= 6 and v[16] == 0:
            self.say(tx("Lembra da regra dos dois compostos: em corrida seca ainda falta parar."), pri=2,
                     chave="dois_compostos", cool=99999)

    # ---------------------------------------------------------------- furo
    def _cr_furo(self):
        dmg = self.d.damage
        if not dmg:
            return
        atual = dmg["tyreDmg"]
        if self.cr_pneu_dmg is None:
            self.cr_pneu_dmg = list(atual)
            return
        for i in range(4):
            if atual[i] >= 50 > self.cr_pneu_dmg[i]:
                self.say(tx("Pneu %s muito danificado, %d por cento. Pode ser furo: box, box!") % (tx(PNEU[i]), atual[i]),
                         pri=1, tom="urgente")
            elif atual[i] >= self.cr_pneu_dmg[i] + 20:
                self.say(tx("Dano no pneu %s, %d por cento.") % (tx(PNEU[i]), atual[i]), pri=1)
        self.cr_pneu_dmg = list(atual)

    # ---------------------------------------------------------------- classificacao e treino
    def _cr_quali(self, v, s, agora):
        tipo = s["typeId"]
        if tipo not in QUALI and tipo not in TREINO:
            return
        tl = s["timeLeft"]
        for lim, texto in ALERTA_TEMPO:
            if tl and tl <= lim and lim not in self.cr_alertas_tempo:
                self.cr_alertas_tempo.add(lim)
                if tl > lim - 20:   # acabou de cruzar (ao entrar no meio da sessao, nao fala os antigos)
                    self.say(tx(texto), pri=2, ttl=15, tom="calmo", chamar=lim <= 60)
        ds = v[25]
        if ds != self.cr_driver_status:
            antes, self.cr_driver_status = self.cr_driver_status, ds
            if antes is not None and not v[15]:
                if ds == 3:
                    self.say(self.escolhe("saida", [tx("Volta de saída. Aqueça os pneus e abra espaço pra volta rápida."),
                                                    tx("Volta de saída: pneus e freios na temperatura e procura espaço.")]),
                             pri=3, ttl=15, tom="calmo")
                elif ds == 2 and antes == 1:
                    self.say(tx("Volta de entrada, pode recolher."), pri=3, ttl=15, tom="calmo")
        if tipo in QUALI_Q1 + QUALI_Q2:
            self._cr_corte(v, s, tipo, agora)

    def _cr_corte(self, v, s, tipo, agora):
        d = self.d
        al = d.all_lap
        if not al:
            return
        n = d.num_active or sum(1 for lv in al if lv[26] in (2, 3))
        if n < 10:
            return
        elim = 5 if n <= 20 else 6
        corte = n - elim if tipo in QUALI_Q1 else n - 2 * elim
        pos = v[13]
        fase = ("Q1" if tipo == 5 else "SQ1") if tipo in QUALI_Q1 else ("Q2" if tipo == 6 else "SQ2")
        self.cr_corte = (pos, corte, fase)
        if v[25] == 1 or agora < self.cool.get("corte", 0):     # nao distrai na volta rapida
            return
        meu = d.hist.get(d.player, (0,))[0]
        ic = self.idx_pos(corte)
        tc = d.hist.get(ic, (0,))[0] if ic is not None else 0
        if not meu:
            if not tl_ok(s):
                return
            texto = tx("Você ainda não tem tempo marcado. Precisa de uma volta limpa.")
        elif pos > corte:
            dif = (meu - tc) / 1000 if tc else 0
            texto = tx("P%d, zona de eliminação. O corte é %s, P%d%s.") % (
                pos, self.quem(ic) if ic is not None else "o P%d" % corte, corte,
                tx(", faltam %s") % fala_dif(dif) if dif > 0 else "")
        elif pos > corte - 3:
            ip = self.idx_pos(corte + 1)
            tp = d.hist.get(ip, (0,))[0] if ip is not None else 0
            margem = (tp - meu) / 1000 if tp else 0
            texto = (tx("P%d, perto do corte. Margem de %s para o P%d.") % (pos, fala_dif(margem), corte + 1)
                     if margem > 0 else tx("P%d, perto do corte.") % pos)
        else:
            return
        self.say(texto, pri=2, ttl=20, chave="corte", cool=60)

    def _cr_trafego(self, v):
        d = self.d
        al = d.all_lap
        L = self.lap_len
        if not al or not L or v[10] < 0 or v[15]:
            return
        minha, ds = v[10], v[25]
        for i, lv in enumerate(al):
            if i == d.player or lv[26] != 2 or lv[15] or lv[10] < 0:
                continue
            delta = (lv[10] - minha) % L
            if ds == 1 and 40 < delta < 450 and lv[25] in (2, 3):
                self.say(tx("Carro lento à frente: %s em volta %s.") % (self.quem(i), tx("de saída") if lv[25] == 3
                                                                    else tx("de entrada")),
                         pri=2, ttl=6, chave="trafego_frente", cool=25)
            elif ds in (2, 3) and L - 450 < delta < L - 30 and lv[25] == 1:
                self.say(tx("Carro em volta rápida atrás, %s. Deixe passar.") % self.quem(i), pri=1, ttl=6,
                         chave="trafego_atras", cool=25, tom="normal", chamar=False)

    # ================================================================ eventos do jogo
    def _cr_evento(self, code, data):
        d = self.d
        p = d.player
        s = d.session
        corrida = bool(s and s["isRace"])
        if code == "OVTK":
            a, b = data[33], data[34]
            if a == p:
                self.cr_ovtk = ("passou", b, time.monotonic())
            elif b == p:
                self.cr_ovtk = ("perdeu", a, time.monotonic())
        elif code == "RTMT" and corrida:
            i, motivo = data[33], data[34]
            if i == p:
                return
            pos = self._pos_de(i)
            minha = d.lap[13] if d.lap else 0
            extra = tx(MOTIVO_ABANDONO.get(motivo))
            self.say(tx("%s abandonou%s.") % (cap(self.quem(i)), ", " + extra if extra else ""),
                     pri=2 if pos and abs(pos - minha) <= 2 else 3, ttl=20)
        elif code == "FTLP" and corrida:
            i = data[33]
            t = struct.unpack_from("<f", data, 34)[0]
            if i != p and t > 0:
                self.say(tx("Volta mais rápida %s: %s.") % (self.de(i), fala_volta(int(t * 1000))), pri=3, ttl=15,
                         chave="ftlp_outro", cool=20, chamar=False)
        elif code == "RCWN" and corrida:
            if data[33] != p:
                self.say(tx("%s vence a corrida.") % cap(self.quem(data[33])), pri=3, ttl=30, chamar=False)
        elif code == "DRSE" and corrida:
            self.say(tx("DRS habilitado."), pri=2, ttl=8, chave="drs_on", cool=30, chamar=False)
        elif code == "DRSD" and corrida:
            motivo = tx(MOTIVO_DRS.get(data[33]))
            if motivo:
                self.say(tx("DRS desabilitado, %s.") % motivo, pri=2, ttl=8, chave="drs_off", cool=30, chamar=False)
        elif code == "SCAR":
            tipo, ev = data[33], data[34]
            if ev == 1 and tipo == 1:
                self.say(tx("Safety car entra nesta volta. Aqueça os pneus e prepare a relargada."), pri=1, ttl=20)
            elif ev == 1 and tipo == 2:
                self.say(tx("VSC terminando. Prepare-se pra acelerar."), pri=1, ttl=15)
        elif code == "RDFL":
            self.say(tx("Bandeira vermelha! Diminua e volte para o pit."), pri=1, ttl=20)
        elif code == "COLL":
            a, b = data[33], data[34]
            if p in (a, b):
                outro = b if a == p else a
                self.say(tx("Contato com %s. Tudo bem? Vou checar os danos.") % self.quem(outro), pri=2, ttl=10,
                         chave="contato", cool=15)

    def _cr_fim_sessao(self):
        """Na classificacao: passou ou ficou de fora."""
        if not self.cr_corte:
            return
        pos, corte, fase = self.cr_corte
        proxima = {"Q1": "Q2", "Q2": "Q3", "SQ1": "SQ2", "SQ2": "SQ3"}.get(fase, tx("próxima fase"))
        if pos <= corte:
            self.say(tx("Passamos! P%d, estamos no %s.") % (pos, proxima), pri=2, tom="animado")
        else:
            self.say(tx("Fim do %s. P%d, ficamos fora dessa vez.") % (fase, pos), pri=2, tom="calmo")
        self.cr_corte = None


def tl_ok(s):
    """So cobra tempo marcado quando faltam menos de 5 minutos."""
    return 0 < s["timeLeft"] < 300
