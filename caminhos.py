"""Onde ficam os arquivos, rodando pelo codigo ou como executavel (PyInstaller).

- RECURSOS: arquivos do programa (pasta web/). No executavel ficam dentro do pacote.
- DADOS: historico, recordes e ajustes do piloto. Ficam na pasta "dados" ao lado do
  PainelF1.exe (ou do codigo), para nao se perderem quando o programa fecha.
"""
import os
import sys

CONGELADO = getattr(sys, "frozen", False)
_AQUI = os.path.dirname(os.path.abspath(__file__))
RECURSOS = getattr(sys, "_MEIPASS", _AQUI)
APP_DIR = os.path.dirname(os.path.abspath(sys.executable)) if CONGELADO else _AQUI
DADOS = os.path.join(APP_DIR, "dados")
