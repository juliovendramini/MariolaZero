# Integração WiFi Interno - Banana Pi M4 Zero
## Alterações no DTS (sun50i-h618-bananapi-m4-zero.dts_6.1)

### 📡 Resumo das Modificações

Integrei as configurações de WiFi interno do kernel 6.6 para o kernel 6.1, habilitando o módulo WiFi Broadcom BCM4329 via interface SDIO.

---

## 🔧 Alterações Realizadas

### 1. **Adicionado Pinctrl para Clock WiFi**
   **Localização:** `/soc/pinctrl@300b000/`
   
   ```dts
   x32clk-fanout-pin {
       pins = "PG10";
       function = "clock";
       phandle = <0x40>;
   };
   ```
   
   - Configura PG10 como saída de clock 32kHz para o módulo WiFi

---

### 2. **Configuração SDIO/MMC1 para WiFi**
   **Localização:** `mmc@4021000`
   
   **Alterações principais:**
   - `status = "okay"` (habilitado)
   - `max-frequency = 0x5f5e100` (100 MHz)
   - `bus-width = 0x04` (4 bits SDIO)
   - `non-removable` (dispositivo soldado)
   - `keep-power-in-suspend` (mantém WiFi ligado em suspend)
   - `mmc-pwrseq = <0x1d>` (sequência de power-on)
   - `vmmc-supply = <0x39>` (alimentação 5V)
   
   **Dispositivo WiFi:**
   ```dts
   wifi@1 {
       reg = <0x01>;
       compatible = "brcm,bcm4329-fmac";
       phandle = <0x66>;
   };
   ```

---

### 3. **Regulador de Tensão 1.8V**
   **Novo bloco adicionado:**
   
   ```dts
   reg_vcc1v8 {
       compatible = "regulator-fixed";
       regulator-name = "vcc-1v8";
       regulator-min-microvolt = <0x1b7740>;  // 1.8V
       regulator-max-microvolt = <0x1b7740>;
       vin-supply = <0x39>;  // Alimentado pelo vcc-5v
       phandle = <0x1c>;
   };
   ```

---

### 4. **Power Sequence para WiFi**
   **Novo bloco adicionado:**
   
   ```dts
   wifi-pwrseq {
       compatible = "mmc-pwrseq-simple";
       clocks = <0x10 0x01>;           // Clock 32kHz do RTC
       clock-names = "ext_clock";
       pinctrl-0 = <0x40>;             // Pinctrl do clock
       pinctrl-names = "default";
       post-power-on-delay-ms = <0xc8>; // 200ms delay
       reset-gpios = <0x1e 0x06 0x12 0x01>; // PG18 (reset WiFi)
       phandle = <0x1d>;
   };
   ```
   
   - Controla o reset do módulo WiFi via GPIO PG18
   - Usa clock 32kHz do RTC como clock externo
   - Adiciona delay de 200ms após power-on

---

## 📋 Phandles Utilizados

| Phandle | Função | Descrição |
|---------|--------|-----------|
| `0x10` | RTC | Clock 32kHz para WiFi |
| `0x1c` | reg_vcc1v8 | Regulador 1.8V |
| `0x1d` | wifi-pwrseq | Sequência power-on WiFi |
| `0x1e` | pinctrl (r_pio) | GPIO PG para reset |
| `0x1f` | mmc1-pins | Pinctrl SDIO |
| `0x39` | vcc5v | Regulador 5V |
| `0x40` | x32clk-fanout | Pinctrl clock 32kHz |
| `0x66` | wifi@1 | Device node WiFi |
| `0x6a` | mmc1 | Controlador SDIO |

---

## 🚀 Como Usar

### 1. **Transferir DTS e Script**
```powershell
scp .\sun50i-h618-bananapi-m4-zero.dts_6.1 banana@192.168.2.181:~
scp .\compila_instala_dtb_wifi.sh banana@192.168.2.181:~
```

### 2. **Compilar e Instalar**
```bash
ssh banana@192.168.2.181
bash ~/compila_instala_dtb_wifi.sh
```

### 3. **Reiniciar**
```bash
reboot
```

---

## ✅ Verificação Pós-Instalação

### Verificar detecção do hardware:
```bash
# Ver se MMC1 foi inicializado
dmesg | grep -i mmc1

# Ver se Broadcom foi detectado
dmesg | grep -i brcm

# Listar interfaces de rede
ip link show

# Ver firmware carregado
dmesg | grep -i firmware
```

### Verificar firmware Broadcom:
```bash
ls -lh /lib/firmware/brcm/
```

### Se firmware não existir:
```bash
apt-get update
apt-get install firmware-brcm80211
```

---

## 🔍 Diferenças entre Kernel 6.1 e 6.6

| Aspecto | Kernel 6.1 (Antes) | Kernel 6.6 (Integrado) |
|---------|-------------------|----------------------|
| WiFi Status | disabled | **okay** |
| Max Frequency | 150 MHz | **100 MHz** (SDIO) |
| Bus Width | N/A | **4 bits** |
| Power Sequence | Não | **Sim** (GPIO PG18) |
| Clock Source | N/A | **RTC 32kHz** |
| Regulador 1.8V | Não | **Sim** |

---

## 📝 Hardware Configurado

### **Módulo WiFi**
- Chipset: **Broadcom BCM4329** (compatível BCM43xx)
- Interface: **SDIO (mmc1)**
- Frequência: **100 MHz**
- Largura de banda: **4 bits**

### **GPIOs Utilizados**
- **PG0-PG5**: Data lines SDIO (6 pinos)
- **PG10**: Clock 32kHz output
- **PG18**: Reset WiFi

### **Power**
- **5V**: vcc5v (main supply)
- **1.8V**: reg_vcc1v8 (WiFi logic)

---

## ⚠️ Notas Importantes

1. **Firmware necessário:** O driver `brcmfmac` precisa do firmware em `/lib/firmware/brcm/`

2. **Clock 32kHz:** O módulo WiFi usa o clock do RTC, certifique-se que está funcionando

3. **GPIO Reset:** O reset do WiFi é controlado por PG18, se não funcionar verifique este GPIO

4. **Compatibilidade:** Esta configuração é específica para Banana Pi M4 Zero com H618

5. **Backup automático:** O script cria backup do DTB original em `/root/backup_dtb_*`

---

## 🐛 Troubleshooting

### WiFi não aparece após reboot:

1. **Verificar se MMC1 foi detectado:**
   ```bash
   dmesg | grep mmc1
   ```

2. **Verificar GPIO PG18:**
   ```bash
   cat /sys/kernel/debug/gpio
   ```

3. **Verificar se firmware foi carregado:**
   ```bash
   dmesg | grep -i "Direct firmware load"
   ```

4. **Forçar reload do módulo:**
   ```bash
   modprobe -r brcmfmac
   modprobe brcmfmac
   dmesg | tail -30
   ```

5. **Verificar reguladores:**
   ```bash
   cat /sys/class/regulator/*/name
   cat /sys/class/regulator/*/microvolts
   ```

---

## 📦 Arquivos Criados

- `sun50i-h618-bananapi-m4-zero.dts_6.1` - DTS modificado
- `compila_instala_dtb_wifi.sh` - Script de instalação
- `WIFI_INTEGRACAO.md` - Esta documentação

---

## 🎯 Status Final

✅ Pinctrl WiFi clock configurado  
✅ SDIO/MMC1 habilitado para WiFi  
✅ Regulador 1.8V adicionado  
✅ Power sequence configurado  
✅ Device tree WiFi definido  
✅ Script de compilação e instalação pronto  

**Pronto para teste!** 🚀
