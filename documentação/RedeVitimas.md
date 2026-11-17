# Rede de vítimas (YOLO) no brick

Como a rede que acha as vítimas (bola preta e bola prata) roda no Banana Pi do Mariola: os formatos,
quanto tempo cada um leva e como medir de novo.

---

## A rede

| item | valor |
|---|---|
| modelo | YOLOv8n (o menor da família, ~3 milhões de parâmetros) |
| entrada | imagem 320 × 320, RGB, valores de 0 a 1 |
| classes | 0 = bola preta, 1 = bola prata |
| saída | `[1, 6, 2100]`: para cada um dos 2100 candidatos, `cx, cy, w, h` (em pixels da entrada) e a nota de cada classe |
| câmera do robô | 320 × 240 |

A mesma rede pode ser gravada em três formatos:

| formato | arquivo | onde roda | como gerar |
|---|---|---|---|
| PyTorch | `best.pt` | no PC (treino) ou no brick com `ultralytics` (lento para carregar) | é o que sai do treino |
| ONNX | `best.onnx` | OpenCV DNN (`cv2.dnn`) ou `onnxruntime` | `yolo export model=best.pt format=onnx imgsz=320` |
| NCNN | pasta `best_ncnn_model/` (`model.ncnn.param` + `model.ncnn.bin`) | biblioteca `ncnn` (feita para processador de celular, como o do Banana Pi) | `yolo export model=best.pt format=ncnn imgsz=320` |

O `imgsz=320` tem de ser o mesmo do treino. A exportação é feita no PC; no brick só se copia o arquivo
(ou a pasta, no NCNN). O `~/meu_venv` do brick já tem `opencv-python`, `onnxruntime` e `ncnn`.

---

## Quanto tempo leva no brick

Medido em 17/11/2026 num brick sem cooler (Banana Pi M4 Zero, 4 núcleos a 1,416 GHz), com 198 fotos
da câmera do robô (320 × 240), 3 passadas, contando preparar a foto + rede + NMS:

| formato | fps | por foto (média) | pior 5% |
|---|---|---|---|
| ONNX, OpenCV DNN | 4,4 | 228 ms | 244 ms |
| ONNX, onnxruntime (4 núcleos) | 4,4 | 229 ms | 251 ms |
| **NCNN, 4 núcleos** | **7,6** | **131 ms** | 153 ms |
| NCNN, 3 núcleos | 6,7 | 150 ms | 151 ms |
| NCNN, 2 núcleos | 5,8 | 173 ms | 174 ms |

* Quase todo o tempo é a rede: preparar a foto leva ~5 ms e o pós-processamento (NMS), ~1 ms.
* **OpenCV DNN e onnxruntime empatam.** Trocar um pelo outro não adianta.
* **NCNN é ~1,7 vez mais rápido** e dá **as mesmas detecções**. Nas 10 fotos comparadas número a número,
  a diferença de confiança entre NCNN e ONNX ficou abaixo de 0,0001, e nas 198 fotos a contagem de
  bolas foi igual nos dois.
* **3 núcleos** é um bom meio-termo para o robô: perde ~1 fps e deixa um núcleo livre para o resto do
  programa (seguidor de linha, sensores, serial). O tempo também fica mais estável (o pior caso fica
  quase igual à média).
* Trocar a rede por outra treinada de novo (mesmo YOLOv8n, mesmo 320) **não muda a velocidade**.

### Temperatura

Rodando a rede sem parar, o brick sem cooler foi de ~46 °C a **87 °C** com ONNX e a **92 °C** com NCNN
em alguns minutos. A frequência não baixou (não há limite de temperatura configurado para isso; o único
é o de 110 °C, que desliga a placa). No robô, a rede só roda na área de resgate e com pausas, mas num
dia quente vale vigiar: `cat /sys/class/thermal/thermal_zone0/temp` (em milésimos de grau).

---

## Como medir de novo

O exemplo [`exemplos/camera/08-medeVelocidadeIA`](../exemplos/camera/08-medeVelocidadeIA/main.py) roda
a rede em fotos (sem câmera) e imprime fps, tempo, quantas bolas achou e a temperatura:

```bash
# na pasta do exemplo, no brick: best.onnx, best_ncnn_model/ e fotos/*.jpg
python3 main.py        # 3 passadas
python3 main.py 5      # 5 passadas
```

Saída num brick (17/11/2026, 40 fotos):

```
ONNX (OpenCV DNN)     4.3 fps | média   234 ms, pior 5%  250 ms | achou 17 pretas e 22 pratas | 64 -> 71 °C
NCNN 4 núcleos        7.6 fps | média   131 ms, pior 5%  132 ms | achou 17 pretas e 22 pratas | 72 -> 74 °C
NCNN 3 núcleos        6.7 fps | média   148 ms, pior 5%  149 ms | achou 17 pretas e 22 pratas | 75 -> 75 °C
NCNN 2 núcleos        5.8 fps | média   173 ms, pior 5%  174 ms | achou 17 pretas e 22 pratas | 75 -> 73 °C
```

---

## Trocar ONNX por NCNN num programa

O preparo da foto e o pós-processamento continuam iguais (a saída do NCNN tem o mesmo formato
`[1, 6, 2100]`). Muda só como a rede é carregada e chamada:

```python
import ncnn

net = ncnn.Net()
net.opt.use_vulkan_compute = False   # o Banana Pi não tem GPU Vulkan: só CPU
net.opt.num_threads = 3              # núcleos usados pela rede
net.load_param("best_ncnn_model/model.ncnn.param")
net.load_model("best_ncnn_model/model.ncnn.bin")

blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (320, 320), swapRB=True, crop=False)

# no lugar de:  net.setInput(blob); saida = net.forward()
with net.create_extractor() as ex:
    ex.input("in0", ncnn.Mat(blob[0]))
    _, out = ex.extract("out0")
saida = np.array(out)[None]          # [1, 6, 2100], igual ao ONNX
```

`in0` e `out0` são os nomes que o `yolo export` dá para a entrada e a saída (estão no
`model.ncnn.param`).

Os dois exemplos prontos:

* [`03-posicionamentoDeteccaoONNX`](../exemplos/camera/03-posicionamentoDeteccaoONNX/main.py): OpenCV
  DNN; estica a foto 320 × 240 para 320 × 320.
* [`03-posicionamentoDeteccaoNCNN`](../exemplos/camera/03-posicionamentoDeteccaoNCNN/main.py): NCNN;
  põe faixas cinza em cima e embaixo (*letterbox*, como no treino) em vez de esticar, e usa confiança
  mínima 0,7. O pós-processamento dele é um laço em Python pelos 2100 candidatos (mais lento que a
  versão com NumPy do exemplo ONNX).

Os números da tabela acima são com a foto esticada, como no exemplo ONNX.

---

## Rede nova x rede antiga (17/11/2026)

A rede da equipe foi treinada de novo com as fotos do robô na arena de 2026, incluindo a **vítima falsa**
(círculo preto colado na parede, que a regra de 2026 permite e que **não** é vítima). Nas mesmas 198
fotos de teste, com confiança 0,5:

| rede | fotos com a contagem de bolas certa | bolas pretas a mais | bolas a menos |
|---|---|---|---|
| antiga (23/06/2026) | 180 de 198 | 18 (quase todas o círculo da parede) | 0 |
| nova (17/11/2026) | 197 de 198 | 0 | 0 |

A única diferença da rede nova (uma prata a mais) é uma bola de verdade, no escuro, que ficou sem
marcação nas fotos de teste. A velocidade das duas é a mesma.

---

## Requisitos

* No brick: `opencv-python`, e `ncnn` para o NCNN (já instalados no `~/meu_venv`).
* No PC, para exportar: `pip install ultralytics`; para o NCNN, também `pip install ncnn pnnx` (se faltar,
  o `yolo export` tenta instalar).
