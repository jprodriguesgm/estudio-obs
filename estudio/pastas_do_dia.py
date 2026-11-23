"""Conversa com o motor do "Pastas do dia" (Apps Script publicado como app da Web, link /exec).

É o mesmo motor que a tela "Pastas do dia.html" usa:
  ?acao=teste                          → confere o link
  ?acao=carregar&data=AAAA-MM-DD       → gravações do dia (agenda producao.eadiec + planilha + Drive)
  ?acao=criar&pasta=<id>&data=AAAA-MM-DD → cria (ou reaproveita) "AAAA MM DD" com Footage e Originais
Resposta: {"ok": true, "dados": ...} ou {"ok": false, "erro": "..."}.

Cada gravação de "carregar" vem assim:
  {id, hora: "08:00–09:00", tipo, professor, curso, disciplina, cancelada,
   candidatos: [{codigo, professor, disciplina, curso, nota, pasta: {id, nome?, url?} | null, pastaDia?: {url}}]}
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request


def contexto_ssl() -> ssl.SSLContext:
    """Certificados para falar com o Google.

    O app empacotado leva um Python próprio, que não enxerga os certificados do Mac. Usa, nesta ordem:
    os certificados do sistema (truststore: Keychain no Mac, repositório do Windows — inclui o certificado
    da rede da instituição, se houver), a lista do certifi, e por último o padrão do Python.
    """
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:  # noqa: BLE001
        pass
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


class ErroPastas(Exception):
    pass


def limpar_url(u: str) -> str:
    """Tira o /u/2/ (várias contas Google) e o que vem depois de /exec, como a tela do Pastas do dia faz."""
    u = (u or "").strip()
    u = re.sub(r"/u/\d+/", "/", u)
    i = u.find("/exec")
    return u[: i + 5] if i >= 0 else u


def _chamar(url: str, params: dict, tempo: int = 90):
    base = limpar_url(url)
    if not base.startswith("https://script.google.com/"):
        raise ErroPastas("O link do Pastas do dia precisa ser o do Apps Script (https://script.google.com/…/exec).")
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{base}?{q}", headers={"User-Agent": "Estudio-NPD"})
    try:
        with urllib.request.urlopen(req, timeout=tempo, context=contexto_ssl()) as r:   # segue o redirecionamento
            texto = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise ErroPastas(f"o Apps Script respondeu com erro {e.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErroPastas(f"sem conexão com o Apps Script ({getattr(e, 'reason', e)})")
    try:
        j = json.loads(texto)
    except ValueError:
        raise ErroPastas('o Apps Script não respondeu como esperado. Confira se a implantação é "Qualquer pessoa" '
                         "e se o link termina em /exec.")
    if not j.get("ok"):
        raise ErroPastas(j.get("erro") or "o Apps Script recusou o pedido")
    return j.get("dados")


def testar(url: str) -> str:
    _chamar(url, {"acao": "teste"}, 30)
    return "Conectado ao Pastas do dia."


def carregar(url: str, data: str) -> dict:
    dados = _chamar(url, {"acao": "carregar", "data": data})
    if not isinstance(dados, dict) or not isinstance(dados.get("gravacoes"), list):
        raise ErroPastas("o Pastas do dia devolveu a agenda num formato que eu não conheço")
    return dados


def criar(url: str, pasta_id: str, data: str) -> dict:
    return _chamar(url, {"acao": "criar", "pasta": pasta_id, "data": data}) or {}


def escolha_padrao(candidatos: list[dict]) -> int:
    """Mesma regra da tela do Pastas do dia: o mais provável; empatado, prefere o que tem pasta no Drive."""
    if not candidatos:
        return -1
    if not candidatos[0].get("pasta"):
        nota = candidatos[0].get("nota")
        for i, c in enumerate(candidatos):
            if c.get("pasta") and c.get("nota") == nota:
                return i
    return 0


def id_da_url(url: str) -> str | None:
    """Id da pasta num link do Drive (…/folders/<id>…)."""
    m = re.search(r"/folders/([A-Za-z0-9_-]{10,})", url or "") or re.search(r"[?&]id=([A-Za-z0-9_-]{10,})", url or "")
    return m.group(1) if m else None
