# `Tela` e `Teclado` — a placa de interface do brick

Arquivos: `libs/tela.py`, `libs/teclado.py`

![Placa da tela e do teclado](../imagens/tela_teclado.jpg)

No brick atual, a **tela OLED 128×64** e o **teclado** ficam numa **placa só**, ligada no
conector **TELA** (barramento I2C 0). É ela que o **menu principal** usa para escolher e iniciar os
programas. No seu programa, serve para escolher modos, mostrar valores dos sensores no campo, fazer
calibração sem computador e indicar estados com os LEDs.

| Posição (da esquerda para a direita) | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| **Botão** | Voltar | Baixo | Cima | Enter |
| Constante | `BOTAO_VOLTAR` | `BOTAO_BAIXO` | `BOTAO_CIMA` | `BOTAO_ENTER` |
| **LED** (acima do botão) | branco | vermelho | laranja | verde |
| Número em `altera_led` | 1 | 2 | 3 | 4 |

| Chip | Endereço I2C | Barramento | Lib |
|---|---|---|---|
| OLED SSD1306 128×64 | 0x3C | 0 (conector TELA) | `tela.py` (via `luma.oled`) |
| PCF8574 (botões + LEDs) | 0x38 | 0 (conector TELA) | `teclado.py` |

> Os conectores TELA e TECLADO são I2C **sem proteção** e a 3,3 V: use só para a tela e o teclado.
> Bricks com a placa antiga têm o teclado separado, no conector TECLADO (barramento 1).

---

## `Teclado(i2c_bus=1, i2c_address=0x38)`

`from teclado import Teclado`

Um expansor PCF8574: pinos 0–3 = botões, 4–7 = LEDs.

> **Atenção ao barramento:** o padrão da lib ainda é `i2c_bus=1` (placa antiga). Na placa atual,
> tela e teclado juntos, use **`Teclado(i2c_bus=0)`**. O menu principal tenta o 1 e depois o 0;
> faça o mesmo se o programa tiver que rodar nos dois tipos de brick:
>
> ```python
> def abre_teclado():
>     for barramento in (0, 1):
>         try:
>             return Teclado(i2c_bus=barramento)
>         except OSError:
>             pass
>     raise RuntimeError('teclado não encontrado')
> ```

| Constante | Valor |
|---|---|
| `BOTAO_VOLTAR`, `BOTAO_BAIXO`, `BOTAO_CIMA`, `BOTAO_ENTER` | 1, 2, 3, 4 |
| `APERTADO`, `LIBERADO` | 0, 1 |

### `le_botao(botao)` → `Teclado.APERTADO` (0) ou `Teclado.LIBERADO` (1)
Botão 1 a 4 (`ValueError` fora disso). Cada chamada lê o chip pelo I2C.

### `altera_led(led, valor)`
Muda o pino do LED 1 a 4 (`ValueError` fora disso) para o nível `valor` (0 ou 1).

> **Qual nível acende?** Na placa atual o PCF8574 **puxa o LED para o GND**: o LED **acende com
> 0** e apaga com 1 (o comentário da lib diz o contrário). Por isso, logo depois de
> `Teclado()`, que deixa os pinos dos LEDs em 0, **os quatro LEDs ficam acesos**. Confira no seu
> brick e esconda o detalhe numa função:
>
> ```python
> LED_ACENDE_COM = 0
> def led(numero, aceso):
>     teclado.altera_led(numero, LED_ACENDE_COM if aceso else 1 - LED_ACENDE_COM)
> ```

**Usos dos LEDs:** cada cor um estado do programa (branco = esperando, laranja = calibrando,
verde = rodando, vermelho = erro), confirmar um aperto, piscar no fim de uma calibração. Como estão
na frente do robô, dá para ver o estado do programa **na pista**.

**Usos dos botões:** escolher o modo (seguir linha / calibrar cores / testar garra), ajustar um
valor (+/−) no campo, confirmar cada etapa de uma calibração.

* **Um evento por aperto:** depois de ver `APERTADO`, espere soltar antes de ler de novo:
  ```python
  def apertou(botao):
      if teclado.le_botao(botao) == Teclado.APERTADO:
          while teclado.le_botao(botao) == Teclado.APERTADO:
              time.sleep(0.02)
          return True
      return False
  ```
* **Menu e programa ao mesmo tempo:** enquanto o seu programa roda, o menu principal fica
  esperando, mas o **VOLTAR segurado por 2 s** continua sendo do menu (abre o menu desligar).

---

## `Tela(i2c_bus=0, i2c_address=0x3C)`

`from tela import Tela`

Tela SSD1306 pela biblioteca `luma.oled` (e Pillow), com **4 linhas** de texto (fonte DejaVu
Sans 12). Lança erro se a tela não responder.

| Método | Faz |
|---|---|
| `escreve(texto, linha=0)` | escreve na linha 0 a 3 e redesenha a tela |
| `limpa(linha=-1)` | apaga uma linha, ou todas (`-1`) |
| `apaga(linha)` | apaga uma linha (`ValueError` fora de 0–3) |
| `linhas` | lista com o texto das 4 linhas |
| `display` | o objeto `ssd1306` do luma (para desenhar o que quiser, abaixo) |

```python
tela = Tela()
tela.escreve('Seguidor v3', 0)
tela.escreve(f'IR {sensor.le_reflexao()}', 1)
```

> **Correção (17/10/2026):** o `_desenha()` usava `self.device`, mas o objeto se chama
> `self.display`, e `escreve()`/`limpa()` davam `AttributeError`. A `libs/tela.py` já está
> corrigida; atualize as cópias que estiverem nos seus projetos.

### Desenhando livre (além das 4 linhas)
```python
from luma.core.render import canvas
with canvas(tela.display) as draw:            # ao sair do with, a imagem vai para a tela
    draw.rectangle((0, 0, 127, 63), outline='white')
    draw.text((4, 4), 'IR', fill='white')
    for i, v in enumerate(sensor.le_reflexao()):
        draw.rectangle((10 + i * 28, 60 - v // 4, 30 + i * 28, 60), fill='white')
```
(Depois disso, um `tela.escreve()` redesenha as 4 linhas por cima de tudo.)

* **Desempenho:** cada atualização redesenha a tela inteira pelo I2C (dezenas de ms). **Não
  atualize a tela dentro do laço do seguidor**; atualize poucas vezes por segundo, ou só fora do
  laço.
* **Dono da tela:** enquanto o seu programa roda, o menu principal não desenha. Ao terminar, ele
  volta a desenhar.

---

## No simulador

Os dois simuladores mostram a **frente do brick** no canto de baixo à direita do mapa: a tela, os
4 LEDs (com as cores de verdade) e os 4 botões.

* **Botões:** clique e segure com o mouse, ou use **F1–F4** (Voltar, Baixo, Cima, Enter).
* **Tecla O:** esconde/mostra o painel.
* A `tela.py` e a `teclado.py` rodam sem mudar. A tela usa o Pillow (`pip install pillow`), como
  no robô; a fonte DejaVu, que no robô fica em `/usr/share/fonts`, vem junto com o simulador.
* No `robo*.json`: `"tela": {"barramento": 0, "endereco": 60}` e
  `"teclado": {"barramento": 0, "endereco": 56, "leds_acendem_com": 0}`. Para simular a placa
  antiga (teclado no barramento 1), use `"teclado": true`.
* Quando o programa (re)começa, a tela apaga e os LEDs voltam ao estado de quando o robô liga.
