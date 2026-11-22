# Instalar o Estúdio

Uma vez em cada computador do estúdio. Leva uns 20 minutos no Mac e uns 30 no Windows (por causa do rclone).

O Estúdio precisa de:

| O quê | Para quê | Mac | Windows |
|---|---|---|---|
| **Python 3.10 ou mais novo** | roda o app | obrigatório | obrigatório |
| **rclone** com a conexão `drive` (conta da instituição) | subir para o Drive | obrigatório | obrigatório |
| **Link do Pastas do dia** (implantação "Estúdio", acesso "Qualquer pessoa") | agenda e pastas no Drive | obrigatório | obrigatório |
| **transcribe** (mlx-whisper + ffmpeg) | transcrever antes de subir | opcional (só Mac com chip Apple) | não existe |
| **OBS** | gravar | qualquer versão | qualquer versão |

Não precisa de senha de administrador para nada do Estúdio em si.

---

## Mac do trabalho

### 1. Python

No Terminal: `python3 --version`

- Apareceu **3.10** ou mais → ok.
- Não tem, ou é 3.9 → baixe o instalador de **python.org** (macOS, "universal2") e instale. Se o Mac pedir senha de
  administrador e você não tiver, rode `xcode-select --install` (vem um Python 3.9, que também deve funcionar).

### 2. rclone (já está nos Macs do setor)

Os Macs que têm o **Subir no Drive** já estão prontos: o Estúdio usa a mesma conexão sozinho.
Se o Mac não tiver o Subir no Drive, rode o instalador dele primeiro (é o jeito mais fácil de deixar o rclone com a
conta certa e a permissão de enviar).

### 3. transcribe (opcional)

Só se quiser que o app transcreva antes de subir. No Mac onde ele já funciona, nada a fazer.
Em outro Mac (chip Apple): instale o ffmpeg e o mlx-whisper e copie o arquivo `transcribe` para `/usr/local/bin`
(igual ao seu Mac). Sem ele, o app sobe sem transcrever e avisa.

### 4. O app

1. Copie a pasta `estudio-obs` para um lugar fixo, por exemplo **Documentos**.
2. Dois cliques em **Abrir Estudio.command**.
   - Primeira vez: se o Mac bloquear, botão direito → **Abrir** → **Abrir**.
   - Se pedir para o Terminal acessar arquivos de um **volume removível** (o SSD), clique em **Permitir**.
3. O navegador abre o Estúdio. **Deixe a janela do Terminal aberta** enquanto estiver gravando.

### 5. Configurar (engrenagem ⚙)

1. **Nome desta máquina:** ex.: `Estúdio 1 — São Gabriel`.
2. **Link do Pastas do dia:** o link da implantação "Estúdio" (o que você testou hoje) → **Testar**.
3. **Pasta onde o OBS grava:** a mesma que está no OBS em *Configurações → Saída → Gravação → Caminho*
   (ex.: o SSD Ilha 3).
4. **Pasta de saída:** onde nascem as pastas dos professores (pode ser no mesmo SSD, ex.: `SSD/Estudio`).
5. **Como subir:** *Pelo rclone*. **Pasta no Drive:** `drive:Gravações IEC` → **Testar conexão** → tem que
   mostrar a conta da instituição.
6. **Transcrever antes de subir:** marcado se tiver o transcribe.
7. **Salvar**. A agenda de hoje aparece.

### 6. OBS (conferir, não mudar)

*Configurações → Avançado → Gravação → Formato do nome do arquivo* tem que ser o padrão:
`%CCYY-%MM-%DD %hh-%mm-%ss`. O app usa a data e a hora do nome. Formato do vídeo: mp4, mov ou mkv, tanto faz.

---

## Windows

### 1. Python

1. Baixe em **python.org → Downloads → Windows** o instalador do Python 3.12 ou 3.13 (64-bit).
2. Na primeira tela, marque **Add python.exe to PATH** e clique em **Install Now**
   (instala só para o usuário, sem administrador).
3. Confira no Prompt de Comando: `py --version`.

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

### 3. O app

1. Copie a pasta `estudio-obs` para, por exemplo, **Documentos**.
2. Dois cliques em **Abrir Estudio.bat**.
   - Se o Windows mostrar "O Windows protegeu o computador": **Mais informações → Executar assim mesmo**.
   - Se o Firewall perguntar: pode permitir só em redes privadas (o app só conversa com o próprio computador).
3. O navegador abre o Estúdio. **Deixe a janela preta aberta** enquanto estiver gravando.

### 4. Configurar (engrenagem ⚙)

Igual ao Mac, com estas diferenças:
- **Onde está o rclone:** escolha o `rclone.exe` (ex.: `C:\rclone\rclone.exe`).
- **Pasta no Drive:** `drive:Gravações IEC` → **Testar conexão**.
- **Transcrever antes de subir:** desmarque (no Windows ainda não existe). A transcrição pode ser feita depois num Mac.

### 5. O que é normal no Windows

- Enquanto o OBS grava, o Windows não deixa mover o arquivo. Logo depois de parar, pode aparecer por alguns
  segundos "Não consegui mover ainda": o app tenta de novo sozinho.

---

## Teste rápido depois de instalar (5 minutos)

1. A agenda de hoje aparece, com o professor do horário marcado como **agora**.
2. **Gravar com este professor** → **Abrir no Drive ↗** abre a pasta do dia com Footage e Originais.
3. Grave 15 segundos no OBS. A janelinha mostra **● Gravando agora**. Ao parar, o clipe aparece na tela do professor.
4. **Conferido, pode subir** → "enviado, pode apagar" e o clipe está na Footage do Drive.
5. Apague o clipe de teste do Drive e da pasta de saída.

Se algo der errado, tire um print da tela do Estúdio **e** da janela do Terminal / janela preta.
