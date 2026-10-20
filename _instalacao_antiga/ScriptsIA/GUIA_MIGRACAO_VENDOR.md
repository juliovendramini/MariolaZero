# Guia de Migração: Kernel Vendor 5.4.125 + U-Boot

## 🎯 Objetivo

Migrar do kernel Armbian atual (6.6.75/6.16.8) para o **kernel vendor 5.4.125** fornecido pelo fabricante, incluindo U-Boot compatível, para garantir funcionamento completo do hardware (Ethernet interno, etc).

---

## 📋 Pré-requisitos

1. ✅ **Cartão SD** com imagem vendor funcionando (opcional, mas recomendado para U-Boot)
2. ✅ **Imagem vendor**: `Armbian_24.8.2_Bpi-m4zero_bookworm_legacy_5.4.125_minimal.img`
3. ✅ **Acesso SSH** à Banana Pi
4. ✅ **Backup** de dados importantes

---

## 🚀 Método Rápido (Recomendado)

### 1. Enviar Scripts

No **PowerShell** (Windows):

```powershell
cd C:\Users\Julio\Documents\Arduino\bananaPiM4Zero
.\envia_scripts_migracao.ps1
```

### 2. Executar Migração Completa

**⚠️ IMPORTANTE: Insira o cartão SD com kernel vendor funcionando ANTES de executar!**

```bash
ssh root@192.168.2.151
bash /root/migracao_completa_vendor.sh
```

O script irá:
- ✅ Diagnosticar o sistema atual
- ✅ Perguntar se deseja copiar U-Boot do SD → eMMC
- ✅ Verificar instalação do kernel vendor
- ✅ Copiar e configurar DTBs
- ✅ Reiniciar automaticamente

### 3. Verificar Após Boot

```bash
# Verificar kernel
uname -r
# Deve mostrar: 5.4.125-legacy-sunxi64

# Verificar Ethernet interno
dmesg | grep -i emac
ip link show

# Verificar DTB
dmesg | grep -i "machine model"
```

---

## 🔧 Método Manual (Passo a Passo)

### Passo 1: Diagnóstico

```bash
ssh root@192.168.2.151
bash /root/diagnostico_uboot.sh
```

Verifique:
- Versão do U-Boot no eMMC vs cartão SD
- Presença de DTBs em `/boot/dtb/`
- Configuração de `armbianEnv.txt`

### Passo 2: Copiar U-Boot (SE NECESSÁRIO)

**⚠️ Apenas se o U-Boot atual não consegue carregar o kernel vendor!**

```bash
# Inserir cartão SD com kernel vendor funcionando
bash /root/copia_uboot_sd_emmc.sh
```

O script:
- ✅ Faz backup automático do U-Boot atual
- ✅ Copia U-Boot do SD para eMMC
- ✅ Preserva a tabela de partições

### Passo 3: Instalar Kernel Vendor

Se ainda não instalou, use o PowerShell:

```powershell
.\install_vendor_kernel_simple.ps1
```

Ou manualmente:

```bash
# Transferir imagem
scp <imagem.img> root@192.168.2.151:/tmp/vendor_kernel.img

# Montar e copiar
OFFSET=$(fdisk -l /tmp/vendor_kernel.img | grep "Linux" | grep -v "swap" | awk '{print $2}')
mount -o loop,offset=$((OFFSET * 512)) /tmp/vendor_kernel.img /mnt

cp /mnt/boot/vmlinuz-5.4.125-legacy-sunxi64 /boot/
cp /mnt/boot/uInitrd-5.4.125-legacy-sunxi64 /boot/
ln -sf vmlinuz-5.4.125-legacy-sunxi64 /boot/vmlinuz
ln -sf uInitrd-5.4.125-legacy-sunxi64 /boot/uInitrd
cp -r /mnt/lib/modules/5.4.125-legacy-sunxi64 /lib/modules/
depmod -a 5.4.125-legacy-sunxi64

umount /mnt
```

### Passo 4: Corrigir DTB

```bash
bash /root/corrige_dtb.sh
```

O script:
- ✅ Copia DTBs da imagem vendor
- ✅ Detecta DTB correto para Banana Pi M4 Zero
- ✅ Atualiza `armbianEnv.txt`

### Passo 5: Reiniciar

```bash
# Remover cartão SD se inserido
# Então:
reboot
```

---

## 🐛 Resolução de Problemas

### Problema: "Cannot find DTB"

**Solução:**
```bash
bash /root/corrige_dtb.sh
```

Verifique `/boot/armbianEnv.txt`:
```bash
cat /boot/armbianEnv.txt | grep fdtfile
```

Deve estar algo como:
```
fdtfile=allwinner/sun50i-h618-orangepi-zero3.dtb
```

### Problema: Sistema não boota após copiar U-Boot

**Solução: Restaurar backup**

1. Boote do cartão SD
2. Monte o eMMC
3. Restaure o backup:

```bash
# O backup está em /root/uboot_backup_<data>/
dd if=/root/uboot_backup_*/emmc_uboot_backup.img of=/dev/mmcblk2 bs=1M conv=fsync
```

### Problema: Kernel 5.4.125 carrega mas Ethernet não funciona

Verifique se o DTB está correto:

```bash
dmesg | grep -i "machine model"
# Deve mostrar Banana Pi ou Orange Pi Zero 3

dmesg | grep -i emac
# Procure por mensagens de inicialização do EMAC
```

Se o DTB estiver errado, tente outro:

```bash
ls /boot/dtb/allwinner/*.dtb
# Escolha o mais adequado

nano /boot/armbianEnv.txt
# Edite: fdtfile=allwinner/<dtb-escolhido>.dtb

reboot
```

---

## 📊 Estrutura de Boot

### Arquivos Críticos

```
/dev/mmcblk2         (eMMC)
├── 0-8KB           → Tabela de partições
├── 8KB-1MB         → U-Boot
└── Partição 1       → Sistema de arquivos
    └── /boot/
        ├── vmlinuz-5.4.125-legacy-sunxi64
        ├── uInitrd-5.4.125-legacy-sunxi64
        ├── armbianEnv.txt
        └── dtb/allwinner/*.dtb
```

### Ordem de Boot

1. **ROM** → carrega U-Boot do offset 8KB
2. **U-Boot** → lê `armbianEnv.txt`
3. **U-Boot** → carrega kernel + initrd + DTB
4. **Kernel** → inicializa hardware

---

## 📝 Backups Criados Automaticamente

| Arquivo | Localização |
|---------|-------------|
| U-Boot original | `/root/uboot_backup_<data>/emmc_uboot_backup.img` |
| armbianEnv.txt | `/boot/armbianEnv.txt.backup_<data>` |
| Kernel anterior | `/boot/vmlinuz.backup-<data>` |
| InitRD anterior | `/boot/uInitrd.backup-<data>` |

---

## ✅ Checklist de Verificação Pós-Migração

- [ ] `uname -r` mostra `5.4.125-legacy-sunxi64`
- [ ] `dmesg | grep -i emac` mostra inicialização do Ethernet
- [ ] `ip link show` mostra interface `eth0` ou `eth1`
- [ ] `lsmod | grep sun` mostra módulos sunxi carregados
- [ ] Todos os dispositivos I2C/SPI/GPIO funcionando

---

## 🆘 Suporte

Se algo der errado:

1. **Boote do cartão SD vendor** (emergência)
2. **Monte o eMMC** e restaure backups
3. **Verifique logs**: `dmesg`, `journalctl -b`

---

## 📚 Referências

- U-Boot: https://docs.u-boot.org/
- Device Tree: https://www.kernel.org/doc/html/latest/devicetree/
- Armbian: https://docs.armbian.com/
