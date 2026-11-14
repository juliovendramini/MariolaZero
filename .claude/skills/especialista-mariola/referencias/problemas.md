# Problemas e pegadinhas conhecidos

Cada item: sintoma → causa → o que fazer (e onde ler mais). Confira no código se ainda vale.

## Programa e bibliotecas

* **`ModuleNotFoundError: No module named 'motores'` (ou outra lib) no robô** → o robô não tem as libs
  instaladas no sistema: a pasta do projeto precisa ter uma cópia de cada lib usada e das que elas
  importam (quase todas usam `portas.py`). Copie de `libs/` (curso 2.2).
* **`from botoes import Botoes` quebra** → a classe `Botoes` foi juntada ao `PinosDigitais` em 27/10/2026
  (as duas disputavam os pinos). Use `PinosDigitais` (`le_botao`, `botao_pressionado`, `LIBERADO`,
  `APERTADO`). `curso/referencia/botoes.md` explica a troca.
* **Pinos digitais não funcionam no brick novo (kernel 6.18)** → lib antiga com o `gpiochip0` fixo; no 6.18
  o PIO principal é o `gpiochip1`. A `libs/pinosDigitais.py` atual acha o chip pelo rótulo: copie de novo.
* **P8 indisponível** → a linha está em uso pelo PWM (ventoinha/buzzer). Outro pino ou não usar o PWM.
* **Teclado não responde na placa atual** → a placa atual (tela + teclado numa PCB, conector TELA) está no
  I2C 0: `Teclado(i2c_bus=0)`. O padrão `i2c_bus=1` é da placa antiga. LEDs do teclado acendem com bit 1;
  ao ligar ficam todos acesos e `Teclado()` apaga (curso 8).
* **Sensor de cor dá cor errada / branco vira vermelho** → `libs/sensorCorReflexao.py` ainda é a V1
  (protocolo antigo). Com o sensor Pro1616 use a **V2** de `exemplos/11-sensorCorReflexaoV2/` e aprenda as
  cores no campo (`aprende_cor`, `salva_cores`/`carrega_cores`, `usa_cores`). Branco do TCS ≈ 127 (vem
  pela metade); prata passa de 127; no IR a fita prata fica ~80, abaixo do branco (~100). Na V2,
  `detectar_cor(...)` é método da instância (era `staticmethod`). Doc: `documentação/CorReflexaoV2.md`.
* **Giroscópio "vira ao contrário"** → na lib o Z é positivo no sentido **horário**; o curso usa positivo
  = esquerda trocando o sinal numa função só (curso 5).
* **Giroscópio lento/atrasado na rampa** → firmware antigo do giroscópio (filtro por eixo, ~1 s de atraso
  nos giros em cima da rampa; amostra perdida = ângulo menor). O firmware novo (FIFO a 100 Hz, vetor da
  gravidade) corrige: peça ao professor para regravar.
* **`Portas.abre_porta_serial` "funciona" mas nada responde** → com o conversor ausente ela devolve um
  Serial **fechado**, não `None`. Teste `porta.is_open` e confira o cabo/porta (curso referência portas).
* **VL53 para de responder (`OSError`/`TimeoutError`, ou "Sensor não encontrado") depois de um Ctrl+C,
  e só volta desligando o robô** → `vl53.py` antigo (antes de 09/11/2026). O Ctrl+C no meio de uma
  sequência deixava o sensor no banco de registradores errado (0xFF = 1) e a inicialização seguinte o
  travava (passava a recusar quase todos os registradores). A lib nova reinicia o sensor por software
  (0xBF) antes de inicializar e no `recover()`: não precisa de fio no XSHUT. Copiar o `libs/vl53.py`
  atual para o robô. Medido num Mariola: 8 travamentos em 300 Ctrl+C com a lib antiga, 0 em 400 com
  a nova. Se travar **sem** Ctrl+C, é outra coisa (cabo, ruído dos motores, alimentação).
* **Leitura I2C travando ou com lixo usando threads** → o I2C só pode ser usado por uma thread (curso 7).
* **Motor dispara na velocidade máxima com qualquer velocidade pedida (ou quando o HOLD liga), só em
  velocidade e não em potência** → o encoder conta ao contrário do motor (cabo ou motor diferente). Com
  o firmware de 10/11/2026 em diante basta calibrar de novo (`calibra_motores()` no brick, `calibrar()`
  na placa de motor, rodas no ar): a calibração descobre a polaridade e corrige. `estado_calibracao_motores()`
  mostra `'encoder_invertido'` e o `'resultado'`. Com firmware antigo, trocar os dois fios do motor **ou**
  os canais A/B do encoder. Roda girando para trás é outra coisa: `direcao_motor()`.
* **Um motor não anda nos comandos de velocidade, mas anda em potência** → está sem calibração (a última
  calibração deu `'o encoder não contou'`: encoder ou motor desligado, fio do encoder solto). Confira o
  cabo e calibre de novo.
* **`Exception: Erro ao ler o estado dos motores` (ou dos servos, do LED) no meio da rodada, com o robô
  andando, e no `dmesg` `usb 1-1: reset high-speed USB device number 2`** → o hub USB do brick reiniciou.
  Atrás dele ficam os conversores do Mariola e das placas de motor (`_SERIAL0` a `SERIAL3`; giroscópio e
  sensor de cor nas `SERIAL4`-`6` são UART do Banana Pi e não caem). Quase sempre é elétrico: queda dos
  5 V (bateria fraca, motor travado ou partindo forte) ou ruído dos motores (capacitor de 100 nF nos
  terminais, fios trançados, longe do cabo USB; conector do hub firme). Conferir logo depois do erro:
  `dmesg -T | tail -40` (o horário bate; `ch341-uart ... disconnected` = os seriais caíram). Até 12/11/2026
  a lib desistia em 10 ms e o programa morria com os motores girando até o timeout de 5 s; desde 12/11 o
  `libs/motores.py` espera a resposta até 50 ms, reabre a porta (achada de novo pelo lugar no hub, porque
  o `ttyUSB` pode mudar) e manda de novo por até 3 s (`TEMPO_RECUPERACAO`; `falhas_comunicacao` conta), e
  a `placaControleMotor.py` reabre a porta quando ela cai. Comando com ângulo não é mandado duas vezes se
  já tinha chegado. Precisa das três libs novas (`motores.py`, `placaControleMotor.py`, `portas.py`); a
  equipe que usa `libs.portas` troca só o `from portas import Portas` por `from libs.portas import Portas`.
* **Motores continuam girando depois de um erro** → falta `try/finally` parando os motores (curso 3). Com
  `Motores(False)` nada muda até `atualiza_motores()` (curso 4).
* **Servos comuns, ventoinha e buzzer brigando** → os três dividem o Timer2 do ATmega: desde o firmware de
  26/10/2026 o primeiro que for usado fica com ele até reiniciar (`documentação/Motores.md`).

## Menu, envio e Linux do brick

* **Arquivo salvo/aberto "some" quando roda pelo menu** → o menu roda com a pasta atual em `/home/banana`:
  `open('cores.json')` vai para `/home/banana/cores.json`. Monte o caminho a partir de `__file__`
  (curso 2.5).
* **O log do programa aparece atrasado ou vazio** → saída em arquivo é guardada em blocos: no começo do
  `main.py`, `sys.stdout.reconfigure(line_buffering=True)`, ou um `main.sh` com `python3 -u` (curso 2.5).
  Logs em `/home/banana/logs/NNNNNN.log` e `NNNNNN_erro.log`.
* **`ssh`/`envia` pede senha toda vez** → configurar a chave SSH (curso 2.3).
* **`REMOTE HOST IDENTIFICATION HAS CHANGED`** → o IP agora é de outro robô (ou regravado):
  `ssh-keygen -R IP` e conectar de novo.
* **Robô regravado pela imagem e a chave parou** → regravar a eMMC apaga as chaves copiadas: copie de novo.
* **Sem IP na tela** → porta de debug serial a 115200 (curso 2.3); TX e RX trocados é o erro mais comum.
* **`apt`/`pip` falham com "Read-only file system"** → a partição do sistema é somente leitura: menu →
  Desbloquear (ou `sudo mount -o remount,rw /`); volta ao reiniciar. `/home/banana` é gravável (curso 2.6).
* **`envia.sh` dá `$'\r': command not found`** → o arquivo pegou quebra de linha do Windows:
  `sed -i 's/\r$//' envia.sh`.
* **F5 do VS Code não envia no Linux** → escolher "Enviar para o robô (Linux/macOS: envia.sh)" no painel
  Executar e Depurar uma vez, ou usar Ctrl+Shift+B; abrir a pasta do projeto, não a de cima (curso 2.4).

## Simulador x robô

* **Funciona no simulador e não no robô** → limitações do simulador: motor ideal (a rotação não cai com
  carga), VL53 sem leitura "velha", barramento de servos/placas ideal. Ver `curso/17-do-simulador-para-o-robo.md`
  e o item de limitações do README do simulador. Ajuste no robô: ganhos, velocidades, tempos.
* **Mesma semente, resultado diferente?** → não deveria: o relógio do simulador é sincronizado (mesma
  semente = mesma rodada). Se mudou, mudou o programa, o robô (`.json`) ou o mapa.
* **Laboratório com Windows travado** → simulador portátil (`Simulador.bat`, sem instalar nada).
