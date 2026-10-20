# Atualização para o kernel 6.18 (Ethernet e Áudio)

O kernel 6.6 que vem na Armbian 25.2.2 **não tem suporte à Ethernet 100M da placa**. O motivo é que o Fast Ethernet do BPI-M4-Zero não vem de um PHY externo, e sim do AC300 EPHY interno do SoC, acessível pelo conector FPC de 24 pinos. O device tree do Armbian descrevia um PHY RMII externo no endereço 1 do MDIO, que não existe fisicamente.

O suporte correto foi submetido no PR [armbian/build#10328](https://github.com/armbian/build/pull/10328) e está no `main`. O mesmo PR também habilita o codec de áudio analógico.

Enquanto a correção não chega em uma versão estável, é necessário usar o kernel 6.18 (rolling/nightly ou compilado localmente).

---

## Atualizando um sistema já configurado

Não é preciso reinstalar nada. Kernel e userland são independentes no Armbian, então dá para manter o Bookworm com toda a configuração e trocar apenas o kernel.

### 1. Verifique o branch atual

```
cat /etc/armbian-release | grep -E 'VERSION|BRANCH'
uname -r
```

O `BRANCH` precisa ser `current`. Se for, os nomes dos pacotes são os mesmos e o novo substitui o antigo direto, sem sobrar lixo.

### 2. Copie os pacotes para a placa

São dois arquivos:

```
scp linux-image-current-sunxi64_*.deb banana@IP_DA_PLACA:~
scp linux-dtb-current-sunxi64_*.deb banana@IP_DA_PLACA:~
```

### 3. Remonte a raiz como gravável

**Esse passo é obrigatório se você seguiu a recomendação de deixar a partição principal somente leitura.** Sem isso o `dpkg` falha.

```
sudo mount -o remount,rw /
```

Ou rode o `remonta.sh` da pasta do usuário.

### 4. Instale

```
sudo dpkg -i linux-image-current-sunxi64_*.deb linux-dtb-current-sunxi64_*.deb
```

Vai aparecer um aviso sobre não conseguir apagar o diretório `/boot/dtb-6.6.75-current-sunxi64` — isso acontece porque o DTB customizado do procedimento antigo fica lá sem dono. É inofensivo, e pode ser removido depois de validar o boot.

**O DTB customizado não é mais necessário.** Tudo que ele fazia (habilitar as seriais e trocar o modo da porta USB) agora é feito por overlay, conforme o passo 5.

### 5. Ative os overlays

**Esta é a mudança mais importante em relação ao procedimento antigo.** Antes, seriais e USB eram habilitados editando o DTB na mão e copiando o arquivo para `/boot/dtb-.../allwinner/`. Agora tudo é feito por overlay, o que sobrevive a atualizações de kernel e não exige recompilar nada.

```
sudo nano /boot/armbianEnv.txt
```

Linha completa:

```
overlays=bananapi-m4-pi-5-6-i2c0 bananapi-m4-pi-7-8-i2c1 bananapi-m4-sdio-wifi-bt gpu uart2-ph bananapi-m4-zero-fpc24-eth bananapi-m4-pi-13-14-uart4 bananapi-m4-ph-2-3-uart5 bananapi-m4-zero-usb0-host pwm1-pi11 cpu-opp-1512-speed0
```

O que cada um faz:

| Overlay | Função | Origem |
|---|---|---|
| `bananapi-m4-pi-5-6-i2c0` | I2C0 nos pinos PI5/PI6 | oficial |
| `bananapi-m4-pi-7-8-i2c1` | I2C1 nos pinos PI7/PI8 | oficial |
| `bananapi-m4-sdio-wifi-bt` | Wi-Fi e Bluetooth | oficial |
| `gpu` | Mali (Panfrost) | oficial |
| `uart2-ph` | UART2 nos pinos PH5/PH6 | oficial |
| `bananapi-m4-pi-13-14-uart4` | UART4 nos pinos PI13/PI14 | oficial |
| `bananapi-m4-ph-2-3-uart5` | UART5 nos pinos PH2/PH3 | oficial |
| `pwm1-pi11` | PWM1 no pino PI11 (controle do cooler) | oficial |
| `bananapi-m4-zero-fpc24-eth` | Ethernet 100M (exige a placa de expansão do FPC24) | PR #10328 |
| `bananapi-m4-zero-usb0-host` | Porta USB-C como host em vez de peripheral | local |
| `cpu-opp-1512-speed0` | Libera 1512 MHz em chips speed0 (overclock) | local |

**Antes de criar qualquer overlay, confira se já não existe um oficial:**

```
ls patch/kernel/archive/sunxi-6.18/overlay_64/ | grep -i <periferico>
```

O Armbian já traz overlays para praticamente todos os PWM e UART do H616, em cada pino possível. Criar um duplicado só gera trabalho de manutenção.

Sobre a Ethernet: ela fica desabilitada por padrão porque só funciona com a placa de expansão do FPC de 24 pinos. Habilitá-la sem a placa reservaria os pinos PA0-PA9 e o PWM5 à toa.

Sobre o USB: por padrão o nó `usb@5100000` (musb/OTG) vem habilitado e os `usb@5101000` / `usb@5101400` (EHCI/OHCI) vêm desabilitados, ou seja, a porta USB-C funciona como device. O overlay inverte isso e a porta passa a funcionar como host. Conferir com:

```
cat /proc/device-tree/soc/usb@5100000/status
cat /proc/device-tree/soc/usb@5101000/status
```

### Os overlays locais

Dois overlays não existem no Armbian e precisam ser adicionados à árvore de build antes de compilar: o `bananapi-m4-zero-usb0-host` e o `cpu-opp-1512-speed0` (descrito mais adiante, na seção de gerenciamento térmico). O `bananapi-m4-zero-fpc24-eth` foi submetido junto com o PR #10328 e já está no `main`.

Crie `patch/kernel/archive/sunxi-6.18/overlay_64/sun50i-h616-bananapi-m4-zero-usb0-host.dtso`:

```
/dts-v1/;
/plugin/;

/ {
	compatible = "sinovoip,bpi-m4-zero", "allwinner,sun50i-h616", "allwinner,sun50i-h618";

	/* Porta USB-C como host, e nao como peripheral (OTG) */
	fragment@0 {
		target = <&usbotg>;
		__overlay__ {
			status = "disabled";
		};
	};

	fragment@1 {
		target = <&ehci0>;
		__overlay__ {
			status = "okay";
		};
	};

	fragment@2 {
		target = <&ohci0>;
		__overlay__ {
			status = "okay";
		};
	};
};
```

E registre no `Makefile` da mesma pasta, junto com os outros `bananapi-m4`:

```
	sun50i-h616-bananapi-m4-zero-usb0-host.dtbo \
```

Atenção: a indentação é **tab**, e a linha termina com barra invertida. Sem esse registro o overlay simplesmente não é compilado, sem mensagem de erro.

### 6. Reinicie

Deixe o cabo serial conectado (115200) na primeira vez, para conseguir ver o log caso algo dê errado.

```
sudo reboot
```

### 7. Verifique as seriais e o USB

```
ls /dev/ttyS*
ls /dev/i2c-*
lsusb
```

As três seriais (UART2, UART4 e UART5) devem aparecer, além do console de debug (UART0). Se algum dispositivo USB conectado na porta USB-C não for reconhecido, confira se o overlay `bananapi-m4-zero-usb0-host` está na lista.

---

## Sobre o U-Boot

**Não precisa atualizar.** O U-Boot da 25.2.2 carrega o kernel 6.18 sem problema.

Vale lembrar que ele fica gravado cru no offset de 8 KB do dispositivo, ou seja, **não é atualizado pelo `dpkg`**. Como o procedimento de instalação usa `dd` do cartão SD para a eMMC, o U-Boot vai junto na cópia e não precisa de tratamento separado.

Se um dia for necessário mesmo assim, lembre que o BROM do H618 tenta bootar pelo cartão SD antes da eMMC — então um U-Boot quebrado na eMMC é recuperável colocando um cartão que funcione.

---

## Verificando a Ethernet

```
ip link
sudo ethtool end0 | grep -iE 'speed|duplex|link detected'
```

O esperado é `Speed: 100Mb/s`, `Duplex: Full`, `Link detected: yes`.

Para medir a vazão real, com `iperf3 -s` rodando em outra máquina da rede:

```
sudo apt install iperf3
iperf3 -c IP_DO_SERVIDOR -t 20
```

Resultado esperado: em torno de 94 Mbit/s, sem retransmissões. Esse é o teto do Fast Ethernet descontando o overhead de TCP/IP.

### Observação sobre o ethtool

O `ethtool` reporta `Supported link modes: 10baseT/Half 10baseT/Full` mesmo com o link negociando 100/Full e atingindo a taxa máxima. É um problema de reporte de capabilities no driver do AC300, não afeta o funcionamento.

### Se não pegar IP

Na instalação Minimal quem gerencia a rede é o `systemd-networkd`, que só configura interfaces com um arquivo `.network` correspondente. Dá para configurar pelo `armbian-config`, mas **a partição precisa estar montada como gravável**, senão a alteração falha silenciosamente e parece que a opção não funcionou.

Alternativa manual, criando `/etc/systemd/network/10-end0.network`:

```
[Match]
Name=end0

[Network]
DHCP=yes
```

E depois:

```
sudo systemctl restart systemd-networkd
```

---

## Áudio analógico

O codec já vem habilitado no kernel novo, sem precisar de overlay. Confira:

```
aplay -l
```

Devem aparecer dois cards: o `card 0: Codec [H616 Audio Codec]` (analógico) e o `card 1: HDMI`.

Teste:

```
speaker-test -D hw:0,0 -c2 -twav -l1
```

Para que qualquer aplicação (Python, sox, pygame) use o codec analógico por padrão sem precisar especificar o device, crie o arquivo `~/.asoundrc`:

```
defaults.pcm.card 0
defaults.ctl.card 0
```

Isso também resolve o caso do som ir parar no HDMI sem você pedir.

### Gerando beeps

Útil para sinalização de estado do robô durante a competição, quando não dá para olhar a tela:

```
sudo apt install sox
play -nq synth 0.2 sine 1000
```

Em Python:

```python
import subprocess

def beep(freq=1000, dur=0.2):
    subprocess.run(['play', '-nq', 'synth', str(dur), 'sine', str(freq)])
```

---

## Gerenciamento térmico e controle do cooler

### As zonas térmicas não estão na ordem óbvia

O H618 expõe quatro zonas, e a que interessa **não é a zero**:

| Zona | Tipo |
|---|---|
| `thermal_zone0` | `gpu-thermal` |
| `thermal_zone1` | `ve-thermal` |
| `thermal_zone2` | `cpu-thermal` |
| `thermal_zone3` | `ddr-thermal` |

Só a `cpu-thermal` tem trip points de throttling. As outras têm apenas o crítico de 110 graus.

```
cat /sys/class/thermal/thermal_zone2/trip_point_0_temp   # 60000 - passive
cat /sys/class/thermal/thermal_zone2/trip_point_1_temp   # 70000 - passive
cat /sys/class/thermal/thermal_zone2/trip_point_2_temp   # 110000 - critical
```

A numeração pode mudar entre versões de kernel, então **localize pelo nome**, não pelo índice:

```
for z in /sys/class/thermal/thermal_zone*; do
    echo "$z: $(cat $z/type)"
done
```

### O throttling começa cedo

Ao passar de 60 graus, o kernel reduz o clock de 1512 MHz para 1200 MHz — uma perda de cerca de 20%. A frequência volta sozinha quando esfria.

Isso é visível no `armbianmonitor -m`, na coluna `C.St.` (cooling state): quando aparece `1/5` em vez de `0/5`, o `cooling_device0` (`cpufreq-cpu0`) está atuando.

```
armbianmonitor -m
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq   # cai para 1200000
```

Note que a mensagem `sun50i_cpufreq_nvmem: Using CPU speed bin speed0` no `dmesg` **não** é a causa dessa redução momentânea — ela indica o bin do chip, que define o teto de hardware (`cpuinfo_max_freq`), não o throttling térmico. Veja a seção sobre liberar 1512 MHz mais abaixo.

### O cooler

Cooler de 4 fios (5V) ligado ao PWM1 no pino PI11. A entrada PWM desses coolers é opto-isolada, então aceita sinal de 3,3V direto do SBC, sem transistor. A frequência esperada pela especificação é 25 kHz, ou seja, período de 40000 ns.

Teste manual:

```
echo 1 | sudo tee /sys/class/pwm/pwmchip0/export
cd /sys/class/pwm/pwmchip0/pwm1
echo 40000 | sudo tee period
echo 20000 | sudo tee duty_cycle    # 50%
echo 1 | sudo tee enable
```

O controle automático é feito pelo `fancontrol.py`, instalado como serviço:

```
sudo ./instalar-fancontrol.sh
```

Ele localiza a zona `cpu-thermal` pelo nome, aplica rampa linear entre 50 e 68 graus (com histerese na parada e duty mínimo de 30%, senão o cooler não parte), e opcionalmente eleva os trips de throttling de 60/70 para 70/80 graus.

Elevar os trips é escolha consciente: o padrão da Allwinner é conservador por segurança, e subir significa rodar mais quente por mais tempo. Faz sentido quando há refrigeração ativa e ventilação adequada, mas não é de graça.

### Ventilação da caixa

Com a placa dentro de uma case fechada, o dissipador satura — esquenta o ar ao redor e para de trocar calor. Foram registrados 95 graus nessa condição.

O que resolve não é um cooler mais forte, e sim **fluxo de ar**: entrada e saída em lados opostos, e o ar passando através das aletas em vez de por cima. Depois de abrir a caixa e instalar um cooler de 20x20mm, a temperatura em carga total ficou em torno de 53 graus.

### Teste de carga

```
sudo apt install stress-ng
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
stress-ng --cpu 4 --cpu-method matrixprod --timeout 1800s --metrics-brief
```

Acompanhe em outro terminal:

```
watch -n1 'cat /sys/class/thermal/thermal_zone2/temp; \
           cat /sys/class/pwm/pwmchip0/pwm1/duty_cycle; \
           cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq'
```

**Teste com a caixa fechada e por tempo longo.** Cinco minutos não dizem nada sobre uma prova de vinte — o calor em espaço confinado é cumulativo. Se a temperatura subir devagar e continuamente em vez de estabilizar, o problema é saída de ar, não potência do cooler.

### Liberando 1512 MHz em chips speed0

No kernel 6.6 a placa rodava a 1512 MHz. No 6.18 o teto cai para 1416 MHz, e **isso não é throttling** — o `cpuinfo_max_freq` (teto de hardware) passa a ser 1416000.

A causa é a tabela de OPP. O H616 classifica cada chip em um *speed bin* gravado no eFuse, visível no boot:

```
dmesg | grep "speed bin"      # sun50i_cpufreq_nvmem: Using CPU speed bin speed0
```

Cada OPP declara quais bins suporta através de uma máscara de bits em `opp-supported-hw`. No `arch/arm64/boot/dts/allwinner/sun50i-h616-cpu-opp.dtsi` do 6.18:

```
opp-1512000000 {
        opp-hz = /bits/ 64 <1512000000>;
        opp-microvolt-speed1 = <1100000>;
        opp-microvolt-speed3 = <1100000>;
        opp-microvolt-speed5 = <1160000>;
        opp-supported-hw = <0x2a>;
};
```

`0x2a` em binário é `101010`, ou seja, bits 1, 3 e 5 — **speed0 não está incluído**. Já o `opp-1416000000` usa `0x2d` (`101101`, bits 0, 2, 3 e 5), que inclui o bin 0. Daí o teto de 1416.

A tabela do kernel 6.6 era bem mais antiga: tinha só 3 bins e dava 1512 MHz a 1,1 V para todos, sem `opp-supported-hw`. Por isso funcionava.

#### O overlay

Como `cpu_opp_table` tem label exportado em `__symbols__`, dá para sobrescrever por overlay — sem recompilar kernel e, principalmente, **podendo desativar editando uma linha** do `armbianEnv.txt` caso apareça instabilidade.

Crie `patch/kernel/archive/sunxi-6.18/overlay_64/sun50i-h616-cpu-opp-1512-speed0.dtso`:

```
/dts-v1/;
/plugin/;

/ {
	compatible = "allwinner,sun50i-h616", "allwinner,sun50i-h618";

	fragment@0 {
		target = <&cpu_opp_table>;
		__overlay__ {
			opp-1512000000 {
				opp-microvolt-speed0 = <1100000>;
				opp-supported-hw = <0x2b>;
			};
		};
	};
};
```

E registre no `Makefile` da mesma pasta.

**As duas propriedades são necessárias.** Mudar só a máscara deixa o OPP sem tensão definida para o bin 0, com comportamento imprevisível. O valor de 1,1 V não é chute: é exatamente o que a tabela do 6.6 usava para speed0 nessa frequência.

O merge de device tree sobrescreve as propriedades declaradas e mantém o resto do nó (`opp-hz`, `clock-latency-ns`, tensões dos outros bins) intacto.

#### Validação

Isso é overclock — você está rodando fora da faixa que a Allwinner validou para esse silício. Valide com carga longa antes de levar para competição:

```
stress-ng --cpu 4 --vm 2 --vm-bytes 256M --timeout 1800s
```

O teste com memória junto importa: instabilidade por tensão insuficiente às vezes só aparece quando CPU e barramento trabalham ao mesmo tempo, que é justamente o padrão de ROS com visão.

```
cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq            # 1512000
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies
```

Resultado medido no BPI-M4-Zero: 1512 MHz estável, 56 graus em carga total por 30 minutos com o cooler ativo e a caixa fechada.

#### Por que não subir mais

Não existe OPP acima de 1512 na tabela, para nenhum bin. Criar um seria território sem referência de tensão nem garantia de que o PLL trava na frequência — as frequências do PLL_CPUX são múltiplos de 24 MHz, então nem "1600 MHz" é um valor válido (seria 1608).

E os 1,16 V do speed5 não são folga para ir além: são a tensão que um chip *melhor* precisa para rodar os mesmos 1512, o que sugere que essa frequência já está perto do limite prático da arquitetura.

---

## Nomes das interfaces de rede

Por padrão o systemd usa nomes previsíveis: a Ethernet vira `end0` e não `eth0`. Para voltar aos nomes clássicos, acrescente ao `/boot/armbianEnv.txt`:

```
extraargs=net.ifnames=0 biosdevname=0
```

Se a linha `extraargs=` já existir, acrescente os parâmetros nela em vez de criar outra.

**Antes de reiniciar**, verifique se alguma configuração referencia o nome antigo — senão você fica sem rede:

```
grep -rl "end0" /etc/systemd/network/ /etc/NetworkManager/ /etc/network/ 2>/dev/null
```

Ajuste o que aparecer. Em instalações Minimal, o arquivo típico é `/etc/systemd/network/10-end0.network`, que precisa virar `10-eth0.network` com o `Name=` correspondente:

```
[Match]
Name=eth0

[Network]
DHCP=yes
```

No Desktop, quem gerencia é o NetworkManager, e as conexões salvas em `/etc/NetworkManager/system-connections/` podem ter o nome da interface fixado no campo `interface-name`.

---

## Travando o kernel

Depois de validar tudo, trave os pacotes para que um `apt upgrade` não devolva o kernel antigo do repositório (o que faria a Ethernet parar de funcionar):

```
sudo apt-mark hold linux-image-current-sunxi64 linux-dtb-current-sunxi64
```

**Isso é temporário.** Quando o Armbian lançar uma versão estável já contendo o PR #10328, dá para liberar e voltar a receber atualizações normalmente:

```
sudo apt-mark unhold linux-image-current-sunxi64 linux-dtb-current-sunxi64
```

---

## Compilando a própria imagem (opcional)

Caso queira gerar uma imagem do zero em vez de atualizar uma existente.

**Requisitos do host:** Ubuntu 24.04 (Noble) para build nativo, ou qualquer Linux com Docker (o framework detecta host não suportado e usa container automaticamente). Mínimo de 8 GB de RAM e cerca de 50 GB de disco livre.

```
git clone --depth=1 https://github.com/armbian/build
cd build
./compile.sh BOARD=bananapim4zero BRANCH=current RELEASE=bookworm BUILD_MINIMAL=yes
```

Para gerar apenas os pacotes do kernel, sem a imagem completa:

```
./compile.sh kernel BOARD=bananapim4zero BRANCH=current RELEASE=bookworm
```

### Onde ficam os pacotes

Os `.deb` recém-gerados saem em `output/packages-hashed/global/` ou em `output/debs/`. Repare no trecho `P####` do nome do arquivo: ele é um hash dos patches, e serve para conferir se uma alteração sua realmente entrou no build. Se o hash não mudou depois de você editar algo, o framework reaproveitou artefato do cache.

**Cuidado com versões acumuladas.** Essas pastas guardam builds antigos, e um glob como `linux-dtb-current-sunxi64_*.deb` pega o primeiro em ordem alfabética, não o mais recente. Sempre confira a data:

```
ls -lat output/debs/linux-dtb-current-sunxi64_*.deb | head -3
```

O mesmo vale na hora de instalar: `dpkg -i *.deb` pode instalar o pacote errado sem reclamar.

### Editando o device tree

O DTS da placa **não vem de um patch** e nem existe no kernel mainline. O framework copia os arquivos da pasta `patch/kernel/archive/sunxi-<versão>/dt_64/` para dentro da árvore do kernel durante o build. O arquivo a editar é:

```
patch/kernel/archive/sunxi-6.18/dt_64/sun50i-h618-bananapi-m4-zero.dts
```

Os overlays ficam em `patch/kernel/archive/sunxi-6.18/overlay_64/`, com extensão `.dtso`, e precisam ser registrados no `Makefile` daquela mesma pasta — senão não são compilados.
