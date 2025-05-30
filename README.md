# MariolaZero
Tutorial de como instalar o Armbian no BananaPi M4 Zero (Base do MariolaZero) e configurar o que for necessário para usar na placa de robótica.

Como a versão utilizada é a de 8Gb de eMMC, devemos baixar a versão do armbian baseada em debian 12, versão Minimal(IoT) (https://www.armbian.com/bananapi-m4-zero/). A atual no momento da criação do manual é a Armbian 25.2.2 Bookworm Minimal.

Agora devemos instalar no cartão SD, dar boot, configurar inicialmente a instação e depois instalar no eMMC usando o armbian-config.

Após isso, ligue a placa já pelo eMMC (remova o cartão SD) rode o comando armbian-config (sudo armbian-config)
Entre em System -> Kernel -> SY210 Manage device tree overlay e Ative as seguintes opções:

![image](https://github.com/user-attachments/assets/ad89cdf0-6a23-4261-a717-17d71dca6672)

Reinicie a placa novamente, agora no armbian-config conecte no wifi para poder instalar e atualizar os demais itens.

* Precisamos agora ativar alguns dispositivos como portas Seriais e USBs. Para isso temos que alterar o arquivo DTB
  * Copie o arquivo DTB para a pasta do usuario:
    - scp sun50i-h618-bananapi-m4-zero.dtb banana@192.168.2.208:~
    - Agora dentro do equipamento mova o arquivo para a pasta (sudo cp sun50i-h618-bananapi-m4-zero.dtb /boot/dtb-6.6.75-current-sunxi64/allwinner/)
    - Reinicie a placa

* Vamos ativar o debug na porta serial que usamos para o primeiro terminal.
   * Edite o arquivo /boot/armbianEnv.txt, "sudo nano /boot/armbianEnv.txt" e adicione a linha "verbosity=7". No proximo reboot, você já verá o log do kernel pela serial. Isso é só para identificar problemas.


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
* Inserir no script de login do usuario a opção já iniciar o terminal com o ambiente python do usuario
  * abra o arquivo .nashrc (nano ~/.bashrc)
  * no final do arquivo adicione (source ~/meu_venv/bin/activate)
  * Agora sempre que logar com o usuario no ssh, o ambiente python já será selecionado. (Um comando a menos para esquecer :D )

* Vamos inserir um script para verificar a partição toda vez que o brick iniciar, isso pode impedir falhar de inicialização e de partição corrompida
  * Rode o comando: sudo nano /etc/systemd/system/force-fsck-root.service
  * Agora crie adicione as linhas no arquivo:
  ```
  [Unit]
  Description=Force fsck on root filesystem
  DefaultDependencies=no
  Before=local-fs.target
  
  [Service]
  Type=oneshot
  ExecStart=/sbin/fsck -f -y /
  RemainAfterExit=true
  
  [Install]
  WantedBy=local-fs.target
  ```

  * Ative o Serviço:
  ```
     sudo systemctl daemon-reexec
     sudo systemctl enable force-fsck-root.service
  ```

Agora é só reiniciar. Caso queira verificar se o fsck está rodando, rode o comando journalctl -u force-fsck-root.service

