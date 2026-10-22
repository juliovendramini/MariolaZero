# Módulo 9 — Servos inteligentes: a garra e a caçamba

**Objetivo:** achar e configurar os servos do barramento, calibrar as posições do mecanismo,
mover e **esperar o movimento terminar**, e entender a trava e os timeouts para não derrubar a
vítima.

Referência: [`PlacaControleServo`](referencia/placaControleServo.md). Códigos:
[`codigos/07_servos/`](codigos/07_servos/). Simulador: robô 4x4 da Line (tem 4 servos na SERIAL1).

## 9.1 O mecanismo do robô do curso

| Servo | ID | Posições (potenciômetro) |
|---|---|---|
| braço | 70 | baixo 820 (garra no chão), alto 270 |
| dedo esquerdo | 71 | aberto 380, fechado 680 |
| dedo direito | 72 | aberto 640, fechado 340 |
| porta da caçamba | 73 | fechada 512, solta um lado 330, solta o outro 700 |

Com o braço no alto, **abrir só um dedo** joga a bolinha naquele lado da caçamba (vivas de um lado,
mortas do outro). A porta, girando para um lado ou para o outro, solta o compartimento
correspondente atrás do robô.

Os números são do robô do curso: **o seu terá outros** (seção 9.3).

## 9.2 Quem está no barramento?

[`busca_servos.py`](codigos/07_servos/busca_servos.py)

```python
encontrados = PlacaControleServo.buscar_servos(Portas.SERIAL1)
```
```
Servo encontrado! ID: 70, Posição: 270
Servo encontrado! ID: 71, Posição: 380
Servo encontrado! ID: 72, Posição: 640
Servo encontrado! ID: 73, Posição: 511
```

### Servo novo: dando um ID
Toda placa nova vem com o mesmo ID. Ligue **uma de cada vez** no barramento:

```python
servo = PlacaControleServo(Portas.SERIAL1, ID_ATUAL)   # o que o buscar_servos mostrou
servo.define_id(71)                                    # grava na EEPROM
```

Anote o ID com uma etiqueta no servo.

### Tempo de trava
Para a garra, aumente o tempo de trava dos dedos (eles precisam continuar apertando a bolinha
enquanto o braço sobe):
```python
servo.calibrar_tempo_detecta_trava(3000)    # ms, de 1000 a 5000; fica gravado
```

### Controle e polaridade
A placa vem no **modo proporcional**: diminui a força perto do alvo e freia se estiver chegando
rápido, então não passa do ponto nem fica tremendo. O modo antigo, **liga-desliga** (força cheia
até chegar), chega mais rápido mas vibra em volta do alvo. Os ganhos ficam gravados na placa:
```python
print(servo.le_configuracao_controle())      # modo, kp, kd, ki, pwm_minimo...
servo.configura_controle(kp=3, kd=8)         # ajuste na bancada, uma vez
servo.define_modo_controle(PlacaControleServo.MODO_LIGA_DESLIGA)   # se quiser o antigo
```
Se um servo **fugir do alvo** em vez de ir até ele (motor ligado ao contrário do potenciômetro),
corrija com `servo.inverte_polaridade()`. A placa costuma descobrir isso sozinha na primeira vez
que liga. Detalhes e a tabela dos parâmetros na [referência](referencia/placaControleServo.md).

## 9.3 Calibrando as posições

As posições são **leituras do potenciômetro do servo montado no seu robô**. Para cada servo:

1. `servo.para_servo()` — motor solto;
2. coloque o mecanismo **com a mão** na posição (braço encostando no chão, dedo aberto...);
3. `print(servo.consulta_posicao())` e anote;
4. confira com `servo.move_servo(valor)`.

Guarde tudo como constantes no topo do `robo.py`. No simulador, os mesmos números vão no `resgate`
do `robo_4x4.json`.

## 9.4 Mover e esperar

`move_servo` **não espera** o servo chegar. Para sequências (abaixar → fechar → levantar) você
precisa esperar cada etapa. Use `consulta_posicao()`, que lê **sem desligar** o motor:

[`testa_garra.py`](codigos/07_servos/testa_garra.py)

```python
def espera_chegar(servo, alvo, tolerancia=25, tempo_max=2.0):
    inicio = time.time()
    while time.time() - inicio < tempo_max:
        pos = servo.consulta_posicao()
        if pos is not None and abs(pos - alvo) <= tolerancia:
            return True
        time.sleep(0.02)
    return False

move_e_espera(braco, BRACO_ALTO)
move_e_espera(dedo_esq, ESQ_ABERTO)
move_e_espera(dedo_dir, DIR_ABERTO)
move_e_espera(braco, BRACO_BAIXO, potencia=180)   # descer mais devagar
dedo_esq.move_servo(ESQ_FECHADO)                   # fecha os dois juntos...
dedo_dir.move_servo(DIR_FECHADO)
espera_chegar(dedo_esq, ESQ_FECHADO)               # ...e só depois espera
espera_chegar(dedo_dir, DIR_FECHADO)
move_e_espera(braco, BRACO_ALTO)
```
```
servo 70: alvo 270, está em 270
servo 71: alvo 380, está em 380
servo 72: alvo 640, está em 639
servo 70: alvo 820, está em 797
servo 70: alvo 270, está em 295
braço ainda em 276
```

Repare: o braço parou em 797 (não 820) — o chão segurou. Por isso a tolerância e o `tempo_max`:
**nem todo alvo é atingido**, e o programa não pode travar esperando.

### Ler a posição para saber se pegou algo
Os dedos fecharam e pararam **longe** do "fechado"? Tem uma bolinha entre eles. Isso é mais
confiável do que esperar e torcer.

## 9.5 Três regras para não derrubar a vítima

1. **Use `consulta_posicao()`, nunca `le_posicao()`** para ler: o `le_posicao()` manda potência 0 e
   **desliga** o motor (o braço cai, os dedos soltam).
2. **Reenvie os comandos antes de 5 s.** Sem pacote por 5 s, a placa desliga o motor. Numa espera
   longa, chame de tempos em tempos um "mantém" que repete os últimos comandos (a classe `Garra` do
   exemplo tem `mantem()`).
3. **Conte com a trava.** Dedos apertando a bolinha travam; depois do tempo de trava o motor desliga
   por 2 s. Calibre um tempo de trava maior (9.2) e **levante logo** depois de fechar.

E uma de mecânica: **o braço só se segura sozinho todo levantado** (no fim de curso). No meio do
caminho, sem força, ele cai.

## 9.6 A classe `Garra` do exemplo

`simuladorLine/exemplo_aluno/robo.py` junta tudo numa classe com métodos de alto nível:

| Método | Faz |
|---|---|
| `Garra.procura(porta)` | cria a garra se o braço responder; senão `None` (robô sem mecanismo) |
| `abaixa_aberta()` | abre os dedos e desce o braço (potência 200) |
| `fecha()` | fecha os dois dedos |
| `levanta()` | sobe o braço e espera chegar |
| `joga_na_cacamba('esq' / 'dir')` | com o braço no alto, abre só um dedo e fecha de novo |
| `solta('esq' / 'dir')` | abre a porta para um lado e fecha |
| `guarda()` | posição de andar: braço no alto, dedos e porta fechados |
| `mantem()` | repete os últimos comandos (chame em esperas longas) |

O programa da área de resgate (módulo 15) só usa esses métodos: **a estratégia não precisa saber
números de potenciômetro**. É assim que se organiza um robô (módulo 13).

## Exercícios

1. Escreva `pega()`: abaixa aberta, fecha, verifica pela posição dos dedos se pegou algo, levanta.
   Devolve `True`/`False`.
2. Mude o tempo de trava para 1000 ms no simulador (`tempo_trava_ms` no `robo_4x4.json`) e veja a
   bolinha cair ao levantar devagar.
3. Faça o braço descer com potência 120 e com 255. Meça o tempo com `time.time()`.
4. Faça uma espera de 10 s com a garra fechada no alto, sem deixar a placa desligar o motor.
