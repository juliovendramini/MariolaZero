# Onde está cada assunto da Maze

Caminhos a partir da raiz do repositório (a pasta em que o especialista roda). Brick, libs, envio, Linux e
sensores em geral: `.claude/skills/especialista-mariola/referencias/mapa.md`.

## Projeto e estratégia

| assunto | onde |
|---|---|
| a Maze em resumo, ações básicas, mão direita, explorador com mapa + BFS, detalhes que fazem diferença | `curso/16-projeto-rescue-maze.md` |
| tutorial da mão direita (código pronto do curso) | `curso/codigos/09_maze/mao_direita.py` |
| organizar o código em módulos, máquina de estados | `curso/13-organizando-o-codigo.md` |
| sensores de distância: várias leituras, thread do I2C, parar a 8 cm, seguir parede, ângulo da parede com 2 sensores, limites | `curso/07-sensores-de-distancia.md`, `curso/referencia/vl53.md`, `curso/referencia/placasMux.md` |
| giroscópio (alvo acumulado, sinal), giro de 90° | `curso/05-giroscopio.md`, `curso/referencia/giroscopio.md` |
| encoder, andar 1 ladrilho, placas de motor | `curso/04-motores-e-encoders.md`, `curso/referencia/motores.md`, `curso/referencia/placaControleMotor.md` |
| cor do piso (preto, azul, prata, vermelho), aprender as cores no campo | `curso/06-sensor-de-linha.md`, `curso/referencia/sensorCorReflexao.md`, `documentação/CorReflexaoV2.md`, `simuladorMaze/exemplo_aluno/calibra_cores.py` |
| para-choque e botão de início | `curso/08-botoes-tela-teclado.md`, `curso/referencia/pinosDigitais.md` |
| câmera e visão (vítimas no robô real) | `curso/10-camera-e-visao.md`, `exemplos/camera/` |
| do simulador para o robô, checklist do dia da competição | `curso/17-do-simulador-para-o-robo.md` |
| regras 2026 em resumo | `referencias/regras.md` desta skill, `simuladorMaze/README.md` "Juiz (regra 2026)", `curso/12-simulador-maze.md` 12.5 |

## O programa de exemplo (`simuladorMaze/exemplo_aluno/`)

| arquivo | o que tem |
|---|---|
| `robo.py` | hardware e movimentos: `anda_mm()` (encoder + giroscópio, centraliza pelos VL53 laterais, para pela parede da frente), `gira()`/`gira_para()` (pelo giroscópio, alvo acumulado), `encosta_na_frente()` (alinha no para-choque), `alinha_parede_lateral()`, `piso()`, `preto_na_frente()`, `espera()` (manda comando a cada 0,5 s), `espera_botao()`, `pisca()`, `ilumina_cameras()`. Constantes: `LADRILHO = 300`, `FOLGA_FRENTE`, `LATERAL_CENTRO`, `CONTAGENS_POR_VOLTA`, LEDs 0-3/4-7 câmeras, 8-9 vítima |
| `navegacao.py` | `Mapa` (`set_parede`, `bloqueado`, `fronteira`, `caminho` = BFS), direções 0 frente, 1 esquerda, 2 trás, 3 direita; `salva_checkpoint`/`carrega_checkpoint` (`checkpoint_maze.json`, escrita atômica) |
| `main.py` | estratégia: piso, paredes, vítimas e kits a cada ladrilho; vizinho não visitado ou BFS até a fronteira; `TEMPO_VOLTAR = 6,5 min` e volta ao início; evita a zona de perigo |
| `calibra_cores.py` | aprende e grava as cores do piso (`cores_piso.json`) |

É um ponto de partida, não a solução (o README diz isso).

## Simulador (`simuladorMaze/`)

| assunto | onde |
|---|---|
| instalar, rodar, linha de comando (`--programa`, `--mapa`, `--robo`, `--semente`, `--sem-janela`, `--velocidade`, `--lop`), botões e teclas da janela | `simuladorMaze/README.md` "Uso rápido" e "Na janela", `curso/12-simulador-maze.md` |
| relógio sincronizado (mesma semente = mesma rodada; laço sem `sleep` trava) | `simuladorMaze/README.md` "Relógio sincronizado" |
| `input()` como pausa | `simuladorMaze/README.md` |
| desafios M01-M06, `avalia.py`, labirinto surpresa | `simuladorMaze/README.md`, `curso/18-desafios.md` 18.3 e 18.4, `simuladorMaze/desafios/desafios.json` |
| câmera e kits no simulador (`DeteccaoVitimas`, `DispensadorKits`), `simdebug` (pose estimada), LEDs | `simuladorMaze/README.md` "O que só existe no simulador", `curso/12-simulador-maze.md` 12.4, `curso/referencia/modulos-simulador.md`, `simuladorMaze/robo_real/` (os modelos para o robô) |
| física e sensores (patinação, giroscópio, VL53 em leque, para-choque, terreno, rampa e escada) | `simuladorMaze/README.md` "Física e sensores" |
| firmware emulado (timeout de 5 s, giro por ângulo, placa de motor, Pro1616) | `simuladorMaze/README.md` "Firmware emulado" |
| mapas (formato JSON) e editor | `simuladorMaze/README.md` "Mapas", `curso/12-simulador-maze.md` 12.6; mapas em `simuladorMaze/mapas/` (`exemplo1.json`, `treino.json`, `rampa_escada.json`) |
| `robo.json` (o que é cada chave, como calibrar) | `simuladorMaze/README.md` "Configuração do robô", `curso/12-simulador-maze.md` 12.3, `curso/17-do-simulador-para-o-robo.md` 17.3 |
| limitações (o que o simulador não faz) | `simuladorMaze/README.md` "Limitações conhecidas" |
| detalhes internos (decisões, números de teste) | `simuladorMaze/CLAUDE.md` |

## O robô da equipe Maze 2026

* `simuladorMaze/robo_maze2026.json`: ligado como no código da equipe (branch `adaptacao-claude` de
  05/11/2026). Tabela da ligação em `simuladorMaze/README.md` "Robô da equipe Maze 2026": motores (Mariola
  canal 1 invertido e 2; placas id 72 à esquerda e 5 invertida à direita no `SERIAL2` a 250000),
  giroscópio no `SERIAL4` diminuindo para a direita, Pro1616 no `SERIAL6`, 5 VL53 (`I2C1`, `I2C3`, `I2C6`,
  `I2C7`, `I2C8`), para-choque P1/P8, 440 contagens por volta no Mariola (880 na placa).
* Rodar o programa da equipe: `python simulador.py --robo robo_maze2026.json --programa CAMINHO/main.py`
  (pasta `simuladorMaze`). Sem câmera USB o `main.py` da equipe cai na primeira procura de vítima: no
  simulador é preciso trocar a detecção de vítimas por um falso (ou usar `DeteccaoVitimas`).
* O código da equipe não está neste repositório. No bot da Maze há uma cópia do repositório dela, atualizada
  a cada 5 min (o pedido diz a pasta e o arquivo `_RAMOS.txt` com o ramo e os últimos commits). Use para
  entender a pergunta e diga de que ramo/commit é o que leu; o que o aluno mandar na conversa pode ser mais
  novo. As regras com os alunos continuam: apontar o erro e o caminho, não reescrever o programa deles.
