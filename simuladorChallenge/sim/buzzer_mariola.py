"""Sons do buzzer do Mariola, copiados da tabela sonsBuzzer do placaBrickVendra/buzzer.h
(firmware de 26/10/2026). O simulador não toca o som: só precisa saber quanto tempo cada um dura,
para o CONSULTA_BUZZER (buzzer_tocando / espera_buzzer / esperar=True) responder como no robô.

Cada nota é (frequência Hz, frequência final, duração ms): frequência 0 = pausa; final 0 = tom
fixo; final > 1 = varredura em passos de 10 ms; final = ALEATORIO = tom sorteado.
Mudou o buzzer.h? Mude aqui também (o mesmo arquivo está nos dois simuladores).
"""

import math

ALEATORIO = 1
REPETE_SEMPRE = 255
PAUSA_REPETICAO_MS = 250          # silêncio entre repetições das melodias
PASSO_VARREDURA_MS = 10

DO5, DOS5, RE5, RES5, MI5, FA5, FAS5, SOL5 = 523, 554, 587, 622, 659, 698, 740, 784
SOLS5, LA5, LAS5, SI5 = 831, 880, 932, 988
DO6, DOS6, RE6, RES6, MI6, FA6, FAS6, SOL6, LA6, SI6, DO7 = 1047, 1109, 1175, 1245, 1319, 1397, 1480, 1568, 1760, 1976, 2093


def T(f, d):
    return (f, 0, d)


def P(d):
    return (0, 0, d)


def V(f0, f1, d):
    return (f0, f1, d)


def A(f, d):
    return (f, ALEATORIO, d)


# (nome da constante na lib, notas, articulado). A ordem é o número do som (começa em 1).
SONS = [
    ('SOM_BIPE', [T(2000, 120)], False),
    ('SOM_BIPE_DUPLO', [T(2000, 80), P(80), T(2000, 80)], False),
    ('SOM_SUCESSO', [T(DO6, 100), T(MI6, 100), T(SOL6, 100), T(DO7, 350)], True),
    ('SOM_ERRO', [T(500, 200), P(60), T(300, 450)], False),
    ('SOM_ALERTA', [T(2600, 70), P(70), T(2600, 70), P(70), T(2600, 70), P(70)], False),
    ('SOM_LIGANDO', [T(DO5, 90), T(MI5, 90), T(SOL5, 90), T(DO6, 90), T(MI6, 90), T(SOL6, 250)], True),
    ('SOM_DESLIGANDO', [T(SOL6, 90), T(MI6, 90), T(DO6, 90), T(SOL5, 90), T(MI5, 90), T(DO5, 250)], True),
    ('SOM_LARGADA', [T(880, 250), P(750), T(880, 250), P(750), T(880, 250), P(750), T(1760, 800)], False),
    ('SOM_RE', [T(1000, 500), P(500)], False),
    ('SOM_SIRENE_DOIS_TONS', [T(950, 450), T(700, 450)], False),
    ('SOM_SIRENE', [V(600, 1400, 700), V(1400, 600, 700)], False),
    ('SOM_MOEDA', [T(RE6, 70), T(LA6, 300)], False),
    ('SOM_POWER_UP', [V(400, 2000, 400)], False),
    ('SOM_LASER', [V(3000, 300, 180)], False),
    ('SOM_BATERIA_FRACA', [V(1000, 800, 300), P(80), V(800, 600, 300), P(80), V(600, 300, 600)], False),
    ('SOM_ROBO', [A(400, 70), P(30), A(400, 50), A(400, 90), P(40), A(400, 60), A(400, 60), P(30),
                  A(400, 120), P(50), A(400, 50), A(400, 80)], False),
    ('MELODIA_ESCALA', [T(DO5, 300), T(RE5, 300), T(MI5, 300), T(FA5, 300), T(SOL5, 300), T(LA5, 300),
                        T(SI5, 300), T(DO6, 600)], True),
    ('MELODIA_PARABENS', [
        T(SOL5, 300), T(SOL5, 100), T(LA5, 400), T(SOL5, 400), T(DO6, 400), T(SI5, 800),
        T(SOL5, 300), T(SOL5, 100), T(LA5, 400), T(SOL5, 400), T(RE6, 400), T(DO6, 800),
        T(SOL5, 300), T(SOL5, 100), T(SOL6, 400), T(MI6, 400), T(DO6, 400), T(SI5, 400), T(LA5, 800),
        T(FA6, 300), T(FA6, 100), T(MI6, 400), T(DO6, 400), T(RE6, 400), T(DO6, 800)], True),
    ('MELODIA_BRILHA_ESTRELINHA', [
        T(DO5, 400), T(DO5, 400), T(SOL5, 400), T(SOL5, 400), T(LA5, 400), T(LA5, 400), T(SOL5, 800),
        T(FA5, 400), T(FA5, 400), T(MI5, 400), T(MI5, 400), T(RE5, 400), T(RE5, 400), T(DO5, 800),
        T(SOL5, 400), T(SOL5, 400), T(FA5, 400), T(FA5, 400), T(MI5, 400), T(MI5, 400), T(RE5, 800),
        T(SOL5, 400), T(SOL5, 400), T(FA5, 400), T(FA5, 400), T(MI5, 400), T(MI5, 400), T(RE5, 800),
        T(DO5, 400), T(DO5, 400), T(SOL5, 400), T(SOL5, 400), T(LA5, 400), T(LA5, 400), T(SOL5, 800),
        T(FA5, 400), T(FA5, 400), T(MI5, 400), T(MI5, 400), T(RE5, 400), T(RE5, 400), T(DO5, 800)], True),
    ('MELODIA_ODE_ALEGRIA', [
        T(MI5, 400), T(MI5, 400), T(FA5, 400), T(SOL5, 400), T(SOL5, 400), T(FA5, 400), T(MI5, 400), T(RE5, 400),
        T(DO5, 400), T(DO5, 400), T(RE5, 400), T(MI5, 400), T(MI5, 600), T(RE5, 200), T(RE5, 800),
        T(MI5, 400), T(MI5, 400), T(FA5, 400), T(SOL5, 400), T(SOL5, 400), T(FA5, 400), T(MI5, 400), T(RE5, 400),
        T(DO5, 400), T(DO5, 400), T(RE5, 400), T(MI5, 400), T(RE5, 600), T(DO5, 200), T(DO5, 800)], True),
    ('MELODIA_JINGLE_BELLS', [
        T(MI5, 300), T(MI5, 300), T(MI5, 600), T(MI5, 300), T(MI5, 300), T(MI5, 600),
        T(MI5, 300), T(SOL5, 300), T(DO5, 450), T(RE5, 150), T(MI5, 1200),
        T(FA5, 300), T(FA5, 300), T(FA5, 450), T(FA5, 150), T(FA5, 300), T(MI5, 300), T(MI5, 300), T(MI5, 150),
        T(MI5, 150),
        T(MI5, 300), T(RE5, 300), T(RE5, 300), T(MI5, 300), T(RE5, 600), T(SOL5, 600),
        T(MI5, 300), T(MI5, 300), T(MI5, 600), T(MI5, 300), T(MI5, 300), T(MI5, 600),
        T(MI5, 300), T(SOL5, 300), T(DO5, 450), T(RE5, 150), T(MI5, 1200),
        T(FA5, 300), T(FA5, 300), T(FA5, 450), T(FA5, 150), T(FA5, 300), T(MI5, 300), T(MI5, 300), T(MI5, 150),
        T(MI5, 150),
        T(SOL5, 300), T(SOL5, 300), T(FA5, 300), T(RE5, 300), T(DO5, 1200)], True),
    ('MELODIA_FUR_ELISE', [
        T(MI6, 150), T(RES6, 150), T(MI6, 150), T(RES6, 150), T(MI6, 150), T(SI5, 150), T(RE6, 150), T(DO6, 150),
        T(LA5, 450),
        T(DO5, 150), T(MI5, 150), T(LA5, 150), T(SI5, 450),
        T(MI5, 150), T(SOLS5, 150), T(SI5, 150), T(DO6, 450),
        T(MI5, 150), T(MI6, 150), T(RES6, 150), T(MI6, 150), T(RES6, 150), T(MI6, 150), T(SI5, 150), T(RE6, 150),
        T(DO6, 150), T(LA5, 450),
        T(DO5, 150), T(MI5, 150), T(LA5, 150), T(SI5, 450),
        T(MI5, 150), T(DO6, 150), T(SI5, 150), T(LA5, 900)], True),
    ('MELODIA_GRAN_VALS', [
        T(MI6, 140), T(RE6, 140), T(FAS5, 280), T(SOLS5, 280),
        T(DOS6, 140), T(SI5, 140), T(RE5, 280), T(MI5, 280),
        T(SI5, 140), T(LA5, 140), T(DOS5, 280), T(MI5, 280),
        T(LA5, 840)], True),
]
QUANTIDADE_SONS = len(SONS)


def _duracao_nota(nota, velocidade):
    """ms de uma nota, como o buzzerGeraSegmento: a duração muda com a velocidade (divisão inteira),
    a varredura anda em passos inteiros e a nota articulada só troca parte do som por silêncio."""
    f, f_fim, d = nota
    dur = max(1, d * 100 // velocidade)
    if f != 0 and f_fim > ALEATORIO:                   # varredura
        passos = max(1, dur // PASSO_VARREDURA_MS)
        return passos * (dur // passos)
    return dur


def duracao_som(numero, repeticoes, velocidade):
    """Segundos que o som 'numero' (1..QUANTIDADE_SONS) toca com 'repeticoes' repetições depois da
    primeira (REPETE_SEMPRE = infinito) e 'velocidade' em % (0 = 100)."""
    if repeticoes == REPETE_SEMPRE:
        return math.inf
    _, notas, articulado = SONS[numero - 1]
    vel = velocidade or 100
    uma = sum(_duracao_nota(n, vel) for n in notas)
    total = uma * (1 + repeticoes) + (PAUSA_REPETICAO_MS * repeticoes if articulado else 0)
    return total / 1000.0


def duracao_tom(duracao_ms):
    return max(1, duracao_ms) / 1000.0
