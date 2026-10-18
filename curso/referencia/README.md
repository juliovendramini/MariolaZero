# Referência das bibliotecas do Mariola

Cada página explica **todos os métodos** da biblioteca, **para que** cada um serve, **quando**
usar e os **cuidados** que evitam horas de depuração. Os tutoriais (módulos 3 a 10) mostram as
mesmas bibliotecas sendo usadas passo a passo.

## Por biblioteca

| Biblioteca | Página | Liga em |
|---|---|---|
| `portas.py` — `Portas` | [portas](portas.md) | — (nomes das portas) |
| `motores.py` — `Motores` | [motores](motores.md) | interno (placa do Mariola) |
| `placaControleMotor.py` — `PlacaControleMotor` | [placaControleMotor](placaControleMotor.md) | SERIAL (barramento) |
| `placaControleServo.py` — `PlacaControleServo` | [placaControleServo](placaControleServo.md) | SERIAL (barramento) |
| `giroscopio.py` — `Giroscopio` | [giroscopio](giroscopio.md) | SERIAL |
| `sensorCorReflexao.py` (V2) — `CorReflexao` | [sensorCorReflexao](sensorCorReflexao.md) | SERIAL |
| `vl53.py` — `VL53L0X` | [vl53](vl53.md) | I2C |
| `tcs34725.py` — `TCS34725` | [tcs34725](tcs34725.md) | I2C |
| `bno085.py` — `BNO085` | [bno085](bno085.md) | I2C |
| `placaMuxVl53l0x.py`, `placaMuxTCS34725.py` | [placasMux](placasMux.md) | SERIAL |
| `botoes.py` — `Botoes` | [botoes](botoes.md) | PINOS DIGITAIS |
| `pinosDigitais.py` — `PinosDigitais` | [pinosDigitais](pinosDigitais.md) | PINOS DIGITAIS |
| `teclado.py`, `tela.py` | [teclado-tela](teclado-tela.md) | TECLADO, TELA |
| `cronometro.py` — `Cronometro` | [cronometro](cronometro.md) | — |
| Lidar, controle Bluetooth, câmera | [extras](extras.md) | SERIAL, USB |
| `simdebug`, `visao`, `deteccaoVitimas`, `dispensadorKits` | [modulos-simulador](modulos-simulador.md) | — |

## Por tarefa: "eu quero..."

| Quero... | Use |
|---|---|
| andar, girar, controlar a velocidade das rodas | `Motores.velocidade_motores` (+ `PlacaControleMotor.velocidade_motor` no 4x4) |
| andar uma distância certa | encoder: `Motores.estado()` + `angulo_motor()`, ou `move_motores` |
| girar 90° certinho / andar reto | `Giroscopio.le_angulo_z()` |
| saber se estou numa rampa | `Giroscopio.le_angulo_x()` |
| seguir a linha | `CorReflexao.le_reflexao()` |
| ver o verde / o vermelho / o prata no chão | `CorReflexao.cores()` (+ confirmar no `le_rgbc`) |
| saber a cor do piso na Maze | `CorReflexao.cor_piso()` |
| ver obstáculo / parede | `VL53L0X` (frente, lados), `Botoes` (para-choque) |
| ver a cor de uma parede / triângulo | `TCS34725` horizontal |
| mover a garra e saber se chegou | `PlacaControleServo.move_servo` + `consulta_posicao` |
| achar as vítimas | `visao.Visao().vitimas()` (Line), `DeteccaoVitimas` (Maze) |
| esperar o botão de início | `Botoes.botao_pressionado(Botoes.P3)` |
| mostrar algo no robô | LEDs (`Motores.set_led_rgb_*`), `Tela`, LEDs do `Teclado` |
| escolher um modo sem computador | `Teclado` + `Tela` |
| medir tempo / lembrar o tempo após reiniciar | `Cronometro` (com arquivo) |
| ver no simulador o que o programa pensa | `simdebug` |

## Regras que valem para todas

1. **Crie cada objeto uma vez**, no começo, e reaproveite. Cada criação abre porta, reinicia
   sensor, cria thread.
2. **Copie as libs para a pasta do projeto.** O programa importa `from motores import Motores`:
   o arquivo tem que estar ao lado do `main.py` no robô. No simulador, se não estiver, ele usa a
   cópia `libs_mariola/`.
3. **Os sensores na serial têm thread**: a leitura é instantânea, devolve o último valor. Os
   sensores I2C (VL53, TCS, BNO085) leem **quando você chama** e demoram.
4. **5 segundos sem comando** e o Mariola e as placas desligam os motores (o Mariola também apaga
   os LEDs). Espere em laço, mandando comando.
5. **Pare tudo no `finally`**, para o robô não sair andando se o programa der erro.
