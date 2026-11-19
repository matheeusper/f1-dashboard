"""Confere se todo texto marcado para traducao tem versao em ingles.

Procura tx("...") e N_("...") nos .py do projeto, T("...") nos .js da pagina e
os trechos de texto dos .html, e compara com textos_en.py (Python) e web/i18n.js (pagina).

    uv run tools/checar_traducao.py            # lista o que falta e o que sobra
    uv run tools/checar_traducao.py --esqueleto  # imprime as chaves que faltam, prontas para colar
"""
import ast
import html
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NUCLEO = os.path.join(RAIZ, "nucleo")
sys.path.insert(0, NUCLEO)
# trechos da pagina que sao iguais nos dois idiomas (siglas e unidades): nao precisam de traducao
SO_SIMBOLO = {"RPM", "km/h", "DRS", "OVERTAKE", "PIT", "ERS", "POS", "G LAT", "G LONG", "MJ", "kg", "kW", "psi",
              "0.00 MJ", "0 kW", "Ex.: Max"}


def textos_py():
    achados = {}
    for nome in sorted(os.listdir(NUCLEO)):
        if not nome.endswith(".py") or nome == "textos_en.py":
            continue
        arvore = ast.parse(open(os.path.join(NUCLEO, nome), encoding="utf-8").read())
        for no in ast.walk(arvore):
            if (isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id in ("tx", "N_")
                    and no.args and isinstance(no.args[0], ast.Constant) and isinstance(no.args[0].value, str)):
                achados.setdefault(no.args[0].value, "%s:%d" % (nome, no.lineno))
    return achados


def _literal_js(s):
    """Conteudo de uma string JS simples ('...' ou "...") -> str."""
    corpo = s[1:-1]
    if s[0] == "'":
        corpo = corpo.replace("\\'", "'").replace('"', '\\"')
    return json.loads('"' + corpo + '"')


def textos_web():
    achados = {}
    web = os.path.join(RAIZ, "web")
    for nome in sorted(os.listdir(web)):
        if nome == "i18n.js" or not nome.endswith((".js", ".html")):
            continue
        texto = open(os.path.join(web, nome), encoding="utf-8").read()
        if nome.endswith(".js"):
            for m in re.finditer(r"""\bT\((['"])((?:\\.|(?!\1).)*)\1""", texto):
                achados.setdefault(_literal_js(m.group(1) + m.group(2) + m.group(1)), nome)
        else:
            # o i18n.js traduz todo trecho de texto da pagina e os atributos title/placeholder/aria-label
            texto = re.sub(r"<(script|style)\b.*?</\1>", "", texto, flags=re.S)
            for m in re.finditer(r">([^<>]+)<", texto):
                t = html.unescape(m.group(1)).strip()
                if re.search(r"[A-Za-zÀ-ú]{2}", t) and t not in SO_SIMBOLO:
                    achados.setdefault(t, nome)
            for m in re.finditer(r'\s(?:title|placeholder|aria-label)="([^"]*)"', texto):
                achados.setdefault(html.unescape(m.group(1)), nome)
    return achados


def catalogo_web():
    texto = open(os.path.join(RAIZ, "web", "i18n.js"), encoding="utf-8").read()
    ini = texto.index("/*EN*/") + len("/*EN*/")
    fim = texto.index("/*FIM*/")
    return json.loads(texto[ini:fim])


def main():
    from textos_en import EN
    esqueleto = "--esqueleto" in sys.argv
    falta = 0
    for titulo, achados, cat in (("Python", textos_py(), EN), ("Pagina", textos_web(), catalogo_web())):
        faltando = {k: v for k, v in achados.items() if k not in cat}
        sobrando = [k for k in cat if k not in achados]
        falta += len(faltando)
        print("== %s: %d textos, %d sem traducao, %d sobrando no catalogo" % (titulo, len(achados), len(faltando),
                                                                              len(sobrando)))
        for k, onde in faltando.items():
            if esqueleto:
                print('    %s: "",  # %s' % (json.dumps(k, ensure_ascii=False), onde))
            else:
                print("  falta  %r  (%s)" % (k, onde))
        for k in sobrando:
            print("  sobra  %r" % k)
        # os %s/%d da traducao precisam bater com os do original
        for k, v in cat.items():
            if k in achados and re.findall(r"%[-+0-9.]*[sdf]", k) != re.findall(r"%[-+0-9.]*[sdf]", v):
                print("  formato diferente: %r -> %r" % (k, v))
                falta += 1
    return 1 if falta else 0


if __name__ == "__main__":
    sys.exit(main())
