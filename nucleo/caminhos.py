"""Onde ficam os arquivos, rodando pelo codigo ou como executavel (PyInstaller).

- RECURSOS: arquivos do programa (pasta web/, na raiz do projeto). No executavel ficam
  dentro do pacote.
- DADOS: historico, recordes e ajustes do piloto. Ficam na pasta "dados" ao lado do
  executavel (ou na raiz do projeto), para nao se perderem quando o programa fecha. O app
  nativo (pasta app/) roda o nucleo de outro lugar e indica a pasta em PAINELF1_DADOS.
"""
import os
import sys

CONGELADO = getattr(sys, "frozen", False)
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # o codigo fica em nucleo/
RECURSOS = getattr(sys, "_MEIPASS", _RAIZ)
APP_DIR = os.path.dirname(os.path.abspath(sys.executable)) if CONGELADO else _RAIZ
DADOS = os.environ.get("PAINELF1_DADOS") or os.path.join(APP_DIR, "dados")
