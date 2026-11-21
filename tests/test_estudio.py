"""Testes do Estúdio: regras da agenda, vigia, troca de professor, conferência e envio.

Rodar: python3 -m pytest -q tests
"""
import json
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("ESTUDIO_HOME", str(tmp_path / "home"))
    from estudio import appdata, simulador, vigia
    base = tmp_path / "NPD Estudio Teste"
    simulador.preparar(base, estavel_seg=2)
    est = vigia.Estudio()
    return {"base": base, "est": est, "cfg": appdata.carregar(), "sim": simulador}


def _hoje(h, m, s=0):
    return datetime.combine(date.today(), datetime.min.time()).replace(hour=h, minute=m, second=s)


# ------------------------------------------------------------------ regras

def test_regras_da_agenda(app):
    from estudio import agenda as ag
    a = ag.ler(app["cfg"]["agenda"])
    assert a.erro is None and len(a.eventos) == 4
    casos = {
        (7, 12): "Testes",
        (7, 30): "26_101 Ana Souza",       # exatamente 30 min antes já conta
        (7, 41): "26_101 Ana Souza",
        (8, 15): "26_101 Ana Souza",
        (9, 12): "26_101 Ana Souza",       # depois do fim, continua
        (9, 31): "26_102 Bruno Costa",     # janela de 30 min do próximo
        (10, 3): "26_102 Bruno Costa",
        (12, 5): "26_102 Bruno Costa",     # intervalo: continua com o último
        (13, 20): "26_104 Daniel Lima",
        (18, 0): "26_104 Daniel Lima",     # depois do último do dia
    }
    for (h, m), esperado in casos.items():
        assert ag.decidir(_hoje(h, m), a).pasta == esperado, (h, m)
    d = ag.decidir(_hoje(10, 3), a)
    assert "Carla Mendes" in d.aviso
    assert ag.decidir(_hoje(15, 0) - timedelta(days=1), a).pasta == "Sem agenda"


def test_agenda_com_problema(tmp_path):
    from estudio import agenda as ag
    assert ag.ler(tmp_path / "nao-existe.json").erro
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"data": "2026-11-21", "eventos": [{"inicio": "10:00", "fim": "09:00", "professor": "X"}]}))
    assert "fim" in ag.ler(p).erro
    assert ag.decidir(_hoje(10, 0), ag.ler(p)).pasta == "Sem agenda"


def test_nome_do_obs():
    from estudio import agenda as ag
    assert ag.hora_do_nome("2026-09-21 08-35-43.mp4") == datetime(2026, 9, 21, 8, 35, 43)
    assert ag.hora_do_nome("2026-09-21 08-35-43.mkv")
    assert ag.hora_do_nome("2026-09-21 08-35-43 (2).mp4")
    assert ag.hora_do_nome("aula final.mp4") is None
    assert ag.hora_do_nome("2026-09-21 08-35-43.mp4.parcial") is None


# ------------------------------------------------------------------ vigia

def _escrever(pasta, nome, n=1000, minutos=10):
    from estudio import simulador
    p = Path(pasta) / nome
    with open(p, "ab") as f:
        if p.stat().st_size == 0:
            f.write(simulador._cabecalho_mp4(minutos * 60))
        f.write(b"\0" * n)
    return p


def test_so_move_depois_de_parar_de_crescer(app):
    est, cfg = app["est"], app["cfg"]
    nome = f"{date.today().isoformat()} 08-15-00.mp4"
    t0 = time.time()
    _escrever(cfg["pasta_obs"], nome)
    est.ciclo(t0)
    assert [g["arquivo"] for g in est.resumo()["gravando"]] == [nome]
    _escrever(cfg["pasta_obs"], nome)          # ainda crescendo
    est.ciclo(t0 + 1.5)
    est.ciclo(t0 + 3)                          # parado há só 1,5 s (precisa de 2)
    assert (Path(cfg["pasta_obs"]) / nome).exists()
    est.ciclo(t0 + 3.6)
    assert not (Path(cfg["pasta_obs"]) / nome).exists()
    dia = date.today().strftime("%Y %m %d")
    alvo = Path(cfg["pasta_saida"]) / "26_101 Ana Souza" / dia / "Footage" / nome
    assert alvo.is_file()
    r = est.registro[0]
    assert r["pasta"] == "26_101 Ana Souza" and round(r["duracao"]) == 600


def _gravar_e_parar(est, cfg, hora, t):
    nome = f"{hora}.mp4" if hora[:4].isdigit() and len(hora) > 10 else f"{date.today().isoformat()} {hora}.mp4"
    _escrever(cfg["pasta_obs"], nome)
    est.ciclo(t)
    est.ciclo(t + 5)
    return nome


def test_troca_de_professor_e_volta_sozinha(app):
    est, cfg = app["est"], app["cfg"]
    t = time.time()
    # gravação em andamento às 10:03 (agenda escolhe o Bruno); troca para a Carla durante a gravação
    nome = f"{date.today().isoformat()} 10-03-10.mp4"
    _escrever(cfg["pasta_obs"], nome)
    est.ciclo(t)
    assert est.resumo()["gravando"][0]["decisao"]["pasta"] == "26_102 Bruno Costa"
    est.trocar("26_103 Carla Mendes")
    assert est.resumo()["gravando"][0]["decisao"]["pasta"] == "26_103 Carla Mendes"
    est.ciclo(t + 5)
    _gravar_e_parar(est, cfg, "10-38-00", t + 10)
    _gravar_e_parar(est, cfg, "12-05-00", t + 20)
    _gravar_e_parar(est, cfg, "13-20-00", t + 30)
    pastas = [r["pasta"] for r in est.registro]
    assert pastas == ["26_103 Carla Mendes"] * 3 + ["26_104 Daniel Lima"]
    assert est.registro[0]["trocado"] is True


def test_conferencia_mover_e_subir(app):
    est, cfg = app["est"], app["cfg"]
    t = time.time()
    for i, h in enumerate(["07-12-05", "07-41-30", "08-15-00"]):
        _gravar_e_parar(est, cfg, h, t + 10 * i)
    teste = next(r for r in est.registro if r["pasta"] == "Testes")
    with pytest.raises(ValueError):
        est.subir("Testes", teste["dia"])
    est.mover(teste["id"], "26_101 Ana Souza")
    assert not (Path(cfg["pasta_saida"]) / "Testes").exists()     # pasta vazia criada pelo app sai
    grupos = est.grupos()
    assert len(grupos) == 1 and len(grupos[0]["itens"]) == 3
    est.subir("26_101 Ana Souza", teste["dia"])
    for _ in range(50):
        if est.envios[f"26_101 Ana Souza|{teste['dia']}"]["estado"] != "enviando":
            break
        time.sleep(0.1)
    assert est.envios[f"26_101 Ana Souza|{teste['dia']}"]["estado"] == "ok"
    assert all(r["estado"] == "enviado" and r["msg"] == "enviado, pode apagar" for r in est.registro)
    destino = Path(cfg["pasta_envio"]) / "26_101 Ana Souza" / teste["dia"] / "Footage"
    assert sorted(p.name for p in destino.iterdir()) == sorted(r["arquivo"] for r in est.registro)
    assert all(Path(r["caminho"]).is_file() for r in est.registro)   # nada apagado da origem
    with pytest.raises(ValueError):
        est.mover(est.registro[0]["id"], "Testes")                     # enviado não muda mais


def test_registro_fica_salvo(app):
    from estudio import vigia
    est, cfg = app["est"], app["cfg"]
    _gravar_e_parar(est, cfg, "08-15-00", time.time())
    assert len(vigia.Estudio().registro) == 1


def test_mesmo_nome_nao_sobrescreve(app):
    est, cfg = app["est"], app["cfg"]
    t = time.time()
    _gravar_e_parar(est, cfg, "08-15-00", t)
    _gravar_e_parar(est, cfg, "08-15-00", t + 10)
    nomes = sorted(r["arquivo"] for r in est.registro)
    assert nomes[0].endswith("08-15-00 (2).mp4") and nomes[1].endswith("08-15-00.mp4")
