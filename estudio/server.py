"""Servidor local: a janela do Estúdio abre no navegador e conversa com o vigia por aqui.

Só escuta em 127.0.0.1 (nada sai do computador). Rodar: python3 -m estudio
"""
from __future__ import annotations

import json
import mimetypes
import socket
import threading
import time
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import __version__, appdata, dialogs, rclone
from .vigia import ESTUDIO

UI_DIR = Path(__file__).resolve().parent / "ui"
PORTA_PADRAO = 8768          # o Montador usa a 8767; os dois podem ficar abertos juntos


class ApiError(Exception):
    pass


ULTIMO_PING = [time.time()]


# ====================================================================== ações

def acao_estado(_q=None) -> dict:
    cfg = appdata.carregar()
    snd = rclone.subir_no_drive()
    envio = {"subir_no_drive": {"remoto": snd["remoto"], "raiz": snd["raiz"], "email": snd["email"]} if snd else None,
             "destino_padrao": rclone.destino_padrao(), "destino": rclone.destino(cfg),
             "transcribe": rclone.achar_transcribe(cfg)}
    return {"versao": __version__, "config": cfg, "envio": envio, **ESTUDIO.resumo()}


def acao_testar(corpo) -> dict:
    if corpo.get("mudancas"):
        appdata.salvar(corpo["mudancas"])
    try:
        return {"msg": rclone.testar(appdata.carregar())}
    except rclone.ErroRclone as e:
        raise ApiError(str(e))


def acao_config(corpo) -> dict:
    appdata.salvar(corpo.get("mudancas") or {})
    return acao_estado()


def acao_escolher(corpo) -> dict:
    tipo = corpo.get("tipo", "pasta")
    titulo = corpo.get("titulo") or ("Escolha a pasta" if tipo == "pasta" else "Escolha o arquivo")
    try:
        if tipo == "pasta":
            p = dialogs.choose_folder(titulo, corpo.get("inicio"))
        else:
            p = dialogs.choose_file(titulo, corpo.get("inicio"), ("json",))
    except dialogs.Unsupported:
        raise ApiError("Neste computador o app ainda não abre a janela de escolher. Cole o caminho no campo.")
    return {"caminho": p}


def acao_trocar(corpo) -> dict:
    ESTUDIO.trocar(corpo.get("pasta") or None)
    return acao_estado()


def acao_mover(corpo) -> dict:
    try:
        ESTUDIO.mover(corpo["id"], corpo["pasta"])
    except (KeyError, ValueError, OSError) as e:
        raise ApiError(str(e))
    return acao_estado()


def acao_subir(corpo) -> dict:
    try:
        ESTUDIO.subir(corpo["pasta"], corpo["dia"])
    except (KeyError, ValueError) as e:
        raise ApiError(str(e))
    return acao_estado()


def acao_esquecer(corpo) -> dict:
    try:
        ESTUDIO.esquecer(corpo["id"])
    except (KeyError, ValueError) as e:
        raise ApiError(str(e))
    return acao_estado()


def acao_mostrar(corpo) -> dict:
    """Mostra o arquivo no Finder / Explorer."""
    import subprocess
    import sys
    p = Path(corpo.get("caminho") or "")
    if not p.exists():
        raise ApiError("Não achei esse arquivo.")
    if sys.platform == "darwin":
        subprocess.run(["open", "-R", str(p)])
    elif sys.platform == "win32":
        subprocess.run(["explorer", "/select,", str(p)])
    else:
        subprocess.run(["xdg-open", str(p.parent)])
    return {"ok": True}


GET = {"/api/estado": acao_estado}
POST = {"/api/config": acao_config, "/api/escolher": acao_escolher, "/api/trocar": acao_trocar,
        "/api/mover": acao_mover, "/api/subir": acao_subir, "/api/esquecer": acao_esquecer,
        "/api/mostrar": acao_mostrar, "/api/testar": acao_testar}


# ====================================================================== HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "Estudio"

    def log_message(self, *a):
        pass

    def _json(self, dados, status=200):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _arquivo(self, p: Path):
        if not p.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        dados = p.read_bytes()
        tipo = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        if p.suffix == ".js":
            tipo = "text/javascript"
        self.send_response(200)
        self.send_header("Content-Type", tipo + ("; charset=utf-8" if tipo.startswith("text") else ""))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def _origem_ok(self) -> bool:
        org = self.headers.get("Origin")
        return not org or org.startswith(("http://127.0.0.1", "http://localhost"))

    def do_GET(self):
        u = urlparse(self.path)
        ULTIMO_PING[0] = time.time()
        if u.path in ("/", "/index.html"):
            return self._arquivo(UI_DIR / "index.html")
        if u.path.startswith("/ui/"):
            alvo = (UI_DIR / unquote(u.path[4:])).resolve()
            if UI_DIR not in alvo.parents:
                return self.send_error(HTTPStatus.FORBIDDEN)
            return self._arquivo(alvo)
        fn = GET.get(u.path)
        if fn is None:
            return self.send_error(HTTPStatus.NOT_FOUND)
        self._rodar(fn, parse_qs(u.query))

    def do_POST(self):
        u = urlparse(self.path)
        ULTIMO_PING[0] = time.time()
        if not self._origem_ok():
            return self.send_error(HTTPStatus.FORBIDDEN)
        if u.path == "/api/sair":
            self._json({"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        fn = POST.get(u.path)
        if fn is None:
            return self.send_error(HTTPStatus.NOT_FOUND)
        tam = int(self.headers.get("Content-Length") or 0)
        try:
            corpo = json.loads(self.rfile.read(tam).decode("utf-8") or "{}") if tam else {}
        except ValueError:
            return self._json({"erro": "Pedido inválido."}, 400)
        self._rodar(fn, corpo)

    def _rodar(self, fn, arg):
        try:
            self._json(fn(arg))
        except ApiError as e:
            self._json({"erro": str(e)}, 400)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._json({"erro": f"Erro inesperado: {e}"}, 500)


def _porta_livre(porta: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", porta)) != 0


def serve(porta: int | None = None, abrir_navegador: bool = True):
    porta = porta or PORTA_PADRAO
    url = f"http://127.0.0.1:{porta}/"
    if not _porta_livre(porta):              # já está aberto: só abre a janela
        if abrir_navegador:
            webbrowser.open(url)
        print(f"O Estúdio já está aberto em {url}")
        return
    ESTUDIO.iniciar()
    srv = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
    print(f"Estúdio {__version__} em {url}")
    print("Deixe esta janela aberta enquanto estiver gravando. Para fechar: Ctrl+C (ou feche a janela).")
    if abrir_navegador:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        ESTUDIO.parar()
        srv.server_close()
