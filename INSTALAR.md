# Instalar o Estúdio

Uma vez em cada computador do estúdio. O app já leva dentro o **Whisper** (transcrição) e o **ffmpeg**:
não precisa instalar Python nem o transcribe.

**Baixar** (sempre a versão oficial mais nova). Veja a versão do Mac em  → **Sobre este Mac**:
- Mac com **macOS 13.5 ou mais novo** (Sonoma, Sequoia…):
  https://github.com/jprodriguesgm/estudio-obs/releases/latest/download/Estudio-mac.zip
- Mac com **macOS 12 até 13.4** (ex.: o Mac Studio do estúdio, Ventura 13.1):
  https://github.com/jprodriguesgm/estudio-obs/releases/latest/download/Estudio-mac-ventura.zip
- Windows: https://github.com/jprodriguesgm/estudio-obs/releases/latest/download/Estudio-windows.zip

Se o Mac disser "Você não pode usar esta versão do aplicativo com esta versão do macOS", baixe a **mac-ventura**.

O que cada computador precisa:

| | Mac | Windows |
|---|---|---|
| Sistema | Mac com chip Apple (M1 ou mais novo), macOS 12 ou mais novo | Windows 10 ou 11, 64 bits |
| **rclone** com a conexão `drive` (conta da instituição) | já pronto nos Macs com o **Subir no Drive** | instalar (passo 2 abaixo) |
| **Link do Pastas do dia** (implantação "Estúdio") | colar nas Configurações | colar nas Configurações |
| Transcrição | macOS 13.5+: mlx-whisper (igual ao transcribe) · macOS 12 a 13.4: whisper.cpp com a placa de vídeo | whisper.cpp |
| OBS | qualquer versão, nome de arquivo padrão | igual |

O app tem cerca de 2 GB por causa do modelo do Whisper. Nada precisa de senha de administrador.

---

## Mac

1. Baixe o **Estudio-mac.zip** (ou o **Estudio-mac-ventura.zip**, veja acima), abra (vira **Estudio.app**) e
   arraste para **Aplicativos**.
2. **Primeira vez:** botão direito no Estudio → **Abrir** → **Abrir**. (O app não é da App Store; depois da
   primeira vez, abre com dois cliques.) Se o Mac disser que "não pode ser aberto", vá em
   *Ajustes do Sistema → Privacidade e Segurança* e clique em **Abrir Mesmo Assim**.
3. Se pedir para acessar arquivos de um **volume removível** (o SSD), clique em **Permitir**.
4. A tela abre no navegador. Para deixar fácil: arraste o Estudio para o Dock.

O rclone: se o Mac tem o **Subir no Drive**, o Estúdio usa a mesma conexão sozinho. Se não tem, instale o Subir
no Drive primeiro (é o jeito mais fácil de deixar o rclone com a conta certa e a permissão de enviar).

## Windows

### 1. O app

1. Baixe o **Estudio-windows.zip** → botão direito → **Extrair tudo** → escolha **Documentos**.
2. Abra a pasta **Estudio** e dê dois cliques em **Estudio.exe**.
   - "O Windows protegeu o computador": **Mais informações → Executar assim mesmo**.
   - Se o Firewall perguntar: pode permitir só em redes privadas (o app só conversa com o próprio computador).
3. Para deixar fácil: botão direito no **Estudio.exe** → **Mostrar mais opções → Enviar para → Área de trabalho (criar atalho)**.

### 2. rclone

1. Baixe em **rclone.org/downloads** a versão **Windows / Intel/AMD 64 Bit** (zip).
2. Descompacte e deixe o `rclone.exe` em `C:\rclone\` (ou, sem administrador, em `C:\Users\<você>\rclone\`).
3. Crie a conexão **drive** com a conta da instituição. No Prompt de Comando:
   ```
   cd C:\rclone
   rclone config
   ```
   - `n` (nova) → nome: **drive** → tipo: **drive** (Google Drive)
   - client_id e client_secret: Enter (vazio)
   - scope: **1** (acesso total — sem isso, não consegue enviar)
   - service_account_file: Enter · Edit advanced config: **n** · Use web browser: **y**
   - No navegador, entre com a **conta da instituição** (de preferência numa janela anônima) → **Permitir**
   - Shared Drive: **n** (a "Gravações IEC" fica no Meu Drive) · Keep this remote: **y** → `q` para sair
4. Teste: `rclone lsd "drive:Gravações IEC"` lista as pastas dos professores.

---

## Configurar (engrenagem ⚙, igual no Mac e no Windows)

1. **Nome desta máquina:** ex.: `Estúdio 1 — São Gabriel`.
2. **Link do Pastas do dia:** o link da implantação "Estúdio" → **Testar**.
3. **Pasta onde o OBS grava:** a mesma do OBS em *Configurações → Saída → Gravação → Caminho*.
4. **Pasta de saída:** onde nascem as pastas dos professores (pode ser no mesmo disco, ex.: `SSD/Estudio`).
5. **Como subir:** *Pelo rclone*. **Pasta no Drive:** `drive:Gravações IEC`.
   No Windows, em **Onde está o rclone**, escolha o `rclone.exe`. → **Testar conexão** (tem que mostrar a conta da instituição).
6. **Transcrever antes de subir:** marcado. A linha embaixo mostra "Transcrição: Whisper do app".
7. **Salvar**. A agenda de hoje aparece.

**OBS (conferir, não mudar):** *Configurações → Avançado → Gravação → Formato do nome do arquivo* tem que ser o
padrão `%CCYY-%MM-%DD %hh-%mm-%ss`. O formato do vídeo (mp4, mov ou mkv) tanto faz.

## Ligar e desligar

- **Ligar:** dois cliques no Estúdio. Não abre janela de terminal: o app fica ligado em segundo plano, vigiando a
  pasta do OBS, e a tela abre no navegador.
- **Fechou o navegador sem querer?** Dois cliques no Estúdio de novo: só abre a tela.
- **Desligar:** botão **Fechar o Estúdio** no alto da tela (clique duas vezes). Com ele desligado, as gravações
  novas ficam esperando na pasta do OBS até você abrir de novo.

## Teste rápido depois de instalar (5 minutos)

1. A agenda de hoje aparece, com o professor do horário marcado como **agora**.
2. **Gravar com este professor** → **Abrir no Drive ↗** abre a pasta do dia com Footage e Originais.
3. Grave 15 segundos no OBS. A janelinha mostra **● Gravando agora**. Ao parar, o clipe aparece na tela do professor.
4. **Conferido, pode subir** → 1/3 transcrevendo → 2/3 subindo → 3/3 conferindo → "enviado, pode apagar".
   O clipe e o `.srt` estão na Footage do Drive.
5. Apague o clipe de teste do Drive e da pasta de saída.

Na primeira transcrição o Whisper demora um pouco mais para começar (está carregando o modelo).
No Windows sem placa de vídeo, a transcrição é mais lenta: uma aula de 1 hora pode levar de 30 a 60 minutos.

Se algo der errado: print da tela do Estúdio + o arquivo **estudio.log**
(Mac: `~/Library/Application Support/Estudio/` · Windows: `%APPDATA%\Estudio\`).

---

## Rodar sem o app empacotado (para quem programa)

Com Python 3.10+: `Abrir Estudio.command` (Mac) ou `Abrir Estudio.bat` (Windows), na pasta do código.
Para transcrever assim, precisa do `transcribe` do Mac em `/usr/local/bin` ou do Whisper instalado no Python.
