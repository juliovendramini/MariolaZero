"""Sensores seriais a 115200: giroscópio (BMI160, comando 0 -> 8 bytes) e sensor de linha Pro1616
(comando 0x61 -> 16 bytes). Os comandos 0x62/0x63 (calibração do sensor de linha) NUNCA são enviados."""

import struct
import time

from contexto import porta, PORTAS_SERIAIS
from interface import ENTER
from portas import Portas


def _abre(nome_porta, timeout=0.05):
    try:
        return Portas().abre_porta_serial(porta(nome_porta), 115200, timeout=timeout)
    except Exception:
        return None


def _troca(ser, comando, tamanho):
    ser.reset_input_buffer()
    ser.write(bytes([comando]))
    dados = ser.read(tamanho)
    fim = time.monotonic() + 0.03
    while len(dados) < tamanho and time.monotonic() < fim:
        dados += ser.read(tamanho - len(dados))
    return dados if len(dados) == tamanho else None


def _sonda(nome_porta, comando, tamanho):
    ser = _abre(nome_porta)
    if ser is None:
        return False
    try:
        return sum(1 for _ in range(3) if _troca(ser, comando, tamanho)) >= 2
    except Exception:
        return False
    finally:
        try:
            ser.close()
        except Exception:
            pass


def _portas_livres(ctx):
    """Portas seriais que não são do barramento (no barramento, 115200 só faz barulho)."""
    bar = (ctx.perfil.get('barramento') or {}).get('porta')
    return [p for p in PORTAS_SERIAIS if p != bar]


def procura(ctx, comando, tamanho, menos=()):
    return [p for p in _portas_livres(ctx) if p not in menos and _sonda(p, comando, tamanho)]


# ---------------------------------------------------------------------------- giroscópio
def _z(dados):
    return struct.unpack('>hhh', dados[:6])


def giroscopio(ctx):
    rel = ctx.rel
    ui = ctx.ui
    esperado = ctx.perfil.get('giroscopio')
    ui.mensagem('GIROSCOPIO', f'procurando no {esperado or "todas as portas"}...')
    nome = None
    if esperado and _sonda(esperado, 0, 8):
        nome = esperado
        rel.ok(f'giroscópio respondeu no {esperado}')
    else:
        linhas = [s['porta'] for s in ctx.perfil.get('sensores_linha', [])]
        achados = procura(ctx, 0, 8, menos=(esperado,) + tuple(linhas))
        if esperado:
            rel.falha(f'o giroscópio não respondeu no {esperado}',
                      f'achei algo que responde como giroscópio em: {", ".join(achados)}' if achados
                      else 'cabo, placa do giroscópio sem 5 V ou firmware')
        if achados:
            nome = achados[0]
            if esperado:
                rel.info(f'testando o giroscópio que achei no {nome}')
            else:
                rel.ok(f'giroscópio encontrado no {nome}')
    if nome is None:
        return
    ser = _abre(nome)
    try:
        # taxa e respostas perdidas
        boas = 0
        t0 = time.monotonic()
        amostras = []
        for _ in range(200):
            d = _troca(ser, 0, 8)
            if d:
                boas += 1
                amostras.append(_z(d))
        duracao = time.monotonic() - t0
        txt = f'giroscópio: {boas}/200 respostas, {boas / duracao:.0f} leituras/s'
        (rel.ok(txt) if boas >= 196 else rel.aviso(txt, 'respostas perdidas: cabo ou ruído') if boas >= 150
         else rel.falha(txt, 'o giroscópio responde mal: cabo, 5 V ou firmware'))
        if not amostras:
            return
        x, y, z0 = amostras[-1]
        txt = f'inclinação parada: X {x}°, Y {y}°'
        if abs(x) > 5 or abs(y) > 5:
            rel.aviso(txt, 'robô fora do plano, ou a placa do giroscópio torta/solta')
        else:
            rel.ok(txt)

        # deriva com o robô parado
        if ui.automatico:
            segundos = 10
        else:
            r = ui.pergunta('GIROSCOPIO', 'Robo parado no chao? Mede 20 s a deriva.')
            segundos = 20 if r else 0
        if segundos:
            inicio = time.monotonic()
            zs = []
            while time.monotonic() - inicio < segundos:
                d = _troca(ser, 0, 8)
                if d:
                    zs.append(_z(d)[2])
                    ui.mostra('GIROSCOPIO', 'nao mexa no robo', f'Z = {zs[-1]}',
                              f'{segundos - (time.monotonic() - inicio):.0f} s', eco=False)
                time.sleep(0.05)
            if zs:
                deriva = (zs[-1] - zs[0]) * 60 / segundos
                txt = f'deriva do Z parado: {zs[-1] - zs[0]:+d}° em {segundos} s ({deriva:+.1f}°/min)'
                if abs(deriva) > 3:
                    rel.falha(txt, 'calibre o giroscópio parado (Giroscopio.calibra()) ou a placa está ruim')
                elif abs(deriva) > 1:
                    rel.aviso(txt, 'deriva alta: calibre o giroscópio com o robô parado')
                else:
                    rel.ok(txt)
                if max(zs) - min(zs) > 3:
                    rel.aviso(f'o Z pulou {max(zs) - min(zs)}° com o robô parado', 'vibração ou leituras ruins')
        else:
            rel.pulou('deriva do giroscópio')

        # giro de 90° à mão
        if ui.automatico or ui.console:
            rel.pulou('giro de 90° à mão (precisa de alguém)')
            return
        r = ui.pergunta('GIROSCOPIO', 'Gire o robo 90 graus para a DIREITA e aperte ENTER',
                        sim='ENTER=girei', nao='VOLTAR=pula')
        d1 = _troca(ser, 0, 8) if r else None
        if not r or not d1:
            rel.pulou('giro de 90° à mão')
            return
        z1 = _z(d1)[2]
        z_antes = zs[-1] if segundos and zs else z0
        giro = z1 - z_antes
        lado = 'aumenta' if giro > 0 else 'diminui'
        txt = f'girando 90° para a direita o Z {lado} {abs(giro)}°'
        if abs(abs(giro) - 90) > 10:
            rel.aviso(txt, 'giro diferente de 90°: escala, placa solta, ou o giro à mão não foi de 90°')
        else:
            rel.ok(txt)
        esperado_lado = ctx.perfil.get('giroscopio_direita')
        if esperado_lado and esperado_lado != lado:
            rel.aviso(f'o programa da equipe espera que o Z {esperado_lado} para a direita',
                      'placa do giroscópio montada virada?')
    finally:
        ser.close()


# ---------------------------------------------------------------------------- sensor de linha
def _media(lista):
    return [sum(c) / len(lista) for c in zip(*lista)] if lista else None


def _amostras(ser, n=10):
    out = []
    for _ in range(n):
        d = _troca(ser, 0x61, 16)
        if d:
            out.append(list(d))
        time.sleep(0.01)
    return out


CANAIS_IR = ('IR0', 'IR1', 'IR2', 'IR3')
CANAIS_C = ((7, 'TCS1'), (11, 'TCS meio'), (15, 'TCS2'))


def sensores_linha(ctx):
    rel = ctx.rel
    ui = ctx.ui
    lista = ctx.perfil.get('sensores_linha', [])
    if not lista:
        if ctx.perfil.get('procurar_tudo'):
            achados = procura(ctx, 0x61, 16, menos=(ctx.perfil.get('giroscopio'),))
            lista = [{'porta': p, 'nome': f'sensor do {p}'} for p in achados]
            if not achados:
                rel.info('nenhum sensor de linha encontrado')
        else:
            rel.pulou('o robo.json não tem sensor de linha')
            return
    for s in lista:
        nome = f'sensor de linha {s.get("nome", "")} ({s["porta"]})'
        ui.mensagem('SENSOR DE LINHA', f'{s.get("nome", "")} {s["porta"]}')
        ser = _abre(s['porta'])
        if ser is None or not _sonda_aberta(ser):
            if ser is not None:
                ser.close()
            menos = tuple(x['porta'] for x in lista) + (ctx.perfil.get('giroscopio'),)
            outros = procura(ctx, 0x61, 16, menos=menos)
            rel.falha(f'{nome} não respondeu',
                      f'algo responde como sensor de linha em: {", ".join(outros)}' if outros
                      else 'cabo, sensor sem 5 V ou firmware do Pro1616')
            continue
        try:
            boas = len(_amostras(ser, 100))
            txt = f'{nome}: {boas}/100 respostas'
            (rel.ok(txt) if boas >= 98 else rel.aviso(txt, 'respostas perdidas: cabo') if boas >= 70
             else rel.falha(txt, 'o sensor responde mal: cabo ou 5 V'))
            v = _media(_amostras(ser, 5))
            rel.info(f'{nome} agora: IR {[round(x) for x in v[:4]]}, RGBC {[round(x) for x in v[4:]]}')
            if ui.automatico or ui.console:
                rel.pulou(f'{nome}: branco e preto (precisa de alguém)')
                continue
            leituras = {}
            for cor in ('BRANCO', 'PRETO'):
                b = ui.ao_vivo(lambda _p: _linhas_sensor(ser, f'ponha no {cor}'), periodo=0.15)
                if b != ENTER:
                    break
                leituras[cor] = _media(_amostras(ser, 10))
            if len(leituras) < 2:
                rel.pulou(f'{nome}: branco e preto (VOLTAR)')
                continue
            br, pr = leituras['BRANCO'], leituras['PRETO']
            rel.info(f'{nome} branco: IR {[round(x) for x in br[:4]]}, C {[round(br[i]) for i, _ in CANAIS_C]}')
            rel.info(f'{nome} preto:  IR {[round(x) for x in pr[:4]]}, C {[round(pr[i]) for i, _ in CANAIS_C]}')
            ruins = []
            for i, canal in enumerate(CANAIS_IR):
                if br[i] - pr[i] < 40:
                    ruins.append(f'{canal} ({pr[i]:.0f}->{br[i]:.0f})')
            for i, canal in CANAIS_C:
                if br[i] - pr[i] < 40:
                    ruins.append(f'{canal} ({pr[i]:.0f}->{br[i]:.0f})')
            if ruins:
                rel.falha(f'{nome}: quase não muda do preto para o branco: {", ".join(ruins)}',
                          'sensor sujo, alto demais (a equipe usa 12 mm) ou sem calibração do branco/preto')
            else:
                rel.ok(f'{nome}: os 4 IR e os 3 TCS separam branco de preto')
            if min(br[:4]) < 70:
                rel.aviso(f'{nome}: branco do IR abaixo de 70 ({[round(x) for x in br[:4]]})',
                          'calibre o branco de novo (o branco calibrado dá ~100)')
        finally:
            ser.close()


def _sonda_aberta(ser):
    return sum(1 for _ in range(3) if _troca(ser, 0x61, 16)) >= 2


def _linhas_sensor(ser, titulo):
    d = _troca(ser, 0x61, 16)
    if not d:
        return [titulo, 'sem resposta', '', 'ENTER=mede VOLTAR']
    ir = ' '.join(f'{x:3d}' for x in d[:4])
    c = ' '.join(f'{d[i]:3d}' for i, _ in CANAIS_C)
    return [titulo, f'IR {ir}', f'C  {c}', 'ENTER=mede VOLTAR']
