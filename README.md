# bananaPiM4Zero
Tutorial de como instalar o Armbian no BananaPi M4 zero e configurar o que for necessário para usar na placa de robótica.

Como a versão utilizada é a de 8Gb de eMMC, devemos baixar a versão do armbian baseada em debian 12, versão Minimal(IoT). A atual no momento da criação do manual é a Armbian 25.2.2 Bookworm Minimal.

Agora devemos instalar no cartão SD, dar boot, configurar inicialmente a instação e depois instalar no eMMC usando o armbian-config.

Após isso, ligue a placa no pelo eMMC e altere o arquivo /boot/armbianEnv.txt
Insira a linha *overlays=bananapi-m4-sdio-wifi-bt* para o wifi funcionar.
Reinicie a placa novamente, agora no armbian-config conecte no wifi para poder instalar e atualizar os demais itens.

* Atualize o APT (sudo apt update)
* Instale o net-tools (sudo apt install net-tools)
* Instale o ambiente gráfico XFCE pelo armbian-config
* Instale o python3-full (sudo apt install python3-full)
* Instale o python3-pip e o pipx (sudo apt install python3-pip pipx)
* Instale o ultralytics usando um ambiente virtual persolalizado:
*   python -m venv meu_venv
    source meu_venv/bin/activate  # No Windows: meu_venv\Scripts\activate
    pip install ultralytics
    python meu_script.py (como rodar o script)
* 
