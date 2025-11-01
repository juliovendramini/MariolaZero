# Configuração Final do Samba - Banana Pi M4 Zero

## ✅ CONFIGURAÇÃO APLICADA

### Estrutura do Sistema de Arquivos

```
/dev/mmcblk2p1  → /          (6.1GB) - Partição raiz (somente leitura no boot)
/dev/mmcblk2p2  → /home      (990MB) - Partição com escrita (rw,relatime)
/dev/zram1      → /var/log   (47MB)  - RAM comprimida para logs
```

### Compartilhamentos Samba

| Compartilhamento | Caminho | Descrição | Windows |
|-----------------|---------|-----------|---------|
| **dados** | `/home/samba-data` | **USE ESTE!** Partição com escrita | `\\192.168.2.167\dados` |
| home | `/home/banana` | Home do usuário banana | `\\192.168.2.167\home` |

### Acesso

- **Usuário:** `banana`
- **Senha:** (vazio - apenas pressione Enter)
- **Modo:** Guest (acesso público sem autenticação)

---

## 📁 ONDE SALVAR ARQUIVOS

### ✅ CORRETO: Use o compartilhamento `dados`

```
\\192.168.2.167\dados
```

- Aponta para `/home/samba-data`
- Está na partição `/home` que tem escrita
- **Arquivos persistem após reinicialização**
- Permissões totalmente abertas (777)

### ⚠️ LIMITADO: Compartilhamento `home`

```
\\192.168.2.167\home
```

- Aponta para `/home/banana`
- Também está na partição com escrita
- Mais espaço disponível (~900MB)

---

## 🔧 CONFIGURAÇÃO TÉCNICA

### Arquivo: `/etc/samba/smb.conf`

```ini
[global]
   workgroup = WORKGROUP
   server string = Banana Pi M4 Zero
   netbios name = BANANAPI
   
   # Autenticação guest
   security = user
   map to guest = Bad User
   guest account = banana
   
   # Protocolos antigos (compatibilidade Windows)
   client min protocol = CORE
   server min protocol = NT1
   
   # Sem restrições Unix
   unix extensions = no
   follow symlinks = yes
   
   # Logs em RAM (zram)
   log level = 2
   log file = /var/log/samba/log.%m
   max log size = 1000

[dados]
   comment = Dados (Partição com Escrita)
   path = /home/samba-data
   browseable = yes
   public = yes
   guest ok = yes
   guest only = yes
   read only = no
   writable = yes
   create mask = 0777
   directory mask = 0777
   force create mode = 0777
   force directory mode = 0777
   force user = banana
   force group = banana

[home]
   comment = Home Banana
   path = /home/banana
   browseable = yes
   public = yes
   guest ok = yes
   guest only = yes
   read only = no
   writable = yes
   create mask = 0777
   directory mask = 0777
   force create mode = 0777
   force directory mode = 0777
   force user = banana
   force group = banana
```

### Permissões

```bash
/home/samba-data
├── Ownership: banana:banana
├── Permissões: 777 (rwxrwxrwx)
└── Estrutura:
    ├── cache/      # Cache do Samba
    ├── private/    # Banco de dados de senhas
    ├── lock/       # Arquivos de lock
    ├── registry/   # Registry do Samba
    ├── run/        # Runtime
    └── log/        # Logs do samba-fix
```

---

## 🚀 SERVIÇO DE INICIALIZAÇÃO AUTOMÁTICA

### Serviço: `samba-fix.service`

**O que faz:**
1. Aguarda rede e sistema de arquivos
2. Cria estrutura em `/home/samba-data` se não existir
3. Recria links simbólicos necessários
4. Garante que usuário Samba `banana` existe
5. Ajusta permissões
6. Reinicia serviços do Samba

**Arquivo:** `/etc/systemd/system/samba-fix.service`

```ini
[Unit]
Description=Samba Fix Service - Sistema com Partição RO
After=network-online.target local-fs.target smbd.service nmbd.service
Wants=network-online.target
Before=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/samba-fix-ro.sh
RemainAfterExit=yes
StandardOutput=journal
StandardError=journal
TimeoutStartSec=60

[Install]
WantedBy=multi-user.target
```

**Script:** `/usr/local/bin/samba-fix-ro.sh`

### Comandos Úteis

```bash
# Ver status do serviço
systemctl status samba-fix

# Ver logs do serviço
journalctl -u samba-fix

# Ver histórico de execuções
cat /home/samba-data/log/samba-fix.log

# Executar manualmente
sudo systemctl start samba-fix

# Ver status do Samba
systemctl status smbd nmbd
```

---

## 🔄 APÓS REINICIALIZAÇÃO

### O que acontece automaticamente:

1. **Sistema inicia** com partição raiz em modo RO
2. **Serviço `samba-fix`** é executado automaticamente
3. **Estrutura `/home/samba-data`** é verificada/criada
4. **Links simbólicos** são recriados
5. **Usuário Samba** é verificado/recriado
6. **Serviços** smbd e nmbd são reiniciados
7. **Compartilhamentos** ficam disponíveis

### Teste após reboot:

```powershell
# No Windows PowerShell
Test-NetConnection -ComputerName 192.168.2.167 -Port 445

# Acessar compartilhamento
explorer.exe \\192.168.2.167\dados
```

---

## 🛠️ SOLUÇÃO DE PROBLEMAS

### Samba não inicia após reboot

```bash
# Verificar serviço samba-fix
sudo systemctl status samba-fix

# Verificar logs
sudo journalctl -u samba-fix -n 50

# Executar manualmente
sudo /usr/local/bin/samba-fix-ro.sh

# Reiniciar Samba
sudo systemctl restart smbd nmbd
```

### Windows pede usuário/senha

**Solução 1:** Limpar credenciais antigas

```powershell
# No Windows PowerShell
net use \\192.168.2.167\dados /delete
cmdkey /delete:192.168.2.167
```

**Solução 2:** Usar credenciais corretas

- Usuário: `banana`
- Senha: (deixar vazio, apenas pressionar Enter)

### Não consegue escrever arquivos

```bash
# No Banana Pi
sudo chown -R banana:banana /home/samba-data
sudo chmod -R 777 /home/samba-data
sudo systemctl restart smbd nmbd
```

### Verificar se partição está com escrita

```bash
# Ver montagem
mount | grep /home

# Deve mostrar:
# /dev/mmcblk2p2 on /home type ext4 (rw,relatime)
```

---

## 📊 ESPAÇO DISPONÍVEL

```bash
# Verificar espaço
df -h /home/samba-data

# Resultado esperado:
# /dev/mmcblk2p2  990M  86M  836M  10% /home
```

---

## ✅ RESUMO

- ✅ Samba configurado para funcionar com partição raiz RO
- ✅ Compartilhamento `dados` aponta para `/home/samba-data` (partição RW)
- ✅ Acesso guest sem senha (usuário: banana, senha: vazio)
- ✅ Serviço automático garante funcionamento após reboot
- ✅ Permissões 777 (total abertura)
- ✅ Compatível com Windows (protocolos antigos habilitados)

**USE:** `\\192.168.2.167\dados` para salvar seus arquivos!




********************
Perfeito! Agora tudo está configurado corretamente. Vou criar um resumo final:

✅ CONFIGURAÇÃO CONCLUÍDA!
🎯 O QUE FOI FEITO:
Identificado o problema: Partição raiz (/) é somente leitura no boot
Solução implementada: Compartilhamento dados apontando para /home/samba-data (partição com escrita)
Serviço automático criado: Garante que Samba funcione após cada reinicialização
Configuração testada: Ambos compartilhamentos funcionando
📁 COMPARTILHAMENTOS DISPONÍVEIS:
Compartilhamento	Caminho	Acesso Windows
✅ dados (USE ESTE!)	/home/samba-data	\\192.168.2.167\dados
home	/home/banana	\\192.168.2.167\home
🔑 ACESSO:
Usuário: banana
Senha: (vazio - apenas pressione Enter)
🚀 PRÓXIMOS PASSOS:
Teste no Windows:

Teste após reboot:

Aguarde ~30 segundos e teste novamente o acesso

📝 ARQUIVOS CRIADOS:
samba_configuracao_final.sh - Script de configuração
instala_servico_samba_ro.sh - Instalador do serviço automático
CONFIGURACAO_SAMBA_FINAL.md - Documentação completa