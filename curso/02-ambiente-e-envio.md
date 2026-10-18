# Módulo 2 — Preparando o computador, mandando e rodando programas

**Objetivo:** ter tudo instalado no computador, saber mandar um programa para o robô, rodá-lo pelo
menu ou pelo terminal e ver o que ele imprimiu.

## 2.1 No seu computador

1. **Python 3.11 ou mais novo** (python.org; no Windows marque "Add Python to PATH"). Versões
   antigas no Windows deixam o simulador lento.
2. **VS Code** com a extensão Python.
3. As bibliotecas dos simuladores (o Pillow é o que desenha a tela OLED, como no robô):
   ```bash
   pip install pygame pymunk numpy pillow
   ```
4. As pastas do projeto do brick (`bananaPiM4Zero/`): `libs/`, `exemplos/`, `simuladorLine/`,
   `simuladorMaze/`, `curso/` (este curso).

Teste o simulador:
```bash
cd simuladorLine
python simulador.py
```
Clique em **▶ Iniciar rodada**: o robô de exemplo começa a seguir a linha. (O
[módulo 11](11-simulador-line.md) explica a janela toda.)

## 2.2 A pasta de um projeto

Cada programa do robô é **uma pasta** com um `main.py`. A pasta precisa ter **as bibliotecas que o
programa usa** (por enquanto o robô não tem as libs instaladas no sistema):

```
meuSeguidor/
├── main.py                 ← o programa (é ele que o menu roda)
├── robo.py                 ← seus módulos (opcional)
├── motores.py              ← cópias das libs usadas (de bananaPiM4Zero/libs/)
├── portas.py
├── sensorCorReflexao.py    ← a V2! (exemplos/11-sensorCorReflexaoV2/)
├── giroscopio.py
├── simdebug.py             ← de simuladorLine/robo_real/ (no robô não faz nada)
├── envia.bat  ou envia.ps1 ← manda a pasta para o robô
└── executa.sh              ← (opcional) roda pelo terminal
```

* Copie **todas** as libs que o programa importa — e as que elas importam (quase todas usam
  `portas.py`).
* No simulador você pode rodar o mesmo `main.py`: ele usa as libs da pasta do programa e, se faltar
  alguma, a cópia `libs_mariola/` dele.

## 2.3 Conectando no robô

1. Ligue o robô e espere o menu aparecer na tela. A **primeira linha mostra o IP** e a temperatura
   da CPU (ex.: `192.168.2.151 48°C`).
2. O computador precisa estar na **mesma rede** (mesmo Wi-Fi).
3. Teste no terminal (PowerShell ou Linux):
   ```bash
   ssh banana@192.168.2.151
   ```
4. Para não digitar senha toda vez, configure a **chave SSH** (passo a passo no `README.md` do
   brick: `ssh-keygen` no PC e a chave pública em `~/.ssh/authorized_keys` no robô).

Usuário: `banana`. Os projetos ficam em `/home/banana/<nome-da-pasta>/`.

## 2.4 Mandando o programa

### Com o `envia.bat` (simples)
Copie `exemplos/01-olamundo/envia.bat` para a pasta do projeto e **troque o IP** na linha
`set IP=...`. Rodando ele (duplo clique ou `.\envia.bat` no terminal do VS Code):

1. copia **tudo** da pasta para `~/<nome-da-pasta>` no robô (`scp -r`);
2. encerra o `main.py` que estiver rodando (`killall main.py`).

O nome da pasta no robô é o mesmo da pasta no PC.

### Com o `envia.ps1` (mais rápido)
`exemplos/10-expansaoMotor/envia.ps1` manda **só os arquivos que mudaram** desde o último envio
(guarda as datas no arquivo `.manifest`), empacotando vários num `.tar.gz`. Troque o `$IP` no
começo. Rode com:
```powershell
powershell -ExecutionPolicy Bypass -File envia.ps1
```
* Na **primeira vez**, crie a pasta no robô: `ssh banana@IP "mkdir -p ~/meuSeguidor"`.
* Ele manda só os arquivos da pasta (não as subpastas).
* No fim ele encerra **qualquer** `python3` rodando no robô.

## 2.5 Rodando o programa

### Pelo menu (como na competição)
O **menu principal** (`menuPrincipal/`, iniciado como serviço no boot) lista as pastas de
`/home/banana` que têm `main.py`:

| Tecla | Faz |
|---|---|
| ↑ / ↓ (CIMA / BAIXO) | escolhe o programa |
| ENTER | roda o programa escolhido |
| VOLTAR | volta para a lista |
| VOLTAR segurado 2 s | menu Desligar / Reiniciar / Wi-Fi off / Wi-Fi on / Desbloquear / Iniciar X |

* Se a pasta tiver um **`main.sh`**, o menu roda ele em vez do `main.py` (útil para passar opções
  ao Python).
* O programa roda **sem terminal**: o que ele imprime vai para **`/home/banana/logs/NNNNNN.log`**
  e os erros para **`NNNNNN_erro.log`** (um número novo a cada execução).
* Enquanto o seu programa roda, o menu espera. Quando ele termina, o menu volta.

> **Dois cuidados quando o programa é iniciado pelo menu:**
>
> 1. **A pasta atual é `/home/banana`, não a do projeto.** Um arquivo aberto com nome simples
>    (`open('cores.json')`) vai parar em `/home/banana/cores.json`. Monte o caminho a partir do
>    próprio programa:
>    ```python
>    import os
>    PASTA = os.path.dirname(os.path.abspath(__file__))
>    ARQUIVO_CORES = os.path.join(PASTA, 'cores.json')
>    ```
> 2. **A saída vai para um arquivo e o Python a guarda em blocos** (só grava de tempos em tempos).
>    Para o log sair na hora, ponha no começo do `main.py`:
>    ```python
>    import sys
>    sys.stdout.reconfigure(line_buffering=True)
>    ```
>    ou crie um `main.sh` com `python3 -u /home/banana/meuSeguidor/main.py`.

Para ver o log de outro computador enquanto o robô roda:
```bash
ssh banana@IP "tail -f \$(ls -t ~/logs/*.log | head -1)"
```

### Pelo terminal (para testar)
```bash
ssh banana@IP
cd ~/meuSeguidor
python3 -u main.py
```
(O `executa.sh` dos exemplos faz isso.) `Ctrl+C` interrompe o programa: o Python gera um
`KeyboardInterrupt`, e o seu `try/finally` para os motores (veja o [módulo 3](03-primeiro-programa.md)).

O `.bashrc` do robô já ativa o ambiente Python (`meu_venv`). Se instalar algo com `pip`, ative
antes: `source ~/meu_venv/bin/activate`.

## 2.6 A partição somente leitura

Para o cartão SD não corromper quando a bateria é tirada com o robô ligado, a **partição do
sistema** pode estar montada **somente leitura**. A pasta `/home/banana` fica em outra partição e
continua gravável: seus projetos, logs e arquivos de calibração funcionam normalmente.

Para instalar pacotes (`apt`, `pip` no sistema), libere antes: menu → **Desbloquear** (ou
`sudo mount -o remount,rw /dev/mmcblk2p1 /`). Reiniciando, volta a ser somente leitura.

## 2.7 Outras formas de mexer nos arquivos do robô

* **Samba:** o brick pode compartilhar a pasta do usuário na rede (abre no Windows Explorer como
  `\\IP\home`). Configuração no `README.md` do brick.
* **VS Code Remote-SSH:** abre a pasta do robô direto no VS Code (bom para ajustes rápidos no
  campo; lembre de trazer as mudanças de volta para o PC).

## Checklist

- [ ] O simulador abre e o exemplo roda.
- [ ] `ssh banana@IP` entra sem senha.
- [ ] O `envia` manda a pasta e o projeto aparece no menu do robô.
- [ ] Você achou o log da última execução em `~/logs/`.

## Exercício

Mande o projeto `codigos/01_ola_mariola/` (copie as libs `motores.py` e `portas.py` para dentro
dele), rode pelo menu e encontre a saída dele no log.
