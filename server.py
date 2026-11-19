"""Painel de telemetria do F1 25.

Escuta a telemetria UDP do jogo e entrega o estado do carro para a pagina web
(http://127.0.0.1:8025) via Server-Sent Events. Usa so a biblioteca padrao.

    python server.py            # espera o jogo
    python server.py --abrir    # e abre o painel no monitor vertical
    python server.py --demo     # dados simulados, sem o jogo
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import historico
import voz as vozmod
from caminhos import CONGELADO, RECURSOS
from f1_packets import Decoder

WEB_DIR = os.path.join(RECURSOS, "web")
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/evolucao": ("evolucao.html", "text/html; charset=utf-8"),
    "/evolucao.js": ("evolucao.js", "application/javascript; charset=utf-8"),
    "/icone.png": ("icone.png", "image/png"),
    "/favicon.ico": ("icone.png", "image/png"),
}

decoder = Decoder()
ajustes = vozmod.Ajustes()
voz = vozmod.Voz(ajustes)
decoder.eng.voz = voz
decoder.eng.ajustes = ajustes


def config_view():
    from engenheiro import BOTOES
    eng = decoder.eng
    return {"ajustes": ajustes.get(), "vozes": vozmod.VOZES, "status": voz.status(), "neural": voz.neural(),
            "botoes": BOTOES, "nomeJogo": eng._seguro(eng.nome_do_jogo), "nomeAtual": eng._seguro(eng.nome) or "",
            "online": bool((decoder.session or {}).get("online"))}


def udp_loop(sock):
    while True:
        try:
            data, _ = sock.recvfrom(4096)
        except OSError:
            continue
        try:
            decoder.feed(data)
        except Exception as exc:  # um pacote ruim nao pode derrubar o painel
            print("Pacote ignorado:", exc)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/stream":
            return self._stream()
        if path == "/state":
            return self._json(decoder.snapshot())
        if path == "/mapa":
            return self._json(decoder.mapa())
        if path == "/telemetria":
            try:
                n = int(parse_qs(query).get("curva", ["0"])[0])
            except ValueError:
                n = 0
            return self._json(decoder.telemetria(n))
        if path == "/tts":
            q = parse_qs(query)
            audio = voz.obter(q.get("t", [""])[0][:600], q.get("tom", ["normal"])[0])
            if audio is None:   # sem voz natural agora: o painel usa a voz do Windows
                return self._send(b"indisponivel", "text/plain; charset=utf-8", 503)
            return self._send(audio, "audio/mpeg")
        if path == "/api/config":
            return self._json(config_view())
        if path == "/api/pistas":
            return self._json(historico.api_pistas(historico.ARQUIVO))
        if path == "/api/evolucao":
            chave = parse_qs(query).get("pista", [""])[0]
            return self._json(historico.api_evolucao(chave, historico.ARQUIVO))
        entry = STATIC.get(path)
        if not entry:
            return self._send(b"Nao encontrado", "text/plain", 404)
        with open(os.path.join(WEB_DIR, entry[0]), "rb") as f:
            self._send(f.read(), entry[1])

    def do_POST(self):
        path = self.path.partition("?")[0]
        if path not in ("/api/config", "/api/pergunta", "/api/treino"):
            return self._send(b"Nao encontrado", "text/plain", 404)
        origem = self.headers.get("Origin")
        if origem and origem.split("://", 1)[-1] != self.headers.get("Host"):
            return self._send(b"origem recusada", "text/plain", 403)   # outro site tentando mudar os ajustes
        n = int(self.headers.get("Content-Length") or 0)
        if n > 4096:
            return self._send(b"grande demais", "text/plain", 413)
        try:
            dados = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._send(b"json invalido", "text/plain", 400)
        if not isinstance(dados, dict):
            return self._send(b"json invalido", "text/plain", 400)
        if path == "/api/treino":     # tecla T: treinar uma curva (so no Time Trial)
            curva = dados.get("curva")
            curva = curva if isinstance(curva, int) and 0 < curva < 100 else None
            with decoder.lock:
                decoder.eng.ptt += 1
                decoder.eng.tr_alternar(curva)
            return self._json({"ok": True})
        if path == "/api/pergunta":   # teclas 1-0 do painel: o mesmo que os botoes do volante
            try:
                n = int(dados.get("acao", 0))
            except (TypeError, ValueError):
                n = 0
            if not 1 <= n <= 12:
                return self._send(b"acao invalida", "text/plain", 400)
            with decoder.lock:
                decoder.eng.pergunta(n)
            return self._json({"ok": True})
        ajustes.atualiza(dados)
        return self._json(config_view())

    def _json(self, obj):
        self._send(json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _send(self, body, ctype, code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            while True:
                payload = json.dumps(decoder.snapshot(), separators=(",", ":"))
                self.wfile.write(b"data: " + payload.encode() + b"\n\n")
                self.wfile.flush()
                # Envia a cada quadro de telemetria do jogo (ate 60 Hz); sem jogo, 4x por segundo.
                with decoder.tick:
                    decoder.tick.wait(0.25)
        except OSError:
            pass  # navegador fechou


# ---------------------------------------------------------------- abrir painel
def monitor_vertical():
    """Retorna (x, y, largura, altura) do primeiro monitor em retrato, ou None."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    found = []
    proc_type = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC,
                                   ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def callback(_mon, _dc, rect, _data):
        r = rect.contents
        found.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
        return 1

    ctypes.windll.user32.EnumDisplayMonitors(0, 0, proc_type(callback), 0)
    for m in found:
        if m[3] > m[2]:
            return m
    return None


def achar_navegador():
    bases = [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"),
             os.environ.get("LOCALAPPDATA")]
    for rel in (r"Google\Chrome\Application\chrome.exe", r"Microsoft\Edge\Application\msedge.exe"):
        for base in bases:
            if base and os.path.isfile(os.path.join(base, rel)):
                return os.path.join(base, rel)
    return None


def focar_painel():
    """Traz para a frente a janela do painel, se ja estiver aberta (so no Windows).
    Devolve True se achou; assim 'Abrir painel' nao abre uma segunda janela."""
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    achadas = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cada(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            titulo = ctypes.create_unicode_buffer(256)
            classe = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, titulo, 256)
            user32.GetClassNameW(hwnd, classe, 256)
            # janela do Chrome/Edge com a pagina do painel (o menu tambem se chama assim, mas e Tk)
            if titulo.value.startswith("Painel F1 25") and classe.value.startswith("Chrome_WidgetWin"):
                achadas.append(hwnd)
        return True

    user32.EnumWindows(cada, 0)
    if not achadas:
        return False
    h = achadas[0]
    if user32.IsIconic(h):
        user32.ShowWindow(h, 9)   # SW_RESTORE
    user32.SetForegroundWindow(h)
    return True


def abrir_ou_focar(url):
    if not focar_painel():
        abrir_painel(url)


def abrir_painel(url):
    exe = achar_navegador()
    if not exe:
        webbrowser.open(url)
        return
    perfil = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "PainelF1", "perfil")
    # As flags de "occlusion/backgrounding" impedem o Chrome de congelar o painel
    # enquanto o jogo esta em tela cheia no outro monitor; a de autoplay deixa o
    # engenheiro falar sem precisar clicar na pagina antes.
    cmd = [exe, "--app=" + url, "--user-data-dir=" + perfil, "--no-first-run",
           "--no-default-browser-check", "--disable-features=CalculateNativeWinOcclusion",
           "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding",
           "--autoplay-policy=no-user-gesture-required"]
    mon = monitor_vertical()
    if mon:
        cmd += ["--window-position=%d,%d" % (mon[0], mon[1]),
                "--window-size=%d,%d" % (mon[2], mon[3]), "--start-fullscreen"]
        print("Abrindo em tela cheia no monitor vertical (%dx%d)." % (mon[2], mon[3]))
    else:
        cmd += ["--window-size=540,960"]
        print("Nenhum monitor vertical detectado: arraste a janela para ele e aperte F11.")
    subprocess.Popen(cmd, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


# ---------------------------------------------------------------------- inicio
class ErroInicio(Exception):
    """Nao deu para subir o painel (porta ocupada etc.). A mensagem vai para o usuario."""


def criar_parser():
    ap = argparse.ArgumentParser(description="Painel de telemetria do F1 25")
    ap.add_argument("--porta-udp", type=int, default=20777, help="porta UDP do jogo (padrao 20777)")
    ap.add_argument("--porta-web", type=int, default=8025, help="porta da pagina (padrao 8025)")
    ap.add_argument("--lan", action="store_true",
                    help="aceita telemetria e navegadores de outros aparelhos da rede (console, tablet)")
    ap.add_argument("--demo", action="store_true", help="gera dados simulados, sem o jogo")
    ap.add_argument("--time-trial", action="store_true", help="no modo demo, simula um Time Trial")
    ap.add_argument("--formato", type=int, default=2025, choices=(2025, 2026),
                    help="formato usado pelo modo demo")
    ap.add_argument("--abrir", action="store_true", help="abre o painel no navegador")
    ap.add_argument("--historico", help="arquivo do historico (padrao: dados/historico.sqlite3; "
                                        "o modo demo usa dados/demo.sqlite3)")
    ap.add_argument("--menu", action="store_true",
                    help="abre a janela de menu (iniciar, demo, celular); e o padrao do executavel")
    return ap


def iniciar(args):
    """Sobe o painel (telemetria UDP + pagina) em segundo plano e devolve o endereco."""
    if args.historico or args.demo:
        # o demo grava num historico separado para nao misturar com as suas voltas reais
        historico.ARQUIVO = os.path.abspath(args.historico or os.path.join(historico.PASTA, "demo.sqlite3"))
        if decoder.eng:
            decoder.eng.hist = historico.Historico(historico.ARQUIVO)

    host = "0.0.0.0" if args.lan else "127.0.0.1"
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        udp.bind((host, args.porta_udp))
    except OSError:
        udp.close()
        raise ErroInicio("A porta UDP %d já está em uso: outro app de telemetria (SimHub, Crew Chief...) "
                         "ou o próprio painel já está aberto." % args.porta_udp)
    try:
        ThreadingHTTPServer.daemon_threads = True
        httpd = ThreadingHTTPServer((host, args.porta_web), Handler)
    except OSError:
        udp.close()
        raise ErroInicio("A porta %d já está em uso: o painel já está aberto?" % args.porta_web)

    threading.Thread(target=udp_loop, args=(udp,), daemon=True).start()
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    if args.demo:
        from simulador import simular
        decoder.demo = True
        threading.Thread(target=simular, kwargs={"port": args.porta_udp, "fmt": args.formato,
                                                 "tipo": 18 if args.time_trial else 15},
                         daemon=True).start()
    url = "http://127.0.0.1:%d" % args.porta_web
    if args.abrir:
        abrir_ou_focar(url)   # depois de "Trocar de modo" a janela antiga continua aberta
    return url


# ---------------------------------------------------------------------- main
def main():
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    ap = criar_parser()
    if CONGELADO and len(sys.argv) == 1:
        sys.argv.append("--menu")   # dois cliques no PainelF1.exe: abre o menu
    args = ap.parse_args()
    if args.menu:
        from menu import abrir_menu
        abrir_menu(args)
        return 0
    try:
        url = iniciar(args)
    except ErroInicio as exc:
        print("ERRO:", exc)
        return 1
    print("Painel F1 25 no ar: " + url)
    print("Esperando telemetria UDP na porta %d%s." % (args.porta_udp, " (modo demo)" if args.demo else ""))
    print("Feche esta janela para desligar.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
