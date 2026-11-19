"""Entende o que o piloto perguntou pela voz (portugues ou ingles).

O painel transcreve a fala (reconhecimento de voz do navegador) e manda o texto;
aqui ele vira uma das perguntas do engenheiro (as mesmas dos botoes do volante)
ou "como estou na curva N". Funciona por palavras-chave, sem acento e em minusculas.
"""
import re
import unicodedata

# pergunta (numero do botao) -> [(palavra ou expressao, peso)]
# peso 1: palavra que define o assunto; 0.5: ajuda, mas sozinha e generica demais
PALAVRAS = {
    1: [("pneu", 1), ("pneus", 1), ("desgaste", 1), ("borracha", 1), ("tyre", 1), ("tyres", 1), ("tire", 1),
        ("tires", 1), ("wear", 1), ("rubber", 1)],
    2: [("gap", 1), ("gaps", 1), ("distancia", 1), ("diferenca", 1), ("intervalo", 1), ("posicao", 1),
        ("na frente", 1), ("atras", 1), ("lider", 1), ("quem esta", 0.5), ("ahead", 1), ("behind", 1),
        ("position", 1), ("interval", 1), ("leader", 1), ("in front", 1)],
    3: [("combustivel", 1), ("gasolina", 1), ("bateria", 1), ("ers", 1), ("energia", 1), ("mistura", 1),
        ("fuel", 1), ("battery", 1), ("energy", 1), ("mix", 1)],
    4: [("perdendo", 1), ("perdi", 1), ("perder", 1), ("onde estou", 1), ("melhorar", 1), ("ganhar tempo", 1),
        ("losing", 1), ("lose", 1), ("lost", 1), ("where am i", 1), ("improve", 1), ("ultima volta", 0.5),
        ("last lap", 0.5)],
    5: [("clima", 1), ("chuva", 1), ("chover", 1), ("previsao", 1), ("tempo la fora", 1), ("temperatura da pista", 1),
        ("weather", 1), ("rain", 1), ("forecast", 1), ("track temp", 1)],
    6: [("repete", 1), ("repetir", 1), ("repita", 1), ("de novo", 0.5), ("nao entendi", 1), ("o que", 0.5),
        ("repeat", 1), ("say again", 1), ("again", 0.5), ("what", 0.3)],
    7: [("silencio", 1), ("quieto", 1), ("cala", 1), ("fala tudo", 1), ("volta a falar", 1), ("radio normal", 1),
        ("quiet", 1), ("silence", 1), ("shut", 1), ("talk again", 1), ("normal radio", 1)],
    8: [("estrategia", 1), ("box", 1), ("parar", 1), ("parada", 1), ("pit", 1), ("undercut", 1), ("overcut", 1),
        ("strategy", 1), ("stop", 0.5), ("pit stop", 1)],
    9: [("meta", 1), ("metas", 1), ("treino", 1), ("objetivo", 1), ("goal", 1), ("goals", 1), ("practice", 1),
        ("target", 1)],
    10: [("acerto", 1), ("equilibrio", 1), ("subesterco", 1), ("sobresterco", 1), ("saindo de frente", 1),
         ("saindo de traseira", 1), ("asa", 0.5), ("setup", 1), ("balance", 1), ("understeer", 1),
         ("oversteer", 1), ("wing", 0.5)],
}

NUMEROS = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8,
    "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14, "quinze": 15,
    "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19, "vinte": 20,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20,
}
CURVA = re.compile(r"\b(?:curva|turn|corner|curve)\s+(?:numero\s+|number\s+)?(\d{1,2}|[a-z]+)\b")


def normaliza(texto):
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return " " + re.sub(r"[^a-z0-9]+", " ", t).strip() + " "


def intencao(texto):
    """('curva', n), ('pergunta', n do botao) ou (None, None) se nao entendeu."""
    t = normaliza(texto or "")
    m = CURVA.search(t)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else NUMEROS.get(m.group(1))
        if n:
            return "curva", n
    pontos = {}
    for n, palavras in PALAVRAS.items():
        p = sum(peso for palavra, peso in palavras if " %s " % palavra in t)
        if p:
            pontos[n] = p
    if not pontos:
        return None, None
    melhor = max(pontos, key=lambda n: (pontos[n], -n))
    return ("pergunta", melhor) if pontos[melhor] >= 0.5 else (None, None)
