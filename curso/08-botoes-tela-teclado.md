# Módulo 8 — Botões, para-choque, teclado, tela e tempo

**Objetivo:** começar a rodada pelo botão, perceber batidas pelo para-choque, medir tempo e montar
um menu no próprio robô para escolher modos e calibrar sem computador.

Referência: [botões e chaves](referencia/botoes.md), [`PinosDigitais`](referencia/pinosDigitais.md),
[`Teclado` e `Tela`](referencia/teclado-tela.md), [`Cronometro`](referencia/cronometro.md).
Códigos: [`codigos/06_interface/`](codigos/06_interface/).

## 8.1 O botão de início

A regra pede que o robô comece quando o time manda (um toque). Ligue um botão num pino digital
(P3 no robô do curso) e espere. Os botões são lidos pela classe `PinosDigitais` (até 27/10/2026
havia uma classe `Botoes` separada; programa antigo: troque `Botoes` por `PinosDigitais`):

```python
from pinosDigitais import PinosDigitais

botoes = PinosDigitais()        # os 8 pinos como entrada

def espera_botao(pino):
    """Espera apertar E soltar (o robô só sai quando o dedo já saiu do botão)."""
    while not botoes.botao_pressionado(pino):
        anda(0, 0)              # manda comando: o Mariola desliga tudo após 5 s sem pacote
        time.sleep(0.05)
    while botoes.botao_pressionado(pino):
        time.sleep(0.02)
```

Por que o `anda(0, 0)` dentro da espera? Porque a espera pode durar minutos e o Mariola **apaga os
LEDs e solta os motores após 5 s sem pacote**. Mandar "parado" mantém tudo vivo.

**Depois do botão:** zere o giroscópio (`reseta_z()`), acenda os LEDs que precisam estar acesos
(iluminação de câmera) e inicie o relógio da rodada.

## 8.2 Para-choque

Duas chaves na frente (P1 esquerda, P2 direita). Apertado = `True`.

[`botao_e_cronometro.py`](codigos/06_interface/botao_e_cronometro.py) anda até bater:

```python
relogio = Cronometro()
relogio.inicia()
while relogio.tempo() < 20000:                  # no máximo 20 s (tempo() é em ms)
    esq = botoes.botao_pressionado(PARA_CHOQUE_ESQ)
    dir_ = botoes.botao_pressionado(PARA_CHOQUE_DIR)
    if esq or dir_:
        print(f'bateu depois de {relogio.tempo()} ms (esquerdo={esq}, direito={dir_})')
        break
    anda(40, 40)
    time.sleep(0.01)
```
```
bateu depois de 10173 ms (esquerdo=False, direito=True)
```

Usos:
* **Line:** confirmar o obstáculo (se o VL53 falhou).
* **Maze:** **alinhar** — andar devagar até os **dois** botões apertarem: o robô está reto contra
  a parede, e o giroscópio pode ser corrigido. Se só um apertou, o robô está torto: gire um pouco
  **para o lado do botão apertado** (só o esquerdo apertou = o robô está virado para a direita).

## 8.3 Medindo tempo

`Cronometro().tempo()` em ms, ou `time.time()` em segundos. Use para:

* **limitar manobras** (girar procurando a linha por no máximo 3 s);
* **regras de tempo** (parado 5 s no azul, mais de 5 s na chegada);
* **estratégia** (aos 6,5 min da Maze, voltar para o início).

Com arquivo (`Cronometro('/home/banana/rodada.txt')`), o tempo da rodada **sobrevive a um
reinício** do programa no LoP.

## 8.4 Um menu no robô: tela, teclado e LEDs

[`menu_teclado.py`](codigos/06_interface/menu_teclado.py)

![Tela e teclado](imagens/tela_teclado.jpg)

Na competição você não vai ter computador. A placa da tela + teclado (conector TELA) permite
escolher "seguir linha", "calibrar cores", "testar garra" no próprio robô e ver o estado dele:

| | Voltar | Baixo | Cima | Enter |
|---|---|---|---|---|
| botão (`Teclado.`) | `BOTAO_VOLTAR` (1) | `BOTAO_BAIXO` (2) | `BOTAO_CIMA` (3) | `BOTAO_ENTER` (4) |
| LED acima dele | 1 branco | 2 vermelho | 3 laranja | 4 verde |

Três detalhes da placa atual (todos explicados na [referência](referencia/teclado-tela.md)):

* o teclado está no **barramento 0**, junto com a tela: `Teclado(i2c_bus=0)` (o padrão da lib, 1, é
  da placa antiga);
* o **LED acende com 1** em `altera_led`. Ao ligar o brick os quatro ficam acesos, e
  `Teclado()` apaga todos;
* um aperto dura vários ciclos do laço: **espere soltar** para contar um aperto só.

```python
tela = Tela()
teclado = abre_teclado()        # tenta o barramento 0 e depois o 1

def led(numero, aceso):
    teclado.altera_led(numero, LED_ACENDE_COM if aceso else 1 - LED_ACENDE_COM)

def apertou(botao):
    """True só uma vez por aperto (espera soltar)."""
    if teclado.le_botao(botao) == Teclado.APERTADO:
        while teclado.le_botao(botao) == Teclado.APERTADO:
            time.sleep(0.02)
        return True
    return False

led(LED_BRANCO, True)           # branco: esperando a escolha
mostra_menu(escolha)
while True:
    if apertou(Teclado.BOTAO_BAIXO):
        escolha = (escolha + 1) % len(OPCOES)
        mostra_menu(escolha)
    elif apertou(Teclado.BOTAO_CIMA):
        escolha = (escolha - 1) % len(OPCOES)
        mostra_menu(escolha)
    elif apertou(Teclado.BOTAO_ENTER):
        led(LED_VERDE, True)    # verde: escolhido
        tela.escreve('Escolhido:', 0)
        break
    time.sleep(0.05)
```

**No simulador** a tela e o teclado aparecem no canto do mapa: clique nos botões (ou F1–F4) e veja a
tela e os LEDs mudarem. A tecla **O** esconde o painel.

**Use os LEDs para o estado do programa.** Uma cor por estado (branco = esperando o botão,
laranja = calibrando, verde = rodando, vermelho = erro) mostra na pista o que o robô está fazendo,
sem computador.

**Não atualize a tela no laço do seguidor:** cada `escreve` leva dezenas de milissegundos. Mostre
valores poucas vezes por segundo, ou só fora do laço.

Outra opção para escolher o que rodar: um projeto (pasta) para cada modo — `seguidor/`,
`calibra_cores/` —, escolhidos no menu principal do brick. Funciona bem enquanto os modos não
precisam conversar.

## 8.5 Pinos como saída

`PinosDigitais` permite usar um pino para **acender um LED**, acionar um relé (com módulo),
um buzzer:

```python
pinos = PinosDigitais()         # o mesmo objeto dos botões (é um só no programa)
pinos.configura_pino(PinosDigitais.P5, PinosDigitais.SAIDA)
pinos.liga_pino(PinosDigitais.P5)
```

> Botões e saídas usam a **mesma** classe: chamar `PinosDigitais()` de novo devolve o mesmo objeto,
> então dá para ler o botão no P3 e acender um LED no P5 no mesmo programa.

## Exercícios

1. Faça o robô esperar o botão, andar até bater e voltar até o ponto de partida (encoder).
2. No para-choque: se bateu só o esquerdo, o robô está virado para a direita: gire 10° para a
   **esquerda** e encoste de novo (e o contrário se bateu só o direito). Repita até os dois
   apertarem (alinhamento).
3. Crie um menu com 3 velocidades para o seguidor (30, 40, 50) e use a escolhida.
4. Faça um "modo sensores" que mostra na tela os 4 IR e as 3 cores a cada 0,5 s, para conferir o
   sensor no campo. Baixo/Cima trocam de página (IR, cores, VL53).
5. Desenhe na tela um gráfico de barras dos 4 canais IR (`canvas(tela.display)`, veja a
   referência).
6. Faça o LED laranja piscar enquanto o robô espera o botão de início.
