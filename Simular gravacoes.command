#!/bin/bash
# Fase 1 do teste: faz o papel do OBS. Cria a pasta "NPD Estudio Teste" na Mesa e grava arquivos falsos.
# Abra antes o "Abrir Estudio.command" (o app precisa estar aberto no navegador).
cd "$(dirname "$0")" || exit 1
python3 -m estudio simular
echo
read -r -p "Simulação terminada. Pressione Enter para fechar esta janela..."
