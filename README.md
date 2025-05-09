# MariolaZero
Tutorial de como instalar o Armbian no BananaPi M4 Zero (Base do MariolaZero) e configurar o que for necessário para usar na placa de robótica.

Como a versão utilizada é a de 8Gb de eMMC, devemos baixar a versão do armbian baseada em debian 12, versão Minimal(IoT) (https://www.armbian.com/bananapi-m4-zero/). A atual no momento da criação do manual é a Armbian 25.2.2 Bookworm Minimal.

Agora devemos instalar no cartão SD, dar boot, configurar inicialmente a instação e depois instalar no eMMC usando o armbian-config.

Após isso, ligue a placa já pelo eMMC (remova o cartão SD) rode o comando armbian-config (sudo armbian-config)
Entre em System -> Kernel -> SY210 Manage device tree overlay e Ative as seguintes opções:
.
![image](https://github.com/user-attachments/assets/ad89cdf0-6a23-4261-a717-17d71dca6672)


Insira a linha *overlays=bananapi-m4-sdio-wifi-bt* para o wifi funcionar.

Reinicie a placa novamente, agora no armbian-config conecte no wifi para poder instalar e atualizar os demais itens.

Para as duas portas usbC funcionarem como HOST, precisamos alterar a configuração do conector CN2 (USB0) para isso precisamos editar o arquivo DTB dele. E alterar as linhas para desativar o USB OTG e ATIVAR os dois modos HOSTs ta porta USB0.
   * Primeiro passo é transformar o dtb em dts
      * Copie o arquivo para a pasta do usuario (cp /boot/dtb-6.6.75-current-sunxi64/allwinner/sun50i-h618-bananapi-m4-zero.dtb ~/)
      * Transforme ele em dts (dtc -O dts sun50i-h618-bananapi-m4-zero.dtb -o sun50i-h618-bananapi-m4-zero.dts)
      * abra o arquivo dts criado com o nano
         * no bloco usb@5100000, coloque ele como *status = "disabled";*
         * no bloco usb@5101000, coloque ele como *status = "okay"*
         * no bloco usb@5101400, coloque ele como *status = "okay"*
     * agora, salve o arquivo, e converta pra dtb com o comando: (dtc -O dtb sun50i-h618-bananapi-m4-zero.dts -o sun50i-h618-bananapi-m4-zero.dtb)
     * vamos fazer um backup da versão original e depois substituir com a versão editada na pasta /boot
     * cp /boot/dtb-6.6.75-current-sunxi64/allwinner/sun50i-h618-bananapi-m4-zero.dtb ~/sun50i-h618-bananapi-m4-zero.dtb_original
     * agora, copie para a pasta /boot o modificado (sudo cp ~/sun50i-h618-bananapi-m4-zero.dtb /boot/dtb-6.6.75-current-sunxi64/allwinner/sun50i-h618-bananapi-m4-zero.dtb)
     * reinicie a placa

* Atualize o APT (sudo apt update)
* Instale alguns pacotes iniciais (sudo apt install net-tools i2c-tools build-essential libgl1)
* Instale o ambiente gráfico XFCE pelo armbian-config
* Instale o python3-full (sudo apt install python3-full)
* Instale o python3-pip e o pipx (sudo apt install python3-pip pipx)
* Instale o ultralytics usando um ambiente virtual personalizado:
    * python3 -m venv meu_venv
    * source meu_venv/bin/activate  
    * pip install ultralytics
    * python3 meu_script.py (como rodar o script)
* Para utilizar as seriais no python é necessário instalar a biblioteca serial (pip install pyserial), ATENÇÂO, sempre que for usar o PIP, você deve usar o comando "source meu_venv/bin/activate" antes (caso ainda nao esteja com o ambiente personalizado já aberto)
* Para acessar os pinos GPIO do BananaPI é necessário instalar a biblioteca (python3-libgpiod)
     * Instale o que é necessário (sudo apt install python3-libgpiod libgpiod-dev python3-dev)
     * Crie o grupo (sudo groupadd gpio)
     * Adicione o usuario ao grupo de GPIO (sudo usermod -aG gpio $USER)
     * Crie o arquivo gipo-rules "sudo nano /etc/udev/rules.d/99-gpio.rules"
          * Dentro do arquivo adicione as duas linhas:
             - SUBSYSTEM=="gpio", KERNEL=="gpiochip[0-9]*", GROUP="gpio", MODE="0660"
             - SUBSYSTEM=="gpio", KERNEL=="gpio[0-9]*", GROUP="gpio", MODE="0660"
      * Recarregue as regras do udev
         * sudo udevadm control --reload-rules
         * sudo udevadm trigger
      * Reinicie a placa
* Para acessar os sensores i2c é necessário instalar o modulo smbus2 e algumas bibliotecas  (pip install smbus2 gpiod netifaces)
   * Agora temos que dar permissão de acesso as portas i2c
   * Crie um arquivo de regra udev (sudo nano /etc/udev/rules.d/99-i2c.rules)
      * Coloque dentro do arquivo (KERNEL=="i2c-[0-9]*", GROUP="i2c", MODE="0660")
   * Crie o grupo i2c (sudo groupadd i2c) 
   * Adicione seu usuário ao grupo i2c (sudo usermod -aG i2c $USER)
   * Agora reinicie a placa
* A porta i2c utilizada para acesso aos sensores é a i2c-1 através do multiplexador TCA9548A
* Para a tela oled funcionar temos que instalar as seguintes libs: (pip install luma.oled)
* Possibilitar acessar via ssh sem ficar pedindo senha:
  * Gera uma chave publica no seu computador, se já fez isso antes, nao é necessário refazer (ssh-keygen -t rsa -b 4096)
  * ssh-copy-id USUARIO@IP (substituia o usuario e o IP pelo correto) (no linux)
  * No windows não tem como ser feito com comando, abra o arquivo id_rsa.pub, na pasta .ssh dentro da pasta seu usuario, copie a linha
  * Logue na placa por ssh e rode os comandos
    * mkdir -p ~/.ssh
    * nano ~/.ssh/authorized_keys
    * Agora, copie o valor do arquivo id_rsa.pub e cole dentro desse arquivo, salve e saia
    * Agora, qualquer login por ssh não pedirá mais senha.
* Copie a pasta do projeto menuPrincipal para a pasta do usuario
  * Dentro da placa, coloque o arquivo start.sh para ser executável
    * Crie um serviço para iniciar o script toda vez que a placa ligar (sudo nano /etc/systemd/system/menuPrincipal.service)
      * O código do que colocar no serviço está no arquivo exemplo.service na pasta do projeto
    * Rode agora sudo systemctl daemon-reexec
    * Depois, sudo systemctl enable menuPrincipal.service
* De permissão para o shutdown e outros comandos necessários sejam executados sem precisar de senha
  * Digite sudo visudo
  * Dentro do arquivo, no final dele, coloque as seguintes linhas:
     - banana ALL=(ALL) NOPASSWD: /usr/bin/psd-overlay-helper
     - banana ALL=(ALL) NOPASSWD: /sbin/shutdown
     - banana ALL=(ALL) NOPASSWD: /sbin/ifconfig
       (troque banana pelo usuario escolhido)
  * Reinicie a placa e veja se a tela exibirá o menu automaticamente (lembre-se a tela e o teclado devem estar encaixados para isso funcionar)

