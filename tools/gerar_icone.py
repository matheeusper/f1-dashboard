"""Gera o icone do programa (conta-giros nas cores do painel) sem bibliotecas externas.

Saidas:
  icone.ico        icone do PainelF1.exe e da janela do menu (16 a 256 px)
  web/icone.png    favicon do painel e da pagina Evolucao (256 px)

Uso:  uv run tools/gerar_icone.py
"""
import math
import os
import struct
import zlib

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CIANO = (45, 226, 230)
LILAS = (125, 139, 255)
MAGENTA = (255, 61, 154)
VERMELHO = (255, 77, 90)
BRANCO = (234, 240, 248)
FUNDO_CIMA = (22, 30, 44)
FUNDO_BAIXO = (5, 7, 11)
BORDA = (40, 52, 72)


def mistura(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def cor_arco(t):
    """Gradiente do arco de RPM: ciano -> lilas -> magenta, com a faixa vermelha no fim."""
    if t > 0.86:
        return VERMELHO
    if t < 0.55:
        return mistura(CIANO, LILAS, t / 0.55)
    return mistura(LILAS, MAGENTA, (t - 0.55) / 0.31)


def amostra(x, y):
    """Cor (r, g, b, a) num ponto do icone em coordenadas 0..256."""
    # fundo: quadrado arredondado com borda
    m, r = 8.0, 54.0
    cx = min(max(x, m + r), 256 - m - r)
    cy = min(max(y, m + r), 256 - m - r)
    d = math.hypot(x - cx, y - cy)
    if d > r:
        return None
    cor = BORDA if d > r - 5 else mistura(FUNDO_CIMA, FUNDO_BAIXO, (y - m) / (256 - 2 * m))
    # conta-giros
    ox, oy = 128.0, 140.0
    dx, dy = x - ox, y - oy
    dist = math.hypot(dx, dy)
    ang = math.degrees(math.atan2(dy, dx)) % 360          # 0 = direita, 90 = baixo
    if ang < 135:
        ang += 360
    t = (ang - 135) / 270.0                               # 0..1 do inicio ao fim do arco
    if 68 <= dist <= 94 and 0 <= t <= 1:
        cor = cor_arco(t)
    elif 60 <= dist < 66 and 0 <= t <= 1 and int(t * 270) % 27 < 4:
        cor = (70, 84, 106)                               # marcacoes
    # ponteiro (em ~62% do giro) e centro
    a = math.radians(135 + 270 * 0.62)
    px, py = math.cos(a), math.sin(a)
    proj = dx * px + dy * py
    perp = abs(-dx * py + dy * px)
    if -6 <= proj <= 80 and perp <= 5.5 * (1 - max(0.0, proj) / 160):
        cor = BRANCO
    if dist <= 15:
        cor = BRANCO if dist > 6 else FUNDO_BAIXO
    return cor + (255,)


def render(tam, sub=4):
    esc = 256.0 / tam
    linhas = []
    for j in range(tam):
        linha = bytearray()
        for i in range(tam):
            acc = [0.0, 0.0, 0.0, 0.0]
            for sj in range(sub):
                for si in range(sub):
                    c = amostra((i + (si + 0.5) / sub) * esc, (j + (sj + 0.5) / sub) * esc)
                    if c:
                        acc[0] += c[0] * c[3]
                        acc[1] += c[1] * c[3]
                        acc[2] += c[2] * c[3]
                        acc[3] += c[3]
            alfa = acc[3] / (sub * sub)
            if acc[3]:
                linha += bytes((int(acc[0] / acc[3]), int(acc[1] / acc[3]), int(acc[2] / acc[3]), int(alfa)))
            else:
                linha += b"\0\0\0\0"
        linhas.append(bytes(linha))
    return linhas


def png(tam, linhas):
    def chunk(tipo, dados):
        return (struct.pack(">I", len(dados)) + tipo + dados +
                struct.pack(">I", zlib.crc32(tipo + dados) & 0xFFFFFFFF))
    bruto = b"".join(b"\0" + l for l in linhas)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", tam, tam, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(bruto, 9)) + chunk(b"IEND", b""))


def main():
    tamanhos = [256, 128, 64, 48, 32, 24, 16]
    imagens = {t: png(t, render(t, 4 if t >= 64 else 8)) for t in tamanhos}
    cab = struct.pack("<HHH", 0, 1, len(tamanhos))
    pos = 6 + 16 * len(tamanhos)
    entradas, dados = b"", b""
    for t in tamanhos:
        img = imagens[t]
        entradas += struct.pack("<BBBBHHII", t % 256, t % 256, 0, 0, 1, 32, len(img), pos + len(dados))
        dados += img
    with open(os.path.join(RAIZ, "icone.ico"), "wb") as f:
        f.write(cab + entradas + dados)
    with open(os.path.join(RAIZ, "web", "icone.png"), "wb") as f:
        f.write(imagens[256])
    print("icone.ico e web/icone.png gerados")


if __name__ == "__main__":
    main()
