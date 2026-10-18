# `Portas` — os nomes das portas do Mariola

Arquivo: `libs/portas.py` · `from portas import Portas`

## Para que serve

O Mariola tem conectores com nome escrito na caixa: **SERIAIS 1 a 6**, **I2C1 a I2C8**. No Linux
essas portas têm outros nomes (`/dev/ttyUSB2`, `/dev/ttyS4`, canal 3 do multiplexador I2C...).
A classe `Portas` faz a tradução: no programa você escreve o nome que está na caixa e a lib
descobre o resto.

Quase nunca você chama `Portas` diretamente. Você passa as **constantes** dela para as outras
bibliotecas:

```python
from portas import Portas
giro = Giroscopio(Portas.SERIAL5)     # sensor ligado no conector SERIAIS 5
frente = VL53L0X(Portas.I2C5)         # sensor ligado no conector I2C5
```

## Constantes

### Portas seriais

| Constante | Valor | Conector na caixa | No Linux |
|---|---|---|---|
| `Portas._SERIAL0` | 0 | (interna) placa do Mariola: motores, servos, LEDs | USB `usb-0:1.1` |
| `Portas.SERIAL1` | 1 | SERIAIS 1 | USB `usb-0:1.4` |
| `Portas.SERIAL2` | 2 | SERIAIS 2 | USB `usb-0:1.3` |
| `Portas.SERIAL3` | 3 | SERIAIS 3 | USB `usb-0:1.2` |
| `Portas.SERIAL4` | 4 | SERIAIS 4 | `/dev/ttyS4` |
| `Portas.SERIAL5` | 5 | SERIAIS 5 | `/dev/ttyS2` |
| `Portas.SERIAL6` | 6 | SERIAIS 6 | `/dev/ttyS5` |

* As **SERIAIS 1, 2 e 3** são conversores USB-serial dentro do brick. O Linux dá a elas um nome
  `/dev/ttyUSBn` que pode mudar a cada boot; por isso a lib procura pelo **caminho físico** em
  `/dev/serial/by-path/`, que não muda.
* As **SERIAIS 4, 5 e 6** são UARTs do próprio processador (Banana Pi M4 Zero).
* Pinagem de todas: **TX, RX, GND, 5V** (veja o [módulo 1](../01-o-brick-mariola.md)).
* `_SERIAL0` começa com `_` porque é de uso interno: só a lib `Motores` usa.

### Portas I2C (canais do multiplexador)

| Constante | Canal do TCA9548A | Conector |
|---|---|---|
| `Portas.I2C1` | 0 | I2C1 |
| `Portas.I2C2` | 1 | I2C2 |
| `Portas.I2C3` | 7 | I2C3 |
| `Portas.I2C4` | 2 | I2C4 |
| `Portas.I2C5` | 3 | I2C5 |
| `Portas.I2C6` | 6 | I2C6 |
| `Portas.I2C7` | 5 | I2C7 |
| `Portas.I2C8` | 4 | I2C8 |

Os 8 conectores I2C passam por um **multiplexador TCA9548A** (endereço 0x70). Cada conector é um
"barramento separado": dá para ligar **oito sensores iguais, com o mesmo endereço** (oito VL53L0X,
por exemplo), um em cada conector. A ordem dos canais não é 0..7 porque segue o desenho da placa:
**sempre use as constantes**, nunca o número.

> As portas I2C dos conectores **TELA** e **TECLADO** não passam pelo multiplexador e **não têm
> proteção**: não ligue sensores nelas.

## Métodos

### `porta_serial_real(porta)`
Devolve o nome Linux da porta (ex.: `'/dev/ttyUSB1'`).

* **Quando usar:** para depurar ("em qual ttyUSB está a SERIAL2?") ou para usar uma biblioteca de
  terceiros que pede o caminho do arquivo.
* **Erros:** `ValueError` se o número não é de nenhuma porta; `RuntimeError` se não conseguiu
  listar `/dev/serial/by-path/`. Se o conversor USB daquela porta não for achado, devolve `None`.

### `abre_porta_serial(porta, baud_rate=250000, timeout=0.010)`
Abre a porta e devolve um objeto `serial.Serial` (pyserial), ou `None` se deu erro ao abrir. Imprime
`Comunicação estabelecida com sucesso na porta ...` quando dá certo.

* **Quando usar:**
  * para as **placas de controle de motor** (`PlacaControleMotor`), que recebem a porta já aberta.
    Abra **uma vez** e passe o mesmo objeto para todas as placas do barramento;
  * para conversar com um dispositivo seu (um Arduino, um módulo Bluetooth) pela serial.
* **Parâmetros:** `baud_rate` padrão 250000 (o das placas de motor e servo); sensores como o
  giroscópio usam 115200 e já passam isso por dentro. `timeout` em segundos: quanto o `read()`
  espera pela resposta.
* **Cuidado:** teste o resultado antes de usar. Atenção a um detalhe do pyserial: se o
  conversor USB (SERIAL1–3) não for encontrado, `porta_serial_real` devolve `None` e o
  `serial.Serial(None, ...)` cria um objeto **fechado** em vez de dar erro. Por isso teste as duas
  coisas:

```python
barramento = Portas().abre_porta_serial(Portas.SERIAL1, 250000, timeout=0.005)
if barramento is None or not barramento.is_open:
    print('não consegui abrir a SERIAL1')
```

* Abrir a porta **não** diz se tem alguma coisa ligada nela (as SERIAIS 1–3 existem sempre, são
  conversores dentro do brick). Para saber se um dispositivo responde, mande um comando e veja a
  resposta (ex.: `PlacaControleMotor.reset()` devolve `None` se a placa não respondeu).

## No simulador

O simulador troca só `porta_serial_real` por uma porta virtual (`sim://SERIAL1`). O resto é igual.
Uma porta sem nada ligado no `robo.json` devolve `None` em `abre_porta_serial`. No robô real as
SERIAIS 1–3 sempre abrem (o conversor está dentro do brick), então **não use "a porta abriu" para
descobrir o que está ligado**: pergunte ao dispositivo.
