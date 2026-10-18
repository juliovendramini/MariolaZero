# Módulo 12 — O simulador da Rescue Maze

**Objetivo:** usar o simulador da Maze: rodar o programa, entender câmeras, kits e LEDs de
vítima, editar labirintos e ler o placar.

Documentação completa: `simuladorMaze/README.md`. O funcionamento geral (programa em processo
separado, libs reais, `simdebug`, sem janela) é o mesmo do simulador da Line ([módulo 11](11-simulador-line.md)).

## 12.1 Rodando

Na pasta `simuladorMaze`:
```bash
python simulador.py                                              # exemplo, mapa exemplo1
python simulador.py --programa ../minhaMaze/main.py --mapa mapas/exemplo1.json
python simulador.py --programa ../minhaMaze/main.py --sem-janela --velocidade 4 --semente 1
```

Opções: `--robo`, `--mapa`, `--programa`, `--sem-janela`, `--velocidade`, `--semente N` (aqui o
padrão é **sortear**: passe uma semente para repetir a rodada), `--lop botao|reiniciar`, `--tempo`.

Como na Line, o relógio é **sincronizado** (veja o [módulo 11.6](11-simulador-line.md)): com a
mesma semente, a rodada sai igual em qualquer velocidade e em qualquer PC. Ponha um
`time.sleep(0.01)` no laço principal.

Para várias rodadas de uma vez e para os desafios M01–M06, use o `avalia.py` da mesma pasta
(`python avalia.py --programa ../minhaMaze/main.py --sementes 1-3`; veja o [módulo 18](18-desafios.md)).

## 12.2 A janela

Iguais à Line: **▶ Iniciar rodada** (F5), **■ Parar**, **↺ Nova rodada** (apaga também os arquivos
de checkpoint listados em `arquivos_rodada`), **LoP** (L), **Botão do robô** (B), **Auto-botão**,
**Pausar**, **Vel.**, arrastar/Q/E para reposicionar, a **tela e o teclado do brick** no canto do
mapa (botões com o mouse ou F1–F4; **O** esconde). Específicas da Maze:

| Tecla | Mostra |
|---|---|
| R | raios dos VL53 |
| T | trilha |
| C | campo de visão das câmeras |
| F | ladrilhos "flutuantes" (roxo) |

## 12.3 O robô da Maze (`robo.json`)

| Peça | Onde |
|---|---|
| Tração 4x4 | Mariola motores 1/2 (trás) + placas de motor IDs 8 e 51 (frente) na SERIAL1 |
| Giroscópio | SERIAL5 |
| Pro1616 | SERIAL6 — cor do piso (preto, prata, azul, vermelho) |
| 5 VL53 | I2C1 esq. frente, I2C2 esq. trás, I2C3 dir. frente, I2C4 dir. trás, I2C5 frente |
| Para-choque | P1 esquerdo, P2 direito |
| Botão de início | P3 |
| Câmeras | laterais (esquerda e direita) |
| LEDs do Mariola | 0–3 iluminação da câmera esquerda, 4–7 da direita, **8–9 sinal de vítima** |
| Kits | dispensador com lado esquerdo e direito |

## 12.4 Vítimas, LEDs e kits

```python
from deteccaoVitimas import DeteccaoVitimas
from dispensadorKits import DispensadorKits

cam = DeteccaoVitimas()
kits = DispensadorKits()

for v in cam.detecta_todas():          # [{'camera': 'esquerda', 'status': 'ferida', 'kits': 2, ...}]
    pisca_led_vitima(5)                # LEDs 8–9: 500 ms aceso / 500 ms apagado por 5 s, parado
    kits.deposita(v['kits'], v['camera'])
```

* A câmera só vê a vítima **de frente**, dentro do campo de visão e sem parede no meio.
* Com `exige_iluminacao`, **câmera com os LEDs apagados não enxerga**. Lembre: o Mariola apaga os
  LEDs após 5 s sem pacote (ex.: esperando o botão). Acenda a iluminação **depois** do botão.
* Só os LEDs 8–9 contam para o juiz como "sinal de vítima".
* No robô, as versões de `robo_real/` têm a mesma interface (complete a sua visão e o seu
  mecanismo de kits).

## 12.5 O juiz da Maze (regra 2026)

Pontua: identificação de vítima (piscar 5 s parado a até 15 cm; 5/15 letra, 10/30 cognitiva,
conforme a parede é ou não "linear"), kits (10 por 1, 30 por 2, só depois da identificação),
checkpoint (10), azul (30, −10 por revisita, LoP se não parar 5 s), lombada (5), escada (10),
identificação errada (−5), LoP no preto, bônus de confiabilidade e **bônus de saída** (piscar
1 s/1 s por 10 s no início). A rodada acaba em 8 min ou na saída.

## 12.6 Mapas e editor

Mapas em `mapas/*.json` (fáceis de editar na mão): `paredes_h`/`paredes_v` (strings de 0 e 1),
`ladrilhos` (piso preto/prata/azul/vermelho, terreno lombada/escada/detritos, zona), `vitimas`
(ladrilho, parede, posição, tipo).

O **editor** ("Editar mapa") faz tudo com o mouse, avisa vítima em posição proibida e ladrilho
inalcançável, e tem "Sortear pisos" (como o dado do juiz).

## 12.7 Diferenças em relação à Line

* As libs de reserva (`libs_mariola/`) do simulador da Maze são de antes de algumas atualizações
  (ex.: `giroscopio.py` sem o modo `ROS_IMU`). **Copie as libs atuais para a pasta do seu
  programa** e é elas que vão rodar.
* A Maze não tem câmera frontal (`visao`) nem garra.
* Não há rampas/pontes de verdade (escada e lombada são efeitos).

## Exercícios

1. Rode `codigos/09_maze/mao_direita.py` com `--semente 1` e assista. Onde ele perde tempo?
2. Edite o `exemplo1.json`: ponha um ladrilho azul onde o robô passa e confira os 30 pontos.
3. Faça um programa que só gira no lugar e imprime `cam.detecta()` com a iluminação apagada e
   acesa.
