# Otimização de boot — Mariola @Work (BPI-M4-Zero / Armbian Noble)

Registro do que foi aplicado para reduzir o tempo de boot do robô.

**Hardware/SO:** Banana Pi BPI-M4-Zero v2 (Allwinner H618, quad Cortex-A53)
Armbian Noble, kernel 6.18.44-current-sunxi64
Rootfs ext4 **read-only** em eMMC + `/home` em partição separada gravável

---

## Resultados

| Etapa | Kernel | Userspace | Total |
|---|---|---|---|
| Baseline | 6,308s | 21,102s | **27,411s** |
| Após passo 1 (wait-online) | 5,789s | 12,386s | **18,176s** |
| Após passos 2–3 (BT + raid6/initramfs) | 5,726s | 11,890s | **17,616s** |
| Após passo 4 (faxina userspace) | 5,229s | 9,506s | **14,736s** |

**Ganho total: 27,411s → 14,736s (−46%).**
`multi-user.target` atingido em 8,794s de userspace (era 21,014s).

### Cadeia crítica final

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

A cadeia ficou curta: saíram `armbian-ramlog`, `var-log.mount`, `dev-zram1`,
`systemd-resolved` e `tmpfiles-setup`. O que resta é essencialmente o
**NetworkManager (4,083s = 46% do userspace)**, deixado como está por decisão
de projeto (ver Pendências).

---

## Observação importante sobre o rootfs read-only

**Todo comando que altera o sistema precisa ser precedido de `./remonta.sh`.**
Sem isso, `systemctl disable` não cria/remove os symlinks e a alteração se perde no reboot.

---

## Passo 1 — NetworkManager-wait-online (ganho: ~9s)

Era o maior gargalo isolado. Ficava esperando **todas** as interfaces gerenciadas
obterem carrier — e a `eth0` está `unavailable` (o robô usa wifi).

```bash
sudo ./remonta.sh
sudo systemctl disable NetworkManager-wait-online.service
```

O `rc-local.service` foi **mantido** (será usado futuramente para iniciar código).
Sem o wait-online, o `network-online.target` é satisfeito instantaneamente e o
rc-local continua na cadeia sem custo.

### Consequência a considerar

Código iniciado pelo rc-local passa a rodar **sem garantia de wifi associado**.
Para bind local (Flask em `0.0.0.0`) não faz diferença. Se precisar alcançar a
rede na largada, implementar retry.

---

## Passo 2 — Bluetooth (ganho: ~4s)

Inútil neste robô. Removido por blacklist de módulos + purge dos pacotes.

```bash
sudo ./remonta.sh
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

O módulo `brcmfmac` (wifi) **não** depende de nenhum destes — o wifi continua
funcionando normalmente. Verificar após reboot com `nmcli dev status`.

Eliminou: `blueman-mechanism.service` (3,4s), `bluetooth.service` (651ms), e
~4s espalhados no dmesg (BNEP 1,17s + firmware BCM 2,13s + RFCOMM).

---

## Passo 3 — raid6 + initramfs (ganho: ~1,4s de kernel)

O kernel rodava um benchmark de RAID6 (`raid6: neonx8 gen()`) que consumia
1,3–1,9s. **Blacklist em `/etc/modprobe.d` sozinho não resolve** — o benchmark
roda dentro do initramfs, que carrega sua própria cópia congelada do
`/etc/modprobe.d`.

A solução foi regenerar o initramfs com resolução de módulos por dependência:

```bash
sudo apt install zstd
```

Em `/etc/initramfs-tools/initramfs.conf`:

```
MODULES=dep
COMPRESS=zstd
```

```bash
sudo ./remonta.sh
sudo update-initramfs -u -k all
```

`MODULES=dep` reduziu a 32 módulos (só o necessário para montar ext4 no eMMC),
eliminando o raid6 por tabela.

### Verificação

```bash
dmesg | grep -i raid6                    # deve vir vazio
lsmod | grep raid                        # deve vir vazio
```

### Ponto deixado em aberto (por segurança)

O initrd ficou em 15MB. A análise mostrou que **12,75MB é `usr/lib/udev/hwdb.bin`**,
inútil dentro do initramfs. Existe a opção de removê-lo via hook, com ganho
estimado de ~0,4s. **Não foi aplicado** — o risco de um boot quebrado em
competição não compensa o ganho.

Se um dia valer a pena:

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

---

## Passo 4 — Faxina do userspace

Nenhum destes serviços estava na cadeia crítica, mas juntos somavam ~7s de CPU
disputando os 4 cores A53 enquanto o NetworkManager tentava subir.

```bash
sudo ./remonta.sh

sudo systemctl disable --now apport avahi-daemon avahi-daemon.socket \
  cups cups-browsed ModemManager e2scrub_reap rng-tools-debian \
  lm-sensors armbian-ramlog

sudo systemctl disable apt-daily.timer apt-daily-upgrade.timer man-db.timer \
  motd-news.timer dpkg-db-backup.timer e2scrub_all.timer

sudo apt purge -y apport apport-symptoms modemmanager cups cups-daemon \
  cups-browsed avahi-daemon snapd lm-sensors
```

### O que cada um faz

| Serviço | Custo | Por que sai |
|---|---|---|
| `apport` | 2,9s | Coletor de crash do Ubuntu |
| `avahi-daemon` | 591ms | mDNS/Bonjour — descoberta de rede local |
| `cups` / `cups-browsed` | 272ms+ | Sistema de impressão |
| `ModemManager` | 478ms | Gerência de modem 3G/4G |
| `e2scrub_reap` | 746ms | Verificação de metadados ext4 (precisa LVM) |
| `rng-tools-debian` | 494ms | Daemon de entropia (o H618 tem RNG em hardware) |
| `lm-sensors` | 340ms | Sensores; a temperatura útil vem do `sun8i-thermal` via sysfs |
| `armbian-ramlog` | 918ms | **Estava na cadeia crítica**; redundante com rootfs read-only |

Temperatura continua acessível sem o lm-sensors:

```bash
cat /sys/class/thermal/thermal_zone0/temp
```

---

## ⚠️ ATENÇÃO — o erro que quebrou o desktop

O comando original desta etapa incluía `plymouth` e `plymouth-theme-*` no purge.
**Não faça isso.**

No Armbian, `plymouth-theme-*` casa com `armbian-plymouth-theme`, que é
dependência do **lightdm**. O apt removeu em cascata:

```
armbian-plymouth-theme → lightdm → slick-greeter → lightdm-settings → light-locker
```

Resultado: interface gráfica removida. Restauração:

```bash
sudo ./remonta.sh
sudo apt install lightdm slick-greeter lightdm-settings light-locker
```

O plymouth volta junto como dependência. Custo real dele no boot é só ~89ms
(`plymouth-quit-wait`) — não vale o risco.

Se algum dia quiser eliminar esse tempo, o caminho seguro é **mascarar sem
desinstalar**:

```bash
sudo systemctl mask plymouth-quit-wait.service
```

---

## O que foi deliberadamente MANTIDO

| Item | Motivo |
|---|---|
| `rc-local.service` | Será usado para iniciar o código do robô |
| `polkit` (1,4s) | NetworkManager e systemd-logind dependem dele — quebra o wifi |
| `alsa-restore` (462ms) | **O robô usa áudio** (codec analógico `sun8i-codec`) |
| `NetworkManager` (4,5s) | Facilita trocar de rede em competição (arena / hotspot / casa) |
| `rsyslog` / `logrotate` | Reversível; só remover se nenhum script ler `/var/log/syslog` |
| `armbian-zram-config` (720ms) | Cria o zram de swap |
| `plymouth` | Dependência do lightdm (ver seção acima) |

---

## Desktop sob demanda

Para ter a interface gráfica disponível sem pagar o custo no boot:

```bash
sudo ./remonta.sh
sudo systemctl set-default multi-user.target
sudo systemctl disable lightdm
```

Quando precisar:

```bash
sudo systemctl start lightdm
```

---

## Verificações pós-reboot

```bash
systemd-analyze
systemd-analyze critical-chain
systemd-analyze blame | head -20

nmcli dev status          # wlan0 deve estar 'connected'
aplay -l                  # card de áudio presente
amixer scontrols          # controles de volume presentes
dmesg | grep -i raid6     # vazio
```

---

## Pendências / próximos passos possíveis

### 1. NetworkManager (4,08s) — DECIDIDO: manter como está

É o último gargalo grande, mas foi **deliberadamente mantido**. Em competição
a troca de rede é frequente (arena / hotspot do celular / casa) e a
praticidade do `nmcli` vale mais do que os segundos.

Se um dia mudar de ideia, na ordem de menor para maior risco:

**Leve** — reduzir o trabalho dele (reversível, mantém o `nmcli`).
Em `/etc/NetworkManager/conf.d/robot.conf`:

```ini
[main]
plugins=keyfile
[device]
wifi.scan-rand-mac-address=no
[connection]
ipv6.method=disabled
```

Desligar IPv6 e MAC randomization costuma cortar 1–2s.

**Definitiva** — migrar para `systemd-networkd` + `wpa_supplicant@wlan0`
(cai para ~300ms). Custo: perde a troca fácil de rede.

### 2. Unit systemd em vez do rc.local

Recomendado quando for colocar o código do robô para iniciar sozinho.
O `rc-local.service` é `Type=forking` com `TimeoutSec=0` — se o código rodar em
foreground, o `multi-user.target` **nunca** é atingido e o boot trava.

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

Vantagens sobre o rc.local: `Restart=always` (importante, dado o histórico de
segfault no OpenCV DNN em thread), `journalctl -u mariola -f` para debug, e
não bloqueia o boot.

`After=network.target` (não `network-online.target`) para não reintroduzir espera.

### 3. journald volátil

Com o `armbian-ramlog` desativado e rootfs read-only, o journald já cai
automaticamente para `/run`. Para tornar explícito, em
`/etc/systemd/journald.conf`:

```
Storage=volatile
RuntimeMaxUse=16M
```

Efeito colateral: log não sobrevive a reboot — ruim para post-mortem de crash.

---

### 4. Ninharias restantes (ganho quase nulo)

Nenhum destes está na cadeia crítica — cortá-los não muda o tempo total:

| Item | Custo | Condição para remover |
|---|---|---|
| `armbian-zram-config` | 672ms | Só se não usar zram como swap |
| `logrotate` | 652ms | Só se nenhum script ler `/var/log/syslog` |
| `rsyslog` | 370ms | Idem (o journald já guarda tudo) |
| `dev-mmcblk1p1.device` | 1,4s | udev esperando o eMMC — pouco a fazer |

### 5. Piso do kernel (5,2s)

O grosso é enumeração USB: hub + 4× CH340 serializados no EHCI custam ~2,5s.
Só reduz tirando adaptador serial do robô.

---

## Nota sobre leitura do `critical-chain`

Na saída pode aparecer `systemd-journald.service` com timestamp **maior** que o
do `multi-user.target` (ex.: `@9.327s` contra `@8.794s`). Isso é o journald
tendo reiniciado após o boot, não um serviço lento. O número real é o do
`systemd-journald.socket` (`@877ms`). Ignorar.

## Nota sobre enumeração MMC

O device do rootfs alterna entre `mmcblk1p1` e `mmcblk2p1` **entre boots** — a
ordem de enumeração MMC no H618 não é estável. O fstab usa UUID, então está
seguro, mas qualquer script com caminho `/dev/mmcblkNpX` hardcoded vai quebrar
aleatoriamente.
