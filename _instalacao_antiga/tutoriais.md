# Tutoriais
Verificando a partição e corrigindo erros caso o brick não queira iniciar mais:
 * Vamos precisar para isso do cabo serial
 * Precisamos inicar o brick com o terminal serial de debug, para conectar lembre-se que a velocidade serial é 115200.
 * Assim que o log de boot começar aparecer, fique precisando alguma tecla para entrar no u-boot.
 * Após entrar no u-boot, cole em ordem os seguintes comando. Cole e Dê enter duas vezes em cada comando (as vezes o terminal fica bugado)
   - ext4load mmc 1:1 0x42000000 /boot/Image
   - ext4load mmc 1:1 0x47000000 /boot/dtb-6.6.75-current-sunxi64/allwinner/sun50i-h618-bananapi-m4-zero.dtb
   - ext4load mmc 1:1 0x60000000 /boot/uInitrd-6.6.75-current-sunxi64
   - booti 0x42000000 0x60000000 0x47000000
   - fsck.ext4 -f -p /dev/mmcblk1p1
 * Após executar corretamente todos os comando, desligue o brick e liguei novamente. Agora, se tudo der certo, ele deve iniciar novamente.


## Verificar e Corrigir a Partição /home (/dev/mmcblk2p2)

Quando a partição /home está com problemas, use o modo rescue para poder desmontá-la com segurança e executar o fsck.

### Passo a Passo:

1. **Entrar em modo rescue:**
   ```bash
   systemctl rescue
   ```
   O sistema pedirá a senha de root e entrará no modo de manutenção.

2. **Desmontar a partição /home:**
   ```bash
   umount /home
   ```

3. **Executar o fsck na partição /dev/mmcblk2p2:**
   ```bash
   fsck.ext4 -f -p /dev/mmcblk2p2
   ```
   
   Opções:
   - `-f`: força verificação mesmo que o sistema de arquivos pareça limpo
   - `-p`: corrige automaticamente problemas que podem ser corrigidos com segurança

4. **Remontar a partição /home:**
   ```bash
   reboot
   ```

5. **O sistema deve reinicar sem problemas**