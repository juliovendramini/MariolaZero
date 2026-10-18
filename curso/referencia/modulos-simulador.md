# Módulos que o simulador fornece: `simdebug`, `visao`, `deteccaoVitimas`, `dispensadorKits`

Algumas partes do robô **não dá para simular de verdade** (a imagem da câmera, a IA, o mecanismo
de kits) e algumas só **existem no simulador** (desenhar na tela dele). Para o mesmo programa rodar
nos dois lugares, o simulador injeta módulos com uma **interface simples**, e a pasta `robo_real/`
de cada simulador traz a versão do robô com a **mesma interface**.

| Módulo | Simulador | No robô real, copie |
|---|---|---|
| `simdebug` | Line e Maze | `robo_real/simdebug.py` (não faz nada) |
| `visao` | Line | `simuladorLine/robo_real/visao.py` (câmera USB + a sua YOLO/OpenCV) |
| `deteccaoVitimas` | Maze | `simuladorMaze/robo_real/deteccaoVitimas.py` (complete) |
| `dispensadorKits` | Maze | `simuladorMaze/robo_real/dispensadorKits.py` (complete) |

`simdebug` e `visao` têm `NO_SIMULADOR` (`True` no simulador, `False` no robô), para o raro caso de o
programa precisar saber onde está.

---

## `simdebug` — desenhar o que o programa "acha"

```python
try:
    import simdebug
except ImportError:          # robô sem o simdebug.py: segue sem desenhar
    simdebug = None

if simdebug:
    simdebug.pose(x_mm, y_mm, theta_graus)
```

| Função | Desenha |
|---|---|
| `pose(x_mm, y_mm, theta_graus)` | o contorno roxo do robô **onde o seu programa acha que ele está** (referencial do início: x para frente, y para a esquerda, θ anti-horário) |
| `texto(s)` | uma frase no painel (o estado da sua máquina de estados, por exemplo) |
| `marca(x_mm, y_mm, cor='amarelo')` | um ponto no mapa (onde achou uma vítima, onde viu o preto...) |
| `limpa()` | apaga as marcas |

* **Quando usar:** sempre que tiver odometria ou um mapa interno. Ver o robô de verdade e o
  "robô imaginado" lado a lado mostra na hora se o erro é de **percepção** ou de **decisão**.

---

## `visao` — câmera da frente (Line, área de resgate)

```python
from visao import Visao
camera = Visao()
for v in camera.vitimas():
    print(v.tipo, v.angulo, v.distancia)
```

### `Visao()`
No simulador, dá erro se o robô não tiver `camera` no `robo*.json` (o de esteira não tem).

### `vitimas()` → lista de detecções, **da mais perto para a mais longe**
Cada uma com:

| Campo | Significado |
|---|---|
| `tipo` | `'viva'` (prata) ou `'morta'` (preta) |
| `angulo` | graus, **+ = à esquerda** do centro da imagem |
| `distancia` | mm (estimada pelo tamanho da bolinha) |
| `x`, `y`, `raio_px` | posição e raio na imagem (320×240) |
| `confianca` | 0 a 1 |

### `triangulos()` → lista de detecções dos triângulos
`cor` (`'verde'`/`'vermelho'`), `angulo`, `distancia` (até a parede do triângulo), `x`, `x_min`,
`x_max`, `largura_px`.

### Como o stub se comporta (igual a uma câmera de verdade)
* **Ritmo:** `vitimas()` entrega ~4 quadros/s (a IA no Banana Pi), `triangulos()` ~30/s (OpenCV).
  Cada chamada **espera o próximo quadro**.
* **Atraso:** a resposta descreve o quadro capturado antes do processamento: o robô já andou um
  pouco.
* **Erros:** 90% de acerto (às vezes a vítima não aparece), ~3% de troca viva/morta, ruído no
  ângulo e na distância, vítimas falsas às vezes detectadas como vivas.
* **O erro fica preso ao ponto de vista:** parado no mesmo lugar, o mesmo erro se repete. Andando
  ou girando, ele é sorteado de novo. Ou seja: **se não viu, mexa-se um pouco e olhe de novo**.
* **Oclusão:** uma vítima esconde a outra; paredes, triângulos e o obstáculo escondem o que está
  atrás; **a garra toda abaixada tapa a câmera**.

### No robô real
`robo_real/visao.py` abre a câmera USB numa thread (sempre o quadro mais novo), calcula ângulo e
distância com o campo de visão e a altura da câmera, e tem dois pontos para você completar:
`_detecta_vitimas(img)` (a sua YOLO) e `_detecta_triangulos(img)` (já vem com OpenCV por faixa
HSV). **Meça** `FOV_GRAUS` e `ALTURA_MM` da sua câmera.

---

## `deteccaoVitimas` — câmeras laterais (Maze)

```python
from deteccaoVitimas import DeteccaoVitimas
cam = DeteccaoVitimas()
v = cam.detecta()                 # olha as duas câmeras; None ou um dict
todas = cam.detecta_todas('esquerda')
```

Cada vítima é um `dict`:
`{'camera': 'esquerda'|'direita', 'tipo': 'letra'|'cognitivo', 'status': 'ferida'|'estavel'|'ilesa',
'kits': 2|1|0, 'letra': 'H'|'S'|'U' (só letras), 'distancia_mm': int}`.

No simulador, a câmera só vê a vítima dentro do campo de visão, de frente e sem parede no meio,
e (opção ligada) **só com os LEDs de iluminação acesos**. No robô, complete `_processa(nome)` em
`robo_real/deteccaoVitimas.py` com a sua visão (letras Φ Ψ Ω e alvos cognitivos).

## `dispensadorKits` — kits de resgate (Maze)

```python
from dispensadorKits import DispensadorKits
kits = DispensadorKits()
saiu = kits.deposita(2, 'esquerda')   # quantos kits saíram
kits.restantes()
```

No robô, `robo_real/dispensadorKits.py` traz um exemplo com dois servos comuns do Mariola
(`DispensadorKits(motores=motores)`); ajuste os ângulos para o seu mecanismo.
