"""Configurações do Estúdio em cada máquina (o que fica salvo entre um uso e outro).

Tudo numa pasta do usuário (não precisa de administrador):
  Mac:      ~/Library/Application Support/Estudio
  Windows:  %APPDATA%\\Estudio
  Linux:    ~/.local/share/estudio
A variável ESTUDIO_HOME troca essa pasta (testes e simulação).
"""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

APP_NAME = "Estudio"

DEFAULTS = {
    "pasta_obs": None,        # onde o OBS grava (o app vigia esta pasta)
    "pasta_saida": None,      # onde nascem as pastas "26_xxx Professor/AAAA MM DD/Footage"
    "agenda": None,           # arquivo da agenda do dia (.json)
    "envio_modo": "rclone",   # "rclone" (conta do Subir no Drive) ou "pasta" (copia para uma pasta; a simulação usa)
    "pasta_envio": None,      # modo pasta: para onde "Conferido, pode subir" copia (na simulação, drive-falso)
    "rclone_destino": "",     # modo rclone: conexão e pasta, ex.: "drive:Gravações IEC". Vazio = a do Subir no Drive
    "rclone_exe": "",         # caminho do rclone, se não estiver nos lugares de sempre
    "transcrever": True,      # rodar o `transcribe` antes de subir (Mac com chip Apple)
    "transcribe_exe": "",     # caminho do transcribe, se não estiver em /usr/local/bin
    "estavel_seg": 5,         # segundos sem crescer para considerar a gravação terminada
    "antecedencia_min": 30,   # gravação até X min antes do evento já é daquele professor
    "nome_maquina": "",       # ex.: "Estúdio 1 — São Gabriel" (aparece no topo)
}

_lock = threading.Lock()


def home() -> Path:
    env = os.environ.get("ESTUDIO_HOME")
    if env:
        p = Path(env)
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / APP_NAME
    elif os.name == "nt":
        p = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")) / APP_NAME
    else:
        p = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")) / "estudio"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _arquivo() -> Path:
    return home() / "configuracoes.json"


def carregar() -> dict:
    with _lock:
        try:
            dados = json.loads(_arquivo().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            dados = {}
        out = dict(DEFAULTS)
        for k, v in dados.items():
            if k in out:
                out[k] = v
        return out


def salvar(mudancas: dict) -> dict:
    atual = carregar()
    for k, v in mudancas.items():
        if k not in DEFAULTS:
            continue
        if k == "transcrever":
            v = bool(v)
        if k in ("estavel_seg", "antecedencia_min"):
            try:
                v = max(1, int(v))
            except (TypeError, ValueError):
                continue
        atual[k] = v
    with _lock:
        tmp = _arquivo().with_suffix(".tmp")
        tmp.write_text(json.dumps(atual, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(_arquivo())
    return atual


def faltando(cfg: dict) -> list[str]:
    """O que ainda precisa ser configurado para o app trabalhar."""
    out = []
    if not cfg.get("pasta_obs") or not Path(cfg["pasta_obs"]).is_dir():
        out.append("pasta do OBS")
    if not cfg.get("pasta_saida") or not Path(cfg["pasta_saida"]).is_dir():
        out.append("pasta de saída")
    if not cfg.get("agenda") or not Path(cfg["agenda"]).is_file():
        out.append("arquivo da agenda")
    return out
