"""Idioma do painel: portugues (pt) ou ingles (en).

Os textos ficam escritos em portugues no codigo, dentro de tx("...") (traduz na hora)
ou N_("...") (so marca; para listas e dicionarios do modulo, traduzidos onde sao usados).
A traducao inglesa fica em textos_en.py; tools/checar_traducao.py acha o que falta.
"""
import sys

IDIOMAS = {"pt": "Português", "en": "English"}
_atual = "pt"
_en = None


def detectar():
    """Idioma do Windows: portugues vira pt, qualquer outro vira en."""
    try:
        if sys.platform == "win32":
            import ctypes
            lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "pt" if (lid & 0x3FF) == 0x16 else "en"
        import locale
        loc = (locale.getlocale()[0] or "").lower()
        return "pt" if loc.startswith("pt") else "en"
    except Exception:
        return "pt"


def definir(lang):
    global _atual
    _atual = lang if lang in IDIOMAS else "pt"


def atual():
    return _atual


def ingles():
    return _atual == "en"


def tx(texto):
    """Traducao do texto (escrito em portugues) para o idioma atual."""
    global _en
    if _atual == "pt" or not texto:
        return texto
    if _en is None:
        from textos_en import EN
        _en = EN
    return _en.get(texto, texto)


def N_(texto):
    """Marca um texto para traducao sem traduzir agora (listas/dicionarios do modulo)."""
    return texto
