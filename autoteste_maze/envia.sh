#!/bin/bash
# Manda a pasta deste projeto para o Mariola. É o envia.bat para Linux (e macOS).
# Uso (no terminal, dentro da pasta do projeto ou não):
#   bash envia.sh                  manda só o que mudou desde o último envio
#   bash envia.sh --tudo           manda a pasta inteira
#   bash envia.sh 192.168.2.151    usa outro IP (dá para juntar com --tudo)
# A pasta no robô tem o mesmo nome desta: /home/banana/<nome-da-pasta>.
# No fim encerra o main.py que estiver rodando no robô (como o envia.bat).
# Precisa só de ssh e tar. Sem a chave SSH ele pede a senha do robô (curso, módulo 2).

IP=192.168.1.202
USUARIO=banana

TUDO=0
for arg in "$@"; do
    case "$arg" in
        -t|--tudo) TUDO=1 ;;
        -h|--ajuda|--help) sed -n '2,9p' "$0"; exit 0 ;;
        *) IP="$arg" ;;
    esac
done

cd "$(dirname "$0")" || exit 1          # a pasta do projeto é a do script
PROJETO=$(basename "$PWD")
ROBO="$USUARIO@$IP"
MARCA=".ultimo_envio_$IP"               # a data deste arquivo = último envio para este robô
NOVA=".envio_em_andamento"
SSH_OPCOES=(-o ConnectTimeout=5)

# o último envio foi há mais de 3 horas (o robô pode ter sido regravado ou trocado): manda tudo
if [ ! -f "$MARCA" ] || [ -n "$(find "$MARCA" -mmin +180)" ]; then
    TUDO=1
fi

touch "$NOVA"   # antes de procurar: o que for salvo durante o envio vai de novo no próximo
LISTA=$(mktemp) || exit 1
trap 'rm -f "$LISTA"' EXIT

FILTRO=()
[ "$TUDO" = 0 ] && FILTRO=(-newer "$MARCA")
find . \( -name __pycache__ -o -name .git -o -name .vscode \) -prune -o -type f \
    ! -name '.ultimo_envio_*' ! -name "$NOVA" ! -name '.manifest' ! -name '*.pyc' \
    ! -name 'envia.sh' ! -name 'envia.bat' ! -name 'envia.ps1' ! -name 'upload_temp.tar.gz' \
    "${FILTRO[@]}" -print0 > "$LISTA"
QUANTOS=$(tr -cd '\0' < "$LISTA" | wc -c | tr -d ' ')

# só o python rodando um main.py (o do menu ou o do executa.sh), não um "nano main.py" aberto
ENCERRA="pkill -f '^([^ ]*/)?python[0-9.]* .*main\\.py' && echo 'Programa que estava rodando no robo: encerrado.'; true"

if [ "$QUANTOS" = 0 ]; then
    rm -f "$NOVA"
    echo "Nada mudou desde o último envio para $IP (para mandar tudo: bash envia.sh --tudo)."
    ssh "${SSH_OPCOES[@]}" "$ROBO" "$ENCERRA"
    exit 0
fi

if [ "$TUDO" = 1 ]; then
    echo "Mandando a pasta inteira ($QUANTOS arquivos) para $ROBO:~/$PROJETO ..."
else
    echo "Mandando $QUANTOS arquivo(s) que mudaram para $ROBO:~/$PROJETO :"
    tr '\0' '\n' < "$LISTA" | sed 's|^\./|  |'
fi

# um pacote só, pela mesma conexão: cria a pasta no robô, desempacota e encerra o programa.
# O -m do tar dá a data de agora aos arquivos (o relógio do robô pode estar diferente do PC).
set -o pipefail
if tar -czf - --null -T "$LISTA" |
    ssh "${SSH_OPCOES[@]}" "$ROBO" "mkdir -p ~/'$PROJETO' && tar -xzmf - -C ~/'$PROJETO' && { $ENCERRA; }"; then
    mv -f "$NOVA" "$MARCA"
    echo "Envio concluído."
else
    rm -f "$NOVA"
    echo
    echo "O envio falhou. Confira:"
    echo "  - o IP na tela do robô ($IP aqui; troque na linha IP= do envia.sh ou passe o IP: bash envia.sh 192.168.2.XXX);"
    echo "  - se o PC está na mesma rede do robô: ssh $ROBO"
    exit 1
fi
