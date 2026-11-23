"""Transcrição das aulas dentro do app — as mesmas regras do `transcribe` do JP (versão de 20/11/2026).

Para cada vídeo: "<nome do vídeo>.srt" ao lado dele, uma legenda por frase, com tempos por palavra.
Com 2 ou mais vídeos na pasta: "SRT unico - <nome da pasta>.srt" (separadores [ARQUIVO: ...]) e
"SRT unico - tabela.txt" (onde cada vídeo começa no SRT único).

Dois motores, o mesmo modelo (Whisper large-v3-turbo):
  Mac (chip Apple, macOS 13.5+): mlx-whisper — igual ao `transcribe` de hoje.
  Windows e Mac com macOS mais antigo: whisper.cpp (com a placa de vídeo no Mac) — pode haver pequenas
  diferenças no texto.
O ffmpeg (para tirar o áudio do vídeo) vai dentro do app (imageio-ffmpeg).

Linha de comando: python -m estudio transcrever <pasta ou vídeos…>   (no app: "Estudio transcrever …")
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import wave
from pathlib import Path

VIDEOS = (".mp4", ".mov", ".mkv", ".m4v", ".avi", ".mxf")
MODELO_MLX = "whisper-large-v3-turbo"                 # pasta do modelo dentro do app (Mac)
MODELO_CPP = "ggml-large-v3-turbo-q8_0.bin"           # arquivo do modelo dentro do app (Windows)

# Regras para montar as frases (iguais ao transcribe)
PAUSA_QUEBRA = 1.5     # pausa (s) entre palavras que encerra a frase mesmo sem pontuação
LIMITE_SUAVE = 25.0    # depois disso, quebra na próxima vírgula ou ponto e vírgula
LIMITE_DURO = 40.0     # nunca deixa uma legenda passar disso


def _p(*a):
    try:
        print(*a, flush=True)
    except UnicodeEncodeError:
        print(*(str(x).encode("ascii", "replace").decode() for x in a), flush=True)


# ====================================================================== onde estão as coisas

def _recursos() -> Path:
    """Pasta dos arquivos que vão dentro do app (ou a pasta do projeto, rodando pelo Python)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def modelo_mlx() -> Path | None:
    for base in (_recursos() / "modelos", Path(os.environ.get("ESTUDIO_MODELOS", "")) if os.environ.get("ESTUDIO_MODELOS") else None):
        if base and (base / MODELO_MLX / "config.json").is_file():
            return base / MODELO_MLX
    return None


def modelo_cpp() -> Path | None:
    for base in (_recursos() / "modelos", Path(os.environ.get("ESTUDIO_MODELOS", "")) if os.environ.get("ESTUDIO_MODELOS") else None):
        if base and (base / MODELO_CPP).is_file():
            return base / MODELO_CPP
    return None


def whisper_cli() -> str | None:
    for nome in ("whisper-cli.exe", "whisper-cli", "main.exe"):
        p = _recursos() / "whisper" / nome
        if p.is_file():
            return str(p)
    return shutil.which("whisper-cli")


def ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).is_file():
            return exe
    except Exception:  # noqa: BLE001 — sem o pacote, procura no sistema
        pass
    return shutil.which("ffmpeg")


def _tem_mlx() -> bool:
    if sys.platform != "darwin":
        return False
    try:
        import mlx_whisper  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _usa_mlx() -> bool:
    """Mac com o mlx-whisper e o modelo dele dentro do app (macOS 13.5+). Senão, whisper.cpp."""
    return sys.platform == "darwin" and modelo_mlx() is not None and _tem_mlx()


def motor() -> dict:
    """Qual motor de transcrição este computador tem dentro do app. {"nome", "ok", "falta", "tipo"}"""
    falta = []
    if not ffmpeg():
        falta.append("ffmpeg")
    if _usa_mlx():
        return {"nome": "mlx-whisper (large-v3-turbo)", "ok": not falta, "falta": falta, "tipo": "mlx"}
    if sys.platform == "darwin" and modelo_mlx() is not None:      # rodando pelo Python, sem o mlx instalado
        falta.append("mlx-whisper")
        return {"nome": "mlx-whisper (large-v3-turbo)", "ok": False, "falta": falta, "tipo": "mlx"}
    if not whisper_cli():
        falta.append("whisper.cpp")
    if not modelo_cpp():
        falta.append("modelo do Whisper")
    return {"nome": "whisper.cpp (large-v3-turbo q8)", "ok": not falta, "falta": falta, "tipo": "cpp"}


# ====================================================================== regras do transcribe (iguais)

def tempo_srt(s):
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def normaliza(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return " ".join(re.findall(r"[a-z0-9]+", t))


def limpa_texto(t):
    t = re.sub(r"\s+", " ", t).strip()
    return t.lstrip("!").strip()


def acha_videos(caminho):
    caminho = str(caminho)
    if os.path.isfile(caminho):
        return [caminho] if caminho.lower().endswith(VIDEOS) else []
    achados = []
    for raiz, pastas, arquivos in os.walk(caminho):
        pastas[:] = sorted(p for p in pastas if not p.startswith("."))
        for a in sorted(arquivos):
            if a.startswith(".") or a.startswith("._"):
                continue
            if a.lower().endswith(VIDEOS) and "_temp" not in a:
                achados.append(os.path.join(raiz, a))
    return achados


def frases_do_json(dados):
    """Junta as palavras do Whisper em frases completas, com o tempo exato da 1ª e da última palavra."""
    palavras = []
    for seg in dados.get("segments", []):
        ws = seg.get("words") or []
        if ws:
            for w in ws:
                txt = w.get("word", "")
                if txt.strip():
                    palavras.append((float(w["start"]), float(w["end"]), txt))
        elif seg.get("text", "").strip():
            # segmento sem palavras: entra inteiro como um bloco
            palavras.append((float(seg["start"]), float(seg["end"]), " " + seg["text"].strip() + "."))
    frases, atual = [], []
    for i, (a, b, txt) in enumerate(palavras):
        atual.append((a, b, txt))
        ini = atual[0][0]
        fim_palavra = txt.strip().rstrip("\"'”»)")
        prox = palavras[i + 1][0] if i + 1 < len(palavras) else None
        dur = b - ini
        quebra = (
            re.search(r"[.?!…]$", fim_palavra)
            or (prox is not None and prox - b > PAUSA_QUEBRA)
            or (dur > LIMITE_SUAVE and re.search(r"[,;:]$", fim_palavra))
            or dur > LIMITE_DURO
            or prox is None
        )
        if quebra:
            texto = limpa_texto("".join(t for _, _, t in atual))
            if texto:
                frases.append([atual[0][0], max(atual[-1][1], atual[0][0] + 0.2), texto])
            atual = []
    return frases


def tira_repeticoes(frases):
    """3 ou mais frases curtas (até 3 palavras) e idênticas em sequência = alucinação do Whisper."""
    limpas, i, removidas = [], 0, 0
    while i < len(frases):
        j = i
        while j + 1 < len(frases) and normaliza(frases[j + 1][2]) == normaliza(frases[i][2]):
            j += 1
        n = j - i + 1
        if n >= 3 and len(frases[i][2].split()) <= 3:
            removidas += n
        else:
            limpas.extend(frases[i:j + 1])
        i = j + 1
    return limpas, removidas


def escreve_srt(caminho, frases):
    linhas = []
    for n, (a, b, t) in enumerate(frases, 1):
        linhas += [str(n), f"{tempo_srt(a)} --> {tempo_srt(b)}", t, ""]
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))


def srt_unico(pasta, resultados):
    """Junta tudo em um SRT, cada vídeo começando num minuto cheio, com separador e 2 s de folga."""
    nome_pasta = os.path.basename(os.path.normpath(pasta))
    saida, tabela, inicio = [], [], 0.0
    for r in resultados:
        fala = inicio + 2.0
        saida.append([inicio, inicio + 1.0, f"[ARQUIVO: {r['nome']}]"])
        for a, b, t in r["frases"]:
            saida.append([a + fala, b + fala, t])
        tabela.append((r["nome"], inicio, fala))
        fim = r["duracao"] or (r["frases"][-1][1] if r["frases"] else 0.0)
        inicio = math.ceil((fala + fim + 30.0) / 60.0) * 60.0
    caminho = os.path.join(pasta, f"SRT unico - {nome_pasta}.srt")
    escreve_srt(caminho, saida)
    with open(os.path.join(pasta, "SRT unico - tabela.txt"), "w", encoding="utf-8") as f:
        f.write(f"SRT único: {os.path.basename(caminho)}\n")
        f.write("Para separar: subtraia de cada tempo o início da fala do vídeo correspondente.\n\n")
        f.write("Vídeo\tSeparador em\tFala começa em\n")
        for nome, sep, fala in tabela:
            f.write(f"{nome}\t{tempo_srt(sep)}\t{tempo_srt(fala)}\n")
    _p(f"\n★ SRT único: {os.path.basename(caminho)}")
    for nome, sep, fala in tabela:
        _p(f"   {nome}  → começa em {tempo_srt(fala)}")


# ====================================================================== os dois motores

def _ler_wav(wav: str):
    """Áudio 16 kHz mono em números (o mlx-whisper recebe o áudio pronto, sem chamar o ffmpeg)."""
    import numpy as np
    with wave.open(wav, "rb") as w:
        dados = w.readframes(w.getnframes())
    return np.frombuffer(dados, np.int16).flatten().astype(np.float32) / 32768.0


def _duracao_wav(wav: str) -> float | None:
    try:
        with wave.open(wav, "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except (OSError, wave.Error):
        return None


def _mlx(wav: str) -> dict:
    """Igual ao transcribe (o mlx-whisper guarda o modelo carregado entre um vídeo e outro)."""
    import mlx_whisper
    if os.environ.get("ESTUDIO_MLX_CPU"):            # computador sem Metal (ex.: o teste no GitHub)
        import mlx.core as mx
        mx.set_default_device(mx.cpu)
    return mlx_whisper.transcribe(
        _ler_wav(wav), path_or_hf_repo=str(modelo_mlx()), language="pt", condition_on_previous_text=False,
        word_timestamps=True, hallucination_silence_threshold=2, verbose=None)


def _cpp_para_segmentos(j: dict) -> dict:
    """JSON completo do whisper.cpp (-ojf) → o mesmo formato do mlx-whisper (segmentos com palavras)."""
    segs = []
    for s in j.get("transcription", []):
        palavras, atual = [], None
        for t in s.get("tokens") or []:
            txt = t.get("text", "")
            off = t.get("offsets")
            if txt.startswith("[_") or not off:            # [_BEG_], [_TT_…] e outros tokens especiais
                continue
            ini, fim = off["from"] / 1000.0, off["to"] / 1000.0
            if atual is None or txt.startswith(" "):
                if atual:
                    palavras.append(atual)
                atual = {"word": txt, "start": ini, "end": fim}
            else:                                          # pedaço da mesma palavra (ou pontuação colada)
                atual["word"] += txt
                atual["end"] = fim
        if atual:
            palavras.append(atual)
        off = s.get("offsets") or {}
        segs.append({"start": off.get("from", 0) / 1000.0, "end": off.get("to", 0) / 1000.0,
                     "text": s.get("text", ""), "words": palavras})
    return {"segments": segs}


def _cpp(wav: str, tmp: str) -> dict:
    base = os.path.join(tmp, "audio")
    cmd = [whisper_cli(), "-m", str(modelo_cpp()), "-f", wav, "-l", "pt", "-mc", "0", "-ojf", "-of", base,
           "-t", str(max(1, (os.cpu_count() or 4) - 1)), "-pp", "-np"]
    if os.environ.get("ESTUDIO_CPP_SEM_GPU"):           # computador sem placa de vídeo útil (ex.: o teste no GitHub)
        cmd.append("-ng")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                         errors="replace", **_sem_janela())
    ultimas = []
    for ln in p.stdout:                                 # type: ignore[union-attr]
        ln = ln.strip()
        m = re.search(r"progress\s*=\s*(\d+)%", ln)
        if m:
            _p(f"  Transcrevendo... {m.group(1)}%")
        elif ln:
            ultimas = (ultimas + [ln])[-5:]
    p.wait()
    js = base + ".json"
    if p.returncode != 0 or not os.path.exists(js):
        raise RuntimeError(f"whisper.cpp falhou ({p.returncode}): {' | '.join(ultimas)[:300]}")
    with open(js, encoding="utf-8", errors="replace") as f:
        dados = json.load(f)
    os.remove(js)
    return _cpp_para_segmentos(dados)


def _sem_janela() -> dict:
    """Windows: não abrir janela preta para cada programa chamado."""
    if os.name == "nt":
        return {"creationflags": 0x08000000}           # CREATE_NO_WINDOW
    return {}


# ====================================================================== transcrever

def transcreve(video, tmp):
    base = os.path.splitext(os.path.basename(video))[0]
    wav = os.path.join(tmp, "audio.wav")
    _p(f"\n▶ {os.path.basename(video)}")
    _p("  Extraindo áudio...")
    r = subprocess.run([ffmpeg(), "-i", video, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                        wav, "-y", "-loglevel", "quiet"], **_sem_janela())
    if r.returncode != 0 or not os.path.exists(wav):
        _p("  ERRO: não consegui extrair o áudio deste arquivo. Pulando.")
        return None
    _p("  Transcrevendo...")
    try:
        dados = _mlx(wav) if _usa_mlx() else _cpp(wav, tmp)
    except Exception as e:  # noqa: BLE001
        _p(f"  ERRO: a transcrição falhou neste arquivo ({e}). Pulando.")
        return None
    dur = _duracao_wav(wav)
    os.remove(wav)
    frases, removidas = tira_repeticoes(frases_do_json(dados))
    srt = os.path.join(os.path.dirname(video), base + ".srt")
    escreve_srt(srt, frases)
    msg = f"  Pronto: {base}.srt ({len(frases)} frases)"
    if removidas:
        msg += f" — removidas {removidas} repetições do Whisper"
    _p(msg)
    return {"nome": base, "frases": frases, "duracao": dur}


def main(entradas: list[str]) -> int:
    m = motor()
    if not m["ok"]:
        _p(f"Erro: falta {', '.join(m['falta'])} para transcrever neste computador.")
        return 1
    if sys.platform == "darwin":
        os.environ.setdefault("NUMBA_CACHE_DIR", str(Path(tempfile.gettempdir()) / "estudio-numba"))
    _p(f"Transcrição: {m['nome']}")
    tmp = tempfile.mkdtemp(prefix="transcribe_")
    falhas = 0
    try:
        for entrada in [os.path.expanduser(a) for a in entradas]:
            if not os.path.exists(entrada):
                _p(f"\nErro: não encontrei {entrada}")
                falhas += 1
                continue
            videos = acha_videos(entrada)
            if not videos:
                _p(f"\nNenhum vídeo em: {entrada}")
                continue
            if os.path.isdir(entrada):
                _p(f"\nPasta {os.path.basename(os.path.normpath(entrada))}: {len(videos)} vídeo(s)")
            resultados = [r for r in (transcreve(v, tmp) for v in videos) if r]
            falhas += len(videos) - len(resultados)
            if os.path.isdir(entrada) and len(resultados) >= 2:
                srt_unico(entrada, resultados)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    _p("\nConcluído." if not falhas else f"\nConcluído com {falhas} vídeo(s) sem transcrição.")
    return 0 if not falhas else 2
