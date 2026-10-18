# Módulo 15 — Projeto: a área de resgate

**Objetivo:** entender a estratégia completa da área de resgate — entrar, achar e pegar as
vítimas, guardar na caçamba, depositar nos triângulos certos e sair — e as armadilhas de cada
etapa.

Programa: `simuladorLine/exemplo_aluno/resgate.py`. Mapas: `mapas/resgate.json` (linha + área) e
`mapas/curso_area.json` (o robô começa na frente da entrada).

```bash
python simulador.py --mapa mapas/curso_area.json
```

## 15.1 A regra em resumo (2026)

* Área de 120 × 90 cm (medida por fora; paredes de 25 mm para dentro, 10 cm de altura). Entrada com
  **fita prata**, saída com **fita preta**, no vão da parede.
* Três vítimas: **duas vivas** (bolas prateadas) e **uma morta** (bola preta), 45 mm, soltas no
  chão. Pode haver vítimas falsas e um obstáculo.
* Dois **triângulos** nos cantos (30 × 30 cm, paredes de 6 cm): **verde** para as vivas,
  **vermelho** para a morta.
* Cada vítima no triângulo certo multiplica a pontuação por 1,4 (perdendo 0,05 por LoP no trecho,
  mínimo 1,25). **A morta só vale depois das duas vivas.**

## 15.2 Dois robôs, duas estratégias

| Robô | Estratégia |
|---|---|
| 4x4 com câmera, garra e caçamba | recolher as 3 vítimas, depositar, sair |
| Esteira, só sensor de linha | **só sair**: achar o vão com fita preta e continuar a linha |

Mesmo sem resgatar ninguém, **sair da área e continuar** vale os pontos do resto da linha.
`AreaResgate.executa()` decide pelo que o robô tem (`visao` disponível ou não).

## 15.3 Detectar a entrada

Quem vê a fita prata é o **TCS**: com os LEDs de 5 mm, a claridade C passa de 127 (o branco) e
chega a ~200. O IR não ajuda a achar o prata, porque lê **menos** nele (~80) que no branco. Mas
em cima da lombada o sensor chega mais perto do chão e **tudo** clareia: o branco também chega a
~200 no TCS. A diferença é que a fita prata atravessa o vão inteiro (os 3 TCS e os 4 canais de IR
ficam em cima dela, sem linha preta), enquanto na lombada a linha continua embaixo do meio do
sensor. O exemplo só aceita a entrada se tudo concordar:

```python
PRATA_C = 165          # claridade C do TCS: branco ~127, prata ~200
IR_PRATA = (50, 120)   # no prata o IR lê ~80; abaixo = linha preta; acima = sensor perto do chão

def eh_prata(r, ir=None):
    ir = ir if ir is not None else r.reflexao()
    if min(ir) < IR_PRATA[0] or max(ir) > IR_PRATA[1]:
        return False                                     # linha preta embaixo, ou IR estourado
    for k in (1, 2, 3):                                  # os 3 TCS muito claros e 'prata'
        if r.cor.le_rgbc(k)[3] < PRATA_C or r.cor.cor(k) != 'prata':
            return False
    return True

def entrada_da_area(r, ir):
    return abs(r.inclinacao()) <= 4 and eh_prata(r, ir)  # e o robô nivelado
```

## 15.4 Um referencial para a área inteira

Ao entrar, o robô guarda `z_entrada = r.z()`. As paredes da área são **paralelas e
perpendiculares** a essa direção, e os triângulos ficam a **45°**. Toda manobra usa essa
referência: "virar para a parede" é girar para `z_entrada + 90·k`; "ficar de frente para o
triângulo" é `z_entrada + 45 + 90·k`.

Cuidado com o giroscópio acumulando voltas (`z` = 384° depois de muitos giros): escolha sempre o
alvo **mais perto** do ângulo atual (`diagonal_mais_perto`, `alinhado`).

## 15.5 Recolher

```
procura (gira de 30 em 30°, olhando)  →  escolhe a mais perto que ainda cabe na caçamba
   → aproxima em passos (até ~26 cm), corrigindo o ângulo a cada quadro
   → confirma o tipo em mais 2 quadros (votação)
   → abaixa a garra aberta  (a câmera fica tapada!)
   → avança devagar até o VL53 da garra ver a bolinha (< 22 mm)
   → fecha, levanta
   → confere com o VL53 da garra se a bolinha está lá
   → joga no lado certo da caçamba (vivas à esquerda, morta à direita)
```

Detalhes que fazem diferença:

* **Escolher:** só vítimas que ainda cabem (2 vivas, 1 morta).
* **Não achou nada girando?** Muda de lugar (anda até perto de uma parede) e procura de novo.
  Vítimas atrás de outras ou perto do triângulo podem não aparecer de um ponto só.
* **Garra abaixada tapa a câmera:** o último trecho é "às cegas", guiado pelo VL53 da garra.
* **Errou?** Se depois de levantar o VL53 da garra não vê nada, volta e tenta de novo.
* **Tempo máximo** na área (`TEMPO_MAXIMO_AREA`): depois disso, desiste e vai para a saída.
* **`garra.mantem()`** nas esperas longas (5 s sem pacote desliga os servos).

## 15.6 Depositar

```
procura o triângulo (câmera, cor)  →  vai até ~50 cm dele
  → gira para a diagonal (de frente para a parede do triângulo)
  → corrige o desvio lateral (centro da parede bem na frente)
  → avança até ~15 cm
  → gira 180° e encosta de RÉ até o TCS de trás ver a cor certa
  → abre a porta do lado certo; as bolinhas caem por cima da parede de 6 cm
```

* O **TCS de trás** é a confirmação: nunca solte sem ver a cor certa (3 tentativas).
* Vivas primeiro. A morta só se as duas vivas foram entregues (senão, ela não vale e ainda ocupa
  tempo).

## 15.7 Sair

O robô **segue a parede pela direita** (VL53 direito a 6 cm, módulo 7), virando nos cantos (VL53 da
frente), até achar um **vão**. Se embaixo do vão há **fita preta**, é a saída: atravessa e volta a
seguir a linha. Se é **prata**, é a entrada: passa reto.

Armadilhas resolvidas no exemplo:
* depois de girar, a primeira leitura do VL53 é velha (de antes do giro): `renova()`;
* limitar o quanto o robô pode "apontar" para a parede (±12° do rumo), senão o sensor mede na
  diagonal e ele se perde;
* detectar robô **preso** (encoder não anda) e dar ré.

## 15.8 Resultados e o que melhorar

No `curso_area.json` (semente 1), o exemplo resgata as três vítimas e sai: total 220 com
multiplicador ×2,744. Em outras sementes às vezes perde uma vítima. Boas melhorias:

1. Procurar vítimas **andando em um padrão** (varrer a área) em vez de só girar parado.
2. Pegar a vítima **encostada na parede** (o braço não chega; empurrar para o meio antes).
3. Lembrar onde viu cada vítima (mapa da área) para não procurar de novo.
4. Usar o tempo: se faltam poucos minutos, sair direto.

## Exercícios

1. Rode o exemplo com as sementes 1 a 6 no `curso_area.json` e anote quantas vítimas resgatou em
   cada uma.
2. Mude a ordem: entregar a morta antes das vivas. O que o juiz faz?
3. Faça o robô de esteira (sem câmera) achar a saída em 6 sementes.
4. Escreva a busca "em padrão": percorra a área em três faixas paralelas, olhando a cada 30 cm.
