# Programas dos tutoriais

Todos foram testados nos simuladores (sem janela, 4x). O comentário do começo de cada arquivo diz
o simulador, o robô e o mapa. Rode de dentro da pasta do simulador:

```bash
cd simuladorLine     # ou simuladorMaze
python simulador.py --programa ../curso/codigos/PASTA/ARQUIVO.py [--robo ...] [--mapa ...]
```

| Pasta / arquivo | Módulo | Simulador, robô, mapa | O que faz |
|---|---|---|---|
| `01_ola_mariola/main.py` | 3 | Line, `robo_esteira.json` | LEDs, anda 1,5 s, lê encoders, para no `finally` |
| `01_ola_mariola/threads.py` | 3 | qualquer um (não usa hardware) | o que é uma thread: um contador que sobe "ao lado" do programa |
| `02_motores/anda_mm.py` | 4 | Line, `robo_esteira.json` | anda 300 mm e volta 150 mm pelo encoder |
| `02_motores/move_motor_angulo.py` | 4 | Line, `robo_esteira.json` | `move_motores` e a armadilha da velocidade guardada |
| `02_motores/tracao_4x4.py` | 4 | Line, `robo_4x4.json` | Mariola + 2 placas de motor; encoder ×2 × ×4 |
| `03_giroscopio/gira_e_anda_reto.py` | 5 | Line, `robo_esteira.json` | quadrado com giro proporcional e alvo acumulado |
| `04_linha/le_sensor.py` | 6 | Line | mostra IR, RGBC e cores |
| `04_linha/seguidor_liga_desliga.py` | 6 | Line, `robo_esteira.json`, `curso_pista.json` | seguidor de 2 estados (balança, perde a linha) |
| `04_linha/seguidor_p.py` | 6 | Line, `robo_esteira.json`, `curso_pista.json` | seguidor PD; para na fita vermelha |
| `05_distancia/le_distancias.py` | 7 | Line ou Maze | 3 VL53, leitura simples × rápida |
| `05_distancia/para_na_parede.py` | 7 | Maze | para a 80 mm da parede |
| `05_distancia/thread_sensores.py` | 7 | Line, `robo_4x4.json` | thread só para os sensores I2C (4 VL53 + 2 TCS, TCS no meio da espera); compara os 3 jeitos de ler |
| `06_interface/botao_e_cronometro.py` | 8 | Maze | botão de início, anda até o para-choque |
| `06_interface/menu_teclado.py` | 8 | Line ou Maze | menu na tela OLED com o teclado (clique ou F1–F4) e os LEDs |
| `07_servos/busca_servos.py` | 9 | Line, `robo_4x4.json` | lista os servos do barramento |
| `07_servos/testa_garra.py` | 9 | Line, `robo_4x4.json` | move braço e dedos esperando cada movimento |
| `08_camera/procura_vitima.py` | 10 | Line, `robo_4x4.json`, `curso_area.json` | acha uma vítima pela câmera e chega perto |
| `09_maze/mao_direita.py` | 16 | Maze | explora pela regra da mão direita, trata preto e azul |

Mapas do curso: `../mapas/` (também em `simuladorLine/mapas/`).

**No robô real:** copie para a pasta do programa as bibliotecas que ele importa (de
`bananaPiM4Zero/libs/`; o `sensorCorReflexao.py` da V2) e, se usar, `simdebug.py`/`visao.py` de
`simuladorLine/robo_real/`.
