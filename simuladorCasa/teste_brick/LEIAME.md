# Testes no Mariola (câmera, rede neural e voz)

Programas para medir no próprio brick o que o robô de casa vai precisar, antes de o robô existir: a
webcam com uma rede de detecção (YOLO), a fala (Piper) e o ouvido (faster-whisper).

## No brick (13/11/2026)

Brick `192.168.2.110` (Banana Pi M4 Zero, 4 × Cortex-A53, 2 GB, Armbian Bookworm, raiz somente
leitura, `/home` de 990 MB). Tudo fica em `~/robo_casa/`, sem mexer no sistema:

| pasta / arquivo | o que é |
|---|---|
| `testa_camera.py`, `testa_voz.py` | estes programas |
| `voz.py` | cópia do `exemplo_casa/voz.py` (o mesmo `Boca` e `Ouvido` do simulador) |
| `pacotes/` (242 MB) | Piper, faster-whisper e dependências, instalados com `pip install --target` (o venv do brick, `/meu_venv`, fica na raiz somente leitura) |
| `modelos/` | `yolo11n.pt`, `yolo11n.onnx` e `yolo11n_ncnn_model/` (320 px; exportados no PC, veja abaixo) |
| `vozes/` | a voz `pt_BR-cadu-medium` do Piper |
| `hf/` | os modelos tiny e base do Whisper (baixados pelo faster-whisper) |
| `saida/` | fotos e áudios dos testes |

O `/meu_venv` já tinha OpenCV, numpy, onnxruntime, ncnn, PyTorch e Ultralytics. Para a voz:

```bash
cd ~/robo_casa
export PYTHONPATH=~/robo_casa/pacotes HF_HOME=~/robo_casa/hf
/meu_venv/bin/python testa_voz.py --circuito             # fala as frases de teste e transcreve
/meu_venv/bin/python testa_voz.py --ouve 6 --modelos base # grava 6 s do microfone e transcreve
/meu_venv/bin/python testa_camera.py --gira 180          # câmera montada de cabeça para baixo
```

Para mandar de novo do PC: `scp exemplo_casa/voz.py teste_brick/*.py banana@192.168.2.110:robo_casa/`.

**Exportar o YOLO no brick não funciona:** o `torch.onnx` do `/meu_venv` morre com "instrução ilegal"
(código 132) no Cortex-A53. Exportei no PC (`ultralytics` 8.4.75):
`YOLO('yolo11n.pt').export(format='ncnn', imgsz=320)` (e `format='onnx', opset=17`) e copiei com `scp`.

## Servidor de voz (o PC ouve e fala pelo robô)

Divisão decidida em 13/11/2026: o brick roda o robô (motores, câmera, localização, rosto, cérebro pela
API) e grava o microfone; o PC transcreve (Whisper grande), diz quem falou e gera a fala, que o brick
toca. Sem o PC, o brick fala sozinho com o Piper (mais devagar) e não ouve.
O PC fala com a `cadu_desenho` (Piper). A voz é sempre gerada localmente, sem internet (decisão do Julio
em 14/11/2026).

* `exemplo_casa/servidor_voz.py` (PC): HTTP em 127.0.0.1:8765. `/ouve` (wav → texto, quem), `/fala`
  (texto → wav), `/apresenta`, `/esquece`, `/saude`.
* `exemplo_casa/voz_brick.py` (brick): `Microfone` (arecord numa thread, frase pelo volume: começo = 3×
  o ruído por 90 ms, fim = 0,8 s quieto; manda mono 16 kHz), `VozRemota` (o cliente), `AltoFalante`
  (fala pelo PC e toca com o aplay; sem o PC, Piper no brick).
* `teste_brick/conversa_eco.py`: a pessoa fala, o robô responde "Entendi: ...".

**O PC está numa rede "Pública" do Windows** e o firewall não deixa o brick chegar nele (nem o ping).
Sem mexer no firewall, quem abre a conexão é o PC: um túnel do SSH (`ssh -R 8765:127.0.0.1:8765
banana@192.168.2.110 ...`); no brick o servidor fica em http://127.0.0.1:8765.

```
python exemplo_casa/servidor_voz.py
ssh -R 8765:127.0.0.1:8765 banana@192.168.2.110 "cd ~/robo_casa && PYTHONPATH=~/robo_casa/pacotes /meu_venv/bin/python conversa_eco.py"
```

Primeiro teste (13/11, webcam UC60, sem caixa de som): "Então eu tenho que ficar falando alguma coisa
com o Bombertinho, é isso? Eu não sabia." certinho; **do fim da fala até a resposta pronta, 1,5 s**
(0,95 s até o texto, 0,76 s disso no PC; 0,56 s para a fala). A voz do Julio não foi reconhecida (foi
guardada com o microfone do PC; outro microfone, outra "assinatura"). Três barulhos curtos da sala
(1,1-1,4 s) passaram do limite do microfone: o filtro de voz do Whisper os descartou. Sem esse filtro o
Whisper "ouve" neles a própria dica ("Bombertinho, me ajuda."): ele tem de ficar sempre ligado.

Segundo teste (13/11, `--apresenta Julio`): já na primeira frase, antes de guardar nada pela webcam, a
voz foi reconhecida (Júlio 0,53; limite 0,45). Guardadas 3 amostras pela webcam (o Júlio ficou com 6:
3 do microfone do PC + 3 da webcam); as frases seguintes deram 0,56 e 0,63. Do fim da fala até a
resposta pronta: 0,7 a 1,5 s. Uma frase saiu "Obrigado." sem dono reconhecido, com o filtro de voz
ligado; o Julio acha que não disse. Era invenção: reprocessado, o mesmo áudio deu "Bombertinho." (o
Whisper puxa da dica ou das invenções típicas dele), e o filtro de voz só achou 0,46 s de fala em 2,4 s.
Palavras soltas de verdade ("Para!", "Sim.", "Não.", "Vai.", 6 vozes de teste, com e sem ruído) dão 1,38 s
ou mais pela mesma medida (o filtro soma uma folga em volta da fala). Regra no `Ouvido.transcreve`:
menos de `MIN_FALA_S` = 0,8 s de fala = barulho, texto vazio. A confiança do Whisper (`avg_logprob`)
não separa: palavra solta de verdade também tem confiança baixa. No mesmo teste, palavra solta sozinha
saiu errada várias vezes ("Para!" virou "Bombertinho." ou "Ai."); com o nome antes ("Bombertinho,
para!") saiu certo em todas as vozes. Circuito fechado do PC continuou 16/16.

## O rosto na tela do brick

`testa_rosto.py` (com o `exemplo_casa/rosto.py` copiado para `~/robo_casa/`): desfile das 28 carinhas,
`--carinha nome`, `--mede`, `--brilho`; `ROSTO_GIRA=2` se a tela ficar de cabeça para baixo.

O **menu do brick** (`menuPrincipal.service` → `start.sh` → `start.py`, usuário banana) usa a mesma
tela. O `sudo` pede senha, então em vez de parar o serviço o teste **pausa** o menu e o devolve depois:

```bash
M=$(pgrep -f '^python3 /home/banana/menuPrincipal/start.py')
kill -STOP $M      # ... teste ...
kill -CONT $M
```

Cuidado: `pgrep -f menuPrincipal/start.py` sem o `^` acha também o próprio comando (a linha dele tem
esse texto) e o pausa junto. Aconteceu no primeiro teste. E pelo PowerShell as aspas de dentro de um
`ssh ... "..."` somem: o comando do pgrep com aspas falha (o Julio teve erro com ele).

O Julio preferiu **parar o menu** durante os testes: `kill` no `start.sh` (o laço) e no `start.py`, sem
`sudo`. O serviço tem `Restart=on-failure` e um `kill` normal conta como saída limpa, então ele fica
`inactive` até o brick religar. Com o menu parado, basta:

```
ssh banana@192.168.2.110 "cd ~/robo_casa && /meu_venv/bin/python testa_rosto.py --carinha zoeiro --tempo 10"
```

Primeiro teste (13/11/2026, tela SSD1309 de 2,42" no conector TELA): abre como `ssd1309` em 0,2 s;
**mandar um quadro: 101 ms (~10 quadros por segundo)**, desenhar: 1,2 ms. Os 101 ms são o I2C a
100 kHz (1 KB por quadro); a 400 kHz seriam ~25 ms, mas isso é configuração do Linux do brick (o
overlay do i2c0) e não foi mexido. O `Rosto` desenha no máximo 8 quadros por segundo e só manda a
imagem quando ela muda, então dá. O desfile das 28 carinhas e da boca falando rodou inteiro.

## Resultados

Webcam UC60 na porta 3 (`/dev/video_usb3`), microfone dela = placa de som `Video` (`plughw:CARD=Video`).

| o quê | tempo no brick |
|---|---|
| captura 640 × 480 (MJPG) | 50 ms por quadro (20 por segundo) |
| YOLO11n ncnn, 320 px | 144 ms por quadro: **~5 quadros por segundo** com a captura |
| YOLO11n ONNX (onnxruntime), 320 px | 233 ms: ~3,5 quadros por segundo |
| Piper, voz cadu com o efeito "desenho" | 0,8 s por segundo de fala (um pouco mais rápido que falar); ~1,8 s até a primeira frase curta estar pronta |
| Whisper tiny (int8, 4 núcleos) | ~5 s para 2-3 s de fala, erra muito ("Bom beitinho. Vai pra cozinhar.") |
| Whisper base | ~9-10 s para 2-3 s de fala, quase certo; `beam_size=1` quase não muda (8,5 s) |
| Whisper large-v3-turbo **no PC** (RTX 5060 Ti) | 0,15-0,25 s para 10 s de áudio |

Conclusões:

* **Câmera e rede neural no robô: dá.** 5 quadros por segundo bastam para chegar devagar num objeto.
  A rede do robô (roupa / brinquedo / deixa) tem o tamanho da YOLO11n, então deve ficar parecida.
* **Falar no robô: dá**, frase por frase.
* **Ouvir no robô: não dá** com o Whisper (2,5 a 4 vezes mais lento que a fala). O brick grava e manda o
  áudio para o PC, que transcreve em menos de meio segundo. Se for preciso ouvir sem o PC (só o nome,
  "para!"), o caminho é um reconhecedor pequeno feito para isso (não testado).
* A webcam desta montagem está de cabeça para baixo (`--gira 180`). A rede achou a pessoa mesmo assim,
  mas às vezes a chamou de cachorro.
* **O microfone da webcam UC60 é ruim:** só manda 8 bits sem sinal (U8), estéreo, a 22, 44 ou 48 kHz
  (`/proc/asound/card2/stream0`), começa com um estalo forte (~1 s) e tem um nível contínuo que vai
  mudando (90% da energia abaixo de 100 Hz). Gravando pelo `plughw` a 16 kHz, nem o Whisper grande do
  PC achava fala (o filtro de voz jogava tudo fora; sem ele, inventava "Obrigado."). Agora o
  `testa_voz.py` grava cru (`hw:CARD=Video`, U8, 2 canais, 48 kHz), joga fora o estalo e limpa (tira a
  média de cada 10 ms e põe o volume no máximo). Com isso, a mesma fala do Julio: PC (large-v3-turbo)
  "Ei, estou falando aqui"; brick tiny "Estou falando..." (4,6 s para 8,8 s); base "E estão falando..."
  (7,9 s). O ganho do microfone estava em 50% (0 dB); subi para 100% (+12 dB) com
  `amixer -c Video sset Mic 100%` (não fica salvo: a raiz é somente leitura). Para o robô, um microfone
  USB de verdade (16 bits) deve ajudar muito; o Julio vai comprar um.
* Segundo teste (sem o ventilador ligado, o Julio falando normal e andando pela sala, ~10 s): base no
  brick "Eu tô procurando, cara, eu não tô te achando não. Bombertinho, hein, então aqui tá uma bagunça e
  isso vai precisar de me ajudar aí." (quase perfeito, com o nome; 14,3 s para 9,8 s de fala); tiny
  "...Um beijinho. Então, aqui está um baguão sensuais..." (8,4 s); PC large-v3-turbo, a frase certa
  mas com "humberto" no lugar do nome. O ventilador ligado no primeiro teste atrapalhava muito.
* Limpeza: o Julio ouviu os dois e achou o áudio original (sem o estalo) melhor que o limpo. No PC, só
  tirar o estalo entende igual ou melhor que a limpeza forte (média de 10 ms + volume), que perdia "Ei"
  e "aqui". O `limpa()` passou a tirar a média de cada 50 ms (só o nível de fundo que vai mudando).
* **O nome:** o Whisper não conhece "Bombertinho" e escrevia "Humberto" (o `chamou()` do `voz.py` não
  aceita: 0,67 de parecido, precisa de 0,78). A dica antiga ("Comandos para o robô Bombertinho. <cômodos>.")
  diluía o nome; a `hotwords` sozinha não bastava. A dica nova do `Ouvido` (`voz.py`) é o nome em frases
  curtas, "Bombertinho, vai para a cozinha. Bombertinho, me ajuda." + os cômodos, com a
  `hotwords='Bombertinho'`: saiu "Bombertinho" em todas as 12 combinações testadas (com e sem filtro
  de voz, com e sem carimbos de tempo, cômodos antes ou depois). O teste de circuito fechado do PC
  (`exemplo_casa/testa_voz.py`) continuou 16/16.
