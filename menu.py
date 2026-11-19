"""Janela do Painel F1 25: escolher o modo (painel, demo, Time Trial, celular) e
acompanhar o painel rodando. Fechar a janela desliga o painel.

E o que abre ao dar dois cliques no PainelF1.exe (ou com `uv run server.py --menu`).
"""
import os
import socket
import subprocess
import sys
import tkinter as tk
import webbrowser

from caminhos import APP_DIR, CONGELADO, RECURSOS

REPO = "https://github.com/matheeusper/f1-dashboard"
BG, CARD, CARD_HOVER, LINHA = "#05070b", "#111823", "#1a2433", "#26324a"
TEXTO, DIM, CIANO, VERDE, VERMELHO = "#eaf0f8", "#8a96a8", "#2de2e6", "#3ddc84", "#ff4d5a"
FONTE = "Bahnschrift"

# (chave, titulo, descricao, argumentos do servidor)
MODOS = [
    ("painel", "Iniciar painel", "Recebe a telemetria do F1 25 e abre o painel", []),
    ("demo", "Demo: corrida simulada", "Veja tudo funcionando sem abrir o jogo", ["--demo"]),
    ("tt", "Demo: Time Trial", "Testa o modo treino e as metas do dia", ["--demo", "--time-trial"]),
    ("lan", "Painel no celular ou tablet", "Libera o painel na rede local e mostra o endereço", ["--lan"]),
]


def ip_local():
    """IP deste PC na rede local (o que o celular deve usar)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))   # nao envia nada, so escolhe a interface de rede
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


def _dpi_nitido():
    """Texto nitido em telas com escala (125%, 150%...)."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


class Menu:
    def __init__(self, base):
        self.base = base
        self.url = None
        _dpi_nitido()
        self.root = root = tk.Tk()
        root.title("Painel F1 25")
        root.configure(bg=BG, padx=26, pady=22)
        root.resizable(False, False)
        self._icone()
        root.protocol("WM_DELETE_WINDOW", self.sair)

        topo = tk.Frame(root, bg=BG)
        topo.pack(fill="x")
        self.img_topo = self._png(64)
        if self.img_topo:
            tk.Label(topo, image=self.img_topo, bg=BG).pack(side="left", padx=(0, 14))
        txt = tk.Frame(topo, bg=BG)
        txt.pack(side="left", fill="x")
        tk.Label(txt, text="PAINEL F1 25", font=(FONTE, 22, "bold"), fg=TEXTO, bg=BG).pack(anchor="w")
        tk.Label(txt, text="Telemetria e engenheiro de corrida", font=(FONTE, 11), fg=DIM, bg=BG).pack(anchor="w")

        self.corpo = tk.Frame(root, bg=BG)
        self.corpo.pack(fill="both", expand=True, pady=(18, 0))
        self._menu()

        rodape = tk.Label(root, text="Manual e novidades no GitHub", font=(FONTE, 10, "underline"),
                          fg=DIM, bg=BG, cursor="hand2")
        rodape.pack(anchor="w", pady=(16, 0))
        rodape.bind("<Button-1>", lambda e: webbrowser.open(REPO))
        self._centralizar()

    # ------------------------------------------------------------ visual
    def _icone(self):
        ico = os.path.join(RECURSOS, "icone.ico")
        try:
            self.root.iconbitmap(default=ico)
        except tk.TclError:
            pass

    def _png(self, tam):
        caminho = os.path.join(RECURSOS, "web", "icone.png")
        try:
            img = tk.PhotoImage(file=caminho)
            fator = max(1, img.width() // tam)
            return img.subsample(fator, fator)
        except tk.TclError:
            return None

    def _centralizar(self):
        r = self.root
        r.update_idletasks()
        w, h = r.winfo_width(), r.winfo_height()
        r.geometry("+%d+%d" % ((r.winfo_screenwidth() - w) // 2, max(0, (r.winfo_screenheight() - h) // 3)))

    def _cartao(self, pai, titulo, descricao, acao, destaque=False):
        f = tk.Frame(pai, bg=CARD, highlightthickness=1, highlightbackground=CIANO if destaque else LINHA,
                     cursor="hand2", padx=16, pady=11)
        f.pack(fill="x", pady=5)
        t = tk.Label(f, text=titulo, font=(FONTE, 14, "bold"), fg=CIANO if destaque else TEXTO, bg=CARD,
                     anchor="w")
        t.pack(fill="x")
        d = tk.Label(f, text=descricao, font=(FONTE, 10), fg=DIM, bg=CARD, anchor="w")
        d.pack(fill="x")

        def cor(c):
            for w in (f, t, d):
                w.configure(bg=c)
        for w in (f, t, d):
            w.bind("<Enter>", lambda e: cor(CARD_HOVER))
            w.bind("<Leave>", lambda e: cor(CARD))
            w.bind("<Button-1>", lambda e: acao())
        return f

    def _botao(self, pai, texto, acao, principal=False):
        b = tk.Label(pai, text=texto, font=(FONTE, 11, "bold"), fg=BG if principal else TEXTO,
                     bg=CIANO if principal else CARD, padx=14, pady=8, cursor="hand2",
                     highlightthickness=1, highlightbackground=CIANO if principal else LINHA)
        b.bind("<Button-1>", lambda e: acao())
        return b

    def _limpar(self):
        for w in self.corpo.winfo_children():
            w.destroy()

    # ------------------------------------------------------------ telas
    def _menu(self):
        self._limpar()
        for i, (chave, titulo, desc, extra) in enumerate(MODOS):
            self._cartao(self.corpo, titulo, desc, lambda c=chave, x=extra: self.escolher(c, x), destaque=i == 0)
        self.erro = tk.Label(self.corpo, text="", font=(FONTE, 10), fg=VERMELHO, bg=BG, wraplength=380,
                             justify="left", anchor="w")
        self.erro.pack(fill="x", pady=(6, 0))

    def escolher(self, chave, extra):
        from server import ErroInicio, criar_parser, iniciar
        argv = ["--abrir"] + extra + ["--porta-udp", str(self.base.porta_udp),
                                      "--porta-web", str(self.base.porta_web)]
        args = criar_parser().parse_args(argv)
        try:
            self.url = iniciar(args)
        except ErroInicio as exc:
            self.erro.configure(text=str(exc))
            return
        self._rodando(chave, args)

    def _rodando(self, chave, args):
        self._limpar()
        titulo = {k: t for k, t, _d, _x in MODOS}[chave]
        linha = tk.Frame(self.corpo, bg=BG)
        linha.pack(fill="x")
        tk.Label(linha, text="●", font=(FONTE, 14), fg=VERDE, bg=BG).pack(side="left")
        tk.Label(linha, text=" %s: rodando" % titulo, font=(FONTE, 14, "bold"), fg=TEXTO, bg=BG).pack(side="left")

        def info(texto, cor=DIM, tam=11):
            tk.Label(self.corpo, text=texto, font=(FONTE, tam), fg=cor, bg=BG, wraplength=390,
                     justify="left", anchor="w").pack(fill="x", pady=(8, 0))

        if chave in ("painel", "lan"):
            info("Esperando o F1 25 na porta UDP %d. Entre na pista e o painel acende sozinho." % args.porta_udp)
            info("No jogo: Configurações → Telemetria → UDP ligado, IP 127.0.0.1, porta %d, 60 Hz."
                 % args.porta_udp, tam=10)
        else:
            info("Dados simulados, sem o jogo. O demo usa um histórico separado do seu.")
        if chave == "lan":
            ip = ip_local()
            endereco = "http://%s:%d" % (ip, args.porta_web) if ip else "(não achei o IP deste PC: veja com ipconfig)"
            info("No celular ou tablet, na mesma rede, abra:", cor=TEXTO)
            campo = tk.Entry(self.corpo, font=(FONTE, 18, "bold"), fg=CIANO, bg=CARD, relief="flat",
                             readonlybackground=CARD, justify="center", highlightthickness=1,
                             highlightbackground=LINHA)
            campo.insert(0, endereco)
            campo.configure(state="readonly")
            campo.pack(fill="x", pady=(6, 0), ipady=6)
            info("Se não abrir, libere o Painel F1 25 no firewall do Windows (redes privadas e públicas). "
                 "Deixe a VOZ desligada no celular para o engenheiro não falar em dobro.", tam=10)

        botoes = tk.Frame(self.corpo, bg=BG)
        botoes.pack(fill="x", pady=(16, 0))
        from server import abrir_ou_focar
        self._botao(botoes, "Abrir painel", lambda: abrir_ou_focar(self.url), principal=True).pack(side="left")
        self._botao(botoes, "Evolução", lambda: webbrowser.open(self.url + "/evolucao")).pack(side="left", padx=8)
        self._botao(botoes, "Trocar de modo", self.reiniciar).pack(side="left")
        info("Fechar esta janela desliga o painel.", tam=10)
        self._centralizar()
        if chave != "lan":   # o painel ja abriu: o menu sai da frente e fica na barra de tarefas
            self.root.after(1500, self.root.iconify)

    # ------------------------------------------------------------ sair / reiniciar
    def reiniciar(self):
        """O jeito limpo de trocar de modo: abre o programa de novo no menu e fecha este."""
        portas = ["--porta-udp", str(self.base.porta_udp), "--porta-web", str(self.base.porta_web)]
        env = os.environ.copy()
        if CONGELADO:
            cmd = [sys.executable, "--menu"] + portas
            # Sem isso o exe novo reaproveita a pasta temporaria deste (_MEI...), que e apagada
            # quando este fecha: o novo quebrava com "No module named '_tkinter'".
            env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
            for k in list(env):
                if k.startswith("_PYI") or k == "_MEIPASS2":
                    del env[k]
        else:
            cmd = [sys.executable, os.path.join(APP_DIR, "server.py"), "--menu"] + portas
        subprocess.Popen(cmd, env=env)
        os._exit(0)

    def sair(self):
        os._exit(0)   # encerra tambem as threads do servidor

    def rodar(self):
        self.root.mainloop()


def abrir_menu(base):
    Menu(base).rodar()
