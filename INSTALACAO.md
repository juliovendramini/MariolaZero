# Instalação do MariolaZero (Banana Pi M4 Zero + Armbian)

Como preparar o Linux de um brick Mariola do zero: gravar o Armbian, passar para a eMMC, trocar
para o kernel 6.18, instalar o Python e as bibliotecas, dar as permissões, ligar o menu, configurar
rede, câmeras, áudio e cooler, e por fim deixar a raiz somente leitura.

* **Usuário do sistema:** `banana`. Troque nos comandos se usar outro.
* **IP:** os exemplos usam `192.168.2.151`; use o que aparece na tela do brick.
* **Arquivos de apoio** (cooler, regra das câmeras, overlays, `remonta.sh`): pasta
  [`instalacao/`](instalacao/).
* **Conectores e pinagem:** [`documentação/Conectores.md`](documentação/Conectores.md).

## Duas imagens

| | **Line e Maze** (brick do curso) | **@Work** |
|---|---|---|
| Placa | BPI-M4 Zero com **8 GB** de eMMC | BPI-M4 Zero com **32 GB** de eMMC |
| Sistema | **Armbian Bookworm** Minimal (Debian 12) | **Armbian Noble** (Ubuntu 24.04), para o **ROS2** |
| Rede | `systemd-networkd` (netplan) | NetworkManager (`nmcli`) |
| Cooler | não usa | usa (`fancontrol`, processamento alto constante) |
| Neste documento | seções 1 a 15 e 17 a 18 | o que foi registrado está no [apêndice D](#apêndice-d--imagem-work-ubuntu-2404--ros2); a seção 16 e a parte do cooler da seção 13 vieram dela |

Quando uma seção vale só para uma das imagens, ela diz.

> Esta documentação junta e reorganiza os arquivos antigos, que estão em `_instalacao_antiga/`
> (o README antigo, `README-kernel-6.18.md`, `OTIMIZACAO_BOOT_MARIOLA_NOBLE.md`,
> `INTALACAO_ORANGEPIZERO_LTS.md`, `tutoriais.md`, `WIFI_INTEGRACAO.md`, os scripts e a pasta
> `ScriptsIA/`). O [apêndice B](#apêndice-b--o-que-ficou-só-em-_instalacao_antiga) lista o que
> ficou só lá.

## O que foi conferido num brick (20/10/2026)

Os arquivos antigos discordavam entre si em alguns pontos. Um brick ligado (Armbian 25.2.2
Bookworm, kernel 6.18.42) resolveu quase todos; o [apêndice C](#apêndice-c--brick-conferido-em-20102026)
tem o estado completo dele e o que vale ajustar.

1. **Samba:** o brick usa a configuração do README antigo (seção 15). A do `ScriptsIA` não está
   instalada.
2. **Cópia para a eMMC:** foi por `dd`: o cartão e a eMMC têm os **mesmos UUIDs** (seção 4).
3. **Partições:** raiz de **6,3 GB** e `/home` de **1 GB**, ocupando a eMMC inteira; a raiz guarda
   também o ambiente Python (`/meu_venv`, 1,3 GB) (seções 2 e 6).
4. **Cooler:** só a imagem @Work usa. O cartão do brick conferido tinha um `fancontrol` antigo
   instalado, que na Line/Maze não faz falta (apêndice C).
5. **Pacotes do kernel:** os `.deb` mais novos (6.18.44) ficam na pasta `debs/` do repositório,
   **fora do git** (o `linux-image` tem 171 MB e o GitHub recusa arquivos acima de 100 MB) (seção 5).
   No brick conferido, a eMMC estava com o sistema antigo (kernel 6.6) e o atualizado só no cartão;
   o Julio clonou a partição 1 do cartão para a eMMC e o brick passou a subir pela eMMC com o 6.18.42.

## Sumário

1. [Visão geral](#1-visão-geral)
2. [Preparar o cartão SD](#2-preparar-o-cartão-sd)
3. [Primeiro boot e acesso](#3-primeiro-boot-e-acesso)
4. [Passar para a eMMC](#4-passar-para-a-emmc)
5. [Kernel 6.18 e overlays](#5-kernel-618-e-overlays)
6. [Pacotes e Python](#6-pacotes-e-python)
7. [Permissões de GPIO e I2C](#7-permissões-de-gpio-e-i2c)
8. [SSH sem senha](#8-ssh-sem-senha)
9. [Menu principal, sudo e ambiente Python](#9-menu-principal-sudo-e-ambiente-python)
10. [Rede](#10-rede)
11. [Câmeras USB com nome fixo](#11-câmeras-usb-com-nome-fixo)
12. [Áudio](#12-áudio)
13. [Temperatura e cooler](#13-temperatura-e-cooler)
14. [Raiz somente leitura e verificação do disco](#14-raiz-somente-leitura-e-verificação-do-disco)
15. [Samba](#15-samba)
16. [Deixar o boot mais rápido (opcional)](#16-deixar-o-boot-mais-rápido-opcional)
17. [Recuperação](#17-recuperação)
18. [Compilar a imagem ou o kernel](#18-compilar-a-imagem-ou-o-kernel)
- [Apêndice A — Orange Pi Zero LTS](#apêndice-a--orange-pi-zero-lts)
- [Apêndice B — O que ficou só em `_instalacao_antiga/`](#apêndice-b--o-que-ficou-só-em-_instalacao_antiga)
- [Apêndice C — Brick conferido em 20/10/2026](#apêndice-c--brick-conferido-em-20102026)
- [Apêndice D — Imagem @Work (Ubuntu 24.04 + ROS2)](#apêndice-d--imagem-work-ubuntu-2404--ros2)

---

## 1. Visão geral

Imagem da **Line e Maze**:

| Item | Escolha |
|---|---|
| Placa | Banana Pi BPI-M4 Zero (Allwinner H618, 4× Cortex-A53), versão com **8 GB de eMMC** |
| Sistema | **Armbian 25.2.2 Bookworm Minimal (IoT)** (Debian 12), de https://www.armbian.com/bananapi-m4-zero/ |
| Kernel | **6.18** (o 6.6 que vem na imagem não tem a Ethernet 100M nem o áudio analógico) |
| Partições | raiz (`/`, somente leitura no fim) + `/home` separada e gravável |
| Rede (Minimal) | `systemd-networkd` (configuração em `/etc/systemd/network/` e netplan) |
| Python | ambiente virtual `/meu_venv` (link `~/meu_venv`), ativado no login |
| Programas | menu principal (`menuPrincipal/`) iniciado por serviço no boot |

Ordem: instale tudo com a raiz **gravável** e só no fim (seção 14) passe a raiz para somente
leitura.

## 2. Preparar o cartão SD

1. Grave a imagem do Armbian no cartão SD (balenaEtcher, Raspberry Pi Imager ou `dd`).
2. **(Recomendado) Partição `/home` separada**, feita num computador **Linux** antes do primeiro
   boot:
   1. No **GParted**, deixe a primeira partição (a raiz) com ~**6,3 GB** e crie logo depois uma
      partição **ext4** de ~**1 GB** para a `/home`. É o que o brick conferido usa e cabe na eMMC
      de 8 GB (7,3 GB úteis), para onde tudo vai ser copiado: não passe disso mesmo com cartão
      grande. A raiz fica maior porque guarda também o ambiente Python (seção 6). (O README antigo
      sugeria 4200 MB + 3000 MB, com o ambiente Python na `/home`.)
   2. Descubra o UUID da partição nova:
      ```bash
      sudo blkid
      ```
      Procure o dispositivo da partição nova (ex.: `/dev/sdb2`) e copie o valor de `UUID=`.
   3. Monte a partição principal do cartão (rótulo `armbian_root`) e acrescente ao `/etc/fstab`
      **dela** (troque o UUID pelo seu):
      ```
      UUID=65cca456-7f07-4d89-9ad2-33a9a64e5c59 /home ext4 defaults,noatime 0 2
      ```
      (No brick conferido a linha está como `defaults,nofail 0 0`: com `nofail` o sistema sobe
      mesmo se a `/home` falhar.)
   4. Copie a `/home` original para a partição nova, preservando donos, permissões e links:
      ```bash
      sudo mkdir /mnt/nova_home
      sudo mount /dev/sdX2 /mnt/nova_home
      sudo rsync -aAX /media/seu_usuario/armbian_root/home/ /mnt/nova_home/
      ls -la /mnt/nova_home/
      ```
      Troque `/dev/sdX2` e o caminho de origem pelos do seu computador. Sem o `-aAX` os usuários
      podem não conseguir entrar.
   5. Confira a cópia e apague a `/home` antiga **da partição principal**:
      ```bash
      sudo rm -r /media/seu_usuario/armbian_root/home/*
      ```


## 3. Primeiro boot e acesso

* **Pela serial de debug** (funciona sem rede e mostra o boot): os 3 pinos no canto da lateral do
  brick, ao lado da mini HDMI; o pino mais externo é o **GND**. Conversor USB-serial de 3,3 V,
  **115200 bps** (8N1). Passo a passo no [curso, módulo 2, item 2.3](curso/02-ambiente-e-envio.md).
* Ou com monitor na mini HDMI e teclado USB.

No primeiro boot o Armbian pede a senha do root e cria o usuário: crie **`banana`**. Depois:

* **Wi-Fi:** `sudo armbian-config` → Network.
* **Log do kernel na serial** (só para achar problemas): acrescente `verbosity=7` em
  `/boot/armbianEnv.txt`.
* **Desligar a atualização automática do kernel:** `armbian-config` → System → Updates → Disable
  Kernel updates. (Depois da seção 5 o kernel também fica travado com `apt-mark hold`.)

## 4. Passar para a eMMC

Com tudo pronto no cartão, copie o cartão **inteiro** para a eMMC com `dd` (assim o U-Boot, que fica
cru no começo do dispositivo, vai junto). Foi assim no brick conferido: cartão e eMMC têm os mesmos
UUIDs e PARTUUIDs. (O README antigo falava em "instalar no eMMC usando o `armbian-config`", que
cria partições novas na eMMC em vez de copiar o cartão.)

Como a eMMC de 8 GB tem 7,3 GB úteis, as partições do cartão precisam caber nela (seção 2).

> **Depois de copiar, tire o cartão.** O BROM do H618 tenta o **cartão SD antes da eMMC**, e com
> os UUIDs iguais o Linux pode montar a raiz de um e a `/home` do outro. Foi o que aconteceu no
> brick conferido: raiz do cartão (`mmcblk0p1`) e `/home` da eMMC (`mmcblk2p2`). Em compensação, um
> cartão bom no slot sempre dá boot, mesmo com a eMMC estragada (seção 17).

**Imagem @Work (eMMC de 32 GB):** o cartão de 32 GB não cabe inteiro na eMMC com `dd`. Use o
`instalacao/clona_sd_emmc.sh`, que copia os arquivos para partições novas (apêndice D).

## 5. Kernel 6.18 e overlays

O kernel 6.6 da Armbian 25.2.2 não tem a Ethernet 100M da placa: ela vem do PHY interno AC300 do
SoC, pelo conector FPC de 24 pinos, e o device tree antigo descrevia um PHY externo que não existe.
O suporte certo (Ethernet e codec de áudio analógico) entrou no PR
[armbian/build#10328](https://github.com/armbian/build/pull/10328), que está no `main`. Até sair
numa versão estável, use o kernel 6.18 (nightly ou compilado, seção 18).

Kernel e sistema são independentes no Armbian: dá para trocar só o kernel e manter o Bookworm.

1. **Confira o branch** (precisa ser `current`, para os pacotes novos substituírem os antigos):
   ```bash
   cat /etc/armbian-release | grep -E 'VERSION|BRANCH'
   uname -r
   ```
2. **Copie os dois pacotes** para a placa. Os mais novos ficam na pasta `debs/` do repositório
   (6.18.44, gerados com os dois overlays locais; a pasta fica fora do git porque o `linux-image`
   tem 171 MB). Só o `linux-image` e o `linux-dtb` são necessários; o `linux-headers` serve para
   compilar módulos no robô e o `linux-libc-dev` para compilar programas contra os cabeçalhos do
   kernel.
   ```bash
   scp debs/linux-image-current-sunxi64_*.deb banana@192.168.2.151:~
   scp debs/linux-dtb-current-sunxi64_*.deb banana@192.168.2.151:~
   ```
3. **Raiz gravável** (obrigatório se ela já estiver somente leitura): `sudo mount -o remount,rw /`
   ou `~/remonta.sh`.
4. **Instale:**
   ```bash
   sudo dpkg -i linux-image-current-sunxi64_*.deb linux-dtb-current-sunxi64_*.deb
   ```
   Um aviso de que não foi possível apagar `/boot/dtb-6.6.75-current-sunxi64` é inofensivo (é o DTB
   customizado antigo, sem dono); apague depois de validar o boot.
5. **Overlays** em `/boot/armbianEnv.txt` (linha completa):
   ```
   overlays=bananapi-m4-pi-5-6-i2c0 bananapi-m4-pi-7-8-i2c1 bananapi-m4-sdio-wifi-bt gpu uart2-ph bananapi-m4-zero-fpc24-eth bananapi-m4-pi-13-14-uart4 bananapi-m4-ph-2-3-uart5 bananapi-m4-zero-usb0-host pwm1-pi11 cpu-opp-1512-speed0
   ```

   | Overlay | Função | Origem |
   |---|---|---|
   | `bananapi-m4-pi-5-6-i2c0` | I2C0 nos pinos PI5/PI6 (tela e teclado) | oficial |
   | `bananapi-m4-pi-7-8-i2c1` | I2C1 nos pinos PI7/PI8 (sensores, pelo mux TCA9548A) | oficial |
   | `bananapi-m4-sdio-wifi-bt` | Wi-Fi e Bluetooth | oficial |
   | `gpu` | Mali (Panfrost) | oficial |
   | `uart2-ph` | UART2 nos pinos PH5/PH6 | oficial |
   | `bananapi-m4-pi-13-14-uart4` | UART4 nos pinos PI13/PI14 | oficial |
   | `bananapi-m4-ph-2-3-uart5` | UART5 nos pinos PH2/PH3 | oficial |
   | `pwm1-pi11` | PWM1 no pino PI11 (cooler da imagem @Work, seção 13; na Line/Maze não é preciso) | oficial |
   | `bananapi-m4-zero-fpc24-eth` | Ethernet 100M (precisa da placa de expansão do FPC24) | PR #10328 |
   | `bananapi-m4-zero-usb0-host` | porta USB-C como **host** em vez de device | local |
   | `cpu-opp-1512-speed0` | libera 1512 MHz em chips speed0 (overclock, seção 13) | local |

   **O DTB customizado do kernel 6.6 não é mais necessário:** as seriais e o modo da USB agora vêm
   dos overlays, que sobrevivem a atualizações de kernel. Os dois overlays **locais** não existem
   no Armbian e entram na compilação (seção 18); os fontes estão em
   [`instalacao/overlays/`](instalacao/overlays/).

   Sem a placa do FPC24, o overlay da Ethernet só reserva os pinos PA0–PA9 e o PWM5 à toa.

   O `cpu-opp-1512-speed0` é **opcional** (overclock): o brick conferido **não** usa, e roda a
   1416 MHz.
6. **Reinicie** com o cabo serial ligado (115200) na primeira vez.
7. **Confira:**
   ```bash
   ls /dev/ttyS*        # UART0 (debug), UART2, UART4 e UART5
   ls /dev/i2c-*
   lsusb
   cat /proc/device-tree/soc/usb@5100000/status   # disabled (OTG desligado)
   cat /proc/device-tree/soc/usb@5101000/status   # okay (host ligado)
   ```
   Se algo na USB-C não for reconhecido, confira o `bananapi-m4-zero-usb0-host`.
8. **Trave o kernel**, para um `apt upgrade` não trazer o 6.6 de volta (e a Ethernet parar):
   ```bash
   sudo apt-mark hold linux-image-current-sunxi64 linux-dtb-current-sunxi64
   apt-mark showhold      # os dois têm de aparecer
   ```
   (No brick conferido só o `linux-image` estava travado.)
   Quando uma versão estável do Armbian tiver o PR #10328, destrave:
   ```bash
   sudo apt-mark unhold linux-image-current-sunxi64 linux-dtb-current-sunxi64
   ```

**U-Boot:** não precisa atualizar; o da 25.2.2 carrega o 6.18. Ele fica gravado cru no offset de
8 KB do dispositivo, então o `dpkg` não mexe nele.

## 6. Pacotes e Python

```bash
sudo apt update
sudo apt install net-tools i2c-tools build-essential libgl1
sudo apt install python3-full python3-pip pipx
sudo apt install python3-libgpiod libgpiod-dev python3-dev
sudo apt install avrdude      # regravar o firmware do Mariola (firmware/mariola/)
```

Interface gráfica XFCE: opcional, pelo `armbian-config`.

O `avrdude` (7.1 no brick conferido) grava o firmware da placa do Mariola pela própria serial USB,
com o RESET apertado à mão: como fazer em [`firmware/mariola/LEIAME.md`](firmware/mariola/LEIAME.md).

**Ambiente virtual** com as bibliotecas do Mariola. Ele fica em **`/meu_venv`, na raiz**, com um
link `~/meu_venv` na pasta do usuário: com o ultralytics (e o PyTorch que vem junto) ele passa de
1,3 GB e não cabe na `/home` de 1 GB. Os programas e o `start.sh` do menu usam sempre o caminho
`~/meu_venv`.

```bash
sudo mkdir /meu_venv
sudo chown banana:banana /meu_venv
python3 -m venv /meu_venv
ln -s /meu_venv ~/meu_venv
source ~/meu_venv/bin/activate
pip install ultralytics                 # visão (YOLO; traz torch, torchvision, opencv-python)
pip install pyserial                    # seriais
pip install smbus2 gpiod netifaces      # I2C, GPIO, rede
pip install luma.oled psutil            # tela OLED e menu
```

* **Sempre que usar o `pip`**, ative o ambiente antes (a seção 9 faz isso no login).
* Como o ambiente está na raiz, depois da seção 14 **todo `pip install` precisa da raiz destravada**
  (`~/remonta.sh` ou menu → Desbloquear).
* No brick conferido: Python 3.11.2, ultralytics 8.3.100, torch 2.6.0, opencv-python 4.11.0.86,
  onnxruntime 1.21.1, numpy 1.26.4, pyserial 3.5, smbus2 0.5.0, gpiod 2.3.0, luma.oled 3.14.0,
  psutil 7.0.0, netifaces 0.11.0.

## 7. Permissões de GPIO e I2C

**GPIO:**

```bash
sudo groupadd gpio
sudo usermod -aG gpio $USER
sudo nano /etc/udev/rules.d/99-gpio.rules
```
```
SUBSYSTEM=="gpio", KERNEL=="gpiochip[0-9]*", GROUP="gpio", MODE="0660"
SUBSYSTEM=="gpio", KERNEL=="gpio[0-9]*", GROUP="gpio", MODE="0660"
```

**I2C:**

```bash
sudo groupadd i2c
sudo usermod -aG i2c $USER
sudo nano /etc/udev/rules.d/99-i2c.rules
```
```
KERNEL=="i2c-[0-9]*", GROUP="i2c", MODE="0660"
```

Recarregue e reinicie:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
sudo reboot
```

Os sensores ficam no **i2c-1**, atrás do multiplexador TCA9548A; a tela e o teclado, no **i2c-0**.

## 8. SSH sem senha

1. No computador (só uma vez): `ssh-keygen -t rsa -b 4096`.
2. **Linux:** `ssh-copy-id banana@192.168.2.151`.
3. **Windows** (não tem `ssh-copy-id`): abra `C:\Users\<você>\.ssh\id_rsa.pub`, copie a linha e,
   no robô:
   ```bash
   mkdir -p ~/.ssh
   nano ~/.ssh/authorized_keys      # cole a linha, salve
   ```

## 9. Menu principal, sudo e ambiente Python

**Menu principal no boot:**

1. Copie a pasta `menuPrincipal/` do repositório para `/home/banana/menuPrincipal/` e torne o
   `start.sh` executável:
   ```bash
   chmod +x ~/menuPrincipal/start.sh
   ```
   O `start.sh` ativa o `meu_venv` e roda o `start.py` em laço (se ele cair, volta em 1 s).
2. Crie o serviço com o conteúdo de `menuPrincipal/exemplo.service`:
   ```bash
   sudo nano /etc/systemd/system/menuPrincipal.service
   ```
   ```ini
   [Unit]
   Description=Meu Script no Boot
   After=network.target

   [Service]
   Type=simple
   User=banana
   WorkingDirectory=/home/banana/
   Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
   ExecStart=/home/banana/menuPrincipal/start.sh
   Restart=on-failure

   [Install]
   WantedBy=multi-user.target
   ```
   ```bash
   sudo systemctl daemon-reexec
   sudo systemctl enable menuPrincipal.service
   ```

**Comandos do menu sem senha** (`sudo visudo`, no fim do arquivo). São os que o brick conferido
tem: o menu usa `shutdown`/`reboot` (Desligar, Reiniciar), `ifconfig` (Wi-Fi on/off) e `mount`
(Desbloquear).

```
banana ALL=(ALL) NOPASSWD: /usr/bin/psd-overlay-helper
banana ALL=(ALL) NOPASSWD: /sbin/shutdown
banana ALL=(ALL) NOPASSWD: /sbin/reboot
banana ALL=(ALL) NOPASSWD: /sbin/ifconfig
banana ALL=(ALL) NOPASSWD: /bin/mount
```

(O README antigo não tinha as linhas do `reboot` e do `mount`.)

Reinicie: com a tela e o teclado encaixados, o menu deve aparecer sozinho.

**Ambiente Python no login:** no fim do `~/.bashrc`:

```bash
source ~/meu_venv/bin/activate
```

## 10. Rede

Na instalação Minimal quem cuida da rede é o **`systemd-networkd`**: ele só configura interfaces que
têm um arquivo `.network` correspondente. O `armbian-config` também configura, **mas só com a raiz
gravável**; com ela somente leitura a alteração falha sem aviso.

**Boot sem esperar a rede:** no netplan, marque o Wi-Fi como opcional

```yaml
wifis:
    wlan0:
      dhcp4: true
      dhcp6: true
      optional: true
```

e desligue a espera:

```bash
sudo systemctl mask systemd-networkd-wait-online.service
```

**Adaptador Wi-Fi USB** (só sobe quando está plugado, para não atrasar o boot). Troque
`wlxd0aeec3e321a` pelo nome da sua interface (`ip link`):

```bash
sudo bash -c 'wpa_passphrase "REDE" "senhawifi" > /etc/wpa_supplicant/wlxd0aeec3e321a.conf'
```

`/etc/systemd/network/30-usb-wlan.network`:

```ini
[Match]
Name=wlxd0aeec3e321a

[Network]
DHCP=yes

[Link]
RequiredForOnline=no
```

Script `~/rede_usb.sh` para ligar o adaptador:

```bash
#!/bin/bash
# ativa-wifi-usb.sh
IFACE=wlxd0aeec3e321a
ip link show "$IFACE" &>/dev/null || { echo "Placa USB não plugada"; exit 1; }
ip link set "$IFACE" up
wpa_supplicant -B -i "$IFACE" -c /etc/wpa_supplicant/"$IFACE".conf
echo "Associando... o networkd cuida do DHCP."
sudo systemctl restart systemd-networkd
```

**Adaptador Ethernet USB:** `/etc/systemd/network/31-usb-eth.network` (troque o nome):

```ini
[Match]
Name=enx00606e2100d0

[Network]
DHCP=yes

[Link]
RequiredForOnline=no
```

**Ethernet da placa (kernel 6.18 + placa do FPC24):** conector **REDE** do brick (RXN, RXP, TXN,
TXP). A interface se chama `end0`.

```bash
ip link
sudo ethtool end0 | grep -iE 'speed|duplex|link detected'   # 100Mb/s, Full, yes
```

O `ethtool` mostra só `10baseT` em "Supported link modes" mesmo com o link em 100/Full: é defeito
de informação do driver do AC300, não afeta nada. Vazão real (com `iperf3 -s` em outro
computador): `sudo apt install iperf3` e `iperf3 -c IP_DO_SERVIDOR -t 20`; o esperado é ~94 Mbit/s,
sem retransmissões.

Se não pegar IP, crie `/etc/systemd/network/10-end0.network`:

```ini
[Match]
Name=end0

[Network]
DHCP=yes
```

e rode `sudo systemctl restart systemd-networkd`.

**Nomes clássicos (`eth0` em vez de `end0`):** acrescente em `/boot/armbianEnv.txt` (na linha
`extraargs=` que já existir, se houver):

```
extraargs=net.ifnames=0 biosdevname=0
```

**Antes de reiniciar**, ache o que usa o nome antigo, senão você fica sem rede:

```bash
grep -rl "end0" /etc/systemd/network/ /etc/NetworkManager/ /etc/network/ 2>/dev/null
```

No Minimal, o `10-end0.network` vira `10-eth0.network` com `Name=eth0`. No Desktop, quem cuida é o
NetworkManager, e as conexões em `/etc/NetworkManager/system-connections/` podem fixar o nome no
campo `interface-name`.

## 11. Câmeras USB com nome fixo

A regra [`instalacao/99-cameras.rules`](instalacao/99-cameras.rules) cria links fixos para a
**primeira** interface de captura de cada câmera, conforme o controlador USB em que ela está:

| Link | Porta do brick | Controladores (`DEVPATH`) |
|---|---|---|
| `/dev/video_usb1` | **1**: USB-C mais à direita (olhando de fora do brick) | `5101000.usb`, `5101400.usb` (USB0, em modo host pelo overlay `bananapi-m4-zero-usb0-host`) |
| `/dev/video_usb2` | **2**: USB-C do meio | `5311000.usb`, `5311400.usb` |
| `/dev/video_usb3` | **3**: conector USB de cima (HX, 4 pinos) | `5200000.usb`, `5200400.usb` |

O par de cada porta é EHCI (USB 2.0) + OHCI (câmera USB 1.1). Uma câmera atrás de um hub ligado
na porta também ganha o link, porque o `DEVPATH` continua passando pelo controlador. O
`5310000.usb` é o hub interno dos 4 conversores seriais do Mariola (`ttyUSB0`–`3`) e não tem link.

Assim o programa abre sempre a mesma câmera, não importa a ordem em que o Linux numerou os
`/dev/videoN`.

Conferido em 28/10/2026 no brick Line/Maze com uma câmera UC60:
* porta 2, atrás de um hub: `video_usb2`;
* porta 3: `video_usb3`;
* porta 1: `video_usb1`, também direto e atrás do hub (o Julio conferiu).

Até 27/10 a regra tinha `5100400.usb` no lugar de `5101400.usb`, endereço que não existe no H618.
Uma câmera USB 1.1 na porta 1 ficava sem link. As câmeras USB 2.0 usam o outro controlador do par
e não eram afetadas.

O arquivo tem de estar com quebra de linha **LF**: com CRLF, o `\` no fim das linhas para de
funcionar. O `instalacao/.gitattributes` garante isso num clone do Windows.

```bash
scp instalacao/99-cameras.rules banana@192.168.2.151:~
sudo cp ~/99-cameras.rules /etc/udev/rules.d/99-cameras.rules
sudo udevadm control --reload
sudo udevadm trigger
ls -l /dev/video_usb*
```

## 12. Áudio

Com o kernel 6.18 o codec analógico já funciona, sem overlay. No brick ele sai no conector
**AUDIO** (GND, L_OUT, L_IN, 5V).

```bash
aplay -l     # card 0: Codec [H616 Audio Codec] (analógico) e card 1: HDMI
speaker-test -D hw:0,0 -c2 -twav -l1
```

Para que qualquer programa (Python, sox, pygame) use o analógico sem dizer o device, e o som não vá
para o HDMI, crie `~/.asoundrc`:

```
defaults.pcm.card 0
defaults.ctl.card 0
```

**Bipes** (bom para sinalizar estado na competição):

```bash
sudo apt install sox
play -nq synth 0.2 sine 1000
```

```python
import subprocess

def beep(freq=1000, dur=0.2):
    subprocess.run(['play', '-nq', 'synth', str(dur), 'sine', str(freq)])
```

## 13. Temperatura e cooler

**Zonas térmicas** (kernel 6.18). A que interessa **não é a zero**, e a numeração muda entre
kernels: procure pelo **nome**.

| Zona | Tipo |
|---|---|
| `thermal_zone0` | `gpu-thermal` |
| `thermal_zone1` | `ve-thermal` |
| `thermal_zone2` | `cpu-thermal` (a única com trips de throttling) |
| `thermal_zone3` | `ddr-thermal` |

```bash
for z in /sys/class/thermal/thermal_zone*; do echo "$z: $(cat $z/type)"; done
cat /sys/class/thermal/thermal_zone2/trip_point_0_temp   # 60000 (passive)
cat /sys/class/thermal/thermal_zone2/trip_point_1_temp   # 70000 (passive)
cat /sys/class/thermal/thermal_zone2/trip_point_2_temp   # 110000 (critical)
```

**Throttling:** acima de 60 °C o kernel baixa de 1512 para 1200 MHz (~20% a menos) e volta sozinho
quando esfria. No `armbianmonitor -m`, a coluna `C.St.` mostra `1/5` em vez de `0/5`;
`scaling_max_freq` cai para 1200000. A mensagem `Using CPU speed bin speed0` do `dmesg` **não** é
isso: ela diz o bin do chip (o teto de hardware), não o throttling.

**Cooler no PWM1 do Banana Pi — só na imagem @Work** (na Line/Maze o processamento alto não é
constante e o brick não usa cooler). Overlay `pwm1-pi11`; cooler de 4 fios, 5 V. A entrada PWM desses
coolers é opto-isolada e aceita os 3,3 V do SBC direto. Frequência da especificação: 25 kHz
(período de 40000 ns). Teste manual:

```bash
echo 1 | sudo tee /sys/class/pwm/pwmchip0/export
cd /sys/class/pwm/pwmchip0/pwm1
echo 40000 | sudo tee period
echo 20000 | sudo tee duty_cycle    # 50%
echo 1 | sudo tee enable
```

Controle automático: copie a pasta [`instalacao/cooler/`](instalacao/cooler/) para o robô e rode
`sudo ./instalar-fancontrol.sh`. O instalador confere o `pwmchip0` e a zona `cpu-thermal`, remonta a
raiz como gravável se precisar, instala o `fancontrol.py` em `/usr/local/bin/`, cria e liga o
`fancontrol.service`. O `fancontrol.py` faz rampa linear entre **50 e 68 °C** (histerese de 5 °C na
parada, duty mínimo de 30%, senão o cooler não parte) e, com `AJUSTAR_TRIPS = True`, sobe os trips
de 60/70 para **70/80 °C**. Subir os trips é escolha consciente: só faz sentido com refrigeração
ativa e boa ventilação. Acompanhe com `journalctl -u fancontrol -f`.

> **Versão antiga:** o cartão do brick Line/Maze conferido tinha um `fancontrol.py` anterior, que lê
> a `thermal_zone0` (no kernel 6.18 é a **GPU**, não a CPU), faz a rampa de 50 a **90 °C** e não
> mexe nos trips (ficam 60/70 °C, e o throttling começa antes de o cooler acelerar). Se a imagem
> @Work estiver com essa versão, rode de novo o `instalar-fancontrol.sh` com a pasta
> `instalacao/cooler/`.

> O brick também pode ligar uma ventoinha na coluna **DEBUG/PWM** do ATmega, pelo programa
> (`Motores.set_ventoinha()`, veja `documentação/Motores.md`). São dois caminhos diferentes.

**Ventilação da caixa:** com a placa numa caixa fechada o dissipador satura; já foram medidos 95 °C.
O que resolve é **fluxo de ar** (entrada e saída em lados opostos, ar passando pelas aletas), não um
cooler mais forte. Com a caixa aberta e um cooler de 20×20 mm, a carga total ficou em ~53 °C.

**Teste de carga** (com a caixa fechada e por bastante tempo: o calor confinado acumula):

```bash
sudo apt install stress-ng
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
stress-ng --cpu 4 --cpu-method matrixprod --timeout 1800s --metrics-brief
watch -n1 'cat /sys/class/thermal/thermal_zone2/temp; \
           cat /sys/class/pwm/pwmchip0/pwm1/duty_cycle; \
           cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq'
```

Se a temperatura sobe devagar e não estabiliza, o problema é saída de ar.

**1512 MHz em chips speed0 (overclock):** no 6.6 a placa rodava a 1512 MHz; no 6.18 o teto cai para
1416 MHz (`cpuinfo_max_freq` = 1416000), e **não é throttling**. O H616 classifica cada chip num
*speed bin* (`dmesg | grep "speed bin"` → `Using CPU speed bin speed0`), e cada OPP diz em
`opp-supported-hw` quais bins aceita. Em `arch/arm64/boot/dts/allwinner/sun50i-h616-cpu-opp.dtsi`
do 6.18:

```
opp-1512000000 {
        opp-hz = /bits/ 64 <1512000000>;
        opp-microvolt-speed1 = <1100000>;
        opp-microvolt-speed3 = <1100000>;
        opp-microvolt-speed5 = <1160000>;
        opp-supported-hw = <0x2a>;
};
```

`0x2a` = `101010` (bits 1, 3 e 5): o speed0 ficou de fora. O `opp-1416000000` usa `0x2d`
(`101101`, bits 0, 2, 3 e 5), que inclui o bin 0, daí o teto de 1416. A tabela do 6.6 era antiga:
só 3 bins, 1512 MHz a 1,1 V para todos e sem `opp-supported-hw`.

O overlay `cpu-opp-1512-speed0` (fonte em
[`instalacao/overlays/`](instalacao/overlays/sun50i-h616-cpu-opp-1512-speed0.dtso)) acrescenta
`opp-microvolt-speed0 = <1100000>` e `opp-supported-hw = <0x2b>` ao OPP de 1512 MHz. **As duas
propriedades são necessárias**: só a máscara deixaria o bin 0 sem tensão. O 1,1 V é o que o 6.6
usava. Para desligar, basta tirar o overlay da linha do `armbianEnv.txt`.

Valide com carga longa, com memória junto (instabilidade de tensão às vezes só aparece com CPU e
barramento trabalhando juntos):

```bash
stress-ng --cpu 4 --vm 2 --vm-bytes 256M --timeout 1800s
cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq            # 1512000
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies
```

Medido no BPI-M4-Zero: 1512 MHz estável, 56 °C em carga total por 30 min, com cooler e caixa
fechada. O merge do overlay só troca as duas propriedades; o resto do nó (`opp-hz`,
`clock-latency-ns`, tensões dos outros bins) fica intacto.

**Por que não subir mais:** não há OPP acima de 1512 para nenhum bin, e o PLL_CPUX só aceita
múltiplos de 24 MHz (1600 nem existe; seria 1608). E os 1,16 V do speed5 não são folga: são o que um
chip **melhor** precisa para os mesmos 1512, sinal de que essa frequência já está perto do limite
da arquitetura.

## 14. Raiz somente leitura e verificação do disco

Faça **por último**, com tudo instalado e testado.

**Raiz somente leitura:** no `/etc/fstab`, acrescente `ro` às opções da linha da raiz. No brick
conferido o fstab inteiro ficou assim (a linha do `/tmp` em memória já vem do Armbian):

```
tmpfs                                      /tmp   tmpfs  defaults,nosuid                                                0  0
UUID=<uuid-da-raiz>                        /      ext4   ro,defaults,noatime,commit=120,errors=remount-ro,x-gvfs-hide  0  1
UUID=<uuid-da-home>                        /home  ext4   defaults,nofail                                               0  0
```

O `/var/log` fica num disco em RAM (`zram`), criado pelo `armbian-ramlog`: os logs somem a cada
boot, e a raiz não precisa gravá-los.

Para mudar qualquer coisa no sistema depois (apt, dpkg, `systemctl enable`, editar `/etc`),
remonte como gravável até o próximo boot:

```bash
sudo mount -o remount,rw /
```

Deixe isso num script na pasta do usuário: [`instalacao/remonta.sh`](instalacao/remonta.sh) →
`~/remonta.sh` (`chmod +x`). O menu do brick também tem a opção **Desbloquear**. Sem remontar,
`systemctl enable/disable` não grava os links e a mudança some no reboot.

> Use `/` e não `/dev/mmcblk2p1` no remount: a numeração `mmcblk0`/`mmcblk1`/`mmcblk2` **muda**
> (entre boots, e conforme há ou não cartão no slot). O fstab usa UUID, então ele não sofre com
> isso. O `remonta.sh` e o "Desbloquear" do menu (`menuPrincipal/telaMenu.py`) do brick conferido
> ainda usam `/dev/mmcblk2p1`.

**Verificação da raiz a cada boot** (evita boot falhando por partição corrompida).
`sudo nano /etc/systemd/system/force-fsck-root.service`:

```ini
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

```bash
sudo systemctl daemon-reexec
sudo systemctl enable force-fsck-root.service
journalctl -u force-fsck-root.service      # depois do reboot, para conferir
```

## 15. Samba

Compartilha a pasta do usuário na rede: no Windows, `\\IP\home` no Explorer.

**Por que a pasta `/home/samba-data`:** com a raiz somente leitura (seção 14) o Samba não consegue
gravar os bancos dele (senhas, compartilhamentos, travas) em `/var/lib/samba` e `/var/cache/samba`.
Eles vão para `/home/samba-data`, na `/home` gravável, e os caminhos originais viram links para lá.

```bash
sudo apt install samba smbclient cifs-utils
```

No fim do `/etc/samba/smb.conf` (o resto do arquivo é o padrão do Debian):

```ini
[home]
     path = /home/banana
     browseable = yes
     writable = yes
     guest ok = yes
     create mask = 0777
     directory mask = 0777
```

```bash
sudo smbpasswd -a banana
sudo systemctl restart smbd
```

Com a raiz gravável e o `smbd` já iniciado uma vez (para ele criar os arquivos), mova os bancos e
deixe links no lugar. É o que está no brick conferido:

```bash
sudo mkdir -p /home/samba-data/{private,cache,lock,registry,run}
sudo chown -R root:root /home/samba-data
sudo chmod -R 755 /home/samba-data

sudo mv /var/lib/samba/private /var/lib/samba/private.bak
sudo ln -s /home/samba-data/private /var/lib/samba/private
sudo cp /var/lib/samba/private.bak/secrets.tdb /home/samba-data/private/
sudo chown root:root /home/samba-data/private/secrets.tdb
sudo chmod 600 /home/samba-data/private/secrets.tdb

sudo mv /var/cache/samba /var/cache/samba.bak
sudo ln -s /home/samba-data/cache /var/cache/samba
sudo mv /var/lock/samba /var/lock/samba.bak
sudo ln -s /home/samba-data/lock /var/lock/samba

for f in account_policy group_mapping share_info registry; do
    sudo mv /var/lib/samba/$f.tdb /home/samba-data/registry/
    sudo ln -s /home/samba-data/registry/$f.tdb /var/lib/samba/$f.tdb
done

sudo systemctl enable smbd
```

* O `passdb.tdb` (as senhas do `smbpasswd`) fica em `private/`, e só o `secrets.tdb` é copiado:
  **rode `sudo smbpasswd -a banana` de novo depois dos links** (no brick conferido o `passdb.tdb`
  está em `/home/samba-data/private/`).
* O README antigo também movia `/var/run/samba` para `/home/samba-data/run`. Não adianta: o
  `/var/run` é o `/run`, que fica em memória e é recriado a cada boot (no brick conferido o
  `/var/run/samba` é uma pasta comum e o Samba funciona).
* O README antigo esquecia a pasta `registry` no `mkdir` e não movia o `registry.tdb`; o brick
  conferido tem os dois.
* Sobra no brick: um `start-samba.service` **desabilitado**, que rodava
  `/usr/local/bin/start-samba.sh` (cria `/var/run/samba`, `/var/cache/samba` e `/var/lib/samba` e
  inicia o `smbd`). Não é necessário.

## 16. Deixar o boot mais rápido (opcional)

> Registro do que foi feito na **imagem @Work** (BPI-M4 Zero de 32 GB, **Armbian Noble /
> Ubuntu 24.04** com ROS2, kernel 6.18.44, raiz somente leitura). A imagem Line/Maze usa o
> Bookworm Minimal, que não tem vários desses serviços (lá a rede é o `systemd-networkd`, seção 10,
> e o que mais pesa no boot é o `systemd-networkd-wait-online`). Confira se o serviço existe
> (`systemctl list-unit-files | grep ...`) antes de aplicar. Todo passo exige a raiz gravável.

Resultado no @Work: **27,4 s → 14,7 s** (−46%); `multi-user.target` em 8,8 s de userspace (era 21 s).

| Etapa | Kernel | Userspace | Total |
|---|---|---|---|
| Início | 6,308 s | 21,102 s | 27,411 s |
| 1. sem wait-online | 5,789 s | 12,386 s | 18,176 s |
| 2–3. sem Bluetooth, sem raid6 | 5,726 s | 11,890 s | 17,616 s |
| 4. faxina do userspace | 5,229 s | 9,506 s | 14,736 s |

Cadeia crítica no fim (saíram `armbian-ramlog`, `var-log.mount`, `dev-zram1`, `systemd-resolved` e
`tmpfiles-setup`; sobrou basicamente o NetworkManager, mantido de propósito):

```
multi-user.target @8.794s
└─chrony.service @8.470s +315ms
  └─network.target @8.454s
    └─NetworkManager.service @4.369s +4.083s
      └─dbus.service @4.043s +292ms
        └─basic.target @3.980s
          └─armbian-hardware-optimize.service @3.741s +237ms
            └─sysinit.target @3.721s
```

**1. Não esperar a rede (~9 s).** O `NetworkManager-wait-online` esperava todas as interfaces (e a
`eth0` sem cabo nunca sobe):

```bash
sudo systemctl disable NetworkManager-wait-online.service
```

Programa iniciado no boot passa a rodar **sem garantia de Wi-Fi conectado**: se precisar da rede
logo, faça novas tentativas. (No Bookworm Minimal o equivalente é o
`systemd-networkd-wait-online`, seção 10.)

**2. Sem Bluetooth (~4 s):**

```bash
sudo tee /etc/modprobe.d/no-bt.conf <<'EOF'
blacklist btbcm
blacklist hci_uart
blacklist bnep
blacklist rfcomm
blacklist btsdio
blacklist bluetooth
EOF
sudo apt purge -y blueman bluez
```

O Wi-Fi (`brcmfmac`) não depende desses módulos (`nmcli dev status` para conferir).

**3. Sem o benchmark de RAID6 (~1,4 s de kernel).** Blacklist em `/etc/modprobe.d` não basta: o
benchmark roda no initramfs. Em `/etc/initramfs-tools/initramfs.conf`:

```
MODULES=dep
COMPRESS=zstd
```

```bash
sudo apt install zstd
sudo update-initramfs -u -k all
dmesg | grep -i raid6      # vazio
lsmod | grep raid          # vazio
```

`MODULES=dep` deixou o initramfs com 32 módulos (só o necessário para montar o ext4 da eMMC).

O initrd ficou com 15 MB, 12,75 MB dos quais são o `usr/lib/udev/hwdb.bin`, inútil ali. Tirá-lo
daria ~0,4 s, mas **não foi feito**: o risco de um boot quebrado na competição não compensa. Se um
dia valer a pena:

```bash
sudo tee /etc/initramfs-tools/hooks/no-hwdb <<'EOF'
#!/bin/sh
[ "$1" = "prereqs" ] && { echo; exit 0; }
. /usr/share/initramfs-tools/hook-functions
rm -f "${DESTDIR}/usr/lib/udev/hwdb.bin"
EOF
sudo chmod +x /etc/initramfs-tools/hooks/no-hwdb
sudo update-initramfs -u -k all
```

**4. Faxina do userspace (~2,4 s):**

```bash
sudo systemctl disable --now apport avahi-daemon avahi-daemon.socket \
  cups cups-browsed ModemManager e2scrub_reap rng-tools-debian \
  lm-sensors armbian-ramlog
sudo systemctl disable apt-daily.timer apt-daily-upgrade.timer man-db.timer \
  motd-news.timer dpkg-db-backup.timer e2scrub_all.timer
sudo apt purge -y apport apport-symptoms modemmanager cups cups-daemon \
  cups-browsed avahi-daemon snapd lm-sensors
```

| Serviço | Custo | Por que sai |
|---|---|---|
| `apport` | 2,9 s | coletor de crash do Ubuntu |
| `avahi-daemon` | 591 ms | mDNS/Bonjour |
| `cups` / `cups-browsed` | 272 ms+ | impressão |
| `ModemManager` | 478 ms | modem 3G/4G |
| `e2scrub_reap` | 746 ms | verificação de ext4 com LVM |
| `rng-tools-debian` | 494 ms | entropia (o H618 tem RNG em hardware) |
| `lm-sensors` | 340 ms | a temperatura útil vem do sysfs |
| `armbian-ramlog` | 918 ms | estava na cadeia crítica; redundante com a raiz somente leitura |

> **Não faça purge de `plymouth`/`plymouth-theme-*`.** No Armbian, `plymouth-theme-*` casa com o
> `armbian-plymouth-theme`, que é dependência do **lightdm**: o apt removeu em cascata
> `lightdm → slick-greeter → lightdm-settings → light-locker` e a interface gráfica sumiu. Para
> restaurar: `sudo apt install lightdm slick-greeter lightdm-settings light-locker`. O plymouth
> custa só ~89 ms; se quiser tirar, `sudo systemctl mask plymouth-quit-wait.service`.

**Mantidos de propósito:** `rc-local.service` (iniciar código); `polkit` (NetworkManager e logind
dependem dele; sem ele o Wi-Fi para); `alsa-restore` (o robô usa áudio); `NetworkManager` (trocar
de rede fácil na competição: arena, hotspot, casa); `rsyslog`/`logrotate` (só tire se nada ler o
`/var/log/syslog`); `armbian-zram-config` (swap em zram); `plymouth`.

**Interface gráfica só quando precisar:**

```bash
sudo systemctl set-default multi-user.target
sudo systemctl disable lightdm
sudo systemctl start lightdm          # quando precisar
```

**Conferir depois do reboot:**

```bash
systemd-analyze
systemd-analyze critical-chain
systemd-analyze blame | head -20
nmcli dev status
aplay -l
amixer scontrols
dmesg | grep -i raid6
```

No `critical-chain`, um `systemd-journald.service` com tempo **maior** que o `multi-user.target` é
o journald reiniciando depois do boot; o número real é o do `systemd-journald.socket`.

**Ideias deixadas para depois (registro do @Work):**

* **NetworkManager** (4,08 s, 46% do userspace): mantido. Opção leve, reversível, em
  `/etc/NetworkManager/conf.d/robot.conf`: `[main] plugins=keyfile`,
  `[device] wifi.scan-rand-mac-address=no`, `[connection] ipv6.method=disabled` (1–2 s a menos).
  Opção definitiva: `systemd-networkd` + `wpa_supplicant@wlan0` (~300 ms), perdendo a troca fácil
  de rede.
* **Serviço systemd em vez do `rc.local`** para o código do robô. O `rc-local.service` é
  `Type=forking` com `TimeoutSec=0`: código em primeiro plano ali **trava o boot**. Exemplo:
  ```ini
  # /etc/systemd/system/mariola.service
  [Unit]
  Description=Mariola @Work
  After=network.target

  [Service]
  Type=simple
  User=banana
  WorkingDirectory=/home/banana/mariola
  ExecStart=/home/banana/.venv/bin/python main.py
  Restart=always
  RestartSec=3

  [Install]
  WantedBy=multi-user.target
  ```
  `Restart=always`, `journalctl -u mariola -f` e não bloqueia o boot. Use `After=network.target`
  (e não `network-online.target`) para não voltar a esperar a rede.
* **journald volátil** (`/etc/systemd/journald.conf`: `Storage=volatile`, `RuntimeMaxUse=16M`):
  com a raiz somente leitura ele já cai para `/run`; o log some no reboot.
* **Quase nada a ganhar:** `armbian-zram-config` (672 ms), `logrotate` (652 ms), `rsyslog`
  (370 ms), `dev-mmcblk1p1.device` (1,4 s, o udev esperando a eMMC).
* **Piso do kernel (~5,2 s):** a maior parte é a enumeração USB (hub + 4× CH340 em série no EHCI,
  ~2,5 s). Só diminui tirando adaptadores seriais.

## 17. Recuperação

**O SD dá boot antes da eMMC:** com um cartão bom no slot o brick sempre liga, mesmo com o U-Boot
ou a raiz da eMMC estragados. Dali dá para montar a eMMC e consertar.

### Cartão de reserva com a imagem da eMMC

O cartão de reserva (16 GB) tem três partições:

| Partição | Tamanho | Conteúdo |
|---|---|---|
| `p1` | 6,3 GB | clone da raiz da eMMC (mesmo UUID): o brick dá boot por ele |
| `p2` | 1 GB | clone da `/home` da eMMC (mesmo UUID) |
| `p3` | 7,6 GB | ext4 com **um arquivo**: a imagem crua da eMMC inteira, `backupMariolaZeroAAAA-MM-DD.img` (7.818.182.656 bytes = a `mmcblk2` toda: tabela de partições, U-Boot e as duas partições). A atual é a de **28/10/2026** (kernel 6.18.42, ajustes do apêndice C, menu novo, `~/firmware_mariola`, regra das câmeras corrigida) |

A `p3` comporta **uma** imagem só: para gravar uma nova, apague a antiga antes. Ela só cabe usando
a reserva de 5% do ext4 para o root (o `dd` com `sudo` usa; um `df` como usuário comum mostra
espaço insuficiente).

Dois scripts em [`instalacao/`](instalacao/) fazem os procedimentos abaixo, com conferências:

* **`atualiza_imagem.sh`** (rode de qualquer lugar, ex.: `/tmp`): grava a eMMC atual na `p3`.
  Confere os discos, deixa a `/home` só leitura, faz `e2fsck` na `p3`, troca a imagem, compara o
  tamanho e sempre religa a `/home` e os serviços no fim, mesmo com erro.
* **`instalacao_emmc.sh`** (fica na raiz do cartão, `/instalacao_emmc.sh`): grava a imagem na eMMC.
  Só roda com o boot pelo cartão, desmonta o que for da eMMC (a `/home`), pega a imagem mais nova da
  `p3`, pede para digitar `SIM` (ou `-y`) e opcionalmente compara a eMMC com a imagem
  (`--verifica`). No fim, **troca o MAC do Wi-Fi** da eMMC (veja abaixo).

  **MAC do Wi-Fi:**
  * O netplan da imagem (`/etc/netplan/armbian.yaml`) fixa os MACs: `macaddress:` da `wlan0`
    (`ac:7a:a3:3c:0e:bd` na imagem de 27/10/2026) e da `end0` (`de:ad:be:ef:00:01`). Todo brick
    gravado com a mesma imagem sairia com o mesmo MAC e brigaria pelo mesmo IP no DHCP.
  * Depois de gravar e conferir, o script monta a raiz da eMMC e troca o MAC da `wlan0`: mantém o
    primeiro e o último grupo e sorteia os 4 do meio (ex.: `ac:5e:09:c2:7f:bd`). Ele mostra o MAC
    antigo e o novo; anote no brick.
  * `--mac ac:12:34:56:78:bd` usa um MAC escolhido (útil para regravar um brick e manter o IP
    reservado no roteador). `--mesmo-mac` não troca.
  * O MAC da `end0` (rede cabeada) não é trocado.
  * Para ver ou trocar à mão num brick já gravado: `sudo nano /etc/netplan/armbian.yaml` (com a
    raiz gravável, seção 14), depois `sudo netplan apply` ou reinicie.

  **Por que na raiz:** no boot pelo cartão, a `/home` costuma vir da **eMMC** (os UUIDs são iguais),
  e a eMMC inteira vai ser regravada, então a `/home` precisa ser desmontada antes. Um script guardado
  na `/home` prenderia a própria partição que ele tem de soltar. Pelo mesmo motivo, **o terminal que
  chama o script também não pode estar dentro da `/home`** (e ele abre no `~`, que é na `/home`):
  saia dela antes.

  ```bash
  cd /
  sudo bash /instalacao_emmc.sh
  ```

  Se algo ainda estiver usando a `/home`, o script não grava nada e mostra quem é (o PID e a pasta).

Na imagem @Work (32 GB) não há cartão de reserva com imagem: o próprio cartão @Work é a
recuperação, e o `clona_sd_emmc.sh` passa ele para a eMMC (apêndice D).

**Detectar o cartão com o brick ligado.** Colocado com o brick já ligado, o cartão pode não
aparecer (o pino de detecção do slot não avisa o kernel). Religue o driver do slot do cartão, o
`4020000.mmc` (a eMMC é o `4022000.mmc` e não é afetada):

```bash
echo 4020000.mmc | sudo tee /sys/bus/platform/drivers/sunxi-mmc/unbind
echo 4020000.mmc | sudo tee /sys/bus/platform/drivers/sunxi-mmc/bind
lsblk        # a eMMC é o disco com boot0/boot1 (mmcblk2); o cartão, o outro (mmcblk0)
```

**Atualizar a imagem guardada** (brick ligado pela eMMC, cartão detectado como acima):

```bash
sudo systemctl stop menuPrincipal smbd nmbd
sudo mount -o remount,ro /home                 # a /home é a p2 da eMMC: não pode mudar durante a cópia
sudo mount /dev/mmcblk0p3 /mnt
sudo rm /mnt/backupMariolaZero*.img            # só cabe uma imagem
sudo dd if=/dev/mmcblk2 of=/mnt/backupMariolaZeroAAAA-MM-DD.img bs=4M conv=fsync status=progress
sudo umount /mnt
sudo reboot                                    # tire o cartão
```

A raiz da eMMC já é somente leitura, então copiar com ela em uso não tem problema. Para deixar
também a `p1`/`p2` do cartão iguais à eMMC (para dar boot por ele), copie partição por partição
antes do reboot: `sudo dd if=/dev/mmcblk2p1 of=/dev/mmcblk0p1 ...` e o mesmo para a `p2`.

**Regravar a eMMC a partir da imagem** (eMMC estragada ou para voltar a um estado conhecido):

1. Ligue o brick **com o cartão**: ele dá boot pelo cartão.
2. Veja de onde veio a `/home` (`findmnt /home`). Como os UUIDs são iguais, ela pode ter vindo da
   **eMMC** (`mmcblk2p2`), e a eMMC inteira vai ser regravada: desmonte antes.
   ```bash
   sudo systemctl stop menuPrincipal smbd nmbd
   cd /
   sudo umount /home
   ```
3. Grave a imagem e reinicie sem o cartão:
   ```bash
   sudo mount -o ro /dev/mmcblk0p3 /mnt
   sudo dd if=/mnt/backupMariolaZeroAAAA-MM-DD.img of=/dev/mmcblk2 bs=4M conv=fsync status=progress
   sudo umount /mnt
   sudo reboot                                  # tire o cartão
   ```

A imagem traz a `/home` **da data em que foi gerada**: o que foi salvo na `/home` depois disso se
perde. Copie antes o que importar (ex.: os programas das equipes).

**Raiz corrompida, o brick não liga mais.** Precisa do cabo serial (115200, seção 3):

1. Ligue o brick com o terminal serial aberto e, assim que o log do boot começar, aperte qualquer
   tecla repetidamente para entrar no **U-Boot**.
2. Cole um comando de cada vez (aperte Enter duas vezes em cada; às vezes o terminal engasga):
   ```
   ext4load mmc 1:1 0x42000000 /boot/Image
   ext4load mmc 1:1 0x47000000 /boot/dtb-6.6.75-current-sunxi64/allwinner/sun50i-h618-bananapi-m4-zero.dtb
   ext4load mmc 1:1 0x60000000 /boot/uInitrd-6.6.75-current-sunxi64
   booti 0x42000000 0x60000000 0x47000000
   ```
   Os nomes `6.6.75` são do kernel antigo: com o 6.18, troque pelos nomes que existem no seu
   `/boot` (`ls /boot`).
3. Quando o sistema subir, verifique a raiz: `fsck.ext4 -f -p /dev/mmcblk1p1` (confira o
   dispositivo: a numeração muda entre boots).
4. Desligue e ligue de novo.

**Partição `/home` com problema** (`/dev/mmcblk2p2`, confira o número):

```bash
systemctl rescue                    # pede a senha do root
umount /home
fsck.ext4 -f -p /dev/mmcblk2p2      # -f força, -p corrige o que é seguro
reboot
```

## 18. Compilar a imagem ou o kernel

**Host:** Ubuntu 24.04 (Noble) para build nativo, ou qualquer Linux com Docker (o framework usa
container sozinho). Mínimo de 8 GB de RAM e ~50 GB livres.

```bash
git clone --depth=1 https://github.com/armbian/build
cd build
./compile.sh BOARD=bananapim4zero BRANCH=current RELEASE=bookworm BUILD_MINIMAL=yes   # imagem
./compile.sh kernel BOARD=bananapim4zero BRANCH=current RELEASE=bookworm              # só os .deb do kernel
```

**Overlays locais** (os dois que não existem no Armbian): copie os fontes de
[`instalacao/overlays/`](instalacao/overlays/) para `patch/kernel/archive/sunxi-6.18/overlay_64/`
e registre cada um no `Makefile` dessa pasta, junto com os outros `bananapi-m4`:

```
	sun50i-h616-bananapi-m4-zero-usb0-host.dtbo \
	sun50i-h616-cpu-opp-1512-speed0.dtbo \
```

A indentação é **tab** e a linha termina com barra invertida. Sem o registro o overlay não é
compilado, sem mensagem de erro. Antes de criar um overlay novo, veja se já não existe um oficial
(o Armbian tem overlays para quase todo PWM e UART do H616):

```bash
ls patch/kernel/archive/sunxi-6.18/overlay_64/ | grep -i <periferico>
```

O `usb0-host` desliga o `usbotg` (musb) e liga o `ehci0` e o `ohci0`: a porta USB-C vira host.

**Device tree da placa:** não vem de patch nem do mainline. O framework copia
`patch/kernel/archive/sunxi-6.18/dt_64/sun50i-h618-bananapi-m4-zero.dts` para a árvore do kernel
durante o build; é esse o arquivo a editar.

**Onde saem os pacotes:** `output/packages-hashed/global/` ou `output/debs/`. O trecho `P####` do
nome é um hash dos patches: se não mudou depois de você editar algo, o build reaproveitou o cache.
**Cuidado com versões acumuladas:** `linux-dtb-current-sunxi64_*.deb` pega o primeiro em ordem
alfabética, não o mais novo; confira a data (`ls -lat output/debs/linux-dtb-current-sunxi64_*.deb |
head -3`). O mesmo vale no `dpkg -i *.deb`.

---

## Apêndice A — Orange Pi Zero LTS

Placa alternativa (H3 ou H2+) para quando falta Banana Pi M4 Zero. Use **Armbian 25.5.5** para
Orange Pi Zero LTS. **Não tem eMMC:** roda do cartão SD. O resto segue este documento, com estas
diferenças:

* **Partição `/home` e raiz somente leitura:** iguais (seções 2 e 14). Com a raiz somente leitura,
  acrescente ao fstab no mínimo:
  ```
  tmpfs /tmp     tmpfs defaults,nosuid,nodev 0 0
  tmpfs /var/log tmpfs defaults,nosuid,nodev 0 0
  tmpfs /var/tmp tmpfs defaults,nosuid,nodev 0 0
  ```
  Se o sistema precisar gravar em outro lugar (ex.: `/var/lib`), mova para a `/home`.
* **U-Boot na memória SPI (opcional, se a placa tiver a flash):** facilita recuperar partição
  corrompida. Em `/boot/armbianEnv.txt`, acrescente `sun8i-h3-spi-jedec-nor` aos overlays e uma
  linha nova:
  ```
  overlays=usbhost2 usbhost3 tve sun8i-h3-spi-jedec-nor
  param_spinor_spi_bus=0
  ```
  Reinicie e grave:
  ```bash
  sudo flash_erase /dev/mtd0 0 0
  sudo dd if=/usr/lib/linux-u-boot-current-orangepizero/u-boot-sunxi-with-spl.bin of=/dev/mtd0
  ```
  Daí em diante o boot começa pela flash.
* **DTB:** copie o DTB da placa para `/boot/dtb/` (`sudo cp sun8i-h2-plus-orangepi-zero.dtb
  /boot/dtb/`) e reinicie. (O documento antigo não trazia esse arquivo no repositório.)
* **Python:** a placa tem pouca RAM e **não roda o ultralytics**. Instale pelo apt e crie o
  ambiente usando os pacotes do sistema:
  ```bash
  sudo apt install python3-opencv python3-serial python3-psutil python3-luma.oled
  rm -rf ~/meu_venv
  python3 -m venv ~/meu_venv --system-site-packages
  python3 -c "import cv2; print(cv2.__version__)"
  ```
  A visão roda modelos ONNX pelo OpenCV. `smbus2`, `gpiod` e `netifaces` continuam pelo `pip`.
* **Câmeras:** a mesma regra da seção 11.

## Apêndice B — O que ficou só em `_instalacao_antiga/`

Material superado que **não** foi trazido para cá (decisão de 20/10/2026). Apagando a pasta, ele
some do disco (fica no histórico do git):

| Arquivo(s) | O que era | Por que ficou de fora |
|---|---|---|
| `sun50i-h618-bananapi-m4-zero.dtb` e `.dts`, `.dts_6.1`, `.dts_6.6` | DTB customizado do kernel 6.6 (seriais e USB) e variantes | substituído pelos overlays do kernel 6.18 (seção 5) |
| Passo "copiar o DTB para `/boot/dtb-6.6.75-current-sunxi64/allwinner/`" e "armbian-config → Manage device tree overlay" do README antigo | jeito antigo de ligar seriais e USB | idem |
| `WIFI_INTEGRACAO.md`, `compila_instala_dtb_wifi.sh` | Wi-Fi interno no kernel 6.1 por DTS | kernel 6.1 abandonado; no 6.18 é o overlay `bananapi-m4-sdio-wifi-bt` |
| `ajusta_boot_allwinner.sh`, `copia_uboot_corrigido.sh`, `corrige_boot_emmc.sh`, `diagnostico_uboot_completo.sh`, `testa_boot_emmc.sh` | consertos do boot da eMMC ("bad magic", U-Boot), out/2025 | problema daquela época; a recuperação atual é a da seção 17 |
| `ScriptsIA/GUIA_MIGRACAO_VENDOR.md`, `migracao_completa_vendor.sh`, `copia_uboot_sd_emmc.sh`, `corrige_dtb.sh`, `diagnostico_uboot.sh`, `envia_*migracao*.ps1` | migração para o kernel vendor 5.4.125 (para ter Ethernet) | superado pelo kernel 6.18 |
| Demais scripts de Samba do `ScriptsIA/` (`corrige_*`, `diagnostico_*`, `samba_*`, `restaura_samba_emergencia.sh`, `garante_samba_boot.sh`, `instala_servico_samba.sh`, `smb.conf.corrigido`, `*.ps1`) e `CONFIGURACAO_SAMBA_FINAL.md` | tentativas de Samba de out/2025 (compartilhamentos `dados` e `home` sem senha, serviço `samba-fix`) | essa configuração não está nos bricks (conferido em 20/10/2026); a que vale está na seção 15 |
| `fancontrol.py`, `fancontrol.service`, `instalar-fancontrol.sh`, `99-cameras.rules` | — | **copiados** para `instalacao/` (iguais) |

Todo o texto dos `.md` antigos foi trazido para este documento, exceto o que está nas linhas acima.

## Apêndice C — Brick conferido em 20/10/2026

Conferência feita por SSH (só leitura) num brick ligado. Serve de referência do que um brick "de
verdade" tem, e lista o que vale ajustar nele.

**Sistema:** Armbian 25.2.2 Bookworm, kernel `6.18.42-current-sunxi64` (pacotes `26.08.0-trunk`;
o `/boot/dtb` aponta para `dtb-6.18.43-current-sunxi64`, de um build um pouco mais novo que o
kernel), U-Boot `25.2.2`. Overlays: a linha da seção 5 **sem** o `cpu-opp-1512-speed0` (CPU a
1416 MHz). Em `/boot/overlay-user/` há um `pi12-pwm.dtbo` antigo (abr/2025), fora da linha de
overlays. Alvo padrão: `graphical.target`, mas o **lightdm não está instalado** (sobrou só o link
`display-manager.service`). **Boot: 2 min 42 s** (5,7 s de kernel + 2 min 36 s de userspace), quase
tudo esperando o `systemd-networkd-wait-online` (item 4 abaixo).

**Discos:** o brick está rodando com a raiz **do cartão SD** (`mmcblk0p1`, 6,3 GB, 75% usada,
incluindo o `/meu_venv` de 1,3 GB) e a `/home` **da eMMC** (`mmcblk2p2`, 1 GB, 15% usada). Cartão e
eMMC têm os mesmos UUIDs (o cartão tem ainda uma terceira partição, de 7,6 GB). **O sistema
atualizado está só no cartão:** a raiz da eMMC (`mmcblk2p1`) ainda é a antiga, com o kernel
6.6.75, só os 5 overlays antigos e sem o `fancontrol`.

**Conforme este documento:** grupos `gpio` e `i2c` e as regras do udev (o arquivo do GPIO se chama
`90-gpio.rules`); `force-fsck-root.service`; `menuPrincipal.service`; `~/.bashrc` ativando o
`meu_venv`; Samba da seção 15; `fancontrol` ativo no PWM1; áudio (cards `Codec` e `HDMI`); seriais
`ttyS0`, `ttyS2`–`ttyS7` e quatro CH340 (`ttyUSB0`–`ttyUSB3`); `i2c-0`, `i2c-1` (e `i2c-5`/`i2c-6`);
a `end0` existe (sem cabo); Wi-Fi pelo netplan do Armbian (`/etc/netplan/armbian.yaml`: só o root
lê, porque tem a senha da rede; lido em 28/10 com a senha escondida: fixa os MACs da `end0` e da
`wlan0`, veja o MAC do Wi-Fi na seção 17).

**Vale ajustar no brick** (nada foi mudado):

1. **Raiz no cartão, `/home` na eMMC** (a raiz da eMMC era o sistema antigo, kernel 6.6).
   **Resolvido em 20/10:** a partição 1 do cartão foi clonada para a partição 1 da eMMC (mesmo
   tamanho, 6.710.886.400 bytes) com a raiz do cartão montada somente leitura:
   `sudo dd if=/dev/mmcblk0p1 of=/dev/mmcblk2p1 bs=4M conv=fsync status=progress`. Sem o cartão, o
   brick sobe pela eMMC com o kernel 6.18.42.
2. **`remonta.sh` e o "Desbloquear" do menu** usam `/dev/mmcblk2p1`, e neste boot a raiz era o
   `mmcblk0p1`. Trocar por `sudo mount -o remount,rw /` (seção 14). O do menu fica em
   `menuPrincipal/telaMenu.py`, linha 257.
3. **`start.service` falhando a cada boot:** sobra antiga que roda `~/start.sh` (só um `source` do
   ambiente; termina na hora e o `Restart=always` desiste). O menu de hoje é o
   `menuPrincipal.service`. Desabilitar: `sudo systemctl disable start.service`.
4. **`systemd-networkd-wait-online` habilitado:** espera a rede até dar timeout ("Timeout occurred
   while waiting for network connectivity") e é o motivo do boot de mais de 2 minutos. Mascarar
   (`sudo systemctl mask systemd-networkd-wait-online.service`, seção 10) deve trazer o boot para
   a casa dos segundos.
5. **Travar também o `linux-dtb-current-sunxi64`** (só o `linux-image` está em `hold`; seção 5).
6. **`fancontrol` no cartão:** a Line/Maze não usa cooler, então ele não faz falta
   (`sudo systemctl disable --now fancontrol`; tirar o `pwm1-pi11` dos overlays é opcional). Se
   for mantido, é a versão antiga (lê a temperatura da GPU; seção 13).

**Aplicado em 20/10/2026:** os itens 2 (só o `remonta.sh`; o menu desse brick é antigo e não tem
o Desbloquear), 3, 4, 5, 7 e 8, pelo script `~/ajustes_brick.sh` (fica na `/home` do brick; só roda
se a raiz for a da eMMC). Depois do reboot: **boot de 14,8 s** (6,7 s de kernel + 8,0 s de
userspace; era 2 min 42 s), nenhuma unidade falhando, alvo `multi-user`, `linux-image` e
`linux-dtb` travados. Item 6: o Julio desabilitou o `fancontrol` (a Line/Maze não usa cooler).
**Menu atualizado (20/10):** o menu do brick era de ago/2025 e procurava o teclado só no `i2c-1`
(placa antiga), mas o brick tem a placa nova (tela em 0x3C e teclado em 0x38 no `i2c-0`): o
`start.py` caía em laço e o menu não aparecia. Foi trocado pela versão do repositório (tenta o
`i2c-1` e depois o `i2c-0`); a antiga ficou em `~/menuPrincipal.antigo_20261020`. Depois do reboot o
`start.py` ficou de pé. Também falta no brick o `i2c-tools` (`i2cdetect`) da seção 6. Os maiores
tempos que sobraram: `force-fsck-root` 3,0 s, `nmbd` 1,5 s, a eMMC 1,4 s e o `samba-ad-dc` 1,1 s
(controlador de domínio do Samba, que o brick não usa).
7. **"Iniciar X" do menu** roda `sudo systemctl start lightdm`, mas o lightdm não está instalado
   (e o comando nem está no sudoers sem senha). Ou tira a opção do menu, ou instala o lightdm e
   acrescenta o `systemctl` ao sudoers. Sem interface gráfica, `sudo systemctl set-default
   multi-user.target` deixa o alvo coerente.
8. `apt-daily-upgrade.service` e `logrotate.service` falham a cada boot (o `logrotate` sai com
   status 3). Com a raiz somente leitura nenhum dos dois tem o que fazer: desabilitar os timers
   (`apt-daily-upgrade.timer`, `logrotate.timer`) tira o aviso.

## Apêndice D — Imagem @Work (Ubuntu 24.04 + ROS2)

O que se sabe da imagem do Mariola @Work. **Ainda não há um passo a passo dela**: só o que ficou
registrado nos arquivos antigos e o que o Julio contou.

| Item | Valor |
|---|---|
| Placa | Banana Pi BPI-M4 Zero com **32 GB** de eMMC |
| Sistema | **Armbian Noble** (Ubuntu 24.04), para usar o **ROS2** |
| Kernel | 6.18 (6.18.44 no registro da otimização do boot) |
| Raiz | ext4 **somente leitura** na eMMC + `/home` em partição separada gravável |
| Rede | **NetworkManager** (mantido de propósito: trocar de rede com `nmcli` na competição) |
| Interface gráfica | lightdm (pode ficar sob demanda, seção 16) |
| Cooler | sim, no PWM1 com o `fancontrol` (seção 13): o processamento alto é constante |
| Áudio | usado (o `alsa-restore` foi mantido) |
| Boot | otimizado de 27,4 s para 14,7 s (seção 16) |

**O que vale igual à Line/Maze:** kernel 6.18 e overlays (seção 5, com o `pwm1-pi11`), permissões
(seção 7), SSH (seção 8), câmeras (seção 11), áudio (seção 12), temperatura (seção 13), raiz
somente leitura (seção 14), recuperação (seção 17) e compilação (seção 18, com
`RELEASE=noble`, a confirmar).

**O que muda ou falta documentar:**

* **ROS2:** a instalação (versão, pacotes, workspace) não está em nenhum arquivo. O `start.sh` do
  menu tem uma linha comentada `source ~/ros2_ws/.venv/bin/activate`, sinal de um workspace em
  `~/ros2_ws`.
* **Rede:** com o NetworkManager, troque `systemd-networkd-wait-online` por
  `NetworkManager-wait-online` nas seções 10 e 16; os arquivos `.network` da seção 10 não se
  aplicam.
* **Programa no boot:** a seção 16 sugere um `mariola.service` (`Restart=always`) em vez do
  `rc.local`.

### Cartão @Work e passagem para a eMMC

Cartão conferido em 27/10/2026 (num brick de 8 GB, só leitura): Armbian-unofficial 26.08.0-trunk
noble, kernel 6.18.43, tabela de partições `dos`:

| Partição | Começo | Tamanho | Rótulo | Montagem |
|---|---|---|---|---|
| `p1` | setor 8192 (4 MiB) | 18,9 GB | `armbi_root` | `/`, somente leitura (`UUID=` no `fstab` e no `armbianEnv.txt`) |
| `p2` | logo depois | 12,2 GB | `homesd` | `/home`, `data=journal` (`LABEL=homesd` no `fstab`) |

Antes da `p1` fica o U-Boot cru (de 8 KiB em diante; é o mesmo
`/usr/lib/linux-u-boot-current-bananapim4zero/u-boot-sunxi-with-spl.bin` do pacote).

O cartão e a eMMC têm 32 GB, mas os dois tamanhos nunca são iguais ao byte. Por isso o `dd` da
seção 4 não serve, e também não sobra espaço para uma partição com a imagem, como no cartão de
reserva da seção 17. O **`instalacao/clona_sd_emmc.sh`** faz a cópia arquivo por arquivo:

1. Ligue o brick **com o cartão** (o SD dá boot antes da eMMC).
2. Copie o script para o brick (ex.: `scp instalacao/clona_sd_emmc.sh banana@IP:~`). Ele pode
   ficar na `/home`: o script só deixa a `/home` somente leitura, não a desmonta.
3. Confira antes, sem gravar nada e sem sudo: `bash ~/clona_sd_emmc.sh -n`. Ele mostra os discos, os
   tamanhos (no cartão, na eMMC, usado) e as opções do ext4.
4. Grave: `sudo bash ~/clona_sd_emmc.sh` e digite `SIM` (ou `-y`). Com os ~16 GB usados de hoje,
   a estimativa é de 10 a 20 minutos (não medido).
5. Desligue, tire o cartão e ligue. Depois confira com `findmnt / /home`, que deve mostrar o
   `mmcblk2p1` e o `mmcblk2p2`.

O que ele faz:

* Cria na eMMC a `p1` com o mesmo começo e o mesmo tamanho da raiz do cartão. A `p2` fica com o
  resto. Se a eMMC for menor que o cartão, a raiz encolhe, desde que os arquivos caibam com folga
  (+10% e +512 MiB). Se não couberem, ele para antes de apagar qualquer coisa: é o que acontece se
  ele for rodado num brick com a eMMC de 8 GB.
* Formata com as mesmas opções do ext4 do cartão:
  * os recursos (`metadata_csum` etc.), o tamanho de bloco e de inode e a reserva do root;
  * as opções de montagem gravadas no ext4: `journal_data_writeback` na raiz e `journal_data` na
    `/home`.
* Os UUIDs são **novos** e os rótulos ficam `armbi_emmc` e `homeemmc`.
* Copia com `rsync -aAXH`. A raiz do cartão já é somente leitura, e a `/home` fica somente
  leitura durante a cópia. Se algum programa estiver com arquivo aberto, ele lista qual é e não
  grava nada.
* Troca os UUIDs no `/etc/fstab` e no `/boot/armbianEnv.txt` (`rootdev=`) **da cópia**. O
  `LABEL=homesd` vira `UUID=` da `p2` da eMMC. No cartão, só esses dois arquivos citam os UUIDs.
* Copia o U-Boot do cartão (de 8 KiB até o setor 8192) e compara com o original.
* No fim, sempre devolve a escrita à `/home` do cartão, mesmo com erro.

Com UUIDs e rótulos diferentes, ligar o brick com o cartão no slot sobe tudo do cartão, sem misturar
com a eMMC, que é o problema da seção 4. O cartão continua servindo de recuperação.

**Testado:**
* o modo `-n` no brick de 8 GB, onde ele recusa porque não cabe;
* o cálculo das partições, fingindo eMMCs de 31,3 GB, 30,7 GB e 15,4 GB;
* o `mkfs` com as opções lidas do cartão, que deu um ext4 igual (`dumpe2fs`);
* a troca dos UUIDs em cópias do `fstab` e do `armbianEnv.txt`.

**Ainda não testado:** a gravação de verdade numa eMMC de 32 GB.
