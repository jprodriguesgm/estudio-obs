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


# ------------------------------------------------------------------ um botão só: transcreve, sobe pelo rclone e confere

FALSOS = Path(__file__).parent / "falsos"


def _esperar(est, k):
    for _ in range(100):
        if est.envios[k]["estado"] not in ("transcrevendo", "enviando", "conferindo"):
            return est.envios[k]
        time.sleep(0.1)
    raise AssertionError("o envio não terminou")


def test_botao_unico_transcreve_sobe_e_confere(app, tmp_path, monkeypatch):
    from estudio import appdata, rclone
    snd = tmp_path / "SubirNoDrive"
    snd.mkdir()
    (snd / "config.txt").write_text("drive\nGravações IEC\niec@pucminas.br\n", encoding="utf-8")
    (snd / "env.sh").write_text(f'export PATH="{FALSOS}:$PATH"\n', encoding="utf-8")
    monkeypatch.setenv("SUBIR_NO_DRIVE_HOME", str(snd))
    monkeypatch.setenv("FAKE_DRIVE", str(tmp_path / "drive"))
    appdata.salvar({"envio_modo": "rclone", "transcrever": True, "transcribe_exe": str(FALSOS / "transcribe")})
    assert rclone.destino(appdata.carregar()) == "drive:Gravações IEC"
    assert "iec@pucminas.br" in rclone.testar(appdata.carregar())
    est, cfg = app["est"], appdata.carregar()
    t = time.time()
    _gravar_e_parar(est, cfg, "08-15-00", t)
    _gravar_e_parar(est, cfg, "08-40-00", t + 10)
    dia = est.registro[0]["dia"]
    est.subir("26_101 Ana Souza", dia)
    env = _esperar(est, f"26_101 Ana Souza|{dia}")
    assert env["estado"] == "ok", env
    assert "2 arquivo(s) de transcrição" not in env["msg"] and "transcrição" in env["msg"]
    no_drive = tmp_path / "drive" / "Gravações IEC" / "26_101 Ana Souza" / dia / "Footage"
    nomes = sorted(p.name for p in no_drive.iterdir())
    assert any(n.endswith("08-15-00.srt") for n in nomes) and "SRT unico - Footage.srt" in nomes
    assert len([n for n in nomes if n.endswith(".mp4")]) == 2
    assert all(r["estado"] == "enviado" for r in est.registro)
    # segunda vez: já transcrito, não roda o transcribe de novo
    assert not est._precisa_transcrever(Path(est.registro[0]["caminho"]).parent)


def test_erro_do_rclone_nao_marca_como_enviado(app, tmp_path, monkeypatch):
    from estudio import appdata
    monkeypatch.setenv("SUBIR_NO_DRIVE_HOME", str(tmp_path / "nada"))
    monkeypatch.setenv("FAKE_DRIVE", str(tmp_path / "drive"))
    monkeypatch.setenv("PATH", f"{FALSOS}:" + os.environ["PATH"])
    appdata.salvar({"envio_modo": "rclone", "rclone_destino": "outra:Pasta", "transcrever": False})
    est, cfg = app["est"], appdata.carregar()
    _gravar_e_parar(est, cfg, "08-15-00", time.time())
    dia = est.registro[0]["dia"]
    est.subir("26_101 Ana Souza", dia)
    env = _esperar(est, f"26_101 Ana Souza|{dia}")
    assert env["estado"] == "erro" and "não existe" in env["msg"]
    assert est.registro[0]["estado"] == "erro"
    assert Path(est.registro[0]["caminho"]).is_file()


# ------------------------------------------------------------------ Pastas do dia: agenda → professor → gravar

def _dados_pd():
    return {"dia": date.today().strftime("%Y %m %d"), "ano": "26", "gravacoes": [
        {"id": "a1", "hora": "08:00–09:00", "tipo": "TP", "professor": "Jorge Augusto", "curso": "C", "disciplina": "D",
         "cancelada": False, "candidatos": [{"codigo": "26_824", "nota": 3,
                                              "pasta": {"id": "P824", "nome": "26_824 Jorge Augusto Pereira"}}]},
        {"id": "b2", "hora": "10:00–11:00", "tipo": "TV", "professor": "Bruno Chiriu", "curso": "C", "disciplina": "E",
         "cancelada": False, "candidatos": [{"codigo": "26_646", "nota": 2, "pasta": None},
                                             {"codigo": "26_714", "nota": 2, "pasta": {"id": "P714", "nome": "26_714 Bruno da Silva Chiriu"}}]},
        {"id": "c3", "hora": "13:00–14:00", "tipo": "TP", "professor": "Fulano", "curso": "", "disciplina": "",
         "cancelada": True, "candidatos": []},
    ]}


@pytest.fixture()
def pd(app, monkeypatch):
    from estudio import appdata, pastas_do_dia
    chamadas = []

    def falso(url, params, tempo=90):
        chamadas.append(params)
        if params["acao"] == "carregar":
            return _dados_pd()
        if params["acao"] == "criar":
            return {"url": f"https://drive/{params['pasta']}/{params['data']}", "jaExistia": False}
        return {}
    monkeypatch.setattr(pastas_do_dia, "_chamar", falso)
    appdata.salvar({"pastas_do_dia_url": "https://script.google.com/macros/s/X/exec"})
    app["est"].atualizar_agenda(esperar=True)
    return chamadas


def test_agenda_do_pastas_do_dia(app, pd):
    a = app["est"].agenda()
    assert a.fonte == "pastas do dia" and len(a.eventos) == 2 and len(a.canceladas) == 1
    jorge, bruno = a.eventos
    assert jorge.pasta == "26_824 Jorge Augusto Pereira"          # nome da pasta do Drive
    assert bruno.codigo == "26_714" and bruno.pasta_id == "P714"   # empate: prefere o que tem pasta
    assert "Mais de um código" in bruno.aviso
    from estudio import agenda as ag
    assert ag.decidir(_hoje(8, 15), a).pasta == "26_824 Jorge Augusto Pereira"
    # a cópia guardada serve se a internet cair
    from estudio import vigia
    assert vigia.Estudio().pd["dados"]["gravacoes"][0]["id"] == "a1"


def test_gravar_com_este_professor(app, pd, monkeypatch):
    from estudio import vigia
    est, cfg = app["est"], app["cfg"]
    monkeypatch.setattr(vigia, "_agora", lambda: _hoje(8, 20))    # no horário do Jorge
    r = est.selecionar("b2")                                       # mas quem chegou foi o Bruno
    assert r["avisos"] == []
    dia = date.today().strftime("%Y %m %d")
    base = Path(cfg["pasta_saida"]) / "26_714 Bruno da Silva Chiriu" / dia
    assert (base / "Footage").is_dir() and (base / "Originais").is_dir()
    assert {"acao": "criar", "pasta": "P714", "data": date.today().isoformat()} in pd
    assert est.sessao == "b2" and est.resumo()["sessao"]["evento"]["pasta_dia_url"].startswith("https://drive/P714")
    _gravar_e_parar(est, cfg, "08-21-00", time.time())
    assert est.registro[-1]["pasta"] == "26_714 Bruno da Silva Chiriu"
    # voltar para a agenda e escolher o professor do horário: a troca some
    est.voltar_agenda()
    est.selecionar("a1")
    assert est.troca is None
    _gravar_e_parar(est, cfg, "08-40-00", time.time() + 10)
    assert est.registro[-1]["pasta"] == "26_824 Jorge Augusto Pereira"


def test_trocar_codigo_do_professor(app, pd):
    est = app["est"]
    est.escolhas_codigo["b2"] = 0
    b = est.agenda().evento("b2")
    assert b.codigo == "26_646" and b.pasta == "26_646 Bruno Chiriu" and "não encontrada" in b.aviso


def test_agenda_de_outro_dia(app, pd, monkeypatch):
    """Escolher um professor na agenda de amanhã: a gravação de hoje vai para a pasta do dia da agenda."""
    from estudio import vigia
    est, cfg = app["est"], app["cfg"]
    amanha = date.today() + timedelta(days=1)
    est.mudar_dia(amanha)
    est.atualizar_agenda(esperar=True)
    a = est.agenda()
    assert a.data == amanha and {"acao": "carregar", "data": amanha.isoformat()} in pd
    est.selecionar("a1")
    dia = amanha.strftime("%Y %m %d")
    assert {"acao": "criar", "pasta": "P824", "data": amanha.isoformat()} in pd
    _gravar_e_parar(est, cfg, time.strftime("%H-%M-%S"), time.time())
    r = est.registro[-1]
    assert r["pasta"] == "26_824 Jorge Augusto Pereira" and r["dia"] == dia
    assert (Path(cfg["pasta_saida"]) / r["pasta"] / dia / "Footage" / r["arquivo"]).is_file()
    est.mudar_dia(None)
    assert est.dia_agenda is None


def test_sobe_direto_na_pasta_do_dia_criada(app, pd, tmp_path, monkeypatch):
    """Mesmo com o destino errado nas Configurações, vai para a pasta do dia que o Pastas do dia criou."""
    from estudio import appdata, pastas_do_dia, vigia
    monkeypatch.setenv("SUBIR_NO_DRIVE_HOME", str(tmp_path / "nada"))
    monkeypatch.setenv("FAKE_DRIVE", str(tmp_path / "drive"))
    monkeypatch.setenv("PATH", f"{FALSOS}:" + os.environ["PATH"])
    monkeypatch.setattr(pastas_do_dia, "_chamar", lambda url, p, tempo=90: (
        _dados_pd() if p["acao"] == "carregar" else
        {"url": "https://drive.google.com/drive/folders/1ABCdefGHIjklMNOpqr"} if p["acao"] == "criar" else {}))
    appdata.salvar({"envio_modo": "rclone", "rclone_destino": "drive:Gravações IEC/26_999 Teste", "transcrever": False})
    est, cfg = app["est"], appdata.carregar()
    monkeypatch.setattr(vigia, "_agora", lambda: _hoje(8, 20))
    est.selecionar("a1")
    _gravar_e_parar(est, cfg, "08-21-00", time.time())
    r = est.registro[-1]
    est.subir(r["pasta"], r["dia"])
    env = _esperar(est, f"{r['pasta']}|{r['dia']}")
    assert env["estado"] == "ok", env
    assert (tmp_path / "drive" / "_id_1ABCdefGHIjklMNOpqr" / "Footage" / r["arquivo"]).is_file()
    assert not (tmp_path / "drive" / "Gravações IEC").exists()
    assert vigia.Estudio().pastas_drive[f"{r['pasta']}|{r['dia']}"] == "1ABCdefGHIjklMNOpqr"


def test_tirar_da_lista_nao_apaga_arquivo(app):
    est, cfg = app["est"], app["cfg"]
    _gravar_e_parar(est, cfg, "07-12-05", time.time())
    r = est.registro[0]
    assert est.esquecer_grupo(r["pasta"], r["dia"]) == 1
    assert est.grupos() == [] and Path(r["caminho"]).is_file()
