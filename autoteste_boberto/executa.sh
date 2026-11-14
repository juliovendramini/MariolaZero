#!/bin/bash
# Roda o autoteste pelo terminal (SSH), no robô, de dentro ou de fora da pasta:
#   bash executa.sh                          menu na tela do robô
#   bash executa.sh ?                        lista os testes que dá para pedir
#   bash executa.sh giroscopio               só um teste (ou vários: i2c motores)
#   bash executa.sh giroscopio --terminal    responde as perguntas aqui, não no teclado do robô
#   bash executa.sh --automatico             tudo sem perguntar (motores parados)
#   bash executa.sh --automatico --motores   ...e gira os motores (rodas no ar!)
echo "Iniciando o autoteste..."
source ~/meu_venv/bin/activate
PASTA=$(dirname "$(readlink -f "$0")")
python3 -u "$PASTA/main.py" "$@"
