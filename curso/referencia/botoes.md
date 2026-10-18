# `Botoes` — botões e chaves nos pinos digitais

Arquivo: `libs/botoes.py` · `from botoes import Botoes`

## Para que serve

Ler **botões e chaves de contato** ligados nos conectores **PINOS DIGITAIS 1 a 8** (pinagem GND +
PINO; aceitam 5 V e têm proteção). Usos:

* **botão de início** da rodada (a regra pede que o robô comece com um toque);
* **para-choque**: duas chaves na frente do robô para saber que bateu (e de que lado);
* chave de fim de curso de um mecanismo.

## Como funciona

Os pinos são linhas GPIO do Banana Pi (`/dev/gpiochip0`), lidas pela biblioteca `gpiod`. Os
pinos têm *pull-up*: **solto = nível alto, apertado (ligado ao GND) = nível baixo**. Por isso as
constantes parecem "ao contrário": `LIBERADO = ACTIVE` e `APERTADO = INACTIVE`.

Ligue o botão entre o PINO e o GND do mesmo conector.

## Constantes

| Constante | Significado |
|---|---|
| `Botoes.P1` … `Botoes.P8` | os 8 pinos (números das linhas GPIO; use sempre o nome) |
| `Botoes.APERTADO`, `Botoes.LIBERADO` | o que `le_botao` devolve |

## Métodos

### `Botoes()`
Reserva os 8 pinos como entrada.

* **Cuidado:** só pode haver **um** dono de cada pino. Não crie dois `Botoes()`, nem `Botoes()` e
  `PinosDigitais()` no mesmo programa (o segundo dá erro "Device or resource busy"). A classe
  `Lidar` cria um `PinosDigitais` por dentro quando recebe `pino_liga`. Se precisar de entradas
  **e** saídas, use só [`PinosDigitais`](pinosDigitais.md), que tem os mesmos métodos.

### `botao_pressionado(pino)` → `True`/`False`
**O método do dia a dia.**

```python
if botoes.botao_pressionado(Botoes.P1):
    print('bateu do lado esquerdo')
```

### `le_botao(pino)` → `Botoes.APERTADO` ou `Botoes.LIBERADO`
O mesmo, devolvendo o nível. `ValueError` para pino inválido.

## Receitas

**Esperar o botão de início (apertar e soltar):**
```python
while not botoes.botao_pressionado(Botoes.P3):
    motores.estado()          # mantém o Mariola acordado (timeout de 5 s)
    time.sleep(0.05)
while botoes.botao_pressionado(Botoes.P3):
    time.sleep(0.02)
```
Esperar soltar evita que o robô saia com a mão do juiz ainda em cima dele.

**Um evento por aperto (para menus):** depois de detectar o aperto, espere soltar antes de ler de
novo. Sem isso, um aperto de 200 ms vira 20 eventos.

**Para-choque:** os dois apertados = robô encostado reto na parede (ótimo para alinhar na Maze).

## No simulador

`botao_inicio` (P3) e `para_choque` (P1 esquerdo, P2 direito) no `robo*.json`. O botão de início
é apertado sozinho 1,5 s depois do programa subir (**Auto-botão**) ou com a tecla **B**.
