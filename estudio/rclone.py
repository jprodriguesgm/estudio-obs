"""rclone (como no app "Subir no Drive") e o `transcribe` do Mac.

Conta e pasta do Drive: o Estúdio aproveita o que o instalador do Subir no Drive já deixou no Mac,
em ~/Library/Application Support/SubirNoDrive:
  config.txt  → 1ª linha: conexão do rclone (ex.: drive) · 2ª: pasta inicial (ex.: Gravações IEC) · 3ª: e-mail
  env.sh      → onde está o rclone (PATH) e, se for o caso, a configuração dele (RCLONE_CONFIG)
Assim o envio vai sempre pela conta da instituição, não importa qual conta está aberta no navegador.
Dá para trocar tudo nas Configurações do Estúdio.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_LOCAL = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
LUGARES_RCLONE = ("/opt/homebrew/bin/rclone", "/usr/local/bin/rclone", str(Path.home() / "Applications" / "rclone"),
                  str(Path.home() / "Applications" / "rclone" / "rclone"), str(Path.home() / "bin" / "rclone"),
                  # Windows
                  str(Path(_LOCAL) / "Microsoft" / "WinGet" / "Links" / "rclone.exe"),
                  str(Path.home() / "rclone" / "rclone.exe"), r"C:\rclone\rclone.exe",
                  r"C:\Program Files\rclone\rclone.exe")
LUGARES_TRANSCRIBE = ("/usr/local/bin/transcribe", "/opt/homebrew/bin/transcribe", str(Path.home() / "bin" / "transcribe"))
PATH_BASE = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]


class ErroRclone(Exception):
    pass


# ------------------------------------------------------------------ Subir no Drive

def pasta_subir_no_drive() -> Path:
    env = os.environ.get("SUBIR_NO_DRIVE_HOME")             # testes
    return Path(env) if env else Path.home() / "Library" / "Application Support" / "SubirNoDrive"


def subir_no_drive() -> dict | None:
    """O que o Subir no Drive deixou configurado neste Mac, ou None."""
    base = pasta_subir_no_drive()
    try:
        linhas = (base / "config.txt").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    if not linhas or not linhas[0].strip():
        return None
    out = {"remoto": linhas[0].strip(), "raiz": (linhas[1].strip() if len(linhas) > 1 else ""),
           "email": (linhas[2].strip() if len(linhas) > 2 else ""), "path": [], "rclone_config": None}
    try:
        for ln in (base / "env.sh").read_text(encoding="utf-8").splitlines():
            m = re.match(r'\s*export PATH="(.*)"\s*$', ln)
            if m:
                out["path"] = [p for p in m.group(1).split(":") if p and "$" not in p]
            m = re.match(r'\s*export RCLONE_CONFIG="(.*)"\s*$', ln)
            if m:
                out["rclone_config"] = m.group(1)
    except OSError:
        pass
    return out


def ambiente() -> dict:
    """Variáveis para rodar rclone e transcribe: PATH completo (o app aberto pelo Finder tem PATH curto)."""
    env = dict(os.environ)
    snd = subir_no_drive() or {}
    extra = list(snd.get("path") or []) + PATH_BASE
    atuais = env.get("PATH", "").split(os.pathsep)
    # o PATH de quem abriu o app vem primeiro (o transcribe precisa do mesmo python3 do Terminal)
    env["PATH"] = os.pathsep.join(dict.fromkeys([p for p in atuais if p] + extra))
    if snd.get("rclone_config") and not env.get("RCLONE_CONFIG"):
        env["RCLONE_CONFIG"] = snd["rclone_config"]
    env.setdefault("LANG", "en_US.UTF-8")
    return env


def destino_padrao() -> str:
    """remoto:pasta a partir do Subir no Drive (ex.: "drive:Gravações IEC")."""
    snd = subir_no_drive()
    if not snd:
        return ""
    return f"{snd['remoto']}:{snd['raiz']}".rstrip("/")


def destino(cfg: dict) -> str:
    return (cfg.get("rclone_destino") or "").strip() or destino_padrao()


# ------------------------------------------------------------------ achar os programas

def _achar(nome: str, escolhido: str, lugares) -> str | None:
    if escolhido:
        return escolhido if Path(escolhido).is_file() else None
    exe = shutil.which(nome, path=ambiente()["PATH"])
    if exe:
        return exe
    for p in lugares:
        if Path(p).is_file() and os.access(p, os.X_OK):
            return p
    return None


def achar(cfg: dict) -> str:
    exe = _achar("rclone", (cfg.get("rclone_exe") or "").strip(), LUGARES_RCLONE)
    if not exe:
        raise ErroRclone("Não achei o rclone neste computador. Em Configurações, informe onde ele está.")
    return exe


def achar_transcribe(cfg: dict) -> str | None:
    return _achar("transcribe", (cfg.get("transcribe_exe") or "").strip(), LUGARES_TRANSCRIBE)


def juntar(base: str, *partes: str) -> str:
    """Monta "remoto:pasta/sub" sem barras duplicadas (o rclone usa / também no Windows)."""
    base = base.rstrip("/")
    resto = "/".join(p.strip("/") for p in partes if p)
    if not resto:
        return base
    return base + resto if base.endswith(":") else f"{base}/{resto}"


# ------------------------------------------------------------------ rodar

def _rodar(exe: str, args: list[str], tempo: int) -> str:
    try:
        r = subprocess.run([exe, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=tempo, env=ambiente())
    except subprocess.TimeoutExpired:
        raise ErroRclone("o rclone demorou demais e foi interrompido")
    except OSError as e:
        raise ErroRclone(f"não consegui rodar o rclone: {e}")
    if r.returncode != 0:
        linhas = [x for x in (r.stderr or r.stdout).strip().splitlines() if x.strip()]
        raise ErroRclone(_amigavel(linhas[-1] if linhas else f"o rclone terminou com erro {r.returncode}"))
    return r.stdout


def _amigavel(msg: str) -> str:
    m = msg.lower()
    if "access_token_scope_insufficient" in m or "insufficient" in m and "scope" in m:
        return "a conexão do rclone só tem permissão de leitura (rode o reconnect, como no Subir no Drive)"
    if "didn't find section in config file" in m or "not found in config" in m:
        return "a conexão do rclone não existe neste computador"
    if "invalid_grant" in m or "token expired" in m:
        return "a autorização do rclone venceu (rode o reconnect, como no Subir no Drive)"
    if "no such host" in m or "dial tcp" in m:
        return "sem internet ou o Drive não respondeu"
    return msg[:300]


def _por_linha(cmd: list[str], ao_ler) -> int:
    """Roda um programa e entrega cada linha da saída (stdout+stderr) para ao_ler, enquanto roda."""
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                         env=ambiente(), encoding="utf-8", errors="replace")
    ultimas: list[str] = []
    for ln in p.stdout:                                   # type: ignore[union-attr]
        for parte in ln.replace("\r", "\n").splitlines():
            parte = parte.strip()
            if parte:
                ultimas = (ultimas + [parte])[-20:]
                ao_ler(parte)
    p.wait()
    _por_linha.ultimas = ultimas                          # type: ignore[attr-defined]
    return p.returncode


_PCT = re.compile(r"Transferred:\s+[\d.]+\s*\S+\s*/\s*[\d.]+\s*\S+,\s*(\d+)%")


def enviar_pasta(exe: str, origem: Path, destino_remoto: str, progresso) -> None:
    """Sobe a pasta inteira (vídeos + SRTs). O que já está igual no Drive não sobe de novo."""
    def ler(linha):
        m = _PCT.search(linha)
        if m:
            progresso(int(m.group(1)))
    cmd = [exe, "copy", str(origem), destino_remoto, "--exclude", ".*", "--exclude", "*.parcial",
           "--transfers", "2", "--drive-chunk-size", "64M", "--retries", "3",
           "--stats", "1s", "--stats-one-line", "-v"]
    try:
        rc = _por_linha(cmd, ler)
    except OSError as e:
        raise ErroRclone(f"não consegui rodar o rclone: {e}")
    if rc != 0:
        ult = [x for x in getattr(_por_linha, "ultimas", []) if "ERROR" in x] or getattr(_por_linha, "ultimas", [])
        raise ErroRclone(_amigavel(ult[-1] if ult else f"o rclone terminou com erro {rc}"))


def listar(exe: str, pasta_remota: str) -> dict[str, int]:
    """{nome: tamanho} dos arquivos que estão na pasta do Drive."""
    saida = _rodar(exe, ["lsjson", "--files-only", pasta_remota], 180)
    try:
        itens = json.loads(saida or "[]")
    except ValueError:
        raise ErroRclone("resposta estranha do rclone ao listar a pasta")
    return {i["Name"]: int(i.get("Size", -1)) for i in itens}


def transcrever(exe: str, pasta: Path, ao_ler) -> None:
    """Roda o `transcribe` do Mac na pasta Footage (um SRT por vídeo + SRT único do dia + tabela)."""
    try:
        rc = _por_linha(["/bin/bash", exe, str(pasta)] if sys.platform != "win32" else [exe, str(pasta)], ao_ler)
    except OSError as e:
        raise ErroRclone(f"não consegui rodar o transcribe: {e}")
    if rc != 0:
        ult = getattr(_por_linha, "ultimas", [])
        raise ErroRclone(f"o transcribe terminou com erro: {ult[-1][:200] if ult else rc}")


def testar(cfg: dict) -> str:
    """Botão "Testar conexão" das Configurações."""
    exe = achar(cfg)
    dest = destino(cfg)
    if ":" not in dest:
        raise ErroRclone("Não sei para onde subir: preencha o destino (ex.: drive:Gravações IEC/Teste Estúdio).")
    remoto = dest.split(":", 1)[0] + ":"
    remotos = _rodar(exe, ["listremotes"], 30).split()
    if remoto not in remotos:
        raise ErroRclone(f"O rclone deste computador não tem a conexão {remoto} (tem: {', '.join(remotos) or 'nenhuma'}).")
    email = ""
    try:
        for ln in _rodar(exe, ["config", "userinfo", remoto], 60).splitlines():
            if ln.strip().lower().startswith("email:"):
                email = ln.split(":", 1)[1].strip()
    except ErroRclone:
        pass
    _rodar(exe, ["mkdir", dest], 60)
    listar(exe, dest)
    return f"Conexão ok: {dest}" + (f" · conta {email}" if email else "")
