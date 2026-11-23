"""Ponto de entrada do app empacotado (PyInstaller).

Dois cliques: liga o Estúdio (sem janela de terminal) e abre a tela no navegador. Ele fica ligado vigiando a
pasta do OBS até alguém clicar em "Fechar o Estúdio" na tela. Abrir de novo com ele ligado só abre a tela.

Pelo Terminal / Prompt:
  Mac:      "Estudio.app/Contents/MacOS/Estudio" diagnostico [video]
  Windows:  "Estudio/estudio-terminal.exe" diagnostico [video]
  … transcrever <pasta>     transcreve como o transcribe (o app usa isso no "Conferido, pode subir")
"""
from __future__ import annotations

import os
import sys
import time


def _log_em_arquivo():
    """Sem janela de terminal: o que o app escreveria vai para estudio.log na pasta de dados do app."""
    from estudio import appdata
    try:
        casa = appdata.home()
        log = casa / "estudio.log"
        if log.is_file() and log.stat().st_size > 2_000_000:
            log.replace(casa / "estudio.log.1")
        fh = open(log, "a", encoding="utf-8", buffering=1, errors="replace")
        fh.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} abrindo (pid {os.getpid()})\n")
        sys.stdout = fh
        sys.stderr = fh
    except OSError:
        pass


def _saida_utf8():
    """Windows: a janela de texto usa outra codificação; acento e "·" não podem derrubar o app."""
    for f in (sys.stdout, sys.stderr):
        try:
            f.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def diagnostico(video: str | None = None) -> int:
    try:
        return _diagnostico(video)
    except BaseException:  # noqa: BLE001 — no diagnóstico, qualquer erro tem que aparecer por escrito
        import traceback
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        return 1


def _diagnostico(video: str | None = None) -> int:
    """Confere o que vai dentro do app e, com um vídeo, transcreve de verdade."""
    import platform
    import shutil
    import tempfile
    from pathlib import Path
    from estudio import __version__, transcricao
    print(f"Estúdio {__version__} · {platform.system()} {platform.machine()} · Python {platform.python_version()}",
          flush=True)
    ok = True
    ff = transcricao.ffmpeg()
    print(f"{'ffmpeg':<10} {'ok' if ff else 'FALTA'}  {ff or ''}", flush=True)
    ok &= bool(ff)
    m = transcricao.motor()
    print(f"{'whisper':<10} {'ok' if m['ok'] else 'FALTA ' + ', '.join(m['falta'])}  {m['nome']}", flush=True)
    ok &= m["ok"]
    if m.get("tipo") == "mlx":
        print(f"{'modelo':<10} {transcricao.modelo_mlx()}", flush=True)
    else:
        print(f"{'modelo':<10} {transcricao.modelo_cpp()}  · {transcricao.whisper_cli()}", flush=True)
        cli = transcricao.whisper_cli()
        if cli:
            import subprocess
            r = subprocess.run([cli, "--help"], capture_output=True, text=True, encoding="utf-8", errors="replace")
            print(f"{'whisper-cli':<10} saída {r.returncode}: {(r.stdout + r.stderr).strip().splitlines()[:1]}",
                  flush=True)
    # conexão segura com o Google (o Pastas do dia): o Python do app precisa achar os certificados
    import ssl
    import urllib.error
    import urllib.request
    from estudio import pastas_do_dia
    try:
        urllib.request.urlopen("https://script.google.com/", timeout=20, context=pastas_do_dia.contexto_ssl()).close()
        https = "ok"
    except urllib.error.HTTPError:
        https = "ok"                                  # respondeu (mesmo com erro HTTP): o certificado foi aceito
    except (ssl.SSLError, urllib.error.URLError) as e:
        https = f"ERRO {getattr(e, 'reason', e)}"
    print(f"{'https':<10} {https}", flush=True)
    ok &= https == "ok"
    from estudio import ui_ok
    print(f"{'tela':<10} {'ok' if ui_ok() else 'FALTA'}", flush=True)
    ok &= ui_ok()
    if video and ok:
        with tempfile.TemporaryDirectory(prefix="estudio_diag_") as t:
            pasta = Path(t) / "Footage"
            pasta.mkdir()
            shutil.copy2(video, pasta / Path(video).name)
            t0 = time.time()
            rc = transcricao.main([str(pasta)])
            srt = pasta / (Path(video).stem + ".srt")
            texto = srt.read_text(encoding="utf-8") if srt.is_file() else ""
            linhas = [x for x in texto.splitlines() if x and not x[0].isdigit()]
            print(f"{'transcr.':<10} {'ok' if rc == 0 and linhas else 'ERRO'} ({time.time() - t0:.0f} s): "
                  f"{' / '.join(linhas)[:300]}", flush=True)
            ok &= rc == 0 and bool(linhas)
    print("TUDO OK" if ok else "FALTA ALGUMA COISA", flush=True)
    return 0 if ok else 1


def main() -> int:
    import multiprocessing
    multiprocessing.freeze_support()
    _saida_utf8()     # bibliotecas do Whisper abrem processos auxiliares; no app empacotado precisa disto
    args = [a for a in sys.argv[1:] if not a.startswith("-psn_")]   # o Finder antigo manda "-psn_…"
    if args and args[0] == "diagnostico":
        return diagnostico(args[1] if len(args) > 1 else None)
    if args and args[0] == "transcrever":
        from estudio import transcricao
        return transcricao.main(args[1:])
    if args:
        from estudio.__main__ import main as cli
        return cli(args) or 0
    if getattr(sys, "frozen", False):
        _log_em_arquivo()
    from estudio import server
    server.serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
