"""Cenários do brick: firmware antigo (ref) x novo, com a mesma calibração na EEPROM."""
import json
import sys

from emu import *

GRAUS = 360.0 / 1156.0          # graus de roda por contagem


def eeprom_brick():
    """EEPROM com a calibração feita pelo próprio firmware (guardada em builds/ para as rodadas seguintes)"""
    arq = os.path.join(BUILDS, 'eeprom_brick.bin')
    if not os.path.exists(arq):
        e = Mariola(*firmware('brick', 'novo'))
        e.roda(0.4)
        e.envia(bytes([0xF3] + [0] * 9))
        e.roda(31.0)
        open(arq, 'wb').write(e.eeprom())
        print('calibração do brick:', struct.unpack('<4i', e.eeprom(16)))
    return open(arq, 'rb').read()


def brick(qual):
    e = Mariola(*firmware('brick', qual), eeprom=eeprom_brick())
    e.roda(0.4)                 # setup() do firmware
    return e


def fino(e, dur, antes=None):
    """roda 'dur' segundos gravando a ponte H a cada 16 us; devolve o trecho do traço"""
    e.passos_traco(1)
    t0 = e.t
    if antes:
        antes()
    e.ate(t0 + dur)
    e.passos_traco(16)
    tr = e.traco()
    return tr[(tr[:, 0] >= t0) & (tr[:, 0] <= t0 + dur)]


def pulso(tr, col, sinal):
    """maior tempo seguido (ms) com a ponte em 100% no sentido 'sinal'"""
    liga = tr[:, col] * sinal > 0.99
    maior = atual = 0
    for v in liga:
        atual = atual + 1 if v else 0
        maior = max(maior, atual)
    return maior * 0.016


def impulso(tr, col):
    """soma da tensão na ponte em ms de 100% (positivo = para frente)"""
    return float(tr[:, col].sum() * 0.016)


def primeiro_pulso(tr, col, sinal):
    """(ms até a ponte ligar, duração do primeiro pulso em ms) no sentido 'sinal'"""
    liga = tr[:, col] * sinal > 0.99
    idx = np.flatnonzero(liga)
    if not len(idx):
        return None, 0.0
    i = idx[0]
    n = 0
    while i + n < len(liga) and liga[i + n]:
        n += 1
    return (tr[i, 0] - tr[0, 0]) * 1000, n * 0.016


def media_vel(e, dur=0.4):
    tr = e.traco()
    tr = tr[tr[:, 0] > e.t - dur]
    return float((tr[-1, 5] - tr[0, 5]) / (tr[-1, 0] - tr[0, 0]))


def partida(e):
    """parado -> velocidade 30 com o PID (o primeiro comando de andar de um programa)"""
    e.anda(0.3, 0, 0)
    tr = fino(e, 0.06, lambda: e.envia(msg_motores(30, 30)))
    e.anda(0.8, 30, 30)
    quando, dur = primeiro_pulso(tr, 1, 1)
    return {'primeiro pulso para frente (ms)': dur, 'maior pulso nos 60 ms (ms)': pulso(tr, 1, 1),
            'pulso em ré nos 60 ms (ms)': pulso(tr, 1, -1), 'velocidade média depois (cont/s)': media_vel(e)}


def parada(e):
    """andando a 50 -> parar em BREAK (10 tentativas em momentos diferentes do ciclo do PWM: o pior caso)"""
    pior = 0.0
    soma = 0.0
    for i in range(10):
        e2 = brick(e.qual)
        e2.anda(0.3, 0, 0)
        e2.anda(0.8 + i * 0.00041, 50, 50, periodo=0.02 + i * 0.00041)
        tr = fino(e2, 0.012, lambda: e2.envia(msg_motores(0, 0)))
        p = pulso(tr, 1, -1)
        pior = max(pior, p)
        soma += p
    return {'pior pulso de 100% em ré (ms)': pior, 'média do pulso em ré (ms)': soma / 10}


def inversao(e):
    """andando a 40 -> -40 com o PID"""
    e.anda(0.3, 0, 0)
    e.anda(0.8, 40, 40)
    tr = fino(e, 0.06, lambda: e.envia(msg_motores(-40, -40)))
    e.anda(1.0, -40, -40)
    return {'maior pulso em ré nos 60 ms (ms)': pulso(tr, 1, -1), 'maior pulso para frente nos 60 ms (ms)': pulso(tr, 1, 1),
            'velocidade média depois (cont/s)': media_vel(e)}


def motor3(e):
    """motores 3 e 4 (sem encoder): parado -> 40 -> parado -> -40 (10 tentativas, pior caso)"""
    pior = {'partida: 1o pulso para frente (ms)': 0.0, 'parada: pulso em ré (ms)': 0.0, 'partida em ré: 1o pulso (ms)': 0.0}
    for i in range(10):
        e2 = brick(e.qual)
        per = 0.02 + i * 0.00041
        e2.anda(0.3, 0, 0, periodo=per)
        tr = fino(e2, 0.012, lambda: e2.envia(msg_motores(0, 0, 40, 40)))
        pior['partida: 1o pulso para frente (ms)'] = max(pior['partida: 1o pulso para frente (ms)'], primeiro_pulso(tr, 3, 1)[1])
        e2.anda(0.5, 0, 0, 40, 40, periodo=per)
        tr = fino(e2, 0.012, lambda: e2.envia(msg_motores(0, 0, 0, 0)))
        pior['parada: pulso em ré (ms)'] = max(pior['parada: pulso em ré (ms)'], pulso(tr, 3, -1))
        e2.anda(0.5, 0, 0, periodo=per)
        tr = fino(e2, 0.012, lambda: e2.envia(msg_motores(0, 0, -40, -40)))
        pior['partida em ré: 1o pulso (ms)'] = max(pior['partida em ré: 1o pulso (ms)'], primeiro_pulso(tr, 3, -1)[1])
    pior['pulso normal de 40% (ms)'] = 1.63
    return pior


def potencia(e):
    """modo potência (sem PID), motores 1 e 2: parado -> 40% -> parado (10 tentativas, pior caso)"""
    pior = {'partida: 1o pulso para frente (ms)': 0.0, 'parada: pulso em ré (ms)': 0.0}
    for i in range(10):
        e2 = brick(e.qual)
        per = 0.02 + i * 0.00041
        e2.anda(0.3, 0, 0, cmd=POTENCIA, periodo=per)
        tr = fino(e2, 0.012, lambda: e2.envia(msg_motores(40, 40, cmd=POTENCIA)))
        pior['partida: 1o pulso para frente (ms)'] = max(pior['partida: 1o pulso para frente (ms)'], primeiro_pulso(tr, 1, 1)[1])
        e2.anda(0.6, 40, 40, cmd=POTENCIA, periodo=per)
        tr = fino(e2, 0.012, lambda: e2.envia(msg_motores(0, 0, cmd=POTENCIA)))
        pior['parada: pulso em ré (ms)'] = max(pior['parada: pulso em ré (ms)'], pulso(tr, 1, -1))
    pior['pulso normal de 40% (ms)'] = 1.63
    return pior


def hold_programa_novo(e):
    """programa termina em HOLD; depois do timeout o aluno reposiciona o robô (roda gira 90 graus);
    o programa seguinte começa mandando parar com HOLD"""
    e.anda(0.3, 0, 0, freio=HOLD)
    e.anda(0.8, 40, 40, freio=HOLD)
    e.anda(0.5, 0, 0, freio=HOLD)
    e.roda(6.0)                             # programa acabou: timeout de 5 s
    e.mao(0, 578)                           # 0,5 s a 578 contagens/s = 289 contagens = 90 graus
    e.roda(0.5)
    e.mao(0, None)
    e.roda(1.0)
    th0 = e.motor(0)[0]
    tr = fino(e, 0.02, lambda: e.envia(msg_motores(0, 0, freio=HOLD)))
    e.anda(1.5, 0, 0, freio=HOLD)
    reg = e.traco()
    reg = reg[reg[:, 0] > e.t - 1.5]
    return {'a roda girou sozinha (graus)': (e.motor(0)[0] - th0) * GRAUS,
            'velocidade máxima no tranco (cont/s)': float(abs(reg[:, 7]).max()),
            'pulso de 100% nos primeiros 20 ms (ms)': max(pulso(tr, 1, 1), pulso(tr, 1, -1))}


def hold_depois_do_break(e):
    """para em BREAK (o robô ainda desliza um pouco e alguém empurra 45 graus); depois liga o HOLD parado"""
    e.anda(0.3, 0, 0)
    e.anda(0.8, 60, 60)
    e.anda(0.4, 0, 0)
    e.mao(0, 289)
    e.anda(0.5, 0, 0)
    e.mao(0, None)
    e.anda(0.3, 0, 0)
    th0 = e.motor(0)[0]
    e.anda(1.5, 0, 0, freio=HOLD)
    reg = e.traco()
    reg = reg[reg[:, 0] > e.t - 1.5]
    return {'a roda girou sozinha (graus)': (e.motor(0)[0] - th0) * GRAUS,
            'velocidade máxima no tranco (cont/s)': float(abs(reg[:, 7]).max())}


def programa_morto(e):
    """programa morre com os motores a 60 (sem mandar parar); 8 s depois começa outro"""
    e.anda(0.3, 0, 0)
    e.anda(1.0, 60, 60)
    t_fim = e.t
    e.passos_traco(1)
    e.roda(5.4)                             # passa pelo timeout
    e.passos_traco(16)
    tr = e.traco()
    desl = tr[(tr[:, 0] > t_fim + 4.9) & (tr[:, 0] < t_fim + 5.4)]
    e.roda(2.6)
    th0 = e.motor(0)[0]
    tr = fino(e, 0.03, lambda: e.envia(msg_motores(0, 0)))
    saida = {'no timeout: pulso de 100% em ré (ms)': pulso(desl, 1, -1),
             'programa novo, 1o comando (parar): pulso de 100% (ms)': max(pulso(tr, 1, 1), pulso(tr, 1, -1)),
             'idem, motor 3: pulso de 100% (ms)': max(pulso(tr, 3, 1), pulso(tr, 3, -1)),
             'a roda girou no 1o comando (graus)': (e.motor(0)[0] - th0) * GRAUS}
    e.anda(0.5, 0, 0)
    r = e.anda(0.8, 40, 40)
    saida['depois anda a 40: velocidade (cont/s)'] = e.motor(0)[1]
    saida['resposta ok'] = r is not None
    return saida


def regressao(e):
    """perfil de velocidades com o PID e um giro por ângulo: os números devem ser os mesmos nos dois"""
    e.anda(0.3, 0, 0)
    saida = {}
    for v in (20, 50, 80, -35):
        e.anda(1.2, v, v)
        saida['velocidade média com %d (cont/s)' % v] = round(media_vel(e, 0.6))
    e.anda(0.6, 0, 0)
    r = e.motores(0, 0)
    th0 = e.motor(0)[0]
    c0 = r[1]
    e.motores(40, 40, ang1=800, ang2=800)   # anda 800 contagens e para sozinho
    for _ in range(100):
        e.roda(0.02)
        r = e.motores(0, 0, cmd=ATUALIZA)
    saida['giro de 800: andou (contagens)'] = round(e.motor(0)[0] - th0)
    saida['giro de 800: contador do firmware'] = r[1] - c0
    # vai e volta 30 vezes e confere se o contador do firmware não perdeu pulso
    for i in range(30):
        e.anda(0.15, 70, -70)
        e.anda(0.15, -70, 70)
    e.anda(0.5, 0, 0)
    r = e.motores(0, 0)
    saida['contador do firmware - eixo, motor 1 (contagens)'] = round(r[1] - e.motor(0)[0])
    saida['contador do firmware - eixo, motor 2 (contagens)'] = round(r[2] - e.motor(1)[0])
    saida['millis() x tempo real (%)'] = round(e.le('timer0_millis', '<I') * 4 / (e.t * 1000) * 100, 2)
    return saida


def modo_4x4(e):
    """comando 4x4 (motores 3 e 4 copiam o 1 e o 2): anda, para em HOLD, empurra a roda 1"""
    e.anda(0.3, 0, 0, cmd=MOTORES_4X4)
    e.anda(1.0, 50, 50, cmd=MOTORES_4X4)
    tr = e.traco()
    tr = tr[tr[:, 0] > e.t - 0.5]
    saida = {'andando: duty motor 1 (%)': float(tr[:, 1].mean() * 100), 'andando: duty motor 3 (%)': float(tr[:, 3].mean() * 100)}
    tr = fino(e, 0.012, lambda: e.envia(msg_motores(0, 0, freio=HOLD, cmd=MOTORES_4X4)))
    saida['parada: pulso em ré motor 1 (ms)'] = pulso(tr, 1, -1)
    saida['parada: pulso em ré motor 3 (ms)'] = pulso(tr, 3, -1)
    e.anda(0.8, 0, 0, freio=HOLD, cmd=MOTORES_4X4)
    th0 = e.motor(0)[0]
    e.mao(0, 200)
    e.anda(0.3, 0, 0, freio=HOLD, cmd=MOTORES_4X4)   # empurra 60 contagens com o hold ligado
    e.mao(0, None)
    e.anda(1.0, 0, 0, freio=HOLD, cmd=MOTORES_4X4)
    saida['hold: erro depois de empurrar 60 contagens (contagens)'] = round(e.motor(0)[0] - th0)
    return saida


def servo_detach(e):
    """servo ligado e depois desligado pelo programa (valor > 180), em 40 momentos do ciclo de 20 ms"""
    presos = 0
    for i in range(40):
        e2 = brick(e.qual)
        e2.comando(bytes([ENVIA_SERVOS, 90, 90, 90, 90, 0, 0, 0, 0, 0]), 1)
        e2.roda(0.1 + i * 0.00053)
        e2.comando(bytes([ENVIA_SERVOS, 255, 255, 255, 255, 0, 0, 0, 0, 0]), 1)
        e2.roda(0.1)
        tr = e2.traco()
        if int(tr[-1, 9]) & 0x0F:
            presos += 1
    return {'vezes com pino de servo preso em HIGH (de 40)': presos}


def timeout_parado(e):
    """programa termina com o robô parado (andou para frente, parou, mandou parar no fim): o que acontece
    5 s depois, no timeout, e quando o programa seguinte começa (10 fases, pior caso; BREAK e HOLD)"""
    saida = {}
    for nome, freio in (('BREAK', BREAK), ('HOLD', HOLD)):
        pior_t = pior_n = giro = 0.0
        for i in range(10):
            e2 = brick(e.qual)
            per = 0.02 + i * 0.00041
            e2.anda(0.3, 0, 0, freio=freio, periodo=per)
            e2.anda(0.8, 50, 50, freio=freio, periodo=per)
            e2.anda(0.6, 0, 0, freio=freio, periodo=per)
            t_fim = e2.t
            th0 = e2.motor(0)[0]
            e2.roda(4.8)
            e2.passos_traco(1)
            e2.roda(0.6)
            e2.passos_traco(16)
            tr = e2.traco()
            tr = tr[tr[:, 0] > t_fim + 4.8]
            pior_t = max(pior_t, pulso(tr, 1, -1), pulso(tr, 1, 1), pulso(tr, 3, -1), pulso(tr, 3, 1))
            e2.roda(1.0)
            tr = fino(e2, 0.03, lambda: e2.envia(msg_motores(0, 0, freio=freio)))
            pior_n = max(pior_n, pulso(tr, 1, -1), pulso(tr, 1, 1), pulso(tr, 3, -1), pulso(tr, 3, 1))
            e2.anda(0.5, 0, 0, freio=freio, periodo=per)
            giro = max(giro, abs(e2.motor(0)[0] - th0) * GRAUS)
        saida[nome + ': pior pulso de 100% no timeout (ms)'] = pior_t
        saida[nome + ': pior pulso no 1o comando do programa novo (ms)'] = pior_n
        saida[nome + ': quanto a roda girou no total (graus)'] = giro
    return saida


def timeout_fases(e):
    """programa morre com os motores a 60: o que acontece no instante do timeout (10 fases do PWM)"""
    pior = 0.0
    for i in range(10):
        e2 = brick(e.qual)
        e2.anda(0.3, 0, 0)
        e2.anda(1.0 + i * 0.00041, 60, 60, periodo=0.02 + i * 0.00041)
        t_fim = e2.t
        e2.roda(4.8)
        e2.passos_traco(1)
        e2.roda(0.6)
        e2.passos_traco(16)
        tr = e2.traco()
        tr = tr[tr[:, 0] > t_fim + 4.8]
        pior = max(pior, pulso(tr, 1, -1))
    return {'pior pulso de 100% em ré no timeout (ms)': pior}


CENARIOS = [partida, parada, inversao, potencia, motor3, modo_4x4, hold_programa_novo, hold_depois_do_break,
            programa_morto, timeout_fases, timeout_parado, regressao, servo_detach]

if __name__ == '__main__':
    so = sys.argv[1:]
    tudo = {}
    for c in CENARIOS:
        if so and c.__name__ not in so:
            continue
        res = {}
        for qual in ('antigo', 'novo'):
            e = brick(qual)
            e.qual = qual
            res[qual] = c(e)
        tudo[c.__name__] = res
        print('\n== %s: %s' % (c.__name__, ' '.join(c.__doc__.split())))
        for k in res['antigo']:
            a, b = res['antigo'][k], res['novo'][k]
            fmt = (lambda x: '%10.2f' % x) if isinstance(a, float) else (lambda x: '%10s' % x)
            print('   %-58s antigo %s   novo %s' % (k, fmt(a), fmt(b)))
    json.dump(tudo, open(os.path.join(BUILDS, 'resultado_brick.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
