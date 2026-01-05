#!/bin/bash
echo "Iniciando o script remoto..."
nomeProjeto=$(basename "$PWD") #usa como nome de envio o nome do projeto
source meu_venv/bin/activate
python3 -u ~/$nomeProjeto/main.py