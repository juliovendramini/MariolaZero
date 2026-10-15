#!/bin/bash

# =========================================================================
# INSTALADOR AUTOMÁTICO - INTERFACE DE TELEMETRIA
# =========================================================================

echo "🚀 Iniciando a instalação do Painel de Telemetria..."

# 0. Destranca o sistema de arquivos (se o usuário usar partição Read-Only)
if [ -f "./remonta.sh" ]; then
    echo "🔓 Sistema protegido detectado. Executando remonta.sh..."
    sudo bash ./remonta.sh
else
    echo "ℹ️ Nenhum remonta.sh detectado. Assumindo partição livre para gravação..."
fi

# 1. Descobre quem é o usuário atual que está rodando o script
USUARIO=$USER

# 2. Instala os pacotes necessários no Linux
echo "📦 Instalando Apache e PHP..."
sudo apt update
sudo apt install -y apache2 php libapache2-mod-php

# 3. Força a ativação do PHP no Apache (resolve conflitos de texto cru)
sudo a2dismod mpm_event 2>/dev/null
sudo a2enmod mpm_prefork 2>/dev/null
VERSAO_PHP=$(php -r "echo PHP_MAJOR_VERSION.'.'.PHP_MINOR_VERSION;")
sudo a2enmod php$VERSAO_PHP 2>/dev/null

# 4. Configura as permissões de Hardware para o Apache
echo "⚙️  Configurando permissões de Hardware (i2c, gpio, video)..."
sudo usermod -aG video,i2c,dialout,gpio,tty www-data

# 5. Configura o Sudoers para o Apache rodar o Python como o usuário da placa
echo "🔑 Configurando permissões de execução (Sudoers)..."
echo "www-data ALL=($USUARIO) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/telemetria_robo > /dev/null
sudo chmod 0440 /etc/sudoers.d/telemetria_robo

# 6. Copia os arquivos da interface para a pasta do servidor
echo "📂 Copiando arquivos Web para o Apache..."
sudo rm -rf /var/www/html/*
sudo cp *.html *.css *.js *.php /var/www/html/ 2>/dev/null

# 7. Ajusta a posse da pasta web
sudo chown -R $USUARIO:www-data /var/www/html
sudo chmod -R 775 /var/www/html

# 8. Reinicia o servidor para aplicar tudo
echo "🔄 Reiniciando o servidor..."
sudo systemctl restart apache2

echo ""
echo "✅ Instalação concluída com sucesso!"
echo "🌐 Acesse no seu navegador: http://$(hostname -I | awk '{print $1}')"
echo "Lembre-se de organizar seus projetos (pastas com main.py) dentro de /home/$USUARIO/"