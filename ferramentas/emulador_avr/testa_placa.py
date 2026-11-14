"""Cenários da placa de motor externa: firmware antigo (ref) x novo."""
import json
import sys

from placa import *

GRAUS = 360.0 / (17 * 34 * 4)
ARQ_EE = os.path.join(BUILDS, 'eeprom_placa.bin')


def calibra():
    e = Placa('novo')
    e.roda(1.0)
    e.envia(pacote(CALIBRACAO))
    e.roda(15.5)
    ee = e.eeprom(256)
    print('calibração da placa:', struct.unpack('<2i', ee[:8]))
    open(ARQ_EE, 'wb').write(ee)


def placa(qual):
    e = Placa(qual, eeprom=open(ARQ_EE, 'rb').read())
    e.roda(0.8)                         # setup() e as 3 piscadas do LED
    return e


def instantes_reset(e):
    tr = e.traco()
    return [round(float(tr[i, 0]), 2) for i in range(1, len(tr)) if tr[i, 10] != tr[i - 1, 10]]


def sem_programa(e):
    """placa ligada, nenhum programa rodando, 60 s"""
    e.roda(60.0)
    r = instantes_reset(e)
    return {'reinícios em 60 s': len(r), 'instantes (s)': ' '.join('%.1f' % x for x in r) or '-'}


def fim_de_programa(e):
    """programa anda 1 s, manda parar e termina; 60 s depois"""
    e.anda(1.0, 40)
    e.anda(0.2, 0)
    t0 = e.t
    e.roda(60.0)
    r = [x - t0 for x in instantes_reset(e)]
    return {'reinícios nos 60 s seguintes': len(r), 'instantes depois do fim (s)': ' '.join('%.1f' % x for x in r) or '-'}


def comeco_no_reinicio(e):
    """um programa começa 5 ms depois de um reinício pelo watchdog: quanto tempo a placa leva para responder"""
    e.anda(0.5, 0)                      # um programa falou e terminou
    t0 = e.t
    while e.resets == 0 and e.t < t0 + 20:
        e.roda(0.001)
    t_reset = e.t
    e.roda(0.005)
    perdidos = 0
    while e.t < t_reset + 2.0:
        prox = e.t + 0.02
        if e.cmd(MODO_PID, 30) is not None:
            break
        perdidos += 1
        e.ate(prox)
    return {'reinício depois do fim do programa (s)': round(t_reset - t0, 1),
            'comandos perdidos (um a cada 20 ms)': perdidos, 'tempo até a primeira resposta (ms)': round((e.t - t_reset) * 1000)}


def _piscadas(e, dur, vel=0):
    """roda 'dur' segundos mandando um comando a cada 20 ms; devolve as piscadas longas do LED (PA6)
    como (início, duração) em ms e o instante da primeira resposta, tudo a partir de agora"""
    t0 = e.t
    e.roda(0)
    e.rx = []
    prox = t0 + 0.005
    piscadas, subiu, antes = [], None, 0
    while e.t < t0 + dur:
        if e.t >= prox:
            e.envia(pacote(MODO_PID, vel))
            prox += 0.02
        e.roda(0.0005)
        led = dll.emu_pino(0, 6)
        if led and not antes:
            subiu = e.t
        elif antes and not led and e.t - subiu > 0.02:      # o LED de "comando recebido" dura menos de 1 ms
            piscadas.append((round((subiu - t0) * 1000), round((e.t - subiu) * 1000)))
        antes = led
    resposta = round((e.rx[0][0] - t0) * 1000) if e.rx else None
    return piscadas, resposta


def piscada_ao_ligar(e):
    """a placa liga com um programa já mandando velocidade 40: piscadas do LED e quando ela começa a obedecer"""
    e = Placa(e.qual, eeprom=open(ARQ_EE, 'rb').read())
    piscadas, resposta = _piscadas(e, 1.0, 40)
    tr = e.traco()
    andando = tr[tr[:, 7] > 200]
    return {'piscadas do LED ao ligar': len(piscadas),
            'início e duração de cada uma (ms)': ' '.join('%d+%d' % p for p in piscadas) or '-',
            'primeira resposta depois de ligar (ms)': resposta,
            'motor começa a girar (ms)': round(float(andando[0, 0]) * 1000) if len(andando) else None}


def piscada_no_reinicio(e):
    """reinício pelo watchdog (programa terminou) e outro programa começa na hora: piscadas e primeira resposta"""
    e.anda(0.5, 0)
    t0 = e.t
    while e.resets == 0 and e.t < t0 + 20:
        e.roda(0.001)
    piscadas, resposta = _piscadas(e, 1.0)
    return {'piscadas do LED no reinício': len(piscadas),
            'início e duração de cada uma (ms)': ' '.join('%d+%d' % p for p in piscadas) or '-',
            'primeira resposta depois do reinício (ms)': resposta}


def piscada_na_calibracao(e):
    """a calibração é pedida 50 ms depois de ligar (ela para o loop): as piscadas continuam?"""
    e = Placa(e.qual, eeprom=open(ARQ_EE, 'rb').read())
    e.roda(0.05)
    e.envia(pacote(CALIBRACAO))
    t0 = e.t
    piscadas, subiu, antes = [], None, 0
    while e.t < t0 + 1.2:
        e.roda(0.0005)
        led = dll.emu_pino(0, 6)
        if led and not antes:
            subiu = e.t
        elif antes and not led and e.t - subiu > 0.02:
            piscadas.append(round((e.t - subiu) * 1000))
        antes = led
    return {'piscadas (contando a que já tinha começado)': len(piscadas),
            'duração de cada uma (ms)': ' '.join(str(p) for p in piscadas) or '-',
            'LED no fim': 'aceso' if antes else 'apagado'}


def freio_parado(e):
    """para em BREAK, a roda é empurrada 90 graus e o programa liga o freio travado"""
    e.anda(1.0, 40)
    e.anda(0.5, 0)
    e.mao(0, 1156)                      # 0,5 s = 578 contagens = 90 graus
    e.anda(0.5, 0)
    e.mao(0, None)
    e.anda(0.3, 0)
    th0 = e.motor(0)[0]
    e.cmd(SET_FREIO, 1)
    for _ in range(75):
        e.roda(0.02)
        e.cmd(ATUALIZA_P)
    tr = e.traco()
    tr = tr[tr[:, 0] > e.t - 1.5]
    return {'a roda girou sozinha (graus)': (e.motor(0)[0] - th0) * GRAUS,
            'velocidade máxima no tranco (cont/s)': float(abs(tr[:, 7]).max())}


def hold_erro_grande(e):
    """freio travado e a roda segurada a 4375 contagens (1,9 volta) do ponto de hold: força do motor para voltar"""
    e.cmd(SET_FREIO, 1)
    e.anda(0.5, 30)
    e.anda(0.5, 0)
    e.mao(0, 4375)
    for _ in range(50):
        e.roda(0.02)
        e.cmd(ATUALIZA_P)
    e.mao(0, 0.0)                       # segura parada nessa posição
    for _ in range(10):
        e.roda(0.02)
        e.cmd(ATUALIZA_P)
    t0 = e.t
    for _ in range(25):
        e.roda(0.02)
        e.cmd(ATUALIZA_P)
    e.mao(0, None)
    tr = e.traco()
    tr = tr[tr[:, 0] > t0]
    return {'potência do motor contra a mão (%)': float(-tr[:, 1].mean() * 100)}


def regressao(e):
    """velocidade com o PID, giro por ângulo e freio travado: devem dar o mesmo nos dois"""
    saida = {}
    for v in (20, 50, 80, -35):
        e.anda(1.2, v)
        tr = e.traco()
        tr = tr[tr[:, 0] > e.t - 0.6]
        saida['velocidade média com %d (cont/s)' % v] = round(float((tr[-1, 5] - tr[0, 5]) / (tr[-1, 0] - tr[0, 0])))
    e.anda(0.6, 0)
    r = e.cmd(ATUALIZA_P)
    th0, c0 = e.motor(0)[0], r[2]
    e.cmd(MODO_PID, 40, 1600 >> 8, 1600 & 0xFF)
    for _ in range(100):
        e.roda(0.02)
        r = e.cmd(ATUALIZA_P)
    saida['giro de 1600: andou (contagens)'] = round(e.motor(0)[0] - th0)
    saida['giro de 1600: contador do firmware'] = r[2] - c0
    e.cmd(SET_FREIO, 1)
    e.anda(0.8, 40)
    e.anda(0.5, 0)
    th0 = e.motor(0)[0]
    e.mao(0, 400)
    e.anda(0.3, 0)                      # empurra 120 contagens com o hold ligado
    e.mao(0, None)
    e.anda(1.0, 0)
    saida['hold: erro depois de empurrar 120 contagens'] = round(e.motor(0)[0] - th0)
    r = e.cmd(ATUALIZA_P)
    saida['contador do firmware - eixo (contagens)'] = round(r[2] - e.motor(0)[0])
    saida['reinícios durante o teste'] = e.resets
    return saida


CENARIOS = [sem_programa, fim_de_programa, comeco_no_reinicio, piscada_ao_ligar, piscada_no_reinicio,
            piscada_na_calibracao, freio_parado, hold_erro_grande, regressao]

if __name__ == '__main__':
    if not os.path.exists(ARQ_EE):
        calibra()
    so = sys.argv[1:]
    tudo = {}
    for c in CENARIOS:
        if so and c.__name__ not in so:
            continue
        res = {q: c(placa(q)) for q in ('antigo', 'novo')}
        tudo[c.__name__] = res
        print('\n== %s: %s' % (c.__name__, ' '.join(c.__doc__.split())))
        for k in res['antigo']:
            a, b = res['antigo'][k], res['novo'][k]
            fmt = (lambda x: '%10.2f' % x) if isinstance(a, float) else (lambda x: '%10s' % x)
            print('   %-52s antigo %s   novo %s' % (k, fmt(a), fmt(b)))
    json.dump(tudo, open(os.path.join(BUILDS, 'resultado_placa.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
