"""Transcrição dentro do app: as regras do transcribe e a leitura do whisper.cpp."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from estudio import transcricao as tr


def _seg(palavras):
    return {"segments": [{"start": palavras[0][0], "end": palavras[-1][1], "text": "",
                          "words": [{"word": w, "start": a, "end": b} for a, b, w in palavras]}]}


def test_frases_iguais_ao_transcribe():
    dados = _seg([(0.0, 0.4, " Olá,"), (0.5, 0.9, " pessoal."), (1.0, 1.3, " Hoje"), (1.4, 1.8, " vamos"),
                  (4.0, 4.5, " começar"), (4.6, 5.0, " agora")])
    frases = tr.frases_do_json(dados)
    assert [f[2] for f in frases] == ["Olá, pessoal.", "Hoje vamos", "começar agora"]   # ponto e pausa > 1,5 s
    assert frases[0][0] == 0.0 and frases[0][1] == 0.9


def test_tira_repeticoes():
    frases = [[0, 1, "E aí"], [1, 2, "E aí"], [2, 3, "e aí!"], [3, 4, "Frase de verdade aqui."]]
    limpas, n = tr.tira_repeticoes(frases)
    assert n == 3 and [f[2] for f in limpas] == ["Frase de verdade aqui."]


def test_whisper_cpp_vira_palavras():
    j = {"transcription": [{"offsets": {"from": 0, "to": 3000}, "text": " Olá, tudo bem?",
                            "tokens": [{"text": "[_BEG_]", "offsets": {"from": 0, "to": 0}},
                                       {"text": " Ol", "offsets": {"from": 100, "to": 300}},
                                       {"text": "á", "offsets": {"from": 300, "to": 500}},
                                       {"text": ",", "offsets": {"from": 500, "to": 520}},
                                       {"text": " tudo", "offsets": {"from": 700, "to": 1000}},
                                       {"text": " bem", "offsets": {"from": 1100, "to": 1400}},
                                       {"text": "?", "offsets": {"from": 1400, "to": 1450}},
                                       {"text": "[_TT_150]", "offsets": {"from": 3000, "to": 3000}}]}]}
    d = tr._cpp_para_segmentos(j)
    ws = d["segments"][0]["words"]
    assert [w["word"] for w in ws] == [" Olá,", " tudo", " bem?"]
    assert ws[0]["start"] == 0.1 and ws[0]["end"] == 0.52
    assert [f[2] for f in tr.frases_do_json(d)] == ["Olá, tudo bem?"]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="sem ffmpeg")
def test_pasta_inteira_com_motor_falso(tmp_path, monkeypatch):
    pasta = tmp_path / "Footage"
    pasta.mkdir()
    for nome, seg in (("2026-11-23 10-00-00.mov", 3), ("2026-11-23 10-20-00.mov", 2)):
        subprocess.run(["ffmpeg", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seg}", "-c:a", "aac",
                        str(pasta / nome), "-y", "-loglevel", "quiet"], check=True)
    monkeypatch.setattr(tr, "motor", lambda: {"nome": "falso", "ok": True, "falta": []})
    monkeypatch.setattr(tr, "ffmpeg", lambda: shutil.which("ffmpeg"))
    falso = lambda wav, *a: _seg([(0.2, 0.6, " Bom"), (0.7, 1.0, " dia.")])   # noqa: E731
    monkeypatch.setattr(tr, "_mlx", falso)
    monkeypatch.setattr(tr, "_cpp", falso)
    assert tr.main([str(pasta)]) == 0
    srt = (pasta / "2026-11-23 10-00-00.srt").read_text(encoding="utf-8")
    assert "00:00:00,200 --> 00:00:01,000\nBom dia." in srt
    unico = (pasta / "SRT unico - Footage.srt").read_text(encoding="utf-8")
    assert "[ARQUIVO: 2026-11-23 10-00-00]" in unico and "[ARQUIVO: 2026-11-23 10-20-00]" in unico
    tabela = (pasta / "SRT unico - tabela.txt").read_text(encoding="utf-8")
    assert "2026-11-23 10-20-00\t00:01:00,000\t00:01:02,000" in tabela     # próximo minuto cheio depois de 3 s + 30 s


def test_comando_de_transcricao_pelo_python(monkeypatch):
    from estudio import rclone
    monkeypatch.setattr(rclone, "_achar", lambda *a: None)
    monkeypatch.setattr(tr, "motor", lambda: {"nome": "falso", "ok": True, "falta": []})
    cmd, desc = rclone.comando_transcricao({})
    assert cmd[-2:] == ["estudio", "transcrever"] and "falso" in desc
