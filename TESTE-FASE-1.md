# Teste da Fase 1 — simulação no Mac, sem OBS

Leva uns 10 minutos. Nada aqui mexe no OBS, no Drive ou em pastas de trabalho: tudo acontece numa pasta
nova na Mesa, **NPD Estudio Teste**.

## 1. Abrir o app

1. Na pasta `estudio-obs`, dê **dois cliques** em `Abrir Estudio.command`.
   - Na primeira vez o Mac pode bloquear. Aí: botão direito no arquivo → **Abrir** → **Abrir**.
   - Se ainda assim não abrir, no Terminal: `chmod +x ~/caminho/estudio-obs/*.command` e tente de novo.
2. O navegador abre a tela do Estúdio. Vai aparecer "Falta configurar…" — normal, a simulação configura.
3. **Deixe a janela do Terminal aberta.** É ela que vigia a pasta.

## 2. Rodar a simulação

1. Dois cliques em `Simular gravacoes.command`. Abre outra janela do Terminal.
2. Ela cria a pasta **NPD Estudio Teste** na Mesa e configura o app. Volte ao navegador: o aviso some e
   aparece a **Agenda do dia** (Ana 8h, Bruno e Carla juntos às 10h, intervalo, Daniel 13h).
3. Clique em **Abrir janelinha** e deixe a janelinha ao lado do Terminal da simulação.
4. No Terminal da simulação, aperte **Enter**. Ela grava 9 arquivos falsos, um de cada vez.

Durante a simulação, confira:

| # | Hora no nome | Deve ir para | O que testa |
|---|---|---|---|
| 1 | 07:12 | Testes | antes do primeiro horário |
| 2 | 07:41 | 26_101 Ana Souza | até 30 min antes |
| 3 | 08:15 | 26_101 Ana Souza | dentro do horário |
| 4 | 09:12 | 26_101 Ana Souza | depois do fim, continua com o último |
| 5 | 10:03 | **26_103 Carla Mendes** | dois professores no mesmo horário → **você troca** |
| 6 | 10:38 | 26_103 Carla Mendes | a troca continua valendo |
| 7 | 12:05 | 26_103 Carla Mendes | intervalo: continua com o último |
| 8 | 13:20 | 26_104 Daniel Lima | horário novo: a troca deixa de valer sozinha |
| 9 | ontem 15:00 | Sem agenda | gravação de outro dia |

- [ ] Enquanto o arquivo cresce, a janelinha mostra **● Gravando agora: …** com o tamanho subindo.
- [ ] O arquivo **só sai** de `gravacoes-obs` uns 3 segundos **depois** de parar de crescer.
- [ ] Na gravação 5, a janelinha avisa "Também na agenda neste horário: Carla Mendes". Quando o Terminal
      pedir, escolha **26_103 Carla Mendes** e clique em **Trocar professor** (você tem uns 25 segundos).
- [ ] No fim, cada arquivo está na pasta certa dentro de `NPD Estudio Teste/saida/`, no formato
      `26_xxx Professor/AAAA MM DD/Footage/`.

## 3. Conferência e envio

Na tela principal, seção **Gravações**:

- [ ] Cada grupo mostra professor, quantidade e duração total; cada gravação mostra hora, duração, tamanho
      e o motivo (a regra que decidiu).
- [ ] Na gravação das **10:38** (Carla), escolha **Mover para… → 26_102 Bruno Costa**. Ela muda de grupo e
      o arquivo muda de pasta em `saida/`.
- [ ] **Testes** e **Sem agenda** dizem "não sobe — mova para o professor certo" (sem botão).
- [ ] No grupo da **Ana**, clique em **Conferido, pode subir**. Aparece "enviado, pode apagar" e os 3
      arquivos estão em `NPD Estudio Teste/drive-falso/26_101 Ana Souza/AAAA MM DD/Footage/`.
- [ ] Os arquivos **continuam** em `saida/` (o app nunca apaga).
- [ ] Clicar no nome de um arquivo mostra ele no Finder.

## 4. Anote o que estranhou

Qualquer coisa: texto confuso, botão no lugar errado, regra que não bateu com o que você esperava.

## Recomeçar do zero

Feche o app (Ctrl+C no Terminal do Estúdio) e dê dois cliques em `Recomecar simulacao.command`. Ele apaga só
a pasta **NPD Estudio Teste** e o registro do app.

## Depois da Fase 1

- **Fase 2:** OBS de verdade no seu Mac (clipes de 10–20 s): nome do arquivo, mp4/mkv/remux, arquivo
  crescendo, leitura da duração.
- **Fase 3:** pasta de teste no Drive de verdade (rclone ou Drive para computador).
- **Fase 4:** no estúdio (versão do OBS, usuário sem admin, SSD exFAT, Mac ou Windows).
