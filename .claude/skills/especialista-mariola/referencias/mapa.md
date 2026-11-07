# Onde está cada assunto

Caminhos a partir da raiz do repositório (a pasta em que o especialista roda).

## Começando, envio e Linux do brick

| assunto | onde |
|---|---|
| visão geral do brick, conectores, portas | `curso/01-o-brick-mariola.md`, `documentação/Conectores.md`, `documentação/README.md` |
| preparar o PC, mandar o programa (envia.bat/.ps1/.sh, F5 e Ctrl+Shift+B do VS Code), SSH, chave, porta de debug serial, menu, logs, partição somente leitura | `curso/02-ambiente-e-envio.md` |
| primeiro programa, `try/finally`, regras de ouro | `curso/03-primeiro-programa.md` |
| organizar o código em módulos, máquina de estados | `curso/13-organizando-o-codigo.md` |
| levar do simulador para o robô (o que muda) | `curso/17-do-simulador-para-o-robo.md` |
| instalação do Linux do brick, rede, câmeras, áudio, recuperação, regravar a eMMC | `INSTALACAO.md` (grande: procure pela seção) |
| menu principal (como roda o programa, logs em `~/logs`) | `menuPrincipal/` (`telaMenu.py`), curso 2.5 |
| regravar o firmware do ATmega do brick | `firmware/mariola/LEIAME.md` |

## Bibliotecas (o código real está em `libs/`)

| lib | referência | curso | código |
|---|---|---|---|
| motores do brick (encoders, `Motores(True/False)`) | `curso/referencia/motores.md` | `04-motores-e-encoders.md` | `libs/motores.py` |
| placa de motor externa | `curso/referencia/placaControleMotor.md` | 04 | `libs/placaControleMotor.py` |
| servos inteligentes | `curso/referencia/placaControleServo.md` | `09-servos-inteligentes.md` | `libs/placaControleServo.py` |
| giroscópio serial | `curso/referencia/giroscopio.md`, `documentação/Giroscopio.md` | `05-giroscopio.md` | `libs/giroscopio.py` |
| BNO085 | `curso/referencia/bno085.md` | | |
| sensor de linha/cor Pro1616 (V2) | `curso/referencia/sensorCorReflexao.md`, `documentação/CorReflexaoV2.md` | `06-sensor-de-linha.md` | `exemplos/11-sensorCorReflexaoV2/` |
| TCS34725 avulso | `curso/referencia/tcs34725.md` | | |
| VL53L0X (distância), placas mux | `curso/referencia/vl53.md`, `curso/referencia/placasMux.md` | `07-sensores-de-distancia.md` | `libs/` |
| botões, pinos P1-P8 | `curso/referencia/pinosDigitais.md`, `curso/referencia/botoes.md` | `08-botoes-tela-teclado.md` | `libs/pinosDigitais.py` |
| tela OLED e teclado | `curso/referencia/teclado-tela.md` | 08 | `libs/tela.py`, `libs/teclado.py` |
| portas seriais (qual USB é qual) | `curso/referencia/portas.md`, `documentação/Portas.md` | | `libs/portas.py` |
| cronômetro | `curso/referencia/cronometro.md` | | `libs/cronometro.py` |
| LEDs, buzzer, outras | `curso/referencia/extras.md` | | `exemplos/07-leds`, `exemplos/13-buzzer` |
| câmera e visão (OpenCV) | | `10-camera-e-visao.md` | `exemplos/camera/` |
| índice das referências | `curso/referencia/README.md` | | |

Exemplos prontos, um por assunto: `exemplos/01-olamundo` a `exemplos/13-buzzer` e `exemplos/camera/`.

## Simuladores

| assunto | onde |
|---|---|
| Rescue Line: janela, robôs (`robo_*.json`), mapas, editor, juiz e pontuação 2026, linha de comando, limitações | `simuladorLine/README.md`, `curso/11-simulador-line.md` |
| Rescue Maze | `simuladorMaze/README.md`, `curso/12-simulador-maze.md` |
| RCB Challenge (CBR 2026) | `simuladorChallenge/README.md` |
| desafios e `avalia.py` | `curso/18-desafios.md`, `simuladorLine/desafios/`, `simuladorMaze/desafios/` |
| módulos só do simulador (simdebug, visão, vítimas, kits) | `curso/referencia/modulos-simulador.md` |
| brick Paçoca (programa `.ino`) no simulador | `simuladorLine/README.md` (procure Paçoca), `simuladorLine/pacoca/` |
| mapa a partir de foto de pista | `simuladorLine/ferramentas/MAPA_DA_FOTO.md` |
| detalhes internos (física, decisões) | `simuladorLine/CLAUDE.md`, `simuladorMaze/CLAUDE.md`, `simuladorChallenge/CLAUDE.md` |

## Projetos e regras da competição

| assunto | onde |
|---|---|
| Rescue Line: seguidor, verdes, gap, obstáculo, rampa, checkpoints e LoP | `curso/14-projeto-rescue-line.md` |
| área de resgate (regra 2026 em resumo, vítimas, triângulos) | `curso/15-projeto-area-de-resgate.md` |
| Rescue Maze (mão direita, vítimas, mapa) | `curso/16-projeto-rescue-maze.md` |
| como o juiz pontua (regra 2026) | `simuladorLine/README.md` "Juiz (regra 2026)", `simuladorMaze/README.md` "Juiz (regra 2026)", `simuladorChallenge/README.md` "O juiz" |
