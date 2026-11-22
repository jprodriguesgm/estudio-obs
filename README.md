# Estúdio

App do estúdio do Núcleo de Produção Digital (PUC Minas / IEC). Vigia a pasta onde o OBS grava e, quando
uma gravação termina, usa a hora do nome do arquivo para achar o professor na agenda do dia e move o vídeo
para `26_xxx Professor/AAAA MM DD/Footage`, a pasta que o **Montador** espera. Antes de subir, a equipe
confere tudo numa tela; depois do envio, o app compara nome e tamanho no destino e avisa quando pode apagar.

Parte C do superprojeto integrado. Segue o modelo do Montador e do Revisor: janela no navegador, Mac e
Windows, sem administrador.

> **Versão 0.2.0 — testes por fases.** Ainda sem empacotamento pelo GitHub Actions: roda com o `python3`
> do Mac. Roteiros: [TESTE-FASE-1.md](TESTE-FASE-1.md) (simulação) e [TESTE-FASE-3.md](TESTE-FASE-3.md) (Drive).

## O que ele faz

1. **Vigia a pasta do OBS.** Arquivo com nome no padrão do OBS (`2026-09-21 08-35-43.mp4`, também `.mkv` e
   `.mov`) que está crescendo = gravando. Não depende da versão do OBS.
2. **Gravação terminou** (X segundos sem crescer): decide o professor e move.
3. **Regras da agenda**
   - dentro do horário, ou até 30 min antes → aquele professor;
   - depois do fim e antes do próximo horário → continua com o último;
   - antes do primeiro horário do dia → `Testes`;
   - sem agenda para aquele dia → `Sem agenda`;
   - dois professores no mesmo horário → o primeiro da agenda, com aviso;
   - sem limite de gravações por horário.
4. **Janelinha "Gravando agora"** com **Trocar professor**: vale para a gravação atual e as próximas, até a
   agenda apontar outro horário (aí volta sozinha a seguir a agenda).
5. **Conferência**: gravações agrupadas por professor, com horário, duração e tamanho; **Mover para** outro
   professor. `Testes` e `Sem agenda` não sobem.
6. **Um botão só — Conferido, pode subir:**
   1. transcreve a pasta `Footage` com o `transcribe` do Mac (um SRT por vídeo + SRT único do dia + tabela),
      se ainda não estiver transcrita;
   2. sobe a pasta inteira pelo **rclone**, com a conexão e a pasta que o app **Subir no Drive** já deixou
      configuradas no Mac (conta da instituição, não importa o navegador): `<destino>/26_xxx Professor/AAAA MM DD/Footage`;
   3. lista a pasta no Drive e confere nome e tamanho de cada arquivo → "enviado, pode apagar".
   Se algo falhar, mostra o motivo e **Tentar de novo**; o que já subiu não sobe outra vez.
7. **Nada é apagado** pelo app. No Mac, só move o arquivo depois que o OBS o fecha (lsof). Arquivo com o mesmo nome no destino ganha " (2)".

## Agenda do dia (formato proposto)

```json
{
  "data": "2026-11-21",
  "eventos": [
    {"inicio": "08:00", "fim": "09:00", "professor": "Ana Souza", "codigo": "26_101"}
  ]
}
```

A pasta do professor é `codigo + espaço + professor`. O Apps Script do Pastas do dia vai escrever neste
formato (a confirmar).

## Para quem programa

Python 3.10+ só com a biblioteca padrão. Tela em HTML/CSS/JS puro servida pelo próprio Python, só em
`127.0.0.1:8768` (o Montador usa a 8767).

| Parte | Onde |
|---|---|
| Agenda e regras | `estudio/agenda.py` |
| Vigia, registro, conferência e envio | `estudio/vigia.py` |
| rclone, Subir no Drive e transcribe | `estudio/rclone.py` |
| Servidor e tela | `estudio/server.py`, `estudio/ui/` |
| Simulação da Fase 1 | `estudio/simulador.py` |
| Configurações por máquina | `estudio/appdata.py` |

    python3 -m estudio                      # abre a tela no navegador
    python3 -m estudio simular              # Fase 1: pasta de teste + gravações falsas
    python3 -m estudio simular --limpar     # recomeça a simulação do zero
    python3 -m pytest -q tests

Configurações e registro: `~/Library/Application Support/Estudio` (Mac) ou `%APPDATA%\Estudio` (Windows);
a variável `ESTUDIO_HOME` troca essa pasta.

## Licença

Copyright (C) 2026 João Paulo Rodrigues. GNU GPL v3 ou posterior ([LICENSE](LICENSE)). As fontes IBM Plex
vão com a licença em `estudio/ui/fonts/`.
