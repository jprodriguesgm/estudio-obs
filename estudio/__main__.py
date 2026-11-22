"""Abrir o Estúdio: python3 -m estudio   (abre a janela no navegador)

  python3 -m estudio simular              simulação da Fase 1 (sem OBS): prepara a pasta e grava arquivos falsos
  python3 -m estudio simular --preparar   só prepara a pasta de teste e configura o app
  python3 -m estudio simular --limpar     apaga a pasta de teste e o registro, para recomeçar
  python3 -m estudio transcrever <pasta>  transcreve como o transcribe (Whisper do app)
"""
from __future__ import annotations

import argparse
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="estudio")
    sub = ap.add_subparsers(dest="cmd")
    ab = sub.add_parser("abrir", help="abre a janela (padrão)")
    ab.add_argument("--porta", type=int, default=None)
    ab.add_argument("--sem-navegador", action="store_true")
    si = sub.add_parser("simular", help="simulação da Fase 1, sem OBS")
    si.add_argument("--pasta", default=None, help="onde criar a pasta de teste (padrão: Mesa/NPD Estudio Teste)")
    si.add_argument("--preparar", action="store_true", help="só prepara a pasta e configura o app")
    si.add_argument("--rapido", action="store_true", help="sem pausas nem perguntas (para os testes automáticos)")
    si.add_argument("--limpar", action="store_true", help="apaga a pasta de teste e o registro")
    tr = sub.add_parser("transcrever", help="transcreve vídeos ou pastas (como o transcribe)")
    tr.add_argument("entradas", nargs="+")
    args = ap.parse_args(argv)

    if args.cmd in (None, "abrir"):
        from . import server
        server.serve(porta=getattr(args, "porta", None), abrir_navegador=not getattr(args, "sem_navegador", False))
        return 0
    if args.cmd == "transcrever":
        from . import transcricao
        return transcricao.main(args.entradas)
    if args.cmd == "simular":
        from . import simulador
        return simulador.main(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
