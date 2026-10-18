# Bibliotecas dos exemplos: Lidar, controle Bluetooth e câmera

Estas bibliotecas ficam junto dos exemplos (não na pasta `libs/`). Copie para o seu projeto.

---

## `Lidar` — lidar 360° (protocolo Neato XV-11)

Arquivo: `exemplos/06-lidar/sensorLidar.py` · `from sensorLidar import Lidar`

Um lidar giratório que mede a distância em **todos os ângulos** (0 a 359°), de 100 a 3000 mm.
Útil para mapear paredes em volta do robô, achar a saída da área de resgate, ver obstáculos.

| Método / propriedade | Faz |
|---|---|
| `Lidar(porta_serial, pino_liga=None)` | abre a serial (115200). `pino_liga` (ex.: `PinosDigitais.P7`) liga o motor do lidar por um relé |
| `liga()` / `desliga()` | liga/desliga o motor pelo pino |
| `pontos(angulo_inicio=0, angulo_fim=359)` | lista `[(angulo, distancia_mm), ...]` só com leituras válidas. Início > fim cruza o 0° (ex.: 340 a 20) |
| `velocidade` | rotação do motor em RPM |
| `conectado` | `True` se chegaram dados nos últimos 2 s |
| `fechar()` | para a thread, desliga o motor e fecha a serial |

```python
lidar = Lidar(Portas.SERIAL6, pino_liga=PinosDigitais.P7)
frente = lidar.pontos(340, 20)
```

* Com `pino_liga`, a classe cria um `PinosDigitais` por dentro: não crie `Botoes()` no mesmo
  programa (use `PinosDigitais` para tudo).
* Não é emulado no simulador.

---

## `ControleRemotoBluetooth` — dirigir o robô pelo celular

Arquivo: `exemplos/12-controleRemotoBluetooth/controleRemotoBluetooth.py`

Lê um módulo **HC-05** (Bluetooth serial, 9600 baud) com o app Android **BT Controller** no modo
analógico. Bom para testar mecânica (tração, garra) e para demonstrações.

| Método / propriedade | Faz |
|---|---|
| `ControleRemotoBluetooth(porta, leitura_continua=True)` | abre a porta; com leitura contínua uma thread atualiza os valores |
| `frente_tras` | -100 (ré) a +100 (frente) |
| `esquerda_direita` | -100 (esquerda) a +100 (direita) |
| `estado()` | `{'frente_tras': ..., 'esquerda_direita': ...}` |
| `ler()` | lê um pacote (quando `leitura_continua=False`) |
| `parar()` | para a thread e fecha a porta |

```python
e = ctrl.estado()
motores.potencia_motores(e['frente_tras'] + e['esquerda_direita'],
                         e['frente_tras'] - e['esquerda_direita'])
```

---

## Câmera

Os exemplos de `exemplos/camera/` mostram, em ordem:

| Pasta | O que ensina |
|---|---|
| `01-streamingVLC` | transmitir a imagem da câmera (Flask) para ver no navegador/VLC em `http://IP:8080/video` (atraso de alguns segundos) |
| `02-processamentoIAStreaming` | rodar a IA (PyTorch) e transmitir a imagem com as detecções |
| `03-posicionamentoDeteccao` | detectar com YOLO e marcar posição e área de cada objeto |
| `03-posicionamentoDeteccaoONNX` / `NCNN` | o mesmo sem PyTorch: OpenCV DNN com ONNX, ou NCNN — inicia muito mais rápido e roda melhor no Banana Pi (instruções de conversão do modelo no próprio arquivo) |
| `04-detectandoPadraoObjetos` | OpenCV: achar retângulos de uma cor (contornos) |
| `05-usandoThreads` | capturar em uma thread e processar em outra (sempre o quadro mais novo) |
| `06-projetoSalvaFotos` | salvar fotos originais e processadas para treinar a rede de novo e ver onde ela errou |
| `07-detectandoAreas` | achar áreas de uma cor por faixa HSV (ex.: os triângulos verde e vermelho) |

Para a área de resgate, o simulador da Line define uma interface simples (`visao`), descrita em
[módulos do simulador](modulos-simulador.md). No robô, `simuladorLine/robo_real/visao.py` tem o
esqueleto com a mesma interface: é onde você encaixa a YOLO e o OpenCV desses exemplos.
