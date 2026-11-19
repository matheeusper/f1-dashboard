"""Decodificador da telemetria UDP do F1 25.

Suporta os dois formatos que o jogo envia:
  - 2025: formato original do F1 25 (22 carros)
  - 2026: formato do Season Pack 2026 (24 carros)

Todos os valores sao little-endian e as structs nao tem padding.
Ordem das rodas nos arrays do jogo: [TE, TD, DE, DD] (traseiras primeiro).
"""
import bisect
import struct
import threading
import time

from idioma import N_, tx
from idioma import atual as idioma_atual

HEADER = struct.Struct("<HBBBBBQfIIBB")  # 29 bytes
HEADER_SIZE = HEADER.size

# IDs de pacote
MOTION, SESSION, LAP_DATA, EVENT, PARTICIPANTS, SETUPS, TELEMETRY, STATUS = 0, 1, 2, 3, 4, 5, 6, 7
DAMAGE, HISTORY, MOTION_EX, TELEMETRY2 = 10, 11, 13, 16
OFF_SLIP = HEADER_SIZE + 16 * 4   # Motion Ex: m_wheelSlipRatio[4] vem depois de 4 arrays de 4 floats

# Structs por carro que sao iguais nos dois formatos
LAP = struct.Struct("<IIHBHBHBHBfff15BHHBfB")      # 57
DAMAGE_CAR = struct.Struct("<4f4B4B4B18B")         # 46
SETUP_CAR = struct.Struct("<4B4f9B4fBf")           # 50
TELEMETRY2_CAR = struct.Struct("<BBHBBHBB")        # 10
SESSION_HEAD = struct.Struct("<BbbBHBbBHHBBBBBB")  # 19, logo apos o header
LAP_HISTORY = struct.Struct("<IHBHBHBB")           # 14

# Offsets fixos dentro do pacote Session (iguais nos dois formatos)
OFF_SAFETY_CAR = 153
OFF_NUM_FORECAST = 155
OFF_FORECAST = 156
FORECAST_SIZE = 8
OFF_PIT_WINDOW = 682

LAYOUTS = {
    2025: {
        "cars": 22,
        "motion": struct.Struct("<6f6h3f3f"),               # 60, forca G em float
        "telemetry": struct.Struct("<HfffBbHBBH4H4B4BH4f4B"),  # 60
        "status": struct.Struct("<5B3fHHBBHBBBb3fB3fB"),    # 55
        "participant": struct.Struct("<7B32sBBHBB12B"),     # 57, nome comeca no byte 7
        "g_div": 1.0,
        "sizes": {MOTION: 1349, SESSION: 753, LAP_DATA: 1285, EVENT: 45, PARTICIPANTS: 1284, SETUPS: 1133,
                  TELEMETRY: 1352, STATUS: 1239, DAMAGE: 1041, HISTORY: 1460, MOTION_EX: 273},
    },
    2026: {
        "cars": 24,
        "motion": struct.Struct("<6f6h3h3f"),               # 54, forca G em int16 / 1000
        "telemetry": struct.Struct("<HfffBbHBBH4H4B4BB4f4B"),  # 59, temp. do motor em uint8
        "status": struct.Struct("<5B3fHHBBHBBBb3fB4fB"),    # 59, + limite de colheita do ERS
        "participant": struct.Struct("<BHHHBBB32sBBHBB12B"),  # 60, ids de 16 bits: nome no byte 10
        "g_div": 1000.0,
        "sizes": {MOTION: 1325, SESSION: 926, LAP_DATA: 1399, EVENT: 45, PARTICIPANTS: 1470, SETUPS: 1233,
                  TELEMETRY: 1448, STATUS: 1445, DAMAGE: 1133, HISTORY: 1460, TELEMETRY2: 269,
                  MOTION_EX: 273},
    },
}

# Confere os tamanhos das structs com os tamanhos oficiais dos pacotes.
for _fmt, _l in LAYOUTS.items():
    _n, _s = _l["cars"], _l["sizes"]
    assert HEADER_SIZE + _n * _l["motion"].size == _s[MOTION], _fmt
    assert HEADER_SIZE + _n * _l["telemetry"].size + 3 == _s[TELEMETRY], _fmt
    assert HEADER_SIZE + _n * _l["status"].size == _s[STATUS], _fmt
    assert HEADER_SIZE + _n * LAP.size + 2 == _s[LAP_DATA], _fmt
    assert HEADER_SIZE + _n * DAMAGE_CAR.size == _s[DAMAGE], _fmt
    assert HEADER_SIZE + _n * SETUP_CAR.size + 4 == _s[SETUPS], _fmt
    assert HEADER_SIZE + 7 + 100 * LAP_HISTORY.size + 8 * 3 == _s[HISTORY], _fmt
    assert HEADER_SIZE + 1 + _n * _l["participant"].size == _s[PARTICIPANTS], _fmt
assert HEADER_SIZE + 24 * TELEMETRY2_CAR.size == LAYOUTS[2026]["sizes"][TELEMETRY2]

PACKET_NAMES = {MOTION: "Motion", SESSION: "Session", LAP_DATA: "Lap Data", EVENT: "Event",
                PARTICIPANTS: "Participants",
                SETUPS: "Car Setups", TELEMETRY: "Car Telemetry", STATUS: "Car Status",
                DAMAGE: "Car Damage", HISTORY: "Session History", TELEMETRY2: "Car Telemetry 2",
                MOTION_EX: "Motion Ex"}

TRACKS = {
    0: "Melbourne", 1: N_("Paul Ricard"), 2: N_("Xangai"), 3: "Sakhir", 4: "Barcelona", 5: N_("Mônaco"),
    6: "Montreal", 7: "Silverstone", 8: "Hockenheim", 9: "Hungaroring", 10: "Spa-Francorchamps",
    11: "Monza", 12: N_("Singapura"), 13: "Suzuka", 14: N_("Abu Dhabi"), 15: "Austin", 16: "Interlagos",
    17: N_("Red Bull Ring"), 18: "Sochi", 19: N_("Cidade do México"), 20: "Baku", 21: N_("Sakhir (curto)"),
    22: N_("Silverstone (curto)"), 23: N_("Austin (curto)"), 24: N_("Suzuka (curto)"), 25: N_("Hanói"),
    26: "Zandvoort", 27: N_("Ímola"), 28: N_("Portimão"), 29: "Jeddah", 30: "Miami", 31: N_("Las Vegas"),
    32: "Losail", 39: N_("Silverstone (invertido)"), 40: N_("Red Bull Ring (invertido)"),
    41: N_("Zandvoort (invertido)"), 42: N_("Madri"),
}
SESSION_TYPES = {
    0: "—", 1: N_("Treino livre 1"), 2: N_("Treino livre 2"), 3: N_("Treino livre 3"), 4: N_("Treino curto"),
    5: N_("Classificação 1"), 6: N_("Classificação 2"), 7: N_("Classificação 3"), 8: N_("Classificação curta"),
    9: N_("Classificação volta única"), 10: N_("Sprint Shootout 1"), 11: N_("Sprint Shootout 2"),
    12: N_("Sprint Shootout 3"), 13: N_("Sprint Shootout curto"), 14: N_("Sprint Shootout volta única"),
    15: N_("Corrida"), 16: N_("Corrida 2"), 17: N_("Corrida 3"), 18: N_("Time Trial"),
}
RACE_SESSIONS = (15, 16, 17)
WEATHER = {0: N_("Limpo"), 1: N_("Poucas nuvens"), 2: N_("Nublado"), 3: N_("Chuva fraca"), 4: N_("Chuva forte"),
           5: N_("Tempestade")}
SC_EVENT = {0: N_("acionado"), 1: N_("voltando aos boxes"), 2: N_("retornou aos boxes"), 3: N_("corrida retomada")}
SC_TYPE = {1: N_("Safety Car"), 2: N_("Virtual Safety Car"), 3: N_("Volta de formação")}


def fmt_time(ms):
    if ms <= 0:
        return "—"
    return "%d:%06.3f" % (ms // 60000, (ms % 60000) / 1000.0)


def _r(x, n=2):
    return round(float(x), n)


class Decoder:
    """Recebe datagramas crus e mantem o estado atual do carro do jogador."""

    def __init__(self):
        self.lock = threading.Lock()
        self.tick = threading.Condition()
        self.fmt = None
        self.uid = None
        self.last_rx = 0.0
        self.warn = None
        self.warn_t = 0.0
        self.demo = False
        self.event_seq = 0
        self.eng = None
        self._reset_session()
        from engenheiro import Engenheiro
        self.eng = Engenheiro(self)

    # ------------------------------------------------------------------ estado
    def _reset_session(self):
        if self.eng is not None:
            try:
                self.eng.end_session()
            except Exception as exc:
                print("Engenheiro:", exc)
            self.eng.reset()
        self.slip = (0.0, 0.0, 0.0, 0.0)
        self.slip_ang = (0.0, 0.0, 0.0, 0.0)
        self.posxz = (0.0, 0.0)
        self.all_tel = None
        self.all_status = None   # (composto visual, idade do pneu) de cada carro
        self.names = None        # nome de cada piloto (pacote Participants)
        self.num_active = 0
        self.all_lap = None
        self.tel = None
        self.status = None
        self.damage = None
        self.lap = None
        self.session = None
        self.motion = None
        self.setup = None
        self.t2 = None
        self.event = None
        self.player = 0
        self.hist = {}          # carro -> (melhor volta, melhor S1, S2, S3) em ms
        self.player_laps = []   # [(volta, s1, s2, s3)] do jogador
        self.trace_d, self.trace_t = [], []
        self.trace_lap = None
        self.trace_invalid = False
        self.ref_d = self.ref_t = None
        self.ref_time = 0

    def _warn(self, text):
        self.warn = text
        self.warn_t = time.monotonic()

    # ------------------------------------------------------------------ entrada
    def feed(self, data):
        if len(data) < HEADER_SIZE:
            return
        h = HEADER.unpack_from(data)
        fmt, pid, uid, player = h[0], h[5], h[6], h[10]
        with self.lock:
            lay = LAYOUTS.get(fmt)
            if lay is None:
                self.last_rx = time.monotonic()
                self._warn(tx("Formato UDP %d não suportado. No jogo, escolha o formato 2025 ou 2026.") % fmt)
                return
            self.last_rx = time.monotonic()
            self.fmt = fmt
            expected = lay["sizes"].get(pid)
            if expected is None:
                return
            if len(data) != expected:
                self._warn(tx("Pacote %s com tamanho inesperado (%d bytes, esperado %d).")
                           % (PACKET_NAMES.get(pid, pid), len(data), expected))
                return
            if uid != self.uid:
                self._reset_session()
                self.uid = uid
            if player >= lay["cars"]:
                return
            self.player = player
            handler = self._HANDLERS.get(pid)
            if handler:
                handler(self, data, lay, player)
        if pid == TELEMETRY:   # acorda quem transmite: um quadro novo do jogo chegou
            with self.tick:
                self.tick.notify_all()

    def _motion(self, data, lay, p):
        st = lay["motion"]
        v = st.unpack_from(data, HEADER_SIZE + p * st.size)
        d = lay["g_div"]
        self.motion = {"gLat": _r(v[12] / d), "gLong": _r(v[13] / d), "gVert": _r(v[14] / d)}
        self.posxz = (v[0], v[2])

    def _motion_ex(self, data, lay, p):
        self.slip = struct.unpack_from("<4f", data, OFF_SLIP)
        self.slip_ang = struct.unpack_from("<4f", data, OFF_SLIP + 16)   # m_wheelSlipAngle[4], em radianos

    def _telemetry(self, data, lay, p):
        st = lay["telemetry"]
        self.all_tel = [st.unpack_from(data, HEADER_SIZE + i * st.size)[:6] for i in range(lay["cars"])]
        v = st.unpack_from(data, HEADER_SIZE + p * st.size)
        suggested = struct.unpack_from("<b", data, HEADER_SIZE + lay["cars"] * st.size + 2)[0]
        self.tel = {
            "speed": v[0], "throttle": _r(v[1], 3), "steer": _r(v[2], 3), "brake": _r(v[3], 3),
            "clutch": v[4], "gear": v[5], "rpm": v[6], "drs": v[7], "revPct": v[8], "revBits": v[9],
            "brakeTemp": list(v[10:14]), "tyreSurf": list(v[14:18]), "tyreInner": list(v[18:22]),
            "engineTemp": v[22], "pressure": [_r(x, 1) for x in v[23:27]], "suggested": suggested,
        }

    def _participants(self, data, lay, p):
        st = lay["participant"]
        self.num_active = data[HEADER_SIZE]
        nomes = []
        for i in range(lay["cars"]):
            v = st.unpack_from(data, HEADER_SIZE + 1 + i * st.size)
            nome = next(x for x in v if isinstance(x, bytes))
            nomes.append(nome.split(b"\0", 1)[0].decode("utf-8", "ignore").strip())
        self.names = nomes

    def _status(self, data, lay, p):
        st = lay["status"]
        self.all_status = [st.unpack_from(data, HEADER_SIZE + i * st.size)[14:16] for i in range(lay["cars"])]
        v = st.unpack_from(data, HEADER_SIZE + p * st.size)
        if self.fmt >= 2026:
            limit, deployed = v[23], v[24]
        else:
            limit, deployed = None, v[23]
        self.status = {
            "tc": v[0], "abs": v[1], "fuelMix": v[2], "brakeBias": v[3], "pitLimiter": v[4],
            "fuel": _r(v[5]), "fuelCap": _r(v[6]), "fuelLaps": _r(v[7]), "maxRpm": v[8],
            "idleRpm": v[9], "drsAllowed": v[11], "drsDist": v[12], "compound": v[13],
            "visual": v[14], "tyreAge": v[15], "flag": v[16],
            "powerKw": _r((v[17] + v[18]) / 1000.0, 0), "ersStore": _r(v[19], 0), "ersMode": v[20],
            "ersHarv": _r(v[21] + v[22], 0), "ersDeployed": _r(deployed, 0),
            "ersLimit": None if limit is None else _r(limit, 0),
        }

    def _damage(self, data, lay, p):
        v = DAMAGE_CAR.unpack_from(data, HEADER_SIZE + p * DAMAGE_CAR.size)
        self.damage = {
            "wear": [_r(x, 1) for x in v[0:4]], "tyreDmg": list(v[4:8]), "brakeDmg": list(v[8:12]),
            "blisters": list(v[12:16]), "fwL": v[16], "fwR": v[17], "rearWing": v[18],
            "floor": v[19], "diffuser": v[20], "sidepod": v[21], "drsFault": v[22],
            "ersFault": v[23], "gearbox": v[24], "engine": v[25], "mguh": v[26], "es": v[27],
            "ce": v[28], "ice": v[29], "mguk": v[30], "tc": v[31], "blown": v[32], "seized": v[33],
        }

    def _setups(self, data, lay, p):
        v = SETUP_CAR.unpack_from(data, HEADER_SIZE + p * SETUP_CAR.size)
        self.setup = {"frontWing": v[0], "rearWing": v[1], "diffOn": v[2], "diffOff": v[3]}

    def _telemetry2(self, data, lay, p):
        v = TELEMETRY2_CAR.unpack_from(data, HEADER_SIZE + p * TELEMETRY2_CAR.size)
        self.t2 = {"aeroMode": v[0], "aeroAvail": v[1], "aeroDist": v[2], "otAvail": v[3],
                   "otActive": v[4], "otDist": v[5], "regs2026": v[6], "wrongWay": v[7]}

    def _session(self, data, lay, p):
        v = SESSION_HEAD.unpack_from(data, HEADER_SIZE)
        stype = v[5]
        rain = []
        n = min(data[OFF_NUM_FORECAST], 64)
        for i in range(n):
            f = struct.unpack_from("<BBBbbbbB", data, OFF_FORECAST + i * FORECAST_SIZE)
            if f[0] == stype:
                rain.append([f[1], f[7]])
            if len(rain) >= 4:
                break
        self.session = {
            "weather": WEATHER.get(v[0], "—"), "weatherId": v[0], "trackTemp": v[1], "airTemp": v[2],
            "totalLaps": v[3], "trackLength": v[4], "type": SESSION_TYPES.get(stype, N_("Sessão")),
            "isRace": stype in RACE_SESSIONS, "track": TRACKS.get(v[6], "Pista %d" % v[6]),
            "timeLeft": v[8], "pitLimit": v[10], "safetyCar": data[OFF_SAFETY_CAR], "rain": rain,
            "trackId": v[6], "formula": v[7], "typeId": stype,
            "pitIdeal": data[OFF_PIT_WINDOW], "pitLatest": data[OFF_PIT_WINDOW + 1],
            "pitRejoin": data[OFF_PIT_WINDOW + 2],
            "online": data[OFF_SAFETY_CAR + 1] == 1,   # m_networkGame vem logo depois do safety car
        }

    def _lap(self, data, lay, p):
        self.all_lap = [LAP.unpack_from(data, HEADER_SIZE + i * LAP.size) for i in range(lay["cars"])]
        v = self.all_lap[p]
        self.lap = v
        self._lap_delta(v)
        try:
            self.eng.on_lap()
        except Exception as exc:
            print("Engenheiro:", type(exc).__name__, exc)

    def _lap_delta(self, v):
        lap_num, dist, cur = v[14], v[10], v[1]
        if self.trace_lap != lap_num:
            # Volta fechada: vira referencia do delta se for valida e a mais rapida ate agora.
            if (self.trace_lap is not None and lap_num == self.trace_lap + 1 and v[0] > 0
                    and not self.trace_invalid and len(self.trace_d) > 30
                    and self.trace_d[0] < 300 and (self.ref_time == 0 or v[0] < self.ref_time)):
                self.ref_d, self.ref_t, self.ref_time = self.trace_d, self.trace_t, v[0]
            self.trace_d, self.trace_t = [], []
            self.trace_lap = lap_num
            self.trace_invalid = False
        if v[18]:
            self.trace_invalid = True
        if dist >= 0:
            while self.trace_d and self.trace_d[-1] >= dist:  # flashback ou carro parado
                self.trace_d.pop()
                self.trace_t.pop()
            self.trace_d.append(dist)
            self.trace_t.append(cur)

    def _history(self, data, lay, p):
        car, num_laps, _stints, best_lap, b1, b2, b3 = struct.unpack_from("<7B", data, HEADER_SIZE)
        num_laps = min(num_laps, 100)
        laps = []
        for i in range(num_laps):
            t, s1, m1, s2, m2, s3, m3, _flags = LAP_HISTORY.unpack_from(
                data, HEADER_SIZE + 7 + i * LAP_HISTORY.size)
            laps.append((t, m1 * 60000 + s1, m2 * 60000 + s2, m3 * 60000 + s3))

        def pick(lap_no, idx):
            return laps[lap_no - 1][idx] if 0 < lap_no <= len(laps) else 0

        self.hist[car] = (pick(best_lap, 0), pick(b1, 1), pick(b2, 2), pick(b3, 3))
        if car == p:
            self.player_laps = laps

    def _event(self, data, lay, p):
        code = data[29:33].decode("ascii", "replace")
        try:
            self.eng.on_event(code, data, p)
        except Exception as exc:
            print("Engenheiro:", type(exc).__name__, exc)
        text, n = None, 0
        if code == "FTLP":
            idx, t = struct.unpack_from("<Bf", data, 33)
            text = tx("Volta mais rápida: ") + fmt_time(int(t * 1000))
            if idx == p:
                text += tx(" — sua!")
        elif code == "STLG":
            n = data[33]
        elif code == "LGOT":
            text = tx("Luzes apagadas!")
        elif code == "CHQF":
            text = tx("Bandeira quadriculada")
        elif code == "RDFL":
            text = tx("Bandeira vermelha")
        elif code == "DRSE":
            text = tx("DRS liberado")
        elif code == "DRSD":
            text = tx("DRS desabilitado")
        elif code == "SCAR":
            kind, ev = data[33], data[34]
            if kind in SC_TYPE:
                text = "%s: %s" % (tx(SC_TYPE[kind]), tx(SC_EVENT.get(ev, "")))
        elif code == "PENA":
            if data[35] == p:
                secs = data[37]
                text = tx("Punição recebida") + (" (%d s)" % secs if 0 < secs < 255 else "")
        else:
            return
        if text is None and code != "STLG":
            return
        self.event_seq += 1
        self.event = {"seq": self.event_seq, "code": code, "text": text, "n": n}

    _HANDLERS = {MOTION: _motion, SESSION: _session, LAP_DATA: _lap, EVENT: _event, PARTICIPANTS: _participants,
                 SETUPS: _setups, TELEMETRY: _telemetry, STATUS: _status, DAMAGE: _damage,
                 HISTORY: _history, TELEMETRY2: _telemetry2, MOTION_EX: _motion_ex}

    # ------------------------------------------------------------------ saida
    def _delta(self):
        if not self.ref_d or self.lap is None or self.lap[25] == 0:
            return None
        dist, cur = self.lap[10], self.lap[1]
        if dist < self.ref_d[0]:
            return None
        i = bisect.bisect_right(self.ref_d, dist)
        if i >= len(self.ref_d):
            ref = self.ref_t[-1]
        else:
            d0, d1 = self.ref_d[i - 1], self.ref_d[i]
            t0, t1 = self.ref_t[i - 1], self.ref_t[i]
            ref = t0 + (t1 - t0) * ((dist - d0) / (d1 - d0) if d1 > d0 else 0)
        return int(cur - ref)

    def _lap_view(self):
        v = self.lap
        if v is None:
            return None
        mine = self.hist.get(self.player, (0, 0, 0, 0))
        overall = [min([h[i] for h in self.hist.values() if h[i] > 0] or [0]) for i in range(4)]
        lap_num, sector = v[14], v[17]
        cur = [v[3] * 60000 + v[2] if sector >= 1 else 0, v[5] * 60000 + v[4] if sector >= 2 else 0, 0]
        prev = (0, 0, 0, 0)
        if 2 <= lap_num <= len(self.player_laps) + 1:
            prev = self.player_laps[lap_num - 2]
        sectors = []
        for i in range(3):
            t, stale = cur[i], False
            if t <= 0:
                t, stale = prev[i + 1], True
            if t <= 0:
                sectors.append(None)
                continue
            color = "y"
            if overall[i + 1] and t <= overall[i + 1]:
                color = "p"
            elif mine[i + 1] and t <= mine[i + 1]:
                color = "g"
            sectors.append({"t": t, "c": color, "stale": stale})
        return {
            "cur": v[1], "last": v[0], "best": mine[0],
            "bestOverall": bool(mine[0] and mine[0] <= overall[0]),
            "delta": self._delta(), "pos": v[13], "num": lap_num, "sector": sector,
            "invalid": v[18], "sectors": sectors,
            "gapFront": v[7] * 60000 + v[6], "gapLeader": v[9] * 60000 + v[8],
            "penalties": v[19], "warnings": v[20], "ccWarnings": v[21], "dt": v[22], "sg": v[23],
            "pits": v[16], "pitStatus": v[15], "driverStatus": v[25],
            "pitLaneMs": v[28] if v[27] else 0, "pitStopMs": v[29],
        }

    def snapshot(self):
        now = time.monotonic()
        with self.lock:
            return {
                "connected": self.last_rx > 0 and now - self.last_rx < 2.0, "lang": idioma_atual(),
                "format": self.fmt, "demo": self.demo,
                "warn": self.warn if self.warn and now - self.warn_t < 6 else None,
                "tel": self.tel, "status": self.status, "damage": self.damage,
                "lap": self._lap_view(), "session": self._session_view(), "motion": self.motion,
                "setup": self.setup, "t2": self.t2, "event": self.event,
                "coach": self.eng.view() if self.eng else None,
            }

    def _session_view(self):
        """A sessao com os nomes no idioma do painel (por dentro ficam em portugues)."""
        s = self.session
        if s is None:
            return None
        return dict(s, track=tx(s["track"]), type=tx(s["type"]), weather=tx(s["weather"]))

    def mapa(self):
        with self.lock:
            return self.eng.mapa() if self.eng else {"ver": 0, "pts": [], "corners": []}

    def telemetria(self, n):
        with self.lock:
            return self.eng.telemetria(n) if self.eng else {"n": n, "ok": False}
