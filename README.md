# MariolaZero
Tutorial de como instalar o Armbian no BananaPi M4 Zero (Base do MariolaZero) e configurar o que for necessário para usar na placa de robótica.

Como a versão utilizada é a de 8Gb de eMMC, devemos baixar a versão do armbian baseada em debian 12, versão Minimal(IoT) (https://www.armbian.com/bananapi-m4-zero/). A atual no momento da criação do manual é a Armbian 25.2.2 Bookworm Minimal.

Agora devemos instalar no cartão SD, dar boot, configurar inicialmente a instação e depois instalar no eMMC usando o armbian-config.

Opcional:
* Antes de iniciar o cartão na placa, recomendo criar um partição separada para os usuários, mas para isso precisamos utilizar o Linux. Coloque o cartão no linux. Use o Gparted, altere o tamanho da primeira partição para ter algo como uns 4200MB e crie uma nova partição ext4 com uns 3000MB. Lembrando que não podemorar criar maior mesmo o cartão tendo mais espaço porque iremos colocar tudo na EMMC de 8GB dele. Caso queira rodar do cartão SD, esses tamanhos podem ser diferentes.

* Apoś isso, edite o arquivo /etc/fstab da partição principal do cartão, o nome dela deve ser armbi_root. Adicione a linha de montagem /home (UUID=65cca456-7f07-4d89-9ad2-33a9a64e5c59 /home  ext4  defaults,noatime  0 2) o UUID deve ser alterado. Para pegar o nome, rode o comando "blkid" e pegue.

Após isso, ligue a placa já pelo eMMC (remova o cartão SD) rode o comando armbian-config (sudo armbian-config)
Entre em System -> Kernel -> SY210 Manage device tree overlay e Ative as seguintes opções:

![image](https://github.com/user-attachments/assets/ad89cdf0-6a23-4261-a717-17d71dca6672)

Reinicie a placa novamente, agora no armbian-config conecte no wifi para poder instalar e atualizar os demais itens.

* Precisamos agora ativar alguns dispositivos como portas Seriais e USBs. Para isso temos que alterar o arquivo DTB
  * Baixe o arquivo Dtb que está neste repositório para seu computador. 
  * Acesse pelo terminal, entre no local onde está o DTB e copie o arquivo DTB para a pasta do usuario:
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

* Instalando o servidor SAMBA para compartilhar a pasta do usuário com acesso remoto no windows:
  * Instale os pacotes: (sudo apt install samba smbclient cifs-utils)
  * Edite o arquivo "sudo nano /etc/samba/smb.conf"
     * No final dele adicione:
       ```
         [home]
              path = /home/banana
              browseable = yes
              writable = yes
              guest ok = yes
              create mask = 0777
              directory mask = 0777
       ```
    * Crie o usuário pro samba: (sudo smbpasswd -a banana)
    * Reinicie o servidor: (sudo systemctl restart smbd)
    
    * Caso a partição / esteja montada como somente-leitura (altamente recomendado), alguns passos serão necessários:
      * Ative o modo gravação da partição, inicie o samba e depois: 
      * rode:
        ```
        sudo mkdir -p /home/samba-data/{private,cache,run,lock}
        sudo chown -R root:root /home/samba-data
        sudo chmod -R 755 /home/samba-data
        sudo mv /var/lib/samba/private /var/lib/samba/private.bak
        sudo ln -s /home/samba-data/private /var/lib/samba/private
        
        sudo mv /var/cache/samba /var/cache/samba.bak
        sudo ln -s /home/samba-data/cache /var/cache/samba
        
        sudo mv /var/run/samba /var/run/samba.bak
        sudo ln -s /home/samba-data/run /var/run/samba
        
        sudo mv /var/lock/samba /var/lock/samba.bak
        sudo ln -s /home/samba-data/lock /var/lock/samba

        sudo cp /var/lib/samba/private.bak/secrets.tdb /home/samba-data/private/
        sudo chown root:root /home/samba-data/private/secrets.tdb
        sudo chmod 600 /home/samba-data/private/secrets.tdb

        


        sudo mv /var/lib/samba/account_policy.tdb /home/samba-data/registry/
        sudo ln -s /home/samba-data/registry/account_policy.tdb /var/lib/samba/account_policy.tdb
        sudo mv /var/lib/samba/group_mapping.tdb /home/samba-data/registry/
        sudo ln -s /home/samba-data/registry/group_mapping.tdb /var/lib/samba/group_mapping.tdb
        sudo mv /var/lib/samba/share_info.tdb /home/samba-data/registry/
        sudo ln -s /home/samba-data/registry/share_info.tdb /var/lib/samba/share_info.tdb


        #ative o serviço para iniciar quando o equipamento ligar
        sudo systemctl enable smbd
        
        ```
      
