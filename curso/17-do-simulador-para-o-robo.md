# Módulo 17 — Do simulador para o robô real (e para a competição)

**Objetivo:** fazer o simulador ficar parecido com o **seu** robô, levar o programa para o robô
sem surpresas e chegar na competição com tudo calibrado e testado.

## 17.1 O que muda entre o simulador e o robô

| Igual nos dois | Diferente |
|---|---|
| o seu `main.py` e as libs | atrito, peso, centro de massa |
| protocolo das placas, timeouts | luz do local (sensores de cor e IR) |
| comportamento do encoder, do VL53, dos servos | bateria (velocidade máxima, leitura do IR) |
| | folgas mecânicas, cabos, mau contato |
| | a câmera (o stub × a sua IA de verdade) |
| | o motor sob carga (o do simulador é ideal), o instante da medida do VL53 e o tempo das conversas I2C (módulo 11.9) |

Por isso: **lógica no simulador, ajuste fino no robô**.

## 17.2 Arquivos que só existem de um lado

| No simulador | No robô, copie para a pasta do projeto |
|---|---|
| `simdebug` (automático) | `robo_real/simdebug.py` (não faz nada) |
| `visao` (stub, Line) | `simuladorLine/robo_real/visao.py` + a sua YOLO |
| `deteccaoVitimas`, `dispensadorKits` (Maze) | `simuladorMaze/robo_real/...` completados |
| `libs_mariola/` (reserva) | as libs de `bananaPiM4Zero/libs/` (+ `sensorCorReflexao` V2) |

## 17.3 Deixando o `robo*.json` igual ao seu robô

Os valores que vêm no simulador são **estimativas**. Meça e ajuste:

| O que | Como medir | Onde no json |
|---|---|---|
| diâmetro da roda / polia | paquímetro | `rodas.diametro` |
| contagens por volta | gire a roda 1 volta à mão e leia `angulo_motor` | `motor_padrao.contagens_por_volta_*` |
| calibração dos motores | `obtem_calibracao_motores()` / `obter_calibracao()` | `motor_padrao.calibracao_*` |
| posição das rodas | régua, a partir do centro do robô (x para frente, y para a esquerda) | `motores[].x/y` |
| medidas e massa | régua e balança | `geometria` |
| posição do sensor de linha | régua (x do IR e dos TCS, altura do chão) | `sensor_linha` |
| leituras de cada material | o robô sobre cada cor, `le_reflexao()`/`le_rgbc()` | `cores_piso` |
| VL53: canal, posição, ângulo, altura | régua | `vl53` |
| giroscópio: sentido, deriva | gire à mão; deixe parado 1 min | `giroscopio` |
| servos: IDs, posições | `buscar_servos`, `consulta_posicao` (módulo 9) | `resgate` |
| câmera: altura, campo de visão | régua; objeto na borda da imagem | `camera` (`altura`, `fov_graus`) |

**Teste de comparação:** rode o **mesmo** programa (andar 1 m, girar 360°, seguir 1 volta da pista)
no robô e no simulador. Ajuste `motor_padrao.rpm_livre`, `motor_padrao.forca_max_N`,
`rodas.atrito_lateral` e `giroscopio.deriva_graus_min` até os resultados baterem.

## 17.4 Primeira vez no robô: passo a passo

1. **Robô suspenso** (rodas no ar). Rode um teste de motores: cada roda gira para o lado certo?
2. Teste cada sensor isolado (os programas de `codigos/`): valores fazem sentido?
3. Calibre o sensor de linha (branco/preto) e **ensine as cores** no piso real.
4. No chão, velocidade baixa: ajuste `KP`/`KD` (eles quase sempre mudam um pouco).
5. Só depois aumente a velocidade.

## 17.5 Problemas que só aparecem no robô

| Sintoma | Suspeite de |
|---|---|
| Funciona com bateria cheia e não com a meia carga | velocidade/limiares no limite; teste com bateria a 70% |
| Cores erradas no local da competição | luz diferente: refaça `aprende_cor` no tempo de calibração |
| Leituras malucas de vez em quando | cabo frouxo, mau contato no conector, ruído do motor |
| Programa trava às vezes | exceção não tratada (veja `~/logs/*_erro.log`); `OSError` de I2C |
| O robô funciona pelo `ssh` e não pelo menu | caminho relativo de arquivo, `print` sem flush (módulo 2) |
| Câmera lenta | modelo pesado: use ONNX/NCNN, imagem menor (320×240) |

## 17.6 Robustez

* `try/except (OSError, TimeoutError)` em volta de leituras I2C, com `recover()` do sensor.
* `PlacaControleServo`/`PlacaControleMotor` devolvem `None` quando falham: trate.
* Uma exceção inesperada **não pode** parar o robô no meio da rodada sem querer. Um padrão:
  ```python
  while True:
      try:
          seguidor.passo()
      except (OSError, TimeoutError) as e:
          log('erro de sensor:', e)       # registra e continua
      time.sleep(0.01)
  ```
  (Erros de lógica — `TypeError`, `NameError` — devem aparecer no teste, não ser escondidos.)

## 17.7 Checklist do dia da competição

**Antes de sair de casa / do laboratório**
- [ ] Versão do programa testada, com cópia de segurança (git/pendrive) — e a anterior também.
- [ ] Todas as libs na pasta do projeto. O programa roda **pelo menu**.
- [ ] Baterias carregadas (e reservas), carregador.
- [ ] Ferramentas, cabos e peças de reposição (servo, VL53, cabos dos conectores).
- [ ] Programa de calibração de cores e programa de teste de sensores no robô.

**No tempo de calibração**
- [ ] Calibre branco/preto se necessário; **ensine as cores** no piso oficial.
- [ ] Confira o verde, o vermelho e o prata com o programa de teste.
- [ ] Teste a câmera com a luz do local (vítimas, triângulos).

**Antes de cada rodada**
- [ ] Bateria conferida.
- [ ] Programa certo selecionado no menu.
- [ ] Arquivos da rodada anterior (checkpoint, relógio) apagados — ou o programa sabe que é rodada
      nova.
- [ ] Robô no início, apontado certo, botão de início.

**Depois de cada rodada**
- [ ] Anote o que aconteceu (LoPs, onde, por quê). Veja o log.
- [ ] Mudou o programa? Teste no simulador **antes** de usar na próxima rodada.

## Exercício

Faça a tabela de 17.3 com as medidas do seu robô, ajuste o `robo*.json` e compare: andar 1 m e
girar 360° no robô e no simulador. Quanto ficou a diferença?
