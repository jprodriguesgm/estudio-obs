# Teste da Fase 3 — um botão só: transcrever, subir pelo rclone e conferir no Drive

Usa as gravações do OBS que já estão em `NPD Estudio Teste/saida/26_199 Teste OBS/`. Leva uns 10 minutos.

## 1. Trocar o app pela versão nova

1. Feche o app (Ctrl+C na janela do Terminal do Estúdio).
2. Apague a pasta `estudio-obs` antiga e descompacte o zip novo no mesmo lugar.
   A pasta **NPD Estudio Teste** e as configurações continuam (elas ficam em outro lugar).
3. Dois cliques em `Abrir Estudio.command`. No topo deve aparecer **0.2.0**.

## 2. Configurar o envio (uma vez)

Clique na engrenagem ⚙:

1. **Como subir:** escolha **Pelo rclone, com a conta do Subir no Drive**.
2. Veja a linha embaixo do campo **Pasta no Drive**:
   - "Subir no Drive encontrado: conexão drive, pasta Gravações IEC…" → o app já sabe a conta certa.
   - "Não achei o Subir no Drive" → o app precisa que você escreva a conexão do rclone (ver abaixo).
3. **Para o teste, NÃO use a pasta de verdade.** No campo **Pasta no Drive**, escreva uma pasta de teste:
   `drive:Gravações IEC/_Teste Estudio`
   (se a sua conexão do rclone tiver outro nome, troque `drive` por ele; no Terminal, `rclone listremotes` mostra.)
4. Clique em **Testar conexão**. Tem que aparecer **✓ Conexão ok** com o e-mail da conta da instituição.
5. Deixe marcado **Transcrever antes de subir**. A linha embaixo tem que dizer "transcribe encontrado".
6. **Salvar**.

## 3. Um botão só

No grupo **26_199 Teste OBS**, clique em **Conferido, pode subir** e acompanhe:

- [ ] **1/3 transcrevendo…** — o `transcribe` roda (a mensagem mostra o que ele está fazendo).
- [ ] **2/3 subindo… %** — a barra anda.
- [ ] **3/3 conferindo…**
- [ ] No fim: "Tudo conferido no destino: 5 vídeo(s) e N arquivo(s) de transcrição…" e **✓ enviado, pode apagar**.
- [ ] No Drive, em `Gravações IEC/_Teste Estudio/26_199 Teste OBS/2026 11 22/Footage`: os 5 `.mov`, um `.srt` para cada
      e o `SRT unico` + `tabela`.
- [ ] Na pasta `saida/…/Footage` do Mac: os mesmos arquivos continuam lá (o app não apaga nada).
- [ ] Clique de novo não acontece nada de errado (o grupo já está enviado). Se der erro no meio, aparece
      **Tentar de novo** e o que já subiu não sobe outra vez.

Depois do teste, pode apagar a pasta `_Teste Estudio` do Drive.
