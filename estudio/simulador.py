"""Simulação da Fase 1: testa o Estúdio sem OBS, sem agenda de verdade e sem Drive.

    python3 -m estudio simular            prepara a pasta de teste e roda as gravações falsas
    python3 -m estudio simular --preparar só cria a pasta de teste e configura o app

Cria (por padrão na Mesa / Desktop) a pasta "NPD Estudio Teste" com:
  gravacoes-obs/     faz o papel da pasta onde o OBS grava
  agenda-hoje.json   agenda inventada de hoje (dois professores no mesmo horário e um intervalo)
  saida/             onde o app cria as pastas "26_xxx Professor/AAAA MM DD/Footage"
  drive-falso/       faz o papel do Drive no "Conferido, pode subir"

Cada gravação falsa é um .mp4 com nome no padrão do OBS que cresce por alguns segundos, como numa
gravação de verdade. As horas no nome são inventadas para cair em cada regra; o app usa a hora do nome.
"""
from __future__ import annotations

import json
import shutil
import struct
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from . import appdata

AGENDA = [
    {"inicio": "08:00", "fim": "09:00", "professor": "Ana Souza", "codigo": "26_101"},
    {"inicio": "10:00", "fim": "11:00", "professor": "Bruno Costa", "codigo": "26_102"},
    {"inicio": "10:00", "fim": "11:00", "professor": "Carla Mendes", "codigo": "26_103"},
    {"inicio": "13:00", "fim": "14:00", "professor": "Daniel Lima", "codigo": "26_104"},
]

ANA, BRUNO, CARLA, DANIEL = (f"{e['codigo']} {e['professor']}" for e in AGENDA)

# (hora no nome, segundos crescendo, minutos de "duração" no cabeçalho, para onde deve ir, por quê, pedido ao JP)
CENARIOS = [
    ("07:12:05", 5, 2, "Testes", "antes do primeiro horário (8h; a janela de 30 min começa 7h30)", None),
    ("07:41:30", 5, 18, ANA, "até 30 min antes do horário da Ana (8h)", None),
    ("08:15:00", 5, 21, ANA, "dentro do horário da Ana", None),
    ("09:12:40", 5, 9, ANA, "depois do fim da Ana (9h) e antes da janela do próximo (9h30): continua com a Ana", None),
    ("10:03:10", 30, 24, CARLA, "Bruno e Carla no mesmo horário: a agenda escolhe o Bruno, você troca para a Carla",
     "AGORA: na janelinha, clique em \"Trocar professor\" e escolha Carla Mendes (você tem uns 25 segundos)."),
    ("10:38:00", 5, 16, CARLA, "mesmo horário: a troca para a Carla continua valendo", None),
    ("12:05:00", 5, 11, CARLA, "intervalo (11h–13h): continua com o último, e a troca ainda vale", None),
    ("13:20:00", 5, 25, DANIEL, "dentro do horário do Daniel: a troca deixa de valer sozinha", None),
    ("ONTEM 15:00:00", 5, 7, "Sem agenda", "gravação de outro dia (a agenda é de hoje)", None),
]


def _box(tipo: bytes, dados: bytes) -> bytes:
    return struct.pack(">I", 8 + len(dados)) + tipo + dados


def _cabecalho_mp4(segundos: float) -> bytes:
    """Só o começo de um MP4 (ftyp + moov com a duração) — o bastante para o app ler a duração."""
    escala = 1000
    mvhd = _box(b"mvhd", bytes(4) + struct.pack(">IIII", 0, 0, escala, round(segundos * escala)) + bytes(80))
    tkhd = _box(b"tkhd", bytes([0, 0, 0, 3]) + struct.pack(">IIII", 0, 0, 1, 0) + struct.pack(">I", round(segundos * 1000))
                + bytes(52) + struct.pack(">II", 1920 << 16, 1080 << 16))
    moov = _box(b"moov", mvhd + _box(b"trak", tkhd))
    ftyp = _box(b"ftyp", b"isom" + struct.pack(">I", 512) + b"isomiso2mp41")
    return ftyp + moov


def pasta_padrao() -> Path:
    mesa = Path.home() / "Desktop"
    return (mesa if mesa.is_dir() else Path.home()) / "NPD Estudio Teste"


def preparar(base: Path, estavel_seg: int = 3) -> dict:
    base = Path(base)
    for sub in ("gravacoes-obs", "saida", "drive-falso"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    agenda = base / "agenda-hoje.json"
    agenda.write_text(json.dumps({"data": date.today().isoformat(), "eventos": AGENDA}, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    return appdata.salvar({
        "pasta_obs": str(base / "gravacoes-obs"), "pasta_saida": str(base / "saida"),
        "agenda": str(agenda), "pasta_envio": str(base / "drive-falso"), "envio_modo": "pasta", "transcrever": False,
        "estavel_seg": estavel_seg, "nome_maquina": "Simulação (Fase 1)",
    })


def _nome(hora: str) -> str:
    if hora.startswith("ONTEM "):
        d, hora = date.today() - timedelta(days=1), hora[6:]
    else:
        d = date.today()
    return f"{d.isoformat()} {hora.replace(':', '-')}.mp4"


def gravar(pasta_obs: Path, nome: str, segundos: float, minutos_cab: float, passo: float = 0.5,
           bloco: int = 512 * 1024):
    """Escreve um arquivo que cresce por `segundos`, como o OBS gravando."""
    p = Path(pasta_obs) / nome
    with open(p, "wb") as f:
        f.write(_cabecalho_mp4(minutos_cab * 60))
        f.flush()
        fim = time.time() + segundos
        while time.time() < fim:
            f.write(b"\0" * bloco)
            f.flush()
            time.sleep(passo)
    return p


def rodar(base: Path, pausa: float = 6.0, rapido: bool = False):
    cfg = appdata.carregar()
    obs = Path(cfg["pasta_obs"])
    print(f"\nPasta de teste: {base}\nO app precisa estar aberto (outra janela do Terminal: python3 -m estudio).\n")
    if not rapido:
        input("Com o app aberto no navegador, aperte Enter para começar as gravações falsas... ")
    linhas = []
    for i, (hora, seg, minutos, destino, porque, pedido) in enumerate(CENARIOS, 1):
        nome = _nome(hora)
        print(f"\n[{i}/{len(CENARIOS)}] Gravando {nome}  ({seg} s)")
        print(f"      Deve ir para: {destino}  — {porque}")
        if pedido:
            print(f"      >>> {pedido}")
        gravar(obs, nome, 2 if rapido else seg, minutos)
        print("      Parou de gravar. O app move quando o arquivo fica parado.")
        linhas.append((nome, destino, porque))
        time.sleep(pausa)
    print("\n" + "=" * 78)
    print("CONFIRA NO APP (seção Gravações) e na pasta saida/:\n")
    for nome, destino, porque in linhas:
        print(f"  {nome:28}  →  {destino}")
    print("\nDepois, teste a conferência:")
    print("  1. Na gravação das 10:38 (Carla), use \"Mover para\" e mande para Bruno Costa.")
    print("  2. Na gravação das 07:12 (Testes), confira que não há botão de subir.")
    print("  3. No grupo da Ana, clique em \"Conferido, pode subir\" e veja \"enviado, pode apagar\".")
    print(f"     Os arquivos aparecem em {Path(cfg['pasta_envio'])}.")
    print("=" * 78)


def limpar(base: Path):
    """Apaga a pasta de teste e o registro do app, para recomeçar a simulação do zero."""
    base = Path(base)
    if base.name != "NPD Estudio Teste" and not (base / "agenda-hoje.json").is_file():
        print("Essa pasta não parece a pasta de teste; não apago nada.")
        return
    shutil.rmtree(base, ignore_errors=True)
    (appdata.home() / "registro.json").unlink(missing_ok=True)
    print(f"Pasta de teste e registro apagados: {base}")


def main(args) -> int:
    base = Path(args.pasta).expanduser() if args.pasta else pasta_padrao()
    if args.limpar:
        limpar(base)
        return 0
    preparar(base)
    print(f"Pasta de teste pronta: {base}")
    print("O app já foi configurado para usar essa pasta (pasta do OBS, saída, agenda e drive-falso).")
    if args.preparar:
        return 0
    try:
        rodar(base, rapido=args.rapido, pausa=2 if args.rapido else 6)
    except KeyboardInterrupt:
        print("\nSimulação interrompida.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(0)
