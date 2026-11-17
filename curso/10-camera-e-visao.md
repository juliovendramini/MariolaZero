# Módulo 10 — Câmera: achar vítimas e triângulos

**Objetivo:** usar a câmera como sensor (ângulo e distância das vítimas e dos triângulos), lidar com
erros de detecção e atraso, e saber o caminho para fazer a mesma interface funcionar no robô real.

Referência: [módulos do simulador — `visao`](referencia/modulos-simulador.md),
[exemplos de câmera](referencia/extras.md). Código:
[`codigos/08_camera/procura_vitima.py`](codigos/08_camera/procura_vitima.py). Mapa:
`mapas/curso_area.json` (o robô começa a dois ladrilhos da entrada da área de resgate).

## 10.1 A ideia: a câmera vira um "sensor de vítimas"

Processar imagem é um assunto enorme. Para a **estratégia** do robô, porém, só interessa a
resposta: *tem vítima? de que tipo? para que lado? a que distância?* O módulo `visao` entrega
exatamente isso:

```python
from visao import Visao
camera = Visao()

for v in camera.vitimas():          # da mais perto para a mais longe
    print(v.tipo, v.angulo, v.distancia)   # 'viva'/'morta', graus (+ = esquerda), mm

for t in camera.triangulos():
    print(t.cor, t.angulo, t.distancia)    # 'verde'/'vermelho', graus, mm até a parede dele
```

* **No simulador** o `visao` é um *stub*: não gera imagem, devolve o que uma boa IA veria (com
  erros realistas).
* **No robô**, `simuladorLine/robo_real/visao.py` tem a **mesma interface** e faz o trabalho de
  verdade com a câmera USB. O programa da estratégia é o mesmo nos dois.

## 10.2 Como a câmera "se comporta"

| Característica | Na prática |
|---|---|
| `vitimas()` ~4 quadros/s (IA) | cada chamada **espera** o próximo quadro (~0,25 s) |
| `triangulos()` ~30 quadros/s (OpenCV) | bem mais rápido |
| Atraso de um quadro | a resposta é de quando a foto foi tirada; o robô já andou |
| 90% de acerto | às vezes a vítima não aparece |
| Erro preso ao ponto de vista | parado, o mesmo erro se repete; **mexa-se e olhe de novo** |
| ~3% de troca viva/morta | confirme o tipo em mais de um quadro |
| Oclusão | vítima atrás de vítima, atrás de parede ou dentro do triângulo não aparece |
| Garra toda abaixada | **tapa a câmera** |

## 10.3 Tutorial: procurar e chegar perto de uma vítima

```bash
python simulador.py --mapa mapas/curso_area.json --programa ../curso/codigos/08_camera/procura_vitima.py
```

**1. Procurar girando em passos.** Gira 20°, para, olha. Parado, a imagem não fica borrada (no
robô real) e o quadro corresponde ao lugar em que o robô está.

```python
for tentativa in range(18):              # no máximo 360°
    vitimas = camera.vitimas()
    if vitimas:
        break
    gira(20)
```

**2. Aproximar corrigindo pelo ângulo** (controle proporcional, de novo):

```python
v = vs[0]
if v.distancia < 150:
    ...                                   # chegou
correcao = max(-20, min(20, v.angulo * 0.8))   # ângulo + = vítima à esquerda
anda(30 - correcao, 30 + correcao)
```

**3. Não desistir no primeiro quadro vazio.** A primeira versão deste tutorial **parava** o robô
quando um quadro vinha sem a vítima. Parado, a câmera via a mesma cena, errava de novo, e o robô
"perdia" a vítima. A versão final continua andando e só desiste depois de 6 quadros seguidos sem
ver nada:

```python
if not vs:
    perdidas += 1
    if perdidas > 6:
        print('perdi a vítima de vista')
        break
    continue                               # mantém o último comando de motor
```

Resultados com 4 sementes diferentes:
```
vi uma vítima viva a 493 mm, -13°  →  cheguei: vítima viva a 115 mm
vi uma vítima viva a 626 mm, -28°  →  cheguei: vítima viva a 101 mm
vi uma vítima viva a 423 mm, +16°  →  cheguei: vítima viva a 131 mm
vi uma vítima viva a 523 mm, -25°  →  cheguei: vítima viva a 136 mm
```

## 10.4 Confiar, mas confirmar

Decisões caras (descer a garra, levar ao triângulo) merecem confirmação:

* **Tipo:** contar votos em 2–3 quadros antes de decidir viva/morta (o exemplo da área de resgate
  faz isso).
* **Na garra:** um VL53 baixo entre os dedos confirma que a bolinha está lá antes de fechar.
* **No triângulo:** o TCS34725 de trás confirma a cor da parede antes de abrir a porta.

## 10.5 No robô real

`robo_real/visao.py` já tem:

* a captura numa **thread** (sempre o quadro mais novo, sem fila de quadros velhos);
* a conversão de **posição na imagem → ângulo** (pelo campo de visão) e de **tamanho → distância**
  (pelo raio da bolinha), e da **base do triângulo → distância** (pela altura da câmera);
* `_detecta_triangulos()` com OpenCV por faixa de cor HSV.

Falta você:

1. **Medir** `FOV_GRAUS` (ângulo de visão horizontal) e `ALTURA_MM` da sua câmera.
2. Colocar a sua YOLO em `_detecta_vitimas(img)` → lista de `(tipo, x, y, raio_px, confiança)`.
   Os exemplos `exemplos/camera/03-posicionamentoDeteccaoONNX` e `...NCNN` mostram como rodar o
   modelo **sem PyTorch** (inicia muito mais rápido no Banana Pi).
3. Ajustar as faixas HSV do verde e do vermelho com a luz do local (`07-detectandoAreas`).
4. Juntar fotos do campo para treinar melhor (`06-projetoSalvaFotos`).

Para ver o que a câmera do robô está vendo: `exemplos/camera/01-streamingVLC` (abre no navegador).

### Quanto tempo a IA leva no brick

A mesma rede pode ir para o brick em dois formatos, os dois gerados no PC a partir do `best.pt`:

```bash
yolo export model=best.pt format=onnx imgsz=320    # best.onnx         -> OpenCV DNN
yolo export model=best.pt format=ncnn imgsz=320    # best_ncnn_model/  -> NCNN
```

Medido num brick em 17/11/2026 (YOLOv8n de 320, fotos 320 × 240 da câmera do robô, sem cooler):

| formato | quadros por segundo | tempo por foto |
|---|---|---|
| ONNX (OpenCV DNN) | 4,4 | ~228 ms |
| **NCNN, 4 núcleos** | **7,6** | **~131 ms** |
| NCNN, 3 núcleos | 6,7 | ~150 ms |

* O NCNN é **~1,7 vez mais rápido** e acha **as mesmas bolas** que o ONNX.
* Com 3 núcleos sobra um para o resto do programa (sensores, motores) e o tempo fica mais estável.
* Quase todo o tempo é a rede. Preparar a foto e o NMS somam ~6 ms: não adianta otimizar isso.
* Rede rodando sem parar **esquenta**: o brick sem cooler passou de 90 °C em alguns minutos.
  Veja a temperatura com `cat /sys/class/thermal/thermal_zone0/temp` (em milésimos de grau).
* Para medir com a **sua** rede e as **suas** fotos, sem câmera: `exemplos/camera/08-medeVelocidadeIA`.

Para trocar o ONNX pelo NCNN num programa, muda só o carregamento e a chamada da rede. A saída tem o
mesmo formato `[1, 6, 2100]`, e o resto do código fica igual:

```python
import ncnn
net = ncnn.Net()
net.opt.num_threads = 3
net.load_param("best_ncnn_model/model.ncnn.param")
net.load_model("best_ncnn_model/model.ncnn.bin")

# no lugar de  net.setInput(blob); saida = net.forward()
with net.create_extractor() as ex:
    ex.input("in0", ncnn.Mat(blob[0]))
    _, out = ex.extract("out0")
saida = np.array(out)[None]
```

Lembre do 10.2: a ~4 quadros por segundo, o robô anda entre uma foto e a resposta. Com o NCNN o
atraso cai, mas não some: continue confirmando em mais de um quadro.

## 10.6 Outra câmera: seguir a linha com OpenCV

Em vez do sensor de linha, o robô pode seguir a linha com uma **câmera de linha**: embaixo do robô,
um pouco atrás das rodas da frente, olhando reto para o chão, com LEDs iluminando. No simulador é o
robô `robo_4x4_camera.json` (o 4x4 sem o Pro1616). Esta câmera **gera a imagem de verdade**, e o
programa usa o OpenCV como no robô:

```python
import cv2
cam = cv2.VideoCapture('/dev/video_usb2')        # a câmera da porta USB 2
ok, img = cam.read()                             # imagem BGR 320 x 240
cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
_, preto = cv2.threshold(cinza, 90, 255, cv2.THRESH_BINARY_INV)   # linha = branco na máscara
m = cv2.moments(preto[:120], binaryImage=True)   # metade de cima = à frente da câmera
if m['m00'] > 300:
    x_linha = m['m10'] / m['m00']                # coluna do centro da linha (160 = meio)
```

* A frente do robô fica no **topo** da imagem. Cada pixel vale ~0,5 mm no chão (a imagem cobre
  16,5 x 12,4 cm).
* As **rodas da frente aparecem nas bordas** da esquerda e da direita: elas são escuras e parecem
  linha. Corte uns 40 px de cada lado antes de procurar o preto.
* O verde e o vermelho saem com `cv2.cvtColor(img, cv2.COLOR_BGR2HSV)` e `cv2.inRange`.
* A luz vem de uma fita de LEDs. Sem difusor, a fita isolante preta **reflete os LEDs** e aparece
  com pontos brancos estourados; com difusor (`"difusor": true` no `robo_4x4_camera.json`), o
  reflexo vira uma faixa cinza mais fraca, mas a imagem fica mais escura. Teste o seu programa nos
  dois casos.
* `read()` espera o próximo quadro (30 por segundo): o laço fica no ritmo da câmera.
* Na janela do simulador, a tecla **C** mostra o último quadro que o programa leu.

O exemplo completo é o `simuladorLine/exemplo_aluno/seguidor_camera.py`: segue a linha só com a
câmera, trata gap, verde e a fita vermelha da chegada. No PC precisa do OpenCV
(`pip install opencv-python-headless`; o pacote do laboratório já traz).

## 10.7 E na Maze?

A Maze usa duas câmeras laterais e outra interface (`deteccaoVitimas`): `detecta()` devolve o tipo
da vítima (letra ou alvo cognitivo), o estado e **quantos kits** deixar. Veja o módulo 16.

## Exercícios

1. Em vez de girar 20° e parar, gire devagar sem parar chamando `vitimas()`. Funciona? O que
   acontece com o ângulo informado (lembre do atraso)?
2. Conte quantas vezes, em 50 quadros parado na frente de uma vítima, ela não apareceu. E andando?
3. Faça o robô ir até o triângulo verde e parar a 10 cm da parede dele.
4. Implemente a votação do tipo: só aceite "viva" ou "morta" depois de 3 quadros concordarem.
