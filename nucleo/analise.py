"""Analise de voltas por curva.

- Trace: o "traco" de uma volta (amostras por distancia percorrida).
- detectar_curvas: acha as curvas da pista a partir de uma volta limpa.
- metricas: tempo do trecho, ponto de frenagem, velocidade minima, retomada
  do acelerador, travadas e patinadas de uma volta em uma curva.
- diagnostico: compara duas voltas na mesma curva e diz o que mudou.
"""
import bisect
from array import array

from idioma import N_, ingles, tx

RODAS = [N_("traseira esquerda"), N_("traseira direita"), N_("dianteira esquerda"), N_("dianteira direita")]
TRAVA = 0.3     # escorregamento da roda na frenagem que conta como travada
PATINA = 0.25   # escorregamento traseiro com acelerador que conta como patinada


class Trace:
    # "bal" = deriva media dos dianteiros - deriva media dos traseiros (rad): + subesterço, - sobresterço
    COMPLETO = ("d", "t", "v", "thr", "brk", "steer", "gear", "lock", "lockw", "spin", "x", "z", "bal")
    LEVE = ("d", "t", "v", "thr", "brk")

    def __init__(self, completo=True):
        self.completo = completo
        self.campos = self.COMPLETO if completo else self.LEVE
        for f in self.campos:
            setattr(self, f, array("f"))
        self.invalid = False
        self.pit = False
        self.flying = True

    def __len__(self):
        return len(self.d)

    def add(self, *vals):
        d = self.d
        while d and d[-1] >= vals[0]:   # flashback ou carro parado: descarta o que ficou "a frente"
            self.pop()
        for f, x in zip(self.campos, vals):
            getattr(self, f).append(x)

    def pop(self):
        for f in self.campos:
            getattr(self, f).pop()

    def interp(self, arr, x):
        D = self.d
        n = len(D)
        if n == 0:
            return 0.0
        i = bisect.bisect_left(D, x)
        if i <= 0:
            return arr[0]
        if i >= n:
            return arr[-1]
        d0, d1 = D[i - 1], D[i]
        if d1 <= d0:
            return arr[i]
        return arr[i - 1] + (arr[i] - arr[i - 1]) * (x - d0) / (d1 - d0)

    def ok(self):
        """Volta inteira, lancada, sem pit: serve para comparar."""
        return (len(self.d) > 100 and self.d[0] < 200 and self.flying and not self.pit
                and max(self.v) > 50 and self.v[0] > 60)


# --------------------------------------------------------------- curvas
def detectar_curvas(tr, comprimento):
    """Acha as curvas pelos minimos de velocidade da volta e monta os trechos."""
    passo = 5.0
    n = int(comprimento / passo)
    if n < 60 or len(tr) < 100:
        return []
    xs = [i * passo for i in range(n)]
    v = [tr.interp(tr.v, x) for x in xs]
    thr = [tr.interp(tr.thr, x) for x in xs]
    brk = [tr.interp(tr.brk, x) for x in xs]
    vs = [sum(v[(i + k) % n] for k in range(-3, 4)) / 7.0 for i in range(n)]

    W, P = 16, 100    # janela do minimo (80 m) e da proeminencia (500 m)
    cands = []
    for i in range(n):
        vi = vs[i]
        if any(vs[(i + k) % n] < vi for k in range(-W, W + 1)):
            continue
        esq = max(vs[(i - k) % n] for k in range(P + 1))
        dir_ = max(vs[(i + k) % n] for k in range(P + 1))
        if min(esq, dir_) - vi >= 12:
            cands.append(i)
    apices = []
    for i in cands:
        if apices and i - apices[-1] < 20:
            if vs[i] < vs[apices[-1]]:
                apices[-1] = i
            continue
        apices.append(i)
    if len(apices) > 1 and apices[0] + n - apices[-1] < 20:
        if vs[apices[0]] <= vs[apices[-1]]:
            apices.pop()
        else:
            apices.pop(0)

    curvas = []
    for idx, i in enumerate(apices):
        entrada = None
        for k in range(1, 121):
            j = (i - k) % n
            if brk[j] < 0.05 and thr[j] > 0.9:
                entrada = k
                break
        saida = None
        for k in range(0, 121):
            j = (i + k) % n
            if thr[j] >= 0.95:
                saida = k
                break
        apex = i * passo
        c = {
            "n": idx + 1,
            "apex": apex,
            "entry": max(0.0, apex - (entrada if entrada else 40) * passo),
            "exit": min(comprimento, apex + (saida if saida is not None else 40) * passo),
            "vin": round(vs[(i - (entrada or 40)) % n], 1),
            "vmin": round(vs[i], 1),
        }
        curvas.append(c)
    for k, c in enumerate(curvas):
        anterior = curvas[k - 1]["apex"] + 30 if k > 0 else 0.0
        c["search"] = max(anterior, c["entry"] - 150)
        c["b0"] = 0.0 if k == 0 else (curvas[k - 1]["apex"] + c["apex"]) / 2
        c["b1"] = comprimento if k == len(curvas) - 1 else (c["apex"] + curvas[k + 1]["apex"]) / 2
        c["last"] = k == len(curvas) - 1
    return curvas


def metricas(tr, c, tempo_volta):
    D = tr.d
    if not D or D[0] > c["b0"] + 40 or (D[-1] < c["b1"] - 40):
        return None
    t0 = 0.0 if c["b0"] <= 0 else tr.interp(tr.t, c["b0"])
    t1 = float(tempo_volta) if c["last"] else tr.interp(tr.t, c["b1"])
    i0 = bisect.bisect_left(D, c["search"])
    ia = bisect.bisect_left(D, c["apex"])
    bp = lp = None
    for k in range(i0, ia):
        if tr.brk[k] > 0.15:
            bp = D[k]
            break
    for k in range(i0, ia):
        if tr.thr[k] < 0.5:
            lp = D[k]
            break
    j0 = bisect.bisect_left(D, c["apex"] - 150)
    j1 = bisect.bisect_right(D, c["apex"] + 150)
    if j1 <= j0:
        return None
    kmin = min(range(j0, j1), key=lambda k: tr.v[k])
    fim = bisect.bisect_right(D, c["exit"] + 150)
    tp = None
    for k in range(kmin, fim):
        if tr.thr[k] >= 0.9:
            tp = D[k]
            break
    lock, lockw, spin = 0.0, -1, 0.0
    if tr.completo:
        for k in range(i0, min(len(D), ia + 10)):
            if tr.brk[k] > 0.2 and tr.lock[k] > lock:
                lock, lockw = tr.lock[k], int(tr.lockw[k])
        for k in range(kmin, fim):
            if tr.thr[k] > 0.3 and tr.spin[k] > spin:
                spin = tr.spin[k]
    return {"seg": t1 - t0, "bp": bp, "lp": lp, "vmin": tr.v[kmin], "tp": tp,
            "lock": lock, "lockw": lockw, "spin": spin}


def ponto_entrada(tr, c):
    """Distancia (m) onde o volante comeca a virar para a curva na volta tr.

    E o ponto de referencia das placas de distancia: 'freia a 95 m da curva' = 95 m antes daqui.
    """
    if "tin" in c:
        return c["tin"]
    D = tr.d
    if not tr.completo or not D:
        return c["apex"]
    ia = min(len(D) - 1, bisect.bisect_left(D, c["apex"]))
    lim = bisect.bisect_left(D, max(c.get("search", 0.0), c["apex"] - 400))
    k = ia
    while k > lim and abs(tr.steer[k]) >= 0.08:
        k -= 1
    c["tin"] = round(D[k], 1)
    return c["tin"]


def frenagem(m):
    """Onde comecou a frenagem (ou a tirada de pe, se nao freou)."""
    return m["bp"] if m["bp"] is not None else m["lp"]


def diagnostico(m, r):
    """Compara a volta m com a referencia r numa curva. Lista de (motivo, valor)."""
    out = []
    if m["lock"] >= TRAVA and r["lock"] < TRAVA and m["lockw"] >= 0:
        out.append(("trava", m["lockw"]))
    pm = m["bp"] if m["bp"] is not None else m["lp"]
    pr = r["bp"] if r["bp"] is not None else r["lp"]
    dv = m["vmin"] - r["vmin"]
    tarde = False
    if pm is not None and pr is not None:
        db = pm - pr
        if db <= -10 and dv > -6:
            out.append(("cedo", round(-db)))
        elif db >= 8 and dv <= -4:
            out.append(("tarde", round(db)))
            tarde = True
    if dv <= -5 and not tarde:
        out.append(("lento", round(-dv)))
    dt = None
    if m["tp"] is not None and r["tp"] is not None:
        dt = m["tp"] - r["tp"]
        if dt >= 15:
            out.append(("acel", round(dt)))
    if m["spin"] >= PATINA and r["spin"] < PATINA:
        out.append(("patinou", 0))
    if dv >= 5 and dt is not None and dt >= 8:
        out.append(("rapido", round(dv)))
    if not out:
        out.append(("geral", 0))
    return out


def deltas(m, r):
    pm = m["bp"] if m["bp"] is not None else m["lp"]
    pr = r["bp"] if r["bp"] is not None else r["lp"]
    return {
        "db": None if pm is None or pr is None else round(pm - pr),
        "dv": round(m["vmin"] - r["vmin"]),
        "dt": None if m["tp"] is None or r["tp"] is None else round(m["tp"] - r["tp"]),
        "lock": m["lock"] >= TRAVA,
        "spin": m["spin"] >= PATINA,
    }


# --------------------------------------------------------------- textos
def texto_meu(motivo, valor):
    return {
        "trava": tx("travou a roda %s") % (tx(RODAS[valor]) if 0 <= valor < 4 else ""),
        "cedo": tx("freou %d metros cedo demais") % valor,
        "tarde": tx("freou %d metros tarde e passou do ponto") % valor,
        "lento": tx("contornou %d km/h mais lento") % valor,
        "acel": tx("acelerou %d metros mais tarde na saída") % valor,
        "patinou": tx("patinou na saída"),
        "rapido": tx("entrou %d km/h rápido demais e saiu mal") % valor,
        "geral": tx("perdeu tempo no trecho"),
    }[motivo]


def texto_outro(motivo, valor):
    return {
        "trava": tx("você travou a roda %s") % (tx(RODAS[valor]) if 0 <= valor < 4 else ""),
        "cedo": tx("ele freia %d metros depois de você") % valor,
        "tarde": tx("ele freia %d metros antes e sai melhor") % valor,
        "lento": tx("ele contorna %d km/h mais rápido") % valor,
        "acel": tx("ele acelera %d metros antes na saída") % valor,
        "patinou": tx("você patinou na saída"),
        "rapido": tx("ele entra mais devagar e sai melhor"),
        "geral": tx("ele é mais rápido no trecho"),
    }[motivo]


DICA = {
    "trava": N_("cuidado com a trava na frenagem"),
    "cedo": N_("freie mais tarde"),
    "tarde": N_("freie um pouco antes"),
    "lento": N_("leve mais velocidade no meio"),
    "acel": N_("acelere mais cedo"),
    "patinou": N_("dose o acelerador na saída"),
    "rapido": N_("entre mais devagar e saia forte"),
    "geral": None,
}

HABITO = {
    "trava": N_("travar as rodas"),
    "cedo": N_("frear cedo demais"),
    "tarde": N_("frear tarde e passar do ponto"),
    "lento": N_("contornar devagar demais"),
    "acel": N_("acelerar tarde na saída"),
    "patinou": N_("patinar na saída"),
    "rapido": N_("entrar rápido demais"),
}


def fala_volta(ms):
    decimos = int(round(ms / 100.0))
    m, resto = divmod(decimos, 600)
    s, d = divmod(resto, 10)
    return "%d %02d %d" % (m, s, d)


def fala_dif(seg):
    decimos = int(round(abs(seg) * 10))
    if decimos == 0:
        return tx("menos de um décimo")
    if decimos == 1:
        return tx("um décimo")
    if decimos < 10:
        return tx("%d décimos") % decimos
    return _segundos(abs(seg))


def _segundos(s):
    if ingles():
        return "%.1f %s" % (s, "second" if round(s, 1) == 1 else "seconds")
    return num(s) + (" segundo" if s < 2 else " segundos")


def fala_gap(ms):
    return _segundos(ms / 1000.0)


def num(x, casas=1):
    """Numero com a virgula (ou ponto, em ingles) decimal."""
    t = "%.*f" % (casas, x)
    return t if ingles() else t.replace(".", ",")
