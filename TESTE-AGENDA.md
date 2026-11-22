# Teste do fluxo pela agenda (versão 0.3.0)

Agenda → escolher o professor → gravar no OBS → **Conferido, pode subir** → voltar para a agenda.
Usa a agenda de verdade (Pastas do dia) e o Drive de verdade, então faça num dia com gravação na agenda, ou
escolha qualquer professor de hoje só para testar e depois apague as pastas de teste no Drive.

## 1. Trocar o app pela versão nova

1. Feche o app (Ctrl+C na janela do Terminal do Estúdio).
2. Troque a pasta `estudio-obs` pela do zip novo. Abra com `Abrir Estudio.command`. No topo: **0.3.0**.

## 2. Ligar ao Pastas do dia (uma vez em cada máquina)

1. Engrenagem ⚙ → **Link do Pastas do dia**: cole o mesmo link `/exec` que está no **Configurar** da tela do
   Pastas do dia. Clique em **Testar** → "✓ Conectado ao Pastas do dia".
2. Confira **Como subir: Pelo rclone** e a **Pasta no Drive**. Para o teste, pode deixar vazio (usa a do
   Subir no Drive, a "Gravações IEC" de verdade), porque as pastas do professor já existem lá.
3. **Salvar**. Em alguns segundos aparece a **Agenda de hoje** com os cartões.

## 3. O que conferir

- [ ] Os cartões batem com a agenda: hora, professor, tipo · disciplina, código. Canceladas aparecem riscadas embaixo.
- [ ] O horário de agora tem a etiqueta **agora** e **próxima gravação vai para cá**.
- [ ] Professor com dois códigos mostra uma lista para escolher o código.
- [ ] Clique em **Gravar com este professor**. Abre a tela do professor.
      **Confira o caminho embaixo do nome** (`26_xxx Nome / AAAA MM DD / Footage`): o nome tem que ser
      **igual ao da pasta no Drive**, letra por letra. Se não for, me avise antes de subir (senão o envio cria
      uma pasta nova com o nome diferente).
- [ ] **Abrir no Drive ↗** abre a pasta do dia, já criada com Footage e Originais.
- [ ] Na pasta de saída do Mac apareceu `26_xxx Nome/AAAA MM DD/Footage` e `Originais`.
- [ ] Grave um clipe curto no OBS. A janelinha mostra o professor escolhido; ao parar, o clipe aparece na tela dele.
- [ ] **Conferido, pode subir** → 1/3 transcrevendo, 2/3 subindo, 3/3 conferindo → "enviado, pode apagar".
      O clipe e o `.srt` aparecem na pasta Footage do Drive.
- [ ] **← Voltar para a agenda**: o cartão do professor mostra "1 gravação(ões)" / "✓ enviada(s)".
- [ ] Escolha outro professor e grave mais um clipe: vai para ele.

## Se a internet cair

O app guarda a última agenda que veio do Pastas do dia e continua funcionando com ela (o topo da agenda avisa
"sem conexão… usando a cópia das HH:MM"). As gravações seguem sendo organizadas; só o envio espera a internet.
