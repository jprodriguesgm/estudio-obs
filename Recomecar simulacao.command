#!/bin/bash
# Apaga a pasta "NPD Estudio Teste" da Mesa e o registro de gravações do app, para rodar a simulação do zero.
# Feche o app antes (Ctrl+C na janela do Terminal do Estúdio).
cd "$(dirname "$0")" || exit 1
read -r -p "Apagar a pasta de teste da Mesa e o registro do app? (s/n) " r
if [ "$r" = "s" ]; then
  python3 -m estudio simular --limpar
fi
read -r -p "Pressione Enter para fechar..."
