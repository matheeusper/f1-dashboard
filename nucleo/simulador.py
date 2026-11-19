"""Simulador de telemetria do F1 25: envia pacotes UDP no formato do jogo.

Simula uma corrida em Interlagos com voce em P4, um rival em P3 (um pouco mais
rapido em algumas curvas) e um carro em P5 se aproximando. A cada volta voce
comete erros diferentes (frear cedo, travar, acelerar tarde...) para o
engenheiro analisar. Ao fim da corrida comeca outra sessao, um pouco melhor.

    uv run nucleo/simulador.py                  # formato 2025
    uv run nucleo/simulador.py --formato 2026   # formato do Season Pack 2026
"""
import argparse
import math
import random
import socket
import struct
import time

from f1_packets import (DAMAGE, DAMAGE_CAR, EVENT, HEADER, HEADER_SIZE, HISTORY, LAP, LAP_DATA,
                        LAP_HISTORY, LAYOUTS, MOTION, MOTION_EX, OFF_FORECAST, OFF_NUM_FORECAST,
                        OFF_PIT_WINDOW, OFF_SAFETY_CAR, OFF_SLIP, PARTICIPANTS, SESSION, SESSION_HEAD,
                        SETUP_CAR, SETUPS, STATUS, TELEMETRY, TELEMETRY2, TELEMETRY2_CAR)

PLAYER, RIVAL, ATRAS, ABANDONA = 19, 3, 7, 11
# nomes ficticios do grid simulado
NOMES = ["Rocha", "Almeida", "Brandt", "Norris", "Okafor", "Lindqvist", "Moreau", "Leclerc", "Tanaka",
         "Ferraz", "Kowalski", "Hamilton", "Duarte", "Novak", "Silva", "Petrov", "Haas", "Ibarra",
         "Costa", "Max VERSTAPPEN", "Quinn", "Varga", "Sato", "Reyes"]
LAP_LEN = 5400.0
TOTAL_LAPS = 12
# (posicao em metros, velocidade minima em km/h, lado: -1 esquerda / 1 direita)
CORNERS = [(350, 110, -1), (900, 210, 1), (1400, 85, -1), (2100, 250, 1), (2600, 140, 1),
           (3300, 95, -1), (3900, 180, 1), (4500, 70, -1), (5100, 160, -1)]
GEAR_TOP = [0, 95, 135, 172, 208, 246, 284, 316, 350]  # km/h no limite de cada marcha
ERROS = {
    "cedo": {"a": 24.0},
    "tarde": {"a": 52.0, "vfac": 0.91},
    "lento": {"vfac": 0.92},
    "acel": {"exit": 90},
    "trava": {"lock": True, "vfac": 0.95},
    "patina": {"spin": True},
}


def split_ms(ms):
    ms = int(ms)
    return ms % 60000, ms // 60000


def track_xz(s):
    a = 2 * math.pi * s / LAP_LEN
    return (900 * math.cos(a) + 140 * math.cos(3 * a), 560 * math.sin(a) + 110 * math.sin(2 * a))


class Carro:
    def __init__(self, pos, params=None):
        self.pos, self.v = pos, 60.0
        self.lap, self.lap_ms, self.sector = 1, 0.0, 0
        self.s1 = self.s2 = 0
        self.last = 0
        self.laps = []
        self.params = params or {}
        self.started = False

    def step(self, dt):
        limit, in_corner, side = 400.0, False, 0
        parcial = trava = patina = False
        fase = None   # (indice da curva, "e"/"m"/"s") para simular a deriva dos pneus
        for k, (c_pos, c_kmh, c_side) in enumerate(CORNERS):
            p = self.params.get(k, {})
            vc = c_kmh / 3.6 * p.get("vfac", 1.0)
            ahead = (c_pos - self.pos) % LAP_LEN
            behind = (self.pos - c_pos) % LAP_LEN
            if behind < 70:
                fase = (k, "m", 0)
            elif behind < 250 and (fase is None or fase[1] == "e"):
                fase = (k, "s", behind)
            elif ahead < 150 and fase is None:
                fase = (k, "e", ahead)
            if behind < 70:
                cand, in_corner, side = vc, True, c_side
            else:
                cand = math.sqrt(vc * vc + 2 * p.get("a", 36.0) * ahead)
            if 70 <= behind < 70 + p.get("exit", 0):
                parcial = True
            if p.get("lock") and ahead < 260:
                trava = True
            if p.get("spin") and 30 < behind < 260:
                patina = True
            limit = min(limit, cand)
        v = self.v
        if v > limit:
            brake = min(1.0, 0.25 + (v - limit) / 4.0)
            throttle = 0.0
            accel = -44.0 * brake * (0.85 if trava and brake > 0.5 else 1.0)
        else:
            throttle = max(0.15, min(1.0, (limit - v) / 3.0))
            if parcial:
                throttle = min(throttle, 0.45)
            brake = 0.0
            accel = throttle * 14.0 * (1 - (v / 97.0) ** 2) * (0.8 if patina and throttle > 0.5 else 1.0)
        self.v = max(8.0, v + accel * dt)
        step = self.v * dt
        self.pos += step
        self.lap_ms += dt * 1000.0
        kmh = self.v * 3.6
        gear = next(g for g in range(1, 9) if kmh <= GEAR_TOP[g] or g == 8)
        slip = [0.0, 0.0, 0.0, 0.0]
        if trava and brake > 0.5:
            slip[2] = -0.55
        if patina and throttle > 0.5:
            slip[0] = slip[1] = 0.35
        fechou = False
        frac = self.pos / LAP_LEN
        if self.sector == 0 and frac >= 1 / 3 and self.pos < LAP_LEN:
            self.s1, self.sector = int(self.lap_ms), 1
        elif self.sector == 1 and frac >= 2 / 3:
            self.s2, self.sector = int(self.lap_ms) - self.s1, 2
        if self.pos >= LAP_LEN:
            self.pos -= LAP_LEN
            if self.started:
                self.last = int(self.lap_ms)
                self.laps.append((self.last, self.s1, self.s2, self.last - self.s1 - self.s2))
                self.lap += 1
                fechou = True
            self.started = True
            self.lap_ms, self.sector, self.s1, self.s2 = 0.0, 0, 0, 0
        # deriva dos pneus (rad): equilibrado, mas com subesterço no meio da curva 2
        # e sobresterço + patinada na saída da curva 8
        ang = [0.0, 0.0, 0.0, 0.0]
        if fase:
            k, f, _dist = fase
            dianteira, traseira = 0.045, 0.045
            if k == 1 and f == "m":
                dianteira, traseira = 0.075, 0.04
            elif k == 7 and f == "s" and throttle > 0.3:
                dianteira, traseira = 0.03, 0.08
                slip[0] = slip[1] = max(slip[0], 0.22)
            ang = [traseira, traseira, dianteira, dianteira]
        steer_v = side * (0.55 if in_corner else 0.0)
        # esterco de entrada (ultimos 40 m antes da curva) e de saida (desvirando)
        if fase and not in_corner and (fase[1] == "e" and fase[2] < 40 or fase[1] == "s" and fase[2] < 180):
            steer_v = CORNERS[fase[0]][2] * 0.2
        return {"kmh": kmh, "throttle": throttle, "brake": brake, "gear": gear, "accel": accel,
                "steer": steer_v, "in_corner": in_corner, "side": side,
                "slip": slip, "ang": ang, "fechou": fechou, "step": step}

    def total(self):
        return (self.lap - 1) * LAP_LEN + self.pos


def simular(host="127.0.0.1", port=20777, fmt=2025, hz=60, stop=None, seed=None, sessoes=None, tipo=15):
    """tipo: tipo de sessao do jogo (15 = corrida, 18 = Time Trial)."""
    corrida = tipo in (15, 16, 17)
    lay = LAYOUTS[fmt]
    cars = lay["cars"]
    rng = random.Random(seed)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dt = 1.0 / hz
    sessao = 0

    while not (stop and stop.is_set()) and (sessoes is None or sessao < sessoes):
        sessao += 1
        habilidade = min(1.04, 1.0 + 0.01 * (sessao - 1))   # voce melhora um pouco a cada sessao
        uid = rng.getrandbits(62) | 1
        frame = 0
        t = 0.0
        eu = Carro(LAP_LEN - 150.0)
        rival = Carro(LAP_LEN - 150.0 + 160.0,
                      {k: {"a": 40.0, "vfac": 1.08 if k in (2, 5) else 1.0} for k in range(len(CORNERS))})
        rival.started = False
        fuel, ers, harv, dep = 20.5, 3.2e6, 0.0, 0.0
        wear = [2.0, 2.0, 3.0, 2.5]
        surf, inner = [88.0, 88.0, 90.0, 90.0], [92.0, 92.0, 95.0, 95.0]
        brk = [420.0, 420.0, 480.0, 480.0]
        warnings = 0
        best = 0

        def novos_erros(volta):
            eu.params = {k: {"vfac": habilidade} for k in range(len(CORNERS))}
            if volta <= 1 or rng.random() < 0.2:
                return
            for k in rng.sample(range(len(CORNERS)), rng.choice((1, 2, 2))):
                eu.params[k] = dict(eu.params[k], **ERROS[rng.choice(list(ERROS))])
            if rng.random() < 0.6:   # vicio fixo: frear cedo na curva 3 (indice 2)
                eu.params[2] = dict(eu.params[2], **ERROS["cedo"])

        novos_erros(1)

        def header(pid):
            return HEADER.pack(fmt, 25, 1, 5, 1, pid, uid, t, frame, frame, PLAYER, 255)

        def per_car(pid, st, values, tail=b"", extra=None):
            zero = bytes(st.size)
            parts = [header(pid)]
            for i in range(cars):
                if i == PLAYER:
                    parts.append(st.pack(*values))
                elif extra and i in extra:
                    parts.append(st.pack(*extra[i]))
                else:
                    parts.append(zero)
            parts.append(tail)
            return b"".join(parts)

        def send(data):
            sock.sendto(data, (host, port))

        def event(code, detail=b""):
            buf = bytearray(lay["sizes"][EVENT])
            buf[:HEADER_SIZE] = header(EVENT)
            buf[29:33] = code
            buf[33:33 + len(detail)] = detail
            send(bytes(buf))

        def history(car, lap_list, partial=None):
            buf = bytearray(lay["sizes"][HISTORY])
            buf[:HEADER_SIZE] = header(HISTORY)
            rows = list(lap_list) + ([partial] if partial else [])

            def best_of(idx):
                done = [(r[idx], i + 1) for i, r in enumerate(lap_list) if r[idx] > 0]
                if idx != 0 and partial and partial[idx] > 0:
                    done.append((partial[idx], len(rows)))
                return min(done)[1] if done else 0

            struct.pack_into("<7B", buf, HEADER_SIZE, car, min(len(rows), 100), 1,
                             best_of(0), best_of(1), best_of(2), best_of(3))
            for i, r in enumerate(rows[:100]):
                a, b, c = split_ms(r[1]), split_ms(r[2]), split_ms(r[3])
                LAP_HISTORY.pack_into(buf, HEADER_SIZE + 7 + i * LAP_HISTORY.size,
                                      r[0], a[0], a[1], b[0], b[1], c[0], c[1], 0x0F)
            send(bytes(buf))

        def lap_vals(c, pos_race, gap_f, gap_l, avisos=0, invalida=0, pit=0, pits=0, lane=0, parada=0, extra_ms=0):
            a, b = split_ms(c.s1), split_ms(c.s2)
            g, ldr = split_ms(gap_f), split_ms(gap_l)
            return (c.last + extra_ms if c.last else 0, int(c.lap_ms), a[0], a[1], b[0], b[1], g[0], g[1], ldr[0], ldr[1],
                    c.pos, c.total(), 0.0,
                    pos_race, c.lap, pit, pits, c.sector, invalida, 0, avisos, avisos, 0, 0, pos_race + 2, 4, 2,
                    1 if pit else 0, min(lane, 65535), parada, 0, 318.5, 1)

        def participantes():
            st = lay["participant"]
            buf = bytearray(lay["sizes"][PARTICIPANTS])
            buf[:HEADER_SIZE] = header(PARTICIPANTS)
            buf[HEADER_SIZE] = 22
            for i in range(cars):
                nome = NOMES[i % len(NOMES)].encode("utf-8")
                st.pack_into(buf, HEADER_SIZE + 1 + i * st.size, 1, i, 0, i % 11, 0, i + 1, 0, nome,
                             1, 1, 0, 255, 0, *([0] * 12))
            send(bytes(buf))

        next_tick = time.perf_counter()
        invalida = 0
        trocou = False
        while not (stop and stop.is_set()):
            o = eu.step(dt)
            r = rival.step(dt)
            kmh, throttle, brake, gear = o["kmh"], o["throttle"], o["brake"], o["gear"]
            rpm = int(max(4200, min(12900, 12600 * kmh / GEAR_TOP[gear])))
            rev_pct = int(max(0, min(100, (rpm - 10400) / 2100 * 100)))
            rev_bits = (1 << round(rev_pct * 15 / 100)) - 1
            steer = o["steer"] + 0.02 * math.sin(t * 3)
            g_lat = o["side"] * min(5.2, (eu.v ** 2) / 900.0) if o["in_corner"] else 0.1 * math.sin(t * 2)
            g_long = o["accel"] / 9.81
            on_straight = eu.pos > 5250 or eu.pos < 250 or 1600 < eu.pos < 2050
            drs_allowed = 1 if on_straight and eu.lap > 1 else 0
            drs = 1 if drs_allowed and throttle > 0.9 else 0

            for i in range(4):
                front = 1.15 if i >= 2 else 1.0
                target = 86 + 5 * abs(g_lat) * front + 10 * brake * front + (i % 2) * 2
                surf[i] += (target - surf[i]) * 0.03
                inner[i] += (surf[i] + 4 - inner[i]) * 0.004
                b_target = 380 + 620 * brake * front
                brk[i] += (b_target - brk[i]) * (0.06 if b_target > brk[i] else 0.012)
                wear[i] += o["step"] / LAP_LEN * (3.4 + 0.6 * (i == 2))
            if throttle > 0.95 and kmh > 150 and ers > 1e5:
                ers -= 120e3 * dt
                dep += 120e3 * dt
            gain = (260e3 * brake + 18e3) * dt
            ers = min(4e6, ers + gain)
            harv += gain
            fuel = max(0.0, fuel - 1.75 * o["step"] / LAP_LEN)

            if o["fechou"]:
                ult = eu.last
                if best == 0 or ult < best:
                    best = ult
                    event(b"FTLP", struct.pack("<Bf", PLAYER, ult / 1000.0))
                harv, dep, invalida = 0.0, 0.0, 0
                if eu.lap == 6:          # um aviso de limite de pista no meio da corrida
                    warnings += 1
                    invalida = 1
                if eu.lap > TOTAL_LAPS:
                    event(b"CHQF")
                    event(b"SEND")
                    break
                novos_erros(eu.lap)
                # roteiro de eventos de corrida, para testar o engenheiro
                if eu.lap == 2:
                    event(b"DRSE")
                elif eu.lap == 3:
                    event(b"FTLP", struct.pack("<Bf", RIVAL, 89.7))
                elif eu.lap == 4:
                    event(b"RTMT", bytes([ABANDONA, 8]))
                elif eu.lap == 7:
                    event(b"COLL", bytes([PLAYER, ATRAS, 1]))
                elif eu.lap == 9:
                    event(b"OVTK", bytes([ATRAS, PLAYER]))
                    trocou = True
                elif eu.lap == 10:
                    event(b"SCAR", bytes([1, 1]))
                elif eu.lap == 11:
                    event(b"OVTK", bytes([PLAYER, ATRAS]))
                    trocou = False

            # ------------------------------------------------------ pacotes
            gd = lay["g_div"]
            g_vals = (g_lat, g_long, 1.0) if gd == 1.0 else (int(g_lat * gd), int(g_long * gd), int(gd))
            px, pz = track_xz(eu.pos)
            send(per_car(MOTION, lay["motion"],
                         (px, 0.0, pz, 0.0, 0.0, 0.0, 0, 0, 0, 0, 0, 0) + g_vals + (0.0, 0.0, 0.0)))
            ex = bytearray(lay["sizes"][MOTION_EX])
            ex[:HEADER_SIZE] = header(MOTION_EX)
            struct.pack_into("<4f", ex, OFF_SLIP, *o["slip"])
            struct.pack_into("<4f", ex, OFF_SLIP + 16, *o["ang"])
            send(bytes(ex))

            def tel_vals(c_o, sp):
                return (int(c_o["kmh"]), c_o["throttle"], c_o["steer"], c_o["brake"], 0, c_o["gear"],
                        int(max(4200, min(12900, 12600 * c_o["kmh"] / GEAR_TOP[c_o["gear"]]))),
                        0, 0, 0, 400, 400, 450, 450, 90, 90, 92, 92, 95, 95, 97, 97, 105,
                        22.6, 22.7, 24.3, 24.5, 0, 0, 0, 0) if sp else None
            tel = (int(kmh), throttle, steer, brake, 0, gear, rpm, drs, rev_pct, rev_bits,
                   *[int(x) for x in brk], *[int(x) for x in surf], *[int(x) for x in inner],
                   104 + int(4 * math.sin(t / 7)), 22.6, 22.7, 24.3, 24.5, 0, 0, 0, 0)
            send(per_car(TELEMETRY, lay["telemetry"], tel, struct.pack("<BBb", 255, 255, 0),
                         extra={RIVAL: tel_vals(r, True)}))

            gap_f = max(50, int((rival.total() - eu.total()) / max(eu.v, 10) * 1000))
            gap_l = gap_f + 6500
            gap_atras = max(400, 2600 - 230 * (eu.lap - 1) - int(230 * eu.pos / LAP_LEN))
            atras_pos = max(0.0, eu.pos - gap_atras / 1000 * eu.v)
            minha_pos, pos_atras = (5, 4) if trocou else (4, 5)
            atras = (0, 0, 0, 0, 0, 0, *split_ms(gap_atras), *split_ms(gap_l + gap_f + gap_atras),
                     atras_pos, atras_pos + (eu.lap - 1) * LAP_LEN, 0.0,
                     pos_atras, eu.lap, 0, 0, 0, 0, 0, 0, 0, 0, 0, 7, 4, 2, 0, 0, 0, 0, 300.0, 1)
            # seu pit stop: comeco da volta 8 (com o limitador desligado no primeiro meio segundo)
            no_pit = eu.lap == 8 and eu.lap_ms < 15000
            meus_pits = 1 if eu.lap > 8 or (eu.lap == 8 and not no_pit) else 0
            rival_pit = rival.lap == 5 and rival.lap_ms < 12000
            pits_rival = 1 if rival.lap > 5 or (rival.lap == 5 and not rival_pit) else 0
            # o resto do grid (so para a torre de tempos ter os 20+ carros): ritmo fixo, metade para na volta 5-8
            resto = [i for i in range(cars) if i not in (PLAYER, RIVAL, ATRAS, ABANDONA)] if corrida else []
            grid_lap, grid_st = {}, {}
            acum, base = 0, gap_l + gap_atras
            for k, (i, pos_g) in enumerate(zip(resto, [1, 2] + list(range(6, cars + 1)))):
                if pos_g == 1:
                    lider_gap, intv = 0, 0
                elif pos_g == 2:
                    lider_gap, intv = 3500, 3500
                else:
                    intv = 1100 + (k * 577) % 1300
                    acum += intv
                    lider_gap = base + acum
                d_g = eu.total() + (gap_l - lider_gap) / 1000 * max(eu.v, 10)
                volta_g = max(1, int(d_g // LAP_LEN) + 1)
                parada = 5 + pos_g % 4 if pos_g % 2 else 99
                pits_g = 1 if volta_g > parada else 0
                no_pit_g = 1 if volta_g == parada + 1 and d_g % LAP_LEN < 400 else 0
                gl, gi = split_ms(lider_gap), split_ms(intv)
                grid_lap[i] = (89800 + (pos_g * 137) % 1500 if volta_g > 1 else 0, 30000, 0, 0, 0, 0, gi[0], gi[1],
                               gl[0], gl[1], d_g % LAP_LEN, d_g, 0.0, pos_g, volta_g, no_pit_g, pits_g, 0, 0, 0, 0, 0,
                               0, 0, pos_g, 4, 2, no_pit_g, 0, 0, 0, 300.0, 1)
                visual = 18 if pits_g else (16 if pos_g % 3 == 0 else 17)
                grid_st[i] = (visual, volta_g - parada if pits_g else volta_g + 2)
            send(per_car(LAP_DATA, LAP, lap_vals(eu, minha_pos, gap_f, gap_l, warnings, invalida,
                                                 pit=1 if no_pit else 0, pits=meus_pits,
                                                 lane=int(eu.lap_ms) if no_pit else 0,
                                                 parada=2400 if no_pit and eu.lap_ms > 6000 else 0),
                         struct.pack("<BB", 255, 255),
                         extra={RIVAL: lap_vals(rival, 3, 1500, 5000, pit=1 if rival_pit else 0, pits=pits_rival,
                                                extra_ms=21000 if rival.lap == 6 else 0),   # volta do pit: +21 s
                                ATRAS: atras, ABANDONA: atras[:13] + (0,) + atras[14:], **grid_lap}))
            if frame % 300 == 0:
                participantes()

            if frame % 6 == 0:
                laps_left = TOTAL_LAPS - eu.lap + 1 - eu.pos / LAP_LEN
                limitador = 1 if no_pit and eu.lap_ms > 600 else 0
                composto, idade = (18, eu.lap - 8) if meus_pits else (17, eu.lap + 2)
                head = [0, 0, 1, 56, limitador, fuel, 110.0, fuel / 1.6 - laps_left, 13000, 4000, 8,
                        drs_allowed, 0 if drs_allowed else 180, composto + 1, composto, idade, 0,
                        560e3 * throttle, 120e3 if throttle > 0.95 else 0.0, ers,
                        3 if throttle > 0.95 and kmh > 250 else 1, harv * 0.85, harv * 0.15]
                tail = [8.5e6, dep, 0] if fmt >= 2026 else [dep, 0]
                h_rival = list(head)
                h_rival[4], h_rival[13], h_rival[14], h_rival[15] = 0, 19 if pits_rival else 18, \
                    18 if pits_rival else 17, rival.lap - 5 if pits_rival else rival.lap + 2
                extra_st = {RIVAL: h_rival + tail}
                for i, (visual, idade_g) in grid_st.items():
                    h_g = list(head)
                    h_g[4], h_g[13], h_g[14], h_g[15] = 0, visual + 1, visual, idade_g
                    extra_st[i] = h_g + tail
                send(per_car(STATUS, lay["status"], head + tail, extra=extra_st))
                fw = 14 if eu.lap >= 2 else 0
                furo = 65 if eu.lap >= 10 else 0     # furo no dianteiro esquerdo na volta 10
                dmg = (wear[0], wear[1], wear[2], wear[3], 0, 0, furo, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                       fw, 0, 0, 6 if eu.lap >= 3 else 0, 0, 0, 0, 0, 3, 5, 22, 18, 12, 31, 26, 15, 0, 0)
                send(per_car(DAMAGE, DAMAGE_CAR, dmg))
                if fmt >= 2026:
                    send(per_car(TELEMETRY2, TELEMETRY2_CAR,
                                 (1 if on_straight else 0, 1 if on_straight else 0, 0, 1,
                                  1 if throttle > 0.95 and kmh > 250 else 0, 0, 1, 0)))

            if frame % 30 == 0:
                buf = bytearray(lay["sizes"][SESSION])
                buf[:HEADER_SIZE] = header(SESSION)
                SESSION_HEAD.pack_into(buf, HEADER_SIZE, 1, 34, 26, TOTAL_LAPS, int(LAP_LEN), tipo, 16, 0,
                                       3600, 7200, 80, 0, 0, 255, 0, 0)
                buf[OFF_SAFETY_CAR] = 3 if frame < 240 and corrida else 0     # volta de formacao no comeco
                buf[OFF_NUM_FORECAST] = 3
                for i, (off, rain) in enumerate(((0, 5), (5, 20), (10, 65))):
                    struct.pack_into("<BBBbbbbB", buf, OFF_FORECAST + i * 8, 15, off, 1, 34, 2, 26, 2, rain)
                buf[OFF_PIT_WINDOW], buf[OFF_PIT_WINDOW + 1] = 6, 8
                send(bytes(buf))

            if frame % 60 == 0:
                history(PLAYER, eu.laps, (0, eu.s1, eu.s2, 0))
                if rival.laps:
                    history(RIVAL, rival.laps)
            if frame % 120 == 0:
                # no Time Trial a asa dianteira sobe um ponto depois da volta 3 (exercita o "antes e depois")
                send(per_car(SETUPS, SETUP_CAR,
                             (29 if not corrida and eu.lap > 3 else 28, 22, 60, 55, -3.5, -2.0, 0.05, 0.2, 41, 3, 15, 8, 22, 55, 100, 56, 80,
                              22.5, 22.5, 24.0, 24.0, 0, 20.5), struct.pack("<f", 28.0)))

            frame += 1
            t += dt
            next_tick += dt
            delay = next_tick - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                next_tick = time.perf_counter()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Simulador de telemetria do F1 25")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--porta", type=int, default=20777)
    ap.add_argument("--formato", type=int, default=2025, choices=(2025, 2026))
    ap.add_argument("--time-trial", action="store_true", help="simula um Time Trial em vez de corrida")
    a = ap.parse_args()
    print("Enviando telemetria simulada (formato %d) para %s:%d. Ctrl+C para parar."
          % (a.formato, a.host, a.porta))
    try:
        simular(a.host, a.porta, a.formato, tipo=18 if a.time_trial else 15)
    except KeyboardInterrupt:
        pass
