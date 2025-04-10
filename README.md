# bananaPiM4Zero
Tutorial de como instalar o Armbian no BananaPi M4 zero e configurar o que for necessário para usar na placa de robótica.

Como a versão utilizada é a de 8Gb de eMMC, devemos baixar a versão do armbian baseada em debian 12, versão Minimal(IoT). A atual no momento da criação do manual é a Armbian 25.2.2 Bookworm Minimal.

Agora devemos instalar no cartão SD, dar boot, configurar inicialmente a instação e depois instalar no eMMC usando o armbian-config.

Após isso, ligue a placa no pelo eMMC rode o comando armbian-config (sudo armbian-config)
Entre em System -> Kernel -> SY210 Manage device tree overlay e Ative as seguintes opções:
![image](https://github.com/user-attachments/assets/436cc935-2355-4c8a-824f-18c14ba28864)

Insira a linha *overlays=bananapi-m4-sdio-wifi-bt* para o wifi funcionar.
Reinicie a placa novamente, agora no armbian-config conecte no wifi para poder instalar e atualizar os demais itens.

Para as duas portas usbC funcionarem como HOST, precisamos alterar a configuração do conector CN2 (USB0) para isso precisamos editar o arquivo DTB dele. E alterar as linhas para desativar o USB OTG e ATIVAR os dois modos HOSTs ta porta USB0.

* Atualize o APT (sudo apt update)
* Instale alguns pacotes iniciais (sudo apt install net-tools i2c-tools)
* Instale o ambiente gráfico XFCE pelo armbian-config
* Instale o python3-full (sudo apt install python3-full)
* Instale o python3-pip e o pipx (sudo apt install python3-pip pipx)
* Instale o ultralytics usando um ambiente virtual personalizado:
    * python -m venv meu_venv
    * source meu_venv/bin/activate  
    * pip install ultralytics
    * python meu_script.py (como rodar o script)
* Para utilizar as seriais no python é necessário instalar a biblioteca serial (pip install serial pyserial), ATENÇÂO, sempre que for usar o PIP, você deve usar o comando "source meu_venv/bin/activate" antes (caso ainda nao esteja com o ambiente personalizado já aberto)
* Para acessar os pinos GPIO do BananaPI é necessário instalar a biblioteca (python3-libgpiod)
     * Instale python3-libgpiod e a libgpiod-dev (sudo apt install python3-libgpiod libgpiod-dev)
     * Crie o grupo (sudo groupadd gpio)
     * Adicione o usuario ao grupo de GPIO (sudo usermod -aG gpio $USER)
     * Crie o arquivo gipo-rules "sudo nano /etc/udev/rules.d/99-gpio.rules"
          * Dentro do arquivo adicione KERNEL=="gpio*", GROUP="gpio", MODE="0660"
      * Recarregue as regras do udev
         * sudo udevadm control --reload-rules
         * sudo udevadm trigger
      * Reinicie a placa
* Para acessar os sensores i2c é necessário instalar o modulo smbus2  (pip install smbus2)
   * Agora temos que dar permissão de acesso as portas i2c
   * Crie um arquivo de regra udev (sudo nano /etc/udev/rules.d/99-i2c.rules)
      * Coloque dentro do arquivo (KERNEL=="i2c-[0-9]*", GROUP="i2c", MODE="0660")
   * Crie o grupo i2c (sudo groupadd i2c) 
   * Adicione seu usuário ao grupo i2c (sudo usermod -aG i2c $USER)
   * Agora reinicie a placa
* Para acessar os sensores i2c é necessário instalar o modulo adafruit-blinka e o módulo do multiplexador i2c adafruit-circuitpython-tca9548a (pip install adafruit-blinka adafruit-circuitpython-tca9548a gpiod)
* Para utilizar o sensor de cor TCS34725 via porta i2c é necessário instalar o módulo adafruit-circuitpython-tcs34725 (pip install adafruit-circuitpython-tcs34725)
* Para usar o sensor a laser VL53lox via porta i2c...
* Para poder executar os scripts via python com o usuario normal e acessar os sensores:
   * monte o debug (sudo mount -t debugfs none /sys/kernel/debug)
   * Verifique se o grupo existe: (grep gpio /etc/group)
      * Se não existir, rode: (sudo groupadd gpio)
   * Adicione o usuario ao grupo (sudo usermod -aG gpio $USER)
   * Dê permissão para ao diretório (sudo chmod -R a+r /sys/kernel/debug/gpio)
* Para usar o PWM é necessario fazer um overlay, para isso, baixe o arquivo pwm-pi12.dts, coloque na pasta do usuario e rode o comando
     *
