# `PlacaControleMotor` — placas de motor extras (barramento de um fio)

Arquivo: `libs/placaControleMotor.py` · `from placaControleMotor import PlacaControleMotor`

## Para que serve

Cada **placa de controle de motor** (ATtiny1616) controla **um** motor com encoder: PID de
velocidade, giro por ângulo, freio que segura a posição. Várias placas ficam penduradas no
**mesmo fio serial** (barramento *half-duplex one-wire*), cada uma com um **ID** gravado.

Uso típico: o robô 4x4 — os 2 motores traseiros no Mariola e os 2 dianteiros em placas na SERIAL1.

## Como funciona o barramento

* Todas as placas recebem todos os pacotes; só responde a que tem o **ID** do pacote.
* Pacote de comando: 6 bytes `[ID, modo, valor, giro_alto, giro_baixo, CRC]`. Resposta: 8 bytes
  `[ID, modo, estado, pulsos(4 bytes), CRC]`. O CRC é o XOR dos bytes.
* Como o fio é um só, o Banana Pi **ouve o próprio pacote** (eco). A lib descarta o eco e lê a
  resposta. Se o CRC não bate, tenta de novo (3 tentativas) e devolve `None` se não conseguiu.
* **Os servos inteligentes podem ficar no mesmo barramento** (IDs diferentes!).

**Segurança da placa:** 5 s sem nenhum pacote para ela → motor para. 10 s → o *watchdog* reinicia
a placa e **a contagem do encoder volta a 0**. Reenvie o comando sempre (no laço de controle isso
acontece naturalmente).

**Encoder em quadratura (×4):** a placa conta as 4 bordas dos 2 canais. O mesmo motor dá **o dobro
de contagens** do que no Mariola (que conta ×2).

## Criando o objeto

### `PlacaControleMotor(objeto_porta_serial, id_equipamento)`
Recebe a **porta já aberta** (não o número da porta!) e o ID.

```python
from portas import Portas
barramento = Portas().abre_porta_serial(Portas.SERIAL1, 250000, timeout=0.005)
frente_esq = PlacaControleMotor(barramento, 8)
frente_dir = PlacaControleMotor(barramento, 51)
frente_esq.reset()
frente_dir.reset()
frente_dir.direcao_motor(PlacaControleMotor.INVERTIDO)
```

* Abra a porta **uma vez** e passe o mesmo objeto para todas as placas.
* `timeout=0.005` deixa o laço rápido (a resposta chega em ~1 ms).

## Constantes

`NORMAL`/`INVERTIDO` (direção), `FREIO_BREAK`/`FREIO_TRAVADO` (freio), `PARADO`,
`GIRANDO_NORMAL`, `GIRANDO_INVERTIDO` (estado), `DEBUG`, e os `MODO_*` do protocolo (uso interno).

## Métodos do dia a dia

Quase todos devolvem um `dict` `{'id', 'modo', 'estado', 'pulsos'}` com a resposta, ou `None` se
a placa não respondeu.

### `direcao_motor(direcao)`
`NORMAL` ou `INVERTIDO`. Só muda a lib (inverte o sinal do que você manda e do que lê).

### `velocidade_motor(velocidade)`
Velocidade com PID (-100 a 100), contínua. Mesma escala do Mariola (100 = calibração).

* **Quando usar:** no laço de controle, junto com `Motores.velocidade_motores`, para as 4 rodas
  andarem juntas.

### `move_motor(velocidade, angulo)`
Gira `angulo` contagens (0 a 65535) e para. **Diferente do Mariola: `angulo` 0 cancela o alvo**
(gira sem parar).

### `potencia_motor(potencia)`
PWM direto (-100 a 100), sem PID.

### `para_motor()`
Velocidade 0 (com PID: o motor freia ativamente).

### `angulo_motor()`
Contagens desde o último `reseta_angulo_motor()`, com o sinal da direção. **Faz uma transação na
serial** (pergunta para a placa). Devolve 0 se falhou.

### `reseta_angulo_motor()`
Lê a contagem atual e passa a contar a partir dela.

### `estado_motor()`
`PARADO`, `GIRANDO_NORMAL` ou `GIRANDO_INVERTIDO` (pergunta para a placa).

### `le_pulsos()` / `atualizar()`
Contagem absoluta (sem desconto) / a resposta completa, sem mudar o comando.

### `set_freio(modo_freio)` · `set_modo_freio(modo)`
`FREIO_BREAK` (solta) ou `FREIO_TRAVADO` (parado, a placa segura a posição com um PD de posição).
Ajuste o freio travado com `set_kp_freio`, `set_kd_freio` e `set_delta_freio` (zona morta, em
contagens).

### `reset()`
Reinicia a placa como se tivesse acabado de ligar: para, zera contadores, recarrega PID e
calibração da EEPROM. Também zera o desconto da lib.

* **Quando usar:** no começo do programa, para começar de um estado conhecido. Também serve para
  **testar se a placa está lá** (`None` = não respondeu).

## Ajuste e calibração (de vez em quando)

| Método | O que faz |
|---|---|
| `pid_motor(kp, ki, kd)` | grava as três constantes (×100) na EEPROM; `True` se todas confirmaram |
| `set_kp(v)`, `set_ki(v)`, `set_kd(v)` | uma constante de cada vez |
| `set_kp_freio(v)`, `set_kd_freio(v)`, `set_delta_freio(v)` | ajuste do freio travado |
| `calibrar()` | a placa gira o motor nos dois sentidos e mede a velocidade máxima (~12–14 s, **robô suspenso**). Devolve `{'giro_max_horario', 'giro_max_antihorario'}` |
| `calibracao_manual(horario, antihorario)` | grava a calibração sem medir (ex.: para igualar ao motor do Mariola) |
| `obter_calibracao()` | lê a calibração e se o encoder está ativo |

Sem calibração gravada, a placa trabalha em PWM direto (a "velocidade" vira potência).

## Para descobrir e configurar placas

### `PlacaControleMotor.buscar_motores(porta_serial, baud_rate=250000)` *(estático)*
Varre os IDs 0 a 255 e devolve a lista `[{'id', 'estado', 'pulsos'}, ...]`. Recebe o **número**
da porta (ex.: `Portas.SERIAL1`), abre e fecha sozinho. Demora alguns segundos.

* **Quando usar:** placa nova, ou "não sei o ID desta placa". Rode com nada mais usando a porta.

### `set_ignorar_retorno(ignorar)`
`True`: manda o comando e não espera resposta (mais rápido, mas você não sabe se chegou e não lê
o encoder).

### `envia_comando(modo, valor, giro=0, tentativas=3)`
O envio "cru". Os outros métodos usam este. Só use para experimentos com o protocolo.

## Erros comuns

| Sintoma | Causa provável |
|---|---|
| Tudo devolve `None` | ID errado, porta errada, baud diferente de 250000 ou placa sem energia |
| Rodas da frente e de trás andando diferente | calibração diferente: veja `obter_calibracao()` e `Motores.obtem_calibracao_motores()` (lembre do ×4 vs ×2) |
| Contagem volta para 0 sozinha | a placa ficou 10 s sem pacote e reiniciou |
| `PlacaControleMotor(Portas.SERIAL1, 8)` dá erro estranho | passou o número da porta: esta classe quer a porta **aberta** |

## No simulador

Emulado byte a byte (eco, CRC, quadratura ×4, giro 0 cancela, timeout 5 s, watchdog 10 s,
calibração). Quais IDs existem e em que roda estão: `motores` no `robo*.json`.
