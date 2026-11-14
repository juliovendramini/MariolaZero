"""Polaridade automática: motor e/ou encoder ligados ao contrário e falhas na calibração.

Para cada caso o próprio firmware calibra e depois o teste confere: modo potência, velocidade com o PID,
freio travado e o estado que a placa informa."""
import sys

from emu import *
from placa import *

RESULTADO = ['ok', 'encoder não contou', 'mesmo sentido', 'sentidos desiguais']
# nome, motor trocado, encoder trocado, falha (1 = canal A solto, 2 = canal B solto, 4 = motor desligado), fator da ré
CASOS = [('tudo certo', 0, 0, 0, 0), ('encoder trocado', 0, 1, 0, 0), ('motor trocado', 1, 0, 0, 0),
         ('os dois trocados', 1, 1, 0, 0), ('canal A do encoder solto', 0, 0, 1, 0),
         ('canal B do encoder solto', 0, 0, 2, 0), ('motor desligado', 0, 0, 4, 0), ('ré com metade da força', 0, 0, 0, 0.5)]


def estado_txt(e):
    return '%s%s, %s' % ('calibrado' if e & 1 else 'sem calibração', ' invertido' if e & 2 else '', RESULTADO[(e >> 2) & 3])


def vel(e, dur=0.4):
    tr = e.traco()
    tr = tr[tr[:, 0] > e.t - dur]
    return (tr[-1, 5] - tr[0, 5]) / (tr[-1, 0] - tr[0, 0])


def brick(qual, mi, ei, falha, k_re, eeprom=None):
    e = Mariola(*firmware('brick', qual), eeprom=eeprom)
    dll.emu_polaridade(0, mi, ei)
    dll.emu_falha(0, falha, k_re)
    e.roda(0.4)
    return e


def testa_brick(qual, mi, ei, falha, k_re, religa):
    e = brick(qual, mi, ei, falha, k_re)
    e.envia(bytes([0xF3] + [0] * 9))
    e.roda(31.0)
    cal = struct.unpack('<4i', e.eeprom(16))[:2]
    if religa:                                          # firmware antigo: a calibração só vale depois de religar
        e = brick(qual, mi, ei, falha, k_re, eeprom=e.eeprom())
    r = e.comando(bytes([0xF4] + [0] * 9))
    informado = struct.unpack('>i', r[1:5])[0]
    est = r[9] & 0x0F
    e.anda(0.3, 0, 0)
    e.anda(1.0, 40, 0, cmd=POTENCIA)
    vp = vel(e)
    cp = e.motores(0, 0, cmd=POTENCIA)[1]
    e.anda(0.5, 0, 0)
    c0 = e.motores(0, 0)[1]
    e.anda(1.5, 40, 0)
    vv = vel(e)
    dc = e.motores(0, 0)[1] - c0
    e.anda(0.6, 0, 0, freio=HOLD)
    th0 = e.motor(0)[0]
    e.mao(0, 300 if not mi else -300)
    e.anda(0.3, 0, 0, freio=HOLD)
    e.mao(0, None)
    e.anda(1.5, 0, 0, freio=HOLD)
    tr = e.traco()
    tr = tr[tr[:, 0] > e.t - 1.0]
    return cal, informado, est, vp, cp, vv, dc, e.motor(0)[0] - th0, float(abs(tr[:, 7]).max())


def testa_placa(qual, mi, ei, falha, k_re, religa):
    e = Placa(qual)
    dll.emu_polaridade(0, mi, ei)
    dll.emu_falha(0, falha, k_re)
    e.roda(1.0)
    e.envia(pacote(CALIBRACAO))
    e.roda(15.5)
    cal = struct.unpack('<2i', e.eeprom(8))
    r = e.comando(pacote(GET_CALIB), 8)
    informado = struct.unpack('>h', r[3:5])[0]
    est = r[2]
    e.anda(0.3, 0)
    e.anda(1.0, 40, modo=MODO_PWM)
    vp = vel(e)
    cp = e.cmd(ATUALIZA_P)[2]
    e.anda(0.5, 0)
    c0 = e.cmd(ATUALIZA_P)[2]
    e.anda(1.5, 40)
    vv = vel(e)
    dc = e.cmd(ATUALIZA_P)[2] - c0
    e.cmd(SET_FREIO, 1)
    e.anda(0.6, 0)
    th0 = e.motor(0)[0]
    e.mao(0, 600)
    e.anda(0.3, 0)
    e.mao(0, None)
    e.anda(1.5, 0)
    tr = e.traco()
    tr = tr[tr[:, 0] > e.t - 1.0]
    return cal, informado, est, vp, cp, vv, dc, e.motor(0)[0] - th0, float(abs(tr[:, 7]).max())


if __name__ == '__main__':
    qual = sys.argv[1] if len(sys.argv) > 1 else 'novo'
    falhou = 0
    for nome, f, cheio in (('BRICK', testa_brick, 2331), ('PLACA EXTERNA', testa_placa, 4659)):
        print('\n%s, firmware "%s" (velocidade livre do modelo: %d contagens/s)' % (nome, qual, cheio))
        print('  %-26s| EEPROM (hor, anti) | informado | estado                                 | potência 40: vel, contador | velocidade 40: vel, contador | HOLD: erro, vel. máx | veredito'
              % 'caso')
        for caso, mi, ei, falha, k_re in CASOS:
            cal, inf, est, vp, cp, vv, dc, erro, vmax = f(qual, mi, ei, falha, k_re, qual != 'novo')
            calibrado = bool(est & 1) if qual == 'novo' else (inf != 0)
            sentido = -1 if mi else 1                       # para que lado o eixo gira com potência positiva
            if falha:
                # sem encoder (ou sem motor) não pode haver calibração nem disparo
                ok = not calibrado and abs(vv) <= abs(vp) + 0.1 * cheio and abs(erro) < 400 and vmax < cheio * 0.5
            else:
                alvo = inf / 0.024576 if nome == 'BRICK' else inf / 0.025
                ok = (calibrado and vp * sentido > 0 and cp > 0 and abs(vv * sentido - 0.4 * alvo) < 0.1 * alvo
                      and dc > 0 and abs(erro) < 60 and vmax < cheio * 0.9)
            falhou += not ok
            print('  %-26s| %-18s | %9d | %-38s | %+6.0f  %+7d           | %+6.0f  %+7d             | %+6.0f  %6.0f       | %s' % (
                caso, str(tuple(cal)), inf, estado_txt(est) if qual == 'novo' else '(firmware antigo não informa)',
                vp, cp, vv, dc, erro, vmax, 'ok' if ok else 'FALHOU'))
    print('\n%d caso(s) com problema' % falhou)
    sys.exit(1 if falhou else 0)
