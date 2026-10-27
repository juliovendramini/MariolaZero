# Botões e chaves nos pinos digitais (com `PinosDigitais`)

Arquivo: `libs/pinosDigitais.py` · `from pinosDigitais import PinosDigitais`

> **Mudou em 27/10/2026:** a classe `Botoes` (`botoes.py`) foi juntada ao
> [`PinosDigitais`](pinosDigitais.md). As duas usavam os mesmos 8 pinos e davam erro ("Device or
> resource busy") quando estavam no mesmo programa. Programa antigo? Troque
> `from botoes import Botoes` por `from pinosDigitais import PinosDigitais` e `Botoes` por
> `PinosDigitais` no resto do código (`Botoes.P3` → `PinosDigitais.P3`, `Botoes()` →
> `PinosDigitais()`). Os métodos são os mesmos.

## Para que serve

Ler **botões e chaves de contato** ligados nos conectores **PINOS DIGITAIS 1 a 8** (pinagem GND +
PINO; aceitam 5 V e têm proteção). Usos:

* **botão de início** da rodada (a regra pede que o robô comece com um toque);
* **para-choque**: duas chaves na frente do robô para saber que bateu (e de que lado);
* chave de fim de curso de um mecanismo.

## Como funciona

Os pinos são linhas GPIO do Banana Pi, lidas pela biblioteca `gpiod`. A lib acha sozinha o
`gpiochip` certo (no kernel do brick é o `/dev/gpiochip1`; em kernels antigos era o `gpiochip0`). Os
pinos têm *pull-up*: **solto = nível alto, apertado (ligado ao GND) = nível baixo**. Por isso as
constantes parecem "ao contrário": `LIBERADO = ACTIVE` e `APERTADO = INACTIVE`.

Ligue o botão entre o PINO e o GND do mesmo conector.

## Constantes

| Constante | Significado |
|---|---|
| `PinosDigitais.P1` … `PinosDigitais.P8` | os 8 pinos (números das linhas GPIO; use sempre o nome) |
| `PinosDigitais.APERTADO`, `PinosDigitais.LIBERADO` | o que `le_botao` devolve |

## Métodos

### `PinosDigitais()`
Reserva os 8 pinos, todos como **entrada**: prontos para botões, sem configurar nada.

* Chamar `PinosDigitais()` de novo no mesmo programa devolve **o mesmo objeto**. Por isso o seu
  programa e a classe `Lidar` (que usa um pino para ligar o motor do lidar) podem usar os pinos
  juntos. Para usar alguns pinos como **saída** (LED, relé), veja
  [`PinosDigitais`](pinosDigitais.md).

### `botao_pressionado(pino)` → `True`/`False`
**O método do dia a dia.**

```python
botoes = PinosDigitais()
if botoes.botao_pressionado(PinosDigitais.P1):
    print('bateu do lado esquerdo')
```

### `le_botao(pino)` → `PinosDigitais.APERTADO` ou `PinosDigitais.LIBERADO`
O mesmo, devolvendo o nível. `ValueError` para pino inválido ou configurado como saída.

## Receitas

**Esperar o botão de início (apertar e soltar):**
```python
while not botoes.botao_pressionado(PinosDigitais.P3):
    motores.estado()          # mantém o Mariola acordado (timeout de 5 s)
    time.sleep(0.05)
while botoes.botao_pressionado(PinosDigitais.P3):
    time.sleep(0.02)
```
Esperar soltar evita que o robô saia com a mão do juiz ainda em cima dele.

**Um evento por aperto (para menus):** depois de detectar o aperto, espere soltar antes de ler de
novo. Sem isso, um aperto de 200 ms vira 20 eventos.

**Para-choque:** os dois apertados = robô encostado reto na parede (ótimo para alinhar na Maze).

## No simulador

`botao_inicio` (P3) e `para_choque` (P1 esquerdo, P2 direito) no `robo*.json`. O botão de início
é apertado sozinho 1,5 s depois do programa subir (**Auto-botão**) ou com a tecla **B**.
