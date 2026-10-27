# `Motores` — motores, encoders, servos comuns e LEDs da placa do Mariola

Arquivo: `libs/motores.py` · `from motores import Motores`

## Para que serve

Dentro do brick há uma placa com um **ATmega328PB** ligada ao Banana Pi pela serial interna
(`_SERIAL0`). É ela que gera o PWM dos motores, conta os encoders, faz o **PID de velocidade**,
move os **servos comuns** e acende os **LEDs RGB**. A classe `Motores` conversa com essa placa.

| Saída | Quantas | Detalhe |
|---|---|---|
| Motores 1 e 2 | 2 | **com encoder**: velocidade com PID, giro por ângulo, leitura da contagem |
| Motores 3 e 4 | 2 | sem encoder: potência direta, ou "copiando" o PID dos motores 1 e 2 (modo 4x4) |
| Servos | 4 conectores (o protocolo tem 6 posições) | servo comum de hobby, 0 a 180° |
| LEDs RGB | 10 (índices 0 a 9) | fita de LEDs endereçáveis |

## Como a conversa funciona (importante para entender os métodos)

A lib guarda os valores em listas (`lista_motores`, `lista_servos`) e **só manda para a placa
quando um método de envio é chamado**. Cada envio é um pacote de 10 bytes, e a placa responde com
a contagem dos encoders e o estado dos motores.

* **`Motores(True)`** (atualização instantânea): todo método que muda um valor já envia. Fácil, bom
  para começar e para testes.
* **`Motores(False)`**: os métodos só mudam a lista; **você** chama `atualiza_motores()` ou
  `atualiza_servos()` quando quiser enviar. Bom no laço de controle: você muda os dois motores e
  manda **um** pacote só (mais rápido, os dois mudam juntos).

**Unidade de velocidade:** `100` = a velocidade de calibração guardada na EEPROM da placa (por
padrão ~80% da rotação livre do motor). O PID tenta manter essa velocidade mesmo com carga, na
subida, com bateria mais fraca. `-100` = mesma coisa para trás.

**Unidade de "ângulo":** contagens do encoder (não são graus!). O Mariola conta as duas bordas de
um canal do encoder: `contagens por volta da roda = pulsos do encoder × redução × 2`. Ex.: motor
com 17 pulsos e redução 34 → 1156 contagens por volta da roda.

**Segurança — timeout de 5 s:** se a placa ficar **5 segundos sem receber nenhum pacote**, ela
solta os motores e **apaga todos os LEDs**. É proteção para o robô não sair andando sozinho se o
programa travar. Consequência: **nunca dê `time.sleep()` longo sem mandar nada** quando os motores
ou LEDs precisam continuar como estão (espere em um laço que reenvia o comando).

## Criando o objeto

### `Motores(atualiza_instantaneo=False)`
Abre a serial interna (250000 baud), envia motores e servos zerados e zera a referência dos
encoders. Lança `Exception('Erro ao abrir a porta serial')` se a placa não for encontrada.

```python
motores = Motores(True)
motores.direcao_motor(2, Motores.INVERTIDO)   # quase sempre um lado é espelhado
```

* Crie **um só** objeto `Motores` no programa inteiro e passe-o para quem precisar.
* Quando o objeto é destruído (fim do programa), `__del__` chama `para_motores()` e fecha a
  serial. Com `Motores(False)` o `para_motores()` não envia nada: pare você mesmo no `finally`.

## Constantes

| Constante | Valor | Uso |
|---|---|---|
| `NORMAL`, `INVERTIDO` | 0, 1 | `direcao_motor()` |
| `BREAK`, `HOLD` | 0, 1 | `set_modo_freio()`: solto / segura parado |
| `PARADO`, `GIRANDO_NORMAL`, `GIRANDO_INVERTIDO` | 0, 1, 2 | `estado_motor()` |
| `DEBUG` | False | `True` imprime cada pacote (deixa lento) |

## Métodos de movimento

### `direcao_motor(motor, direcao)`
Diz se o motor (1 a 4) está montado invertido. Depois disso, velocidade positiva = robô para
frente nos dois lados, e `angulo_motor()` também já vem com o sinal certo.

* **Quando usar:** uma vez, logo depois de criar o objeto. Os motores de um lado do robô ficam
  espelhados em relação ao outro lado, então um deles precisa de `INVERTIDO`.
* **Como descobrir:** mande `velocidade_motores(30, 30)`; a roda que girar para trás é a invertida.

### `velocidade_motor(motor, velocidade)`
Velocidade de **um** motor (1 a 4), de -120 a 120. Nos motores 1 e 2 é velocidade com PID; nos
motores 3 e 4 (sem encoder) o valor vira **potência direta**.

* **Quando usar:** quando só um motor muda (ex.: um motor de esteira transportadora, um rolo).

### `velocidade_motores(velocidade1, velocidade2)`
Velocidade dos motores 1 e 2 juntos (-120 a 120). É o comando principal de um robô de duas rodas
ou duas esteiras: `velocidade_motores(ve, vd)`.

* **Quando usar:** em todo laço de controle (seguidor de linha, andar reto, girar).
* **Dica:** a diferença entre os dois lados é o que faz o robô virar. `(40, 40)` reto,
  `(20, 60)` curva para a esquerda, `(-30, 30)` gira no lugar para a esquerda.

### `velocidade_motores_4x4(velocidade1, velocidade2)`
Como `velocidade_motores`, mas o motor 3 recebe o mesmo controle do motor 1 e o 4 o do 2 (os
motores sem encoder "copiam" o PID dos com encoder). Faixa -100 a 100.

* **Quando usar:** robô com 4 motores todos ligados no Mariola (2 com encoder, 2 sem).

### `potencia_motor(motor, potencia)` / `potencia_motores(p1, p2)` / `potencia_motores_4x4(p1, p2)`
**Potência PWM direta** (-100 a 100), **sem PID**. O encoder continua contando.

* **Quando usar:** quando você quer a força bruta e não a velocidade: empurrar um obstáculo,
  teste de motor, controle feito por você mesmo, motor sem encoder.
* **Diferença para a velocidade:** com potência 40 o robô anda mais devagar na subida e mais rápido
  na descida; com velocidade 40 o PID compensa. Para seguir linha e andar distâncias, prefira
  velocidade.

### `move_motor(motor, velocidade, angulo)` / `move_motores(v1, a1, v2, a2)` / `move_motores_4x4(v1, a1, v2, a2)`
Gira o motor (só 1 e 2, que têm encoder) **um número de contagens** e para sozinho. `angulo` de 0
a 32767 (a placa lê como número com sinal de 16 bits: acima disso o motor para na hora). O sentido
vem do sinal da velocidade.

```python
motores.move_motores(40, 1156, 40, 1156)    # uma volta da roda nos dois motores
```

* **Quando usar:** movimentos curtos e exatos sem precisar de laço: andar 1 ladrilho, recuar 5 cm.
* **Como esperar terminar:** em laço, `estado()` e `estado_motor(1) == Motores.PARADO`
  (veja o [tutorial 4](../04-motores-e-encoders.md)).
* **Cuidados:**
  * com `Motores(True)` o método já envia e espera 50 ms;
  * `angulo` 0 **não cancela**: mantém o alvo anterior. Para cancelar, mande velocidade 0;
  * ao chegar no alvo o motor para, mas **a velocidade fica guardada**: o próximo pacote de motor
    (qualquer `velocidade_motor`, `atualiza_motores`...) faz ele voltar a girar sem fim. Depois de
    chegar, mande `velocidade_motores(0, 0)`. Para só acompanhar, use `estado()`, que não reenvia;
  * o robô passa um pouco do alvo (inércia). Para precisão, desacelere perto do fim.

### `para_motores()`
Velocidade 0 nos quatro motores (modo 4x4). Com `Motores(False)`, chame `atualiza_motores()`
depois (senão nada é enviado).

### `set_modo_freio(modo)`
`Motores.BREAK` (padrão): parado, o motor fica livre. `Motores.HOLD`: parado, a placa **segura**
o motor. O valor vai junto no próximo pacote de motores (não envia sozinho).

* **Quando usar `HOLD`:** parar em rampa sem escorregar, ficar parado num lugar exato.

### `pid_motor(kp, ki, kd)`
Grava as constantes do PID de velocidade **na EEPROM** da placa (multiplicadas por 100: de 0 a
655,35). Demora ~1,1 s. Lança exceção se a placa não confirmar.

* **Quando usar:** só quando for ajustar o PID; não precisa chamar em todo programa (fica gravado).

## Métodos de leitura (encoders)

### `atualiza_motores()`
**Envia** o pacote de motores e **lê** a resposta: contagem dos encoders e estado. Lança
`Exception('Erro ao ler o estado dos motores')` se a placa não respondeu certo.

* **Quando usar:** com `Motores(False)`, uma vez por volta do laço, depois de definir as
  velocidades. Com `Motores(True)` os métodos já chamam por você.

### `estado()`
**Só lê** contagens e estado, sem mudar nada nos motores. Mantém a placa "acordada" (conta como
pacote para o timeout de 5 s).

* **Quando usar:** para ler encoders sem reenviar velocidade (principalmente depois de
  `move_motor`), e para manter a placa viva enquanto espera.

### `angulo_motor(motor)`
Contagem do motor 1 ou 2 desde o último `reseta_angulo_motor`, já com o sinal certo (respeita
`direcao_motor`). **Não lê da placa**: devolve o valor recebido no último `atualiza_motores()` ou
`estado()`. Chame um deles antes.

### `reseta_angulo_motor(motor)`
Zera a referência do motor 1 ou 2. Não mexe na placa: só guarda o valor atual para descontar.

* **Cuidado:** o "valor atual" é o do último pacote. Para zerar exatamente agora, faça
  `motores.estado()` e depois `reseta_angulo_motor(...)`.

### `estado_motor(motor)`
`PARADO`, `GIRANDO_NORMAL` ou `GIRANDO_INVERTIDO` para o motor 1 ou 2 (do último pacote).

### Distância andada (receita)

```python
import math
MM_POR_CONTAGEM = math.pi * DIAMETRO_RODA_MM / CONTAGENS_POR_VOLTA
motores.estado()
mm = (motores.angulo_motor(1) + motores.angulo_motor(2)) / 2 * MM_POR_CONTAGEM
```

Lembre: a roda patina (curva, arranque, empurrando parede). O encoder mede a roda, não o robô.

## Calibração de velocidade

### `obtem_calibracao_motores()`
Devolve `(calibracao_motor1, calibracao_motor2)`: a velocidade (contagens a cada 25 ms) que vale
"100". Serve para conferir e para o simulador ficar igual ao seu robô.

### `calibra_motores()`
Manda a placa medir a velocidade máxima dos motores e gravar a calibração. **Os motores giram
sozinhos** e a placa fica ~26 s sem responder. Faça com o robô **suspenso** (rodas no ar).

* **Quando usar:** motor novo, troca de redução/roda, robô andando torto com velocidades iguais.

## Servos comuns

### `move_servo(servo, angulo)`
Servo comum ligado nos pinos amarelos (1 a 4), de 0 a 180°. Com `Motores(False)`, envie com
`atualiza_servos()`.

### `desativa_servo(servo)`
Para de mandar pulso (o servo fica solto e para de consumir/forçar).

### `atualiza_servos()`
Envia a lista dos servos.

* **Quando usar servo comum:** mecanismos simples (uma alavanca, uma porta) em que não é preciso
  saber a posição real. Para garra com leitura de posição e detecção de travamento, use os
  [servos inteligentes](placaControleServo.md).

## LEDs RGB

### `set_led_rgb_all(r, g, b)` · `set_led_rgb_one(indice, r, g, b)`
Acende todos os LEDs, ou um (índice 0 a 9), com a cor (0 a 255 cada). Enviam na hora (não
dependem de `atualiza_instantaneo`). A fita fica na coluna **LEDs** do header amarelo (a 5ª, depois
dos 4 servos).

* **Quando usar:** indicar estado do programa (ótimo para depurar sem tela!), iluminar as
  câmeras, sinalizar vítima na Maze.
* **Cuidado:** o timeout de 5 s apaga os LEDs. Se o programa fica parado esperando o botão, os
  LEDs apagam: reacenda depois.

### `set_led_rgb_all_porta4(r, g, b)` · `set_led_rgb_one_porta4(indice, r, g, b)`
Uma **segunda fita de LEDs** (WS2812B, 10 LEDs, índice 0 a 9) ligada na coluna **SERVO 4** do
header amarelo.
Funcionam como as de cima. Precisam do firmware do Mariola de 19/10/2026 ou mais novo.

* A porta 4 é servo **ou** fita de LEDs, conforme o último comando: o primeiro comando de LED
  desliga o servo 4; `move_servo(4, angulo)` apaga a fita e a porta volta a ser servo.
* **Cuidado:** não ligue um servo e uma fita na porta 4 ao mesmo tempo.

## Ventoinha

### `set_ventoinha(potencia)` · `desliga_ventoinha()`
Liga a ventoinha com potência de 0 a 100 (%). Ela vai na coluna **DEBUG/PWM** do header amarelo
(a 6ª, a última; é o pino 11 do ATmega). `desliga_ventoinha()` é o mesmo que `set_ventoinha(0)`.

* Antes do primeiro `set_ventoinha`, essa coluna é o **TX do serial de debug do ATmega** (115200
  bps): dá para ver as mensagens do firmware com um conversor USB-serial. Depois, vira PWM até o
  brick reiniciar.

* **Cuidado 1:** servos comuns, ventoinha e buzzer usam o mesmo timer do ATmega: **o primeiro que
  for usado fica com ele até o brick reiniciar** (veja "Um de cada vez", mais abaixo).
  Depois de `set_ventoinha`, `move_servo` e o buzzer dão erro. Os
  [servos inteligentes](placaControleServo.md) não são afetados.
* **Cuidado 2:** o timeout de 5 s **não** desliga a ventoinha. A lib desliga quando o objeto
  `Motores` é destruído (fim normal do programa), mas se o programa travar ela continua girando.

## Buzzer

O buzzer vai na coluna **DEBUG/PWM** do header amarelo, a mesma da ventoinha (precisa do firmware
do Mariola de 26/10/2026 ou mais novo). Quem toca é o ATmega: **a função volta na hora** e o robô
continua andando, lendo sensores e mandando comandos enquanto o som toca.

### `toca_som(som, vezes=1, velocidade=100, esperar=False)`
Toca um som pronto.

* `som`: uma das constantes da tabela abaixo, por exemplo `Motores.SOM_SUCESSO`.
* `vezes`: quantas vezes toca. `0` repete até você chamar `para_buzzer()`.
* `velocidade`: em %, de 10 a 255. `200` toca duas vezes mais rápido, `50` na metade.
* `esperar=True`: só volta quando o som termina (útil para não emendar um som no outro).

| sinalização | melodias |
|---|---|
| `SOM_BIPE`, `SOM_BIPE_DUPLO`, `SOM_SUCESSO`, `SOM_ERRO`, `SOM_ALERTA`, `SOM_LIGANDO`, `SOM_DESLIGANDO`, `SOM_LARGADA`, `SOM_RE`, `SOM_SIRENE_DOIS_TONS`, `SOM_SIRENE`, `SOM_MOEDA`, `SOM_POWER_UP`, `SOM_LASER`, `SOM_BATERIA_FRACA`, `SOM_ROBO` | `MELODIA_ESCALA`, `MELODIA_PARABENS`, `MELODIA_BRILHA_ESTRELINHA`, `MELODIA_ODE_ALEGRIA`, `MELODIA_JINGLE_BELLS`, `MELODIA_FUR_ELISE`, `MELODIA_GRAN_VALS` (o toque de celular) |

### `toca_tom(frequencia, duracao_ms, esperar=False)`
Toca uma nota qualquer: `frequencia` em Hz (31 a 20000) por `duracao_ms` milissegundos.

### `para_buzzer()` · `buzzer_tocando()` · `espera_buzzer(timeout=None)`
Para o som; diz se ainda está tocando; espera terminar (`timeout` em segundos).

### `set_nivel_buzzer(nivel)` · `nivel_buzzer()`
O buzzer padrão do Mariola apita com o pino em **LOW** (`Motores.BUZZER_LIGA_LOW`). Se o seu apita
em HIGH, rode uma vez `motores.set_nivel_buzzer(Motores.BUZZER_LIGA_HIGH)`: fica salvo no brick.

```python
motores.toca_som(Motores.SOM_LARGADA, esperar=True)  # espera a largada terminar
motores.toca_som(Motores.MELODIA_JINGLE_BELLS)       # toca enquanto o robô anda
motores.velocidade_motores(50, 50)
```

* **Quando usar:** avisar que o robô terminou a calibração, que achou uma vítima, que viu a fita
  prata; depurar sem olhar para a tela.
* **Cuidado:** o timeout de 5 s sem comando para o buzzer. Exemplo completo em `exemplos/13-buzzer/`.

## Um de cada vez: servos, ventoinha e buzzer

Os servos comuns, a ventoinha e o buzzer dividem o mesmo timer do ATmega. O primeiro que o
programa usar fica com ele **até o brick reiniciar**, e os outros dois dão erro:

* servos: o primeiro `move_servo` (com ângulo de 0 a 180) que chega na placa;
* ventoinha: o primeiro `set_ventoinha`;
* buzzer: o primeiro `toca_som` ou `toca_tom` (`para_buzzer` e `set_nivel_buzzer` não contam).

Vale também entre programas: se o programa anterior usou o buzzer, o seguinte não consegue usar
servos até reiniciar o brick. Precisa de garra e de som no mesmo robô? Use os
[servos inteligentes](placaControleServo.md), que não usam esse timer.

## Erros comuns

| Sintoma | Causa provável |
|---|---|
| Robô gira em vez de andar reto | falta `direcao_motor(2, Motores.INVERTIDO)` (ou o motor errado invertido) |
| Nada acontece com `Motores(False)` | esqueceu de chamar `atualiza_motores()` |
| Motor volta a girar depois de `move_motor` | a velocidade ficou guardada: mande `velocidade_motores(0, 0)` |
| Robô para sozinho e LEDs apagam | ficou 5 s sem mandar pacote (um `sleep` longo) |
| `angulo_motor` não muda | não chamou `estado()`/`atualiza_motores()` antes |
| `Exception: Erro ao ler o estado dos motores` | dois programas usando a placa ao mesmo tempo (o anterior não fechou?) ou cabo/placa |

## No simulador

Emulado byte a byte (PID a 40 Hz, encoder ×2, timeout de 5 s, LEDs). Os motores e LEDs ligados em
cada canal estão no `robo*.json` (`motores`, `leds`). A fita da porta 4 responde como no robô, mas
não aparece na tela do simulador. O buzzer também responde como no robô: cada som dura o tempo
certo (`buzzer_tocando()`, `espera_buzzer()` e `esperar=True` funcionam), vale a regra do Timer2
(servos, ventoinha e buzzer, um de cada vez) e o timeout de 5 s, mas o som não toca no PC.
