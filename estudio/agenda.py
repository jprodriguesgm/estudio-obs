"""Agenda do dia e as regras que decidem de qual professor é cada gravação.

Formato do arquivo (proposta; o Apps Script do "Pastas do dia" vai escrever igual):

    {
      "data": "2026-11-21",
      "eventos": [
        {"inicio": "08:00", "fim": "09:00", "professor": "Ana Souza", "codigo": "26_101"},
        ...
      ]
    }

Regras (decididas no superprojeto, Parte C):
  - dentro do horário, ou até 30 min antes dele      → aquele professor
  - depois do fim e antes do próximo evento          → continua com o último
  - antes do primeiro evento                         → Testes
  - sem agenda para aquele dia                       → Sem agenda
  - dois professores no mesmo horário                → o primeiro da agenda, com aviso (use "Trocar professor")
  - sem limite de gravações por evento.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

TESTES = "Testes"
SEM_AGENDA = "Sem agenda"

# Nome padrão do OBS: "2026-09-21 08-35-43.mp4" (o OBS também aceita .mkv e .mov)
PADRAO_OBS = re.compile(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2})-(\d{2})-(\d{2})(?: \(\d+\))?\.(mp4|mkv|mov)$", re.I)


def hora_do_nome(nome: str) -> datetime | None:
    m = PADRAO_OBS.match(nome)
    if not m:
        return None
    try:
        return datetime(*(int(x) for x in m.groups()[:6]))
    except ValueError:
        return None


def pasta_dia(d: date) -> str:
    """Nome da pasta do dia, no padrão que o Montador espera: "2026 11 21"."""
    return d.strftime("%Y %m %d")


@dataclass
class Evento:
    inicio: time
    fim: time
    professor: str
    codigo: str = ""
    indice: int = 0
    # o que vem do Pastas do dia (na agenda .json fica vazio)
    id: str = ""
    nome_pasta: str = ""         # nome da pasta do professor no Drive ("26_824 Jorge Augusto …")
    tipo: str = ""
    curso: str = ""
    disciplina: str = ""
    pasta_id: str = ""           # id da pasta do professor no Drive (para criar a pasta do dia)
    pasta_url: str = ""
    pasta_dia_url: str = ""
    candidatos: list = field(default_factory=list)
    escolha: int = -1
    aviso: str = ""

    @property
    def pasta(self) -> str:
        return self.nome_pasta or f"{self.codigo} {self.professor}".strip()

    def para_json(self) -> dict:
        return {"inicio": self.inicio.strftime("%H:%M"), "fim": self.fim.strftime("%H:%M"),
                "professor": self.professor, "codigo": self.codigo, "pasta": self.pasta, "indice": self.indice,
                "id": self.id or f"ev{self.indice}", "tipo": self.tipo, "curso": self.curso,
                "disciplina": self.disciplina, "tem_pasta_drive": bool(self.pasta_id), "pasta_url": self.pasta_url,
                "pasta_dia_url": self.pasta_dia_url, "escolha": self.escolha, "aviso": self.aviso,
                "candidatos": [{"codigo": c.get("codigo", ""), "tem_pasta": bool(c.get("pasta"))}
                               for c in self.candidatos]}


@dataclass
class Agenda:
    data: date | None = None
    eventos: list[Evento] = field(default_factory=list)
    erro: str | None = None
    fonte: str = "arquivo"           # "arquivo" (.json) ou "pastas do dia"
    canceladas: list[dict] = field(default_factory=list)
    carregando: bool = False
    info: str = ""                   # ex.: "atualizada às 07:58" ou "sem internet: usando a cópia das 07:58"

    def para_json(self) -> dict:
        return {"data": self.data.isoformat() if self.data else None, "erro": self.erro, "fonte": self.fonte,
                "eventos": [e.para_json() for e in self.eventos], "canceladas": self.canceladas,
                "carregando": self.carregando, "info": self.info}

    def evento(self, id_: str) -> "Evento | None":
        for e in self.eventos:
            if (e.id or f"ev{e.indice}") == id_:
                return e
        return None

    def pastas(self) -> list[str]:
        """Destinos possíveis (para "Trocar professor" e para mover na conferência), sem repetir."""
        vistos = []
        for e in self.eventos:
            if e.pasta not in vistos:
                vistos.append(e.pasta)
        return vistos + [TESTES, SEM_AGENDA]


def _hora(txt) -> time:
    txt = str(txt).strip()
    for fmt in ("%H:%M", "%H:%M:%S", "%Hh%M", "%Hh"):
        try:
            return datetime.strptime(txt, fmt).time()
        except ValueError:
            pass
    raise ValueError(f"hora inválida: {txt!r}")


def ler(caminho: str | Path | None) -> Agenda:
    if not caminho:
        return Agenda(erro="Nenhum arquivo de agenda configurado.")
    p = Path(caminho)
    try:
        dados = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Agenda(erro=f"Agenda não encontrada: {p.name}")
    except (OSError, ValueError) as e:
        return Agenda(erro=f"Não consegui ler a agenda ({p.name}): {e}")
    try:
        d = date.fromisoformat(str(dados["data"]))
        eventos = []
        for i, ev in enumerate(dados.get("eventos") or []):
            prof = str(ev.get("professor") or "").strip()
            if not prof:
                continue
            ini, fim = _hora(ev["inicio"]), _hora(ev["fim"])
            if fim <= ini:
                raise ValueError(f"evento de {prof}: o fim ({ev['fim']}) é antes do início ({ev['inicio']})")
            eventos.append(Evento(ini, fim, prof, str(ev.get("codigo") or "").strip(), i))
    except (KeyError, ValueError, TypeError) as e:
        return Agenda(erro=f"Agenda com problema: {e}")
    # ordem estável: por início; no mesmo horário, a ordem do arquivo
    eventos.sort(key=lambda e: (e.inicio, e.indice))
    for i, e in enumerate(eventos):
        e.indice = i
    return Agenda(d, eventos)


def _hora_pd(txt: str) -> tuple[time, time]:
    """ "08:00–09:00" (traço comprido do Apps Script) → (08:00, 09:00)."""
    partes = re.split(r"\s*[–—-]\s*", str(txt).strip())
    return _hora(partes[0]), _hora(partes[1])


def de_pastas_do_dia(dados: dict, data: date, escolhas: dict | None = None) -> Agenda:
    """Agenda a partir do "carregar" do Pastas do dia. escolhas = {id do evento: índice do código escolhido}."""
    from .pastas_do_dia import escolha_padrao
    escolhas = escolhas or {}
    eventos, canceladas = [], []
    for i, g in enumerate(dados.get("gravacoes") or []):
        try:
            ini, fim = _hora_pd(g.get("hora", ""))
        except (ValueError, IndexError):
            continue
        prof = str(g.get("professor") or "").strip()
        if not prof:
            continue
        if g.get("cancelada"):
            canceladas.append({"hora": g.get("hora"), "professor": prof, "tipo": g.get("tipo", "")})
            continue
        cands = list(g.get("candidatos") or [])
        gid = str(g.get("id") or f"pd{i}")
        esc = escolhas.get(gid, escolha_padrao(cands))
        if not (0 <= esc < len(cands)):
            esc = escolha_padrao(cands)
        c = cands[esc] if esc >= 0 else {}
        pasta = c.get("pasta") or {}
        codigo = str(c.get("codigo") or "").strip()
        nome = str(pasta.get("nome") or pasta.get("name") or "").strip()
        aviso = ""
        if not cands:
            aviso = "Sem código na planilha: a pasta vai ficar só com o nome do professor."
        elif not pasta:
            aviso = "Pasta do professor não encontrada no Drive."
        elif len(cands) > 1:
            aviso = "Mais de um código para este professor: confira o código."
        eventos.append(Evento(ini, fim, prof, codigo, i, id=gid, nome_pasta=nome, tipo=str(g.get("tipo") or ""),
                              curso=str(g.get("curso") or ""), disciplina=str(g.get("disciplina") or ""),
                              pasta_id=str(pasta.get("id") or ""), pasta_url=str(pasta.get("url") or ""),
                              pasta_dia_url=str((c.get("pastaDia") or {}).get("url") or ""),
                              candidatos=cands, escolha=esc, aviso=aviso))
    eventos.sort(key=lambda e: (e.inicio, e.indice))
    for i, e in enumerate(eventos):
        e.indice = i
    return Agenda(data, eventos, fonte="pastas do dia", canceladas=canceladas)


@dataclass
class Decisao:
    pasta: str                   # "26_101 Ana Souza", "Testes" ou "Sem agenda"
    regra: str                   # explicação curta, aparece na tela
    chave: str                   # identifica a decisão da agenda (a troca de professor vale enquanto ela não muda)
    professor: str = ""
    aviso: str = ""
    trocado: bool = False        # True quando veio do "Trocar professor"

    def para_json(self) -> dict:
        return {"pasta": self.pasta, "regra": self.regra, "chave": self.chave, "professor": self.professor,
                "aviso": self.aviso, "trocado": self.trocado}


def _aviso_mesmo_horario(escolhido: Evento, outros: list[Evento]) -> str:
    nomes = [e.professor for e in outros if e is not escolhido]
    if not nomes:
        return ""
    return f"Também na agenda neste horário: {', '.join(nomes)}. Se for outro professor, use Trocar professor."


def _chave(e: Evento) -> str:
    return e.id or f"ev{e.indice}"


def decidir(quando: datetime, agenda: Agenda, antecedencia_min: int = 30) -> Decisao:
    if agenda.carregando:
        return Decisao(SEM_AGENDA, "a agenda ainda está carregando", "carregando")
    if agenda.erro or agenda.data is None:
        return Decisao(SEM_AGENDA, "sem agenda carregada", "sem-agenda")
    if quando.date() != agenda.data:
        return Decisao(SEM_AGENDA, f"a agenda carregada é de {agenda.data.strftime('%d/%m')}", "sem-agenda")
    if not agenda.eventos:
        return Decisao(SEM_AGENDA, "nenhuma gravação na agenda deste dia", "sem-agenda")

    t = quando
    ant = timedelta(minutes=antecedencia_min)

    def ini(e):
        return datetime.combine(agenda.data, e.inicio)

    def fim(e):
        return datetime.combine(agenda.data, e.fim)

    dentro = [e for e in agenda.eventos if ini(e) <= t < fim(e)]
    if dentro:
        e = dentro[0]
        return Decisao(e.pasta, f"dentro do horário ({e.inicio:%H:%M}–{e.fim:%H:%M})", _chave(e),
                       e.professor, _aviso_mesmo_horario(e, dentro))

    logo = [e for e in agenda.eventos if ini(e) - ant <= t < ini(e)]
    if logo:
        primeiro = min(ini(e) for e in logo)
        mesmos = [e for e in logo if ini(e) == primeiro]
        e = mesmos[0]
        return Decisao(e.pasta, f"até {antecedencia_min} min antes do horário ({e.inicio:%H:%M})", _chave(e),
                       e.professor, _aviso_mesmo_horario(e, mesmos))

    if t < ini(agenda.eventos[0]) - ant:
        return Decisao(TESTES, "antes do primeiro horário do dia", "testes")

    terminados = [e for e in agenda.eventos if fim(e) <= t]
    if terminados:
        ultimo_fim = max(fim(e) for e in terminados)
        mesmos = [e for e in terminados if fim(e) == ultimo_fim]
        e = mesmos[0]
        return Decisao(e.pasta, f"depois do fim ({e.fim:%H:%M}), continua com o último", _chave(e),
                       e.professor, _aviso_mesmo_horario(e, mesmos))

    return Decisao(SEM_AGENDA, "nenhum horário da agenda bate", "sem-agenda")
