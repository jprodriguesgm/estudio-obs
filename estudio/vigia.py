"""O vigia da pasta do OBS, o registro das gravações do dia, a conferência e o envio.

Como funciona:
  1. A cada segundo, olha a pasta do OBS. Arquivo com nome no padrão do OBS que está crescendo = "gravando".
  2. Quando o arquivo fica X segundos sem crescer (estavel_seg), a gravação terminou: o app decide o
     professor pela hora do nome (agenda.decidir, ou a troca feita na janelinha) e move para
     <saída>/<26_xxx Professor>/<AAAA MM DD>/Footage/.
  3. Cada gravação movida entra no registro (registro.json na pasta do app). Na conferência, dá para
     mover entre professores. "Conferido, pode subir" copia para a pasta de envio e confere nome e
     tamanho de cada arquivo. Nada é apagado pelo app.
"""
from __future__ import annotations

import json
import shutil
import threading
import time
import uuid
from datetime import date, datetime
from pathlib import Path

from . import agenda as ag
from . import appdata, mp4info, pastas_do_dia, rclone


def _agora() -> datetime:
    return datetime.now()


def aberto_por_outro(p: Path) -> bool:
    """Mac/Linux: o arquivo ainda está aberto por algum programa (o OBS gravando)? Usa o lsof do sistema.

    Segurança extra para o caso de o OBS ficar alguns segundos sem escrever no meio da gravação.
    No Windows não precisa: lá o arquivo aberto pelo OBS não deixa ser movido (o app tenta de novo).
    Sem lsof, responde False (fica só a regra dos segundos parado).
    """
    import os
    import shutil as _sh
    import subprocess
    if os.name == "nt":
        return False
    exe = _sh.which("lsof") or ("/usr/sbin/lsof" if Path("/usr/sbin/lsof").is_file() else None)
    if not exe:
        return False
    try:
        r = subprocess.run([exe, "-t", "--", str(p)], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(r.stdout.strip())


class Estudio:
    def __init__(self):
        self.lock = threading.RLock()
        self.vistos: dict[str, dict] = {}       # nome → {"tam", "mtime", "mudou"} (arquivos na pasta do OBS)
        self.erros: dict[str, str] = {}         # nome → motivo de não ter conseguido mover (tenta de novo)
        self.troca: dict | None = None          # {"chave", "pasta", "dia"}: vale enquanto a agenda apontar a mesma chave
        self.envios: dict[str, dict] = {}       # "pasta|dia" → andamento do envio
        self.pd: dict = self._carregar_cache_pd()  # agenda do Pastas do dia: {"data", "dados", "quando", "erro", "carregando"}
        self.escolhas_codigo: dict[str, int] = {}  # id do evento → índice do código escolhido
        self.pasta_dia_urls: dict[str, str] = {}   # id do evento → link da pasta do dia no Drive (depois de criar)
        self.sessao: str | None = None            # id do evento aberto na tela do professor
        self.registro: list[dict] = self._carregar_registro()
        self.ultimo_ciclo: float = 0.0
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()

    # ------------------------------------------------------------------ registro (fica salvo)

    @staticmethod
    def _arq_registro() -> Path:
        return appdata.home() / "registro.json"

    def _carregar_registro(self) -> list[dict]:
        try:
            return json.loads(self._arq_registro().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def _salvar_registro(self):
        tmp = self._arq_registro().with_suffix(".tmp")
        tmp.write_text(json.dumps(self.registro, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self._arq_registro())

    def _entrada(self, id_: str) -> dict:
        for r in self.registro:
            if r["id"] == id_:
                return r
        raise KeyError("Gravação não encontrada no registro.")

    # ------------------------------------------------------------------ decisão

    # ------------------------------------------------------------------ agenda (arquivo .json ou Pastas do dia)

    @staticmethod
    def _arq_cache_pd() -> Path:
        return appdata.home() / "agenda-pastas-do-dia.json"

    def _carregar_cache_pd(self) -> dict:
        """Última agenda que veio do Pastas do dia (serve quando a internet cai)."""
        try:
            c = json.loads(self._arq_cache_pd().read_text(encoding="utf-8"))
            return {"data": c["data"], "dados": c["dados"], "quando": c["quando"], "erro": None, "carregando": False}
        except (OSError, ValueError, KeyError):
            return {"data": None, "dados": None, "quando": 0, "erro": None, "carregando": False}

    def atualizar_agenda(self, cfg: dict | None = None, esperar: bool = False):
        """Busca a agenda de hoje no Pastas do dia (em segundo plano; demora alguns segundos)."""
        cfg = cfg or appdata.carregar()
        url = (cfg.get("pastas_do_dia_url") or "").strip()
        if not url or self.pd.get("carregando"):
            return
        hoje = _agora().date().isoformat()
        self.pd["carregando"] = True

        def buscar():
            try:
                dados = pastas_do_dia.carregar(url, hoje)
                with self.lock:
                    self.pd.update(data=hoje, dados=dados, quando=time.time(), erro=None)
                try:
                    self._arq_cache_pd().write_text(json.dumps({"data": hoje, "dados": dados, "quando": time.time()},
                                                               ensure_ascii=False), encoding="utf-8")
                except OSError:
                    pass
            except pastas_do_dia.ErroPastas as e:
                with self.lock:
                    self.pd.update(erro=str(e), quando=time.time())
            finally:
                self.pd["carregando"] = False

        if esperar:
            buscar()
        else:
            threading.Thread(target=buscar, daemon=True).start()

    def agenda(self, cfg: dict | None = None) -> ag.Agenda:
        cfg = cfg or appdata.carregar()
        url = (cfg.get("pastas_do_dia_url") or "").strip()
        if not url:
            return ag.ler(cfg.get("agenda"))
        hoje = _agora().date()
        pd = self.pd
        velha = time.time() - (pd.get("quando") or 0) > 15 * 60
        if (pd.get("data") != hoje.isoformat() or velha) and not pd.get("carregando"):
            self.atualizar_agenda(cfg)
        if pd.get("dados") is not None and pd.get("data") == hoje.isoformat():
            a = ag.de_pastas_do_dia(pd["dados"], hoje, self.escolhas_codigo)
            for e in a.eventos:
                if e.id in self.pasta_dia_urls:
                    e.pasta_dia_url = self.pasta_dia_urls[e.id]
            hora = datetime.fromtimestamp(pd["quando"]).strftime("%H:%M") if pd.get("quando") else ""
            a.info = (f"sem conexão com o Pastas do dia ({pd['erro']}); usando a cópia das {hora}" if pd.get("erro")
                      else f"Pastas do dia · atualizada às {hora}")
            return a
        if pd.get("carregando") or pd.get("data") != hoje.isoformat() and not pd.get("erro"):
            return ag.Agenda(hoje, carregando=True, fonte="pastas do dia", info="carregando a agenda do Pastas do dia…")
        return ag.Agenda(erro=f"Não consegui ler a agenda do Pastas do dia: {pd.get('erro')}", fonte="pastas do dia")

    # ------------------------------------------------------------------ escolher o professor na agenda

    def selecionar(self, evento_id: str, codigo: int | None = None) -> dict:
        """"Gravar com este professor": cria as pastas (Drive e local) e manda as próximas gravações para ele.

        Funciona como o "Trocar professor": vale a partir de agora, até a agenda chegar ao horário de outro
        professor (aí volta a seguir o horário sozinho).
        """
        cfg = appdata.carregar()
        with self.lock:
            if codigo is not None:
                self.escolhas_codigo[evento_id] = int(codigo)
            a = self.agenda(cfg)
            e = a.evento(evento_id)
            if e is None:
                raise ValueError("Esse horário não está mais na agenda. Atualize a agenda.")
            dia = ag.pasta_dia(a.data)
            avisos = []
            saida = cfg.get("pasta_saida")
            if saida and Path(saida).is_dir():
                for sub in ("Footage", "Originais"):
                    (Path(saida) / e.pasta / dia / sub).mkdir(parents=True, exist_ok=True)
            else:
                avisos.append("pasta de saída não configurada")
        url = (cfg.get("pastas_do_dia_url") or "").strip()
        if url and e.pasta_id:
            try:
                r = pastas_do_dia.criar(url, e.pasta_id, a.data.isoformat())
                if r.get("url"):
                    self.pasta_dia_urls[evento_id] = r["url"]
            except pastas_do_dia.ErroPastas as erro:
                avisos.append(f"não consegui criar a pasta no Drive ({erro}); o envio cria na hora de subir")
        elif url:
            avisos.append("pasta do professor não encontrada no Drive; o envio cria uma com este nome")
        with self.lock:
            self.trocar(e.pasta)
            self.sessao = evento_id
        return {"pasta": e.pasta, "avisos": avisos}

    def voltar_agenda(self):
        self.sessao = None

    def decidir(self, quando: datetime, agenda: ag.Agenda, cfg: dict) -> ag.Decisao:
        d = ag.decidir(quando, agenda, int(cfg.get("antecedencia_min") or 30))
        t = self.troca
        if t and t["chave"] == d.chave and t["dia"] == quando.date().isoformat() and t["pasta"] != d.pasta:
            return ag.Decisao(t["pasta"], f"escolhido à mão (pelo horário seria {d.pasta})", d.chave,
                              t["pasta"], "", True)
        return d

    def trocar(self, pasta: str | None, quando: datetime | None = None) -> dict | None:
        """"Trocar professor": a partir de agora, o que a agenda mandaria para <chave atual> vai para <pasta>.

        Vale para a gravação em andamento e as próximas, até a agenda apontar outro horário.
        pasta=None volta a seguir a agenda.
        """
        quando = quando or _agora()
        cfg = appdata.carregar()
        with self.lock:
            if not pasta:
                self.troca = None
                return None
            # a referência é a gravação em andamento (se houver) ou o momento atual
            ref = quando
            for g in self._gravando_nomes():
                h = ag.hora_do_nome(g)
                if h:
                    ref = h
            d = ag.decidir(ref, self.agenda(cfg), int(cfg.get("antecedencia_min") or 30))
            if d.pasta == pasta:                  # a agenda já manda para este professor
                self.troca = None
                return None
            self.troca = {"chave": d.chave, "pasta": pasta, "dia": ref.date().isoformat(),
                          "agenda_dizia": d.pasta}
            return self.troca

    # ------------------------------------------------------------------ vigia

    def iniciar(self):
        if self._thread and self._thread.is_alive():
            return
        self._parar.clear()
        self._thread = threading.Thread(target=self._laco, daemon=True)
        self._thread.start()

    def parar(self):
        self._parar.set()

    def _laco(self):
        while not self._parar.is_set():
            try:
                self.ciclo()
            except Exception as e:  # noqa: BLE001 — o vigia nunca pode morrer
                self.erros["(vigia)"] = str(e)
            self._parar.wait(1.0)

    def ciclo(self, agora: float | None = None):
        """Uma olhada na pasta do OBS. Separado do laço para os testes chamarem direto."""
        agora = agora or time.time()
        cfg = appdata.carregar()
        pasta = cfg.get("pasta_obs")
        self.ultimo_ciclo = agora
        if not pasta or not Path(pasta).is_dir():
            return
        estavel = float(cfg.get("estavel_seg") or 5)
        presentes = set()
        with self.lock:
            for p in Path(pasta).iterdir():
                if not p.is_file() or p.name.startswith(".") or not ag.hora_do_nome(p.name):
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                presentes.add(p.name)
                v = self.vistos.get(p.name)
                if v is None or v["tam"] != st.st_size or v["mtime"] != st.st_mtime:
                    self.vistos[p.name] = {"tam": st.st_size, "mtime": st.st_mtime, "mudou": agora,
                                           "primeiro": v["primeiro"] if v else agora}
                    continue
                if st.st_size > 0 and agora - v["mudou"] >= estavel:
                    if aberto_por_outro(p):
                        self.erros[p.name] = "O OBS ainda está com o arquivo aberto; espero ele fechar."
                        continue
                    self._mover_do_obs(p, cfg)
            for nome in list(self.vistos):
                if nome not in presentes:
                    self.vistos.pop(nome, None)
                    self.erros.pop(nome, None)

    def _gravando_nomes(self) -> list[str]:
        cfg = appdata.carregar()
        estavel = float(cfg.get("estavel_seg") or 5)
        agora = time.time()
        return sorted(n for n, v in self.vistos.items() if agora - v["mudou"] < estavel or v["tam"] == 0)

    @staticmethod
    def _destino_livre(pasta: Path, nome: str) -> Path:
        alvo = pasta / nome
        if not alvo.exists():
            return alvo
        base, ext = Path(nome).stem, Path(nome).suffix
        n = 2
        while (pasta / f"{base} ({n}){ext}").exists():
            n += 1
        return pasta / f"{base} ({n}){ext}"

    def _footage(self, cfg: dict, pasta: str, dia: str) -> Path:
        return Path(cfg["pasta_saida"]) / pasta / dia / "Footage"

    def _mover_do_obs(self, p: Path, cfg: dict):
        if not cfg.get("pasta_saida") or not Path(cfg["pasta_saida"]).is_dir():
            self.erros[p.name] = "Pasta de saída não configurada."
            return
        quando = ag.hora_do_nome(p.name)
        agenda = self.agenda(cfg)
        if agenda.carregando:
            self.erros[p.name] = "Esperando a agenda carregar para saber o professor."
            return
        d = self.decidir(quando, agenda, cfg)
        dia = ag.pasta_dia(quando.date())
        destino_dir = self._footage(cfg, d.pasta, dia)
        tam = p.stat().st_size
        try:
            destino_dir.mkdir(parents=True, exist_ok=True)
            alvo = self._destino_livre(destino_dir, p.name)
            shutil.move(str(p), str(alvo))
        except OSError as e:                     # Windows: o OBS ainda segura o arquivo → tenta no próximo ciclo
            self.erros[p.name] = f"Não consegui mover ainda: {e}"
            return
        self.erros.pop(p.name, None)
        self.vistos.pop(p.name, None)
        info = mp4info.info(alvo) or {}
        dur = info.get("duracao") or mp4info.ffprobe(alvo)
        self.registro.append({
            "id": uuid.uuid4().hex[:10], "arquivo": alvo.name, "inicio": quando.isoformat(timespec="seconds"),
            "data": quando.date().isoformat(), "dia": dia, "pasta": d.pasta, "regra": d.regra, "aviso": d.aviso,
            "pasta_agenda": d.pasta if not d.trocado else None, "trocado": d.trocado,
            "caminho": str(alvo), "tamanho": tam, "duracao": dur, "estado": "na pasta", "msg": "",
            "movido_em": datetime.now().isoformat(timespec="seconds"),
        })
        self._salvar_registro()

    # ------------------------------------------------------------------ conferência

    def mover(self, id_: str, pasta: str) -> dict:
        cfg = appdata.carregar()
        with self.lock:
            r = self._entrada(id_)
            if r["estado"] == "enviado":
                raise ValueError("Esta gravação já foi enviada. Mover agora deixaria o Drive diferente da pasta.")
            if r["pasta"] == pasta:
                return r
            origem = Path(r["caminho"])
            if not origem.is_file():
                raise ValueError(f"O arquivo não está mais em {origem.parent} (foi mexido fora do app?).")
            destino_dir = self._footage(cfg, pasta, r["dia"])
            destino_dir.mkdir(parents=True, exist_ok=True)
            alvo = self._destino_livre(destino_dir, origem.name)
            shutil.move(str(origem), str(alvo))
            self._limpar_vazias(origem.parent, Path(cfg["pasta_saida"]))
            r.update(pasta=pasta, caminho=str(alvo), arquivo=alvo.name, estado="na pasta", msg="",
                     regra=f"movido na conferência (antes: {r['pasta']})")
            self._salvar_registro()
            return r

    @staticmethod
    def _limpar_vazias(pasta: Path, raiz: Path):
        """Tira as pastas que o próprio app criou e ficaram vazias (Footage, dia, professor). Só pastas vazias."""
        for _ in range(3):
            if pasta == raiz or raiz not in pasta.parents:
                return
            try:
                pasta.rmdir()                     # só funciona se estiver vazia
            except OSError:
                return
            pasta = pasta.parent

    def esquecer(self, id_: str):
        """Tira do registro uma gravação cujo arquivo sumiu (não mexe em arquivo nenhum)."""
        with self.lock:
            r = self._entrada(id_)
            if Path(r["caminho"]).exists():
                raise ValueError("O arquivo ainda existe; só dá para tirar da lista o que sumiu.")
            self.registro.remove(r)
            self._salvar_registro()

    def grupos(self) -> list[dict]:
        """Registro agrupado por dia e professor, para a tela de conferência."""
        with self.lock:
            out: dict[str, dict] = {}
            for r in sorted(self.registro, key=lambda x: x["inicio"]):
                k = f"{r['pasta']}|{r['dia']}"
                g = out.setdefault(k, {"chave": k, "pasta": r["pasta"], "dia": r["dia"], "data": r["data"],
                                       "itens": [], "envio": self.envios.get(k)})
                item = dict(r)
                item["existe"] = Path(r["caminho"]).is_file()
                g["itens"].append(item)
            for g in out.values():
                estados = {i["estado"] for i in g["itens"]}
                g["enviado"] = estados == {"enviado"}
                g["pode_subir"] = g["pasta"] not in (ag.TESTES, ag.SEM_AGENDA)
            return sorted(out.values(), key=lambda g: (g["data"], g["itens"][0]["inicio"]))

    # ------------------------------------------------------------------ envio

    def subir(self, pasta: str, dia: str) -> dict:
        """"Conferido, pode subir": um botão só faz tudo, em segundo plano.

        1. transcreve a pasta Footage com o `transcribe` (se estiver ligado e ainda não tiver os SRTs);
        2. sobe a pasta inteira (vídeos + SRTs) — pelo rclone, com a conta do Subir no Drive, ou para uma pasta;
        3. confere no destino o nome e o tamanho de cada arquivo → "enviado, pode apagar".
        """
        cfg = appdata.carregar()
        if pasta in (ag.TESTES, ag.SEM_AGENDA):
            raise ValueError(f"\"{pasta}\" não sobe. Mova as gravações para o professor certo antes.")
        modo = cfg.get("envio_modo") or "rclone"
        if modo == "rclone":
            if ":" not in rclone.destino(cfg):
                raise ValueError("Não sei para onde subir. Em Configurações, preencha o destino no Drive.")
            try:
                rclone.achar(cfg)
            except rclone.ErroRclone as e:
                raise ValueError(str(e))
        else:
            envio = cfg.get("pasta_envio")
            if not envio or not Path(envio).is_dir():
                raise ValueError("Configure a pasta de envio (na simulação, a pasta drive-falso).")
        k = f"{pasta}|{dia}"
        with self.lock:
            if self.envios.get(k, {}).get("estado") in ("transcrevendo", "enviando", "conferindo"):
                return self.envios[k]
            itens = [r for r in self.registro if r["pasta"] == pasta and r["dia"] == dia]
            if not itens:
                raise ValueError("Nada para subir.")
            faltam = [r["arquivo"] for r in itens if not Path(r["caminho"]).is_file()]
            if faltam:
                raise ValueError(f"Não achei {', '.join(faltam)} na pasta. Confira antes de subir.")
            for r in itens:
                r["estado"], r["msg"] = "conferido", "conferido, na fila"
            self._salvar_registro()
            self.envios[k] = {"estado": "transcrevendo", "pct": 0, "msg": "começando…", "etapa": ""}
        footage = self._footage(cfg, pasta, dia)
        threading.Thread(target=self._processar, args=(k, itens, footage, pasta, dia, cfg), daemon=True).start()
        return self.envios[k]

    @staticmethod
    def _precisa_transcrever(footage: Path) -> bool:
        videos = [p for p in footage.iterdir() if p.suffix.lower() in (".mp4", ".mov", ".mkv") and not p.name.startswith(".")]
        for v in videos:
            srt = v.with_suffix(".srt")
            if not srt.is_file() or srt.stat().st_mtime < v.stat().st_mtime:
                return True
        if len(videos) >= 2 and not any(p.name.startswith("SRT unico") and p.suffix == ".srt" for p in footage.iterdir()):
            return True
        return False

    def _processar(self, k: str, itens: list[dict], footage: Path, pasta: str, dia: str, cfg: dict):
        andamento = self.envios[k]

        def marcar(estado, msg):
            with self.lock:
                for r in itens:
                    r["estado"], r["msg"] = estado, msg

        try:
            # 1. transcrição
            if cfg.get("transcrever", True):
                exe_t = rclone.achar_transcribe(cfg)
                if not exe_t:
                    andamento["etapa"] = "Sem o transcribe neste computador: subindo sem transcrever."
                elif self._precisa_transcrever(footage):
                    andamento.update(estado="transcrevendo", msg="transcrevendo…")
                    marcar("conferido", "transcrevendo…")
                    rclone.transcrever(exe_t, footage, lambda ln: andamento.update(msg=ln[:160]))
                else:
                    andamento["etapa"] = "Já estava transcrito."
            # 2. envio
            andamento.update(estado="enviando", pct=0, msg="subindo…")
            marcar("conferido", "subindo…")
            locais = {p.name: p.stat().st_size for p in footage.iterdir()
                      if p.is_file() and not p.name.startswith(".") and not p.name.endswith(".parcial")}
            if (cfg.get("envio_modo") or "rclone") == "rclone":
                exe = rclone.achar(cfg)
                remoto = rclone.juntar(rclone.destino(cfg), pasta, dia, "Footage")
                rclone.enviar_pasta(exe, footage, remoto, lambda pct: andamento.update(pct=pct))
                andamento.update(estado="conferindo", msg="conferindo no Drive…")
                no_destino = rclone.listar(exe, remoto)
                onde = remoto
            else:
                destino = Path(cfg["pasta_envio"]) / pasta / dia / "Footage"
                self._copiar_pasta(footage, destino, locais, andamento)
                andamento.update(estado="conferindo", msg="conferindo…")
                no_destino = {p.name: p.stat().st_size for p in destino.iterdir() if p.is_file()}
                onde = str(destino)
            # 3. conferência: nome e tamanho de cada arquivo da pasta (vídeos e SRTs)
            problemas = [n for n, t in locais.items() if no_destino.get(n) != t]
            with self.lock:
                for r in itens:
                    nome = Path(r["caminho"]).name
                    if nome in problemas:
                        r["estado"] = "erro"
                        r["msg"] = "não está no destino — não apague" if nome not in no_destino \
                            else "tamanho diferente no destino — não apague"
                    else:
                        r["estado"], r["msg"] = "enviado", "enviado, pode apagar"
                        r["enviado_para"] = f"{onde}/{nome}"
                n_srt = sum(1 for n in locais if n.endswith((".srt", ".txt")))
                if problemas:
                    andamento.update(estado="erro", msg=f"{len(problemas)} arquivo(s) não conferem: "
                                     f"{', '.join(problemas[:3])}. Não apague. Clique de novo para tentar.")
                else:
                    extra = f" e {n_srt} arquivo(s) de transcrição" if n_srt else ""
                    andamento.update(estado="ok", pct=100,
                                     msg=f"Tudo conferido no destino: {len(locais) - n_srt} vídeo(s){extra}, "
                                         "mesmo nome e mesmo tamanho.")
                self._salvar_registro()
        except (rclone.ErroRclone, OSError) as e:
            with self.lock:
                for r in itens:
                    if r["estado"] != "enviado":
                        r["estado"], r["msg"] = "erro", "não subiu — veja o aviso do grupo"
                andamento.update(estado="erro", msg=f"Parou: {e}. Nada foi apagado. Clique de novo para tentar.")
                self._salvar_registro()

    @staticmethod
    def _copiar_pasta(origem: Path, destino: Path, locais: dict, andamento: dict):
        destino.mkdir(parents=True, exist_ok=True)
        total = sum(locais.values()) or 1
        feito = 0
        for nome, tam in locais.items():
            alvo = destino / nome
            if not (alvo.is_file() and alvo.stat().st_size == tam):
                parcial = alvo.with_name(nome + ".parcial")
                with open(origem / nome, "rb") as fi, open(parcial, "wb") as fo:
                    while True:
                        bloco = fi.read(4 * 1024 * 1024)
                        if not bloco:
                            break
                        fo.write(bloco)
                        feito += len(bloco)
                        andamento["pct"] = int(100 * feito / total)
                parcial.replace(alvo)
            else:
                feito += tam
                andamento["pct"] = int(100 * feito / total)

    # ------------------------------------------------------------------ o que a tela mostra

    def _sessao_json(self, agenda: ag.Agenda) -> dict | None:
        if not self.sessao or agenda.data is None:
            return None
        e = agenda.evento(self.sessao)
        if e is None:
            return None
        return {"evento": e.para_json(), "dia": ag.pasta_dia(agenda.data), "data": agenda.data.isoformat()}

    def resumo(self) -> dict:
        cfg = appdata.carregar()
        agenda = self.agenda(cfg)
        agora = _agora()
        with self.lock:
            gravando = []
            for nome in self._gravando_nomes():
                v = self.vistos[nome]
                h = ag.hora_do_nome(nome)
                d = self.decidir(h, agenda, cfg)
                gravando.append({"arquivo": nome, "tamanho": v["tam"], "desde": h.isoformat(timespec="seconds"),
                                 "decisao": d.para_json(), "erro": self.erros.get(nome)})
            parados = [{"arquivo": n, "erro": e} for n, e in self.erros.items() if n not in {g["arquivo"] for g in gravando}]
            # o que vale "agora" (sem gravação): mostra quem receberia uma gravação que começasse neste minuto
            ref = ag.hora_do_nome(gravando[-1]["arquivo"]) if gravando else agora
            if agenda.data and not gravando and agora.date() != agenda.data:
                ref = datetime.combine(agenda.data, agora.time())   # agenda de outro dia: simula o horário nela
            atual = self.decidir(ref, agenda, cfg)
            return {
                "agenda": agenda.para_json(), "opcoes": agenda.pastas(),
                "gravando": gravando, "presos": parados, "atual": atual.para_json(),
                "referencia": ref.isoformat(timespec="seconds"),
                "troca": self.troca, "grupos": self.grupos(), "faltando": appdata.faltando(cfg),
                "sessao": self._sessao_json(agenda),
                "vigia_ok": time.time() - self.ultimo_ciclo < 5,
            }


ESTUDIO = Estudio()


def hoje() -> date:
    return _agora().date()
