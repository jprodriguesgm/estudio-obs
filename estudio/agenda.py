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

    @property
    def pasta(self) -> str:
        return f"{self.codigo} {self.professor}".strip()

    def para_json(self) -> dict:
        return {"inicio": self.inicio.strftime("%H:%M"), "fim": self.fim.strftime("%H:%M"),
                "professor": self.professor, "codigo": self.codigo, "pasta": self.pasta, "indice": self.indice}


@dataclass
class Agenda:
    data: date | None = None
    eventos: list[Evento] = field(default_factory=list)
    erro: str | None = None

    def para_json(self) -> dict:
        return {"data": self.data.isoformat() if self.data else None, "erro": self.erro,
                "eventos": [e.para_json() for e in self.eventos]}

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


def decidir(quando: datetime, agenda: Agenda, antecedencia_min: int = 30) -> Decisao:
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
        return Decisao(e.pasta, f"dentro do horário ({e.inicio:%H:%M}–{e.fim:%H:%M})", f"ev{e.indice}",
                       e.professor, _aviso_mesmo_horario(e, dentro))

    logo = [e for e in agenda.eventos if ini(e) - ant <= t < ini(e)]
    if logo:
        primeiro = min(ini(e) for e in logo)
        mesmos = [e for e in logo if ini(e) == primeiro]
        e = mesmos[0]
        return Decisao(e.pasta, f"até {antecedencia_min} min antes do horário ({e.inicio:%H:%M})", f"ev{e.indice}",
                       e.professor, _aviso_mesmo_horario(e, mesmos))

    if t < ini(agenda.eventos[0]) - ant:
        return Decisao(TESTES, "antes do primeiro horário do dia", "testes")

    terminados = [e for e in agenda.eventos if fim(e) <= t]
    if terminados:
        ultimo_fim = max(fim(e) for e in terminados)
        mesmos = [e for e in terminados if fim(e) == ultimo_fim]
        e = mesmos[0]
        return Decisao(e.pasta, f"depois do fim ({e.fim:%H:%M}), continua com o último", f"ev{e.indice}",
                       e.professor, _aviso_mesmo_horario(e, mesmos))

    return Decisao(SEM_AGENDA, "nenhum horário da agenda bate", "sem-agenda")
