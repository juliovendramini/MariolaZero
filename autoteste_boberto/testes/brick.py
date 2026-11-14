"""Brick (ATmega328PB do Mariola, _SERIAL0): comunicação, calibração, motores 1 a 4, LEDs RGB,
buzzer e servos comuns (Timer2) e o teste de estresse."""

import statistics
import time


def _brick(ctx):
    b = ctx.brick()
    if b is None:
        ctx.rel.falha(f'o brick não respondeu ({ctx.erro_brick})',
                      'cabo USB interno do ATmega, firmware, ou o brick sem 5 V')
    return b


# ---------------------------------------------------------------------------- comunicação
def comunicacao(ctx):
    rel = ctx.rel
    ui = ctx.ui
    ui.mensagem('BRICK', 'conversando com o ATmega...')
    b = _brick(ctx)
    if b is None:
        return
    rel.ok(f'brick respondeu em {b.ser.port}')
    falhas_antes = b.falhas_comunicacao
    tempos = []
    erros = 0
    for i in range(200):
        t0 = time.monotonic()
        try:
            b.estado()
            tempos.append((time.monotonic() - t0) * 1000)
        except Exception:
            erros += 1
        if i % 20 == 0:
            ui.mostra('BRICK', 'comunicacao', f'{i}/200', '', eco=False)
    repeticoes = b.falhas_comunicacao - falhas_antes
    if tempos:
        txt = (f'200 trocas: média {statistics.mean(tempos):.1f} ms, máximo {max(tempos):.1f} ms, '
               f'{repeticoes} repetidas, {erros} perdidas')
        if erros:
            rel.falha(txt, 'a comunicação com o ATmega cai: cabo USB interno, hub ou 5 V')
        elif repeticoes or max(tempos) > 40:
            rel.aviso(txt, 'respostas atrasadas ou repetidas: ruído ou hub USB')
        else:
            rel.ok(txt)
    else:
        rel.falha('nenhuma das 200 trocas com o brick deu certo')

    # calibração dos motores 1 e 2 (firmware de 10/11/2026 em diante informa o estado)
    try:
        cal = b.obtem_calibracao_motores()
        estado = b.estado_calibracao_motores()
    except Exception as erro:
        rel.falha(f'não deu para ler a calibração ({erro})')
        return
    rel.info(f'calibração gravada: motor 1 = {cal[0]}, motor 2 = {cal[1]}')
    if estado is None:
        rel.info('firmware antigo: não informa se a calibração vale nem se o encoder está invertido')
        for m, v in ((1, cal[0]), (2, cal[1])):
            if v == 0:
                rel.aviso(f'motor {m} sem calibração (0)', 'calibre (menu: Calibrar motores, rodas no ar)')
        return
    for m, e in enumerate(estado, 1):
        if m not in ctx.perfil.get('brick', {}).get('motores_encoder', [1, 2]):
            continue
        if not e['calibrado']:
            rel.aviso(f'motor {m} sem calibração válida: sem ela o brick não usa o encoder',
                      'calibre (menu: Calibrar motores, rodas no ar)')
        else:
            rel.ok(f'motor {m} calibrado')
        if e['encoder_invertido']:
            rel.info(f'motor {m}: encoder ligado ao contrário do motor (o brick corrige sozinho)')
        if e['resultado'] != 'ok':
            rel.falha(f'motor {m}: a última calibração deu "{e["resultado"]}"',
                      'motor ou encoder desligado, ou um fio do encoder solto')


def calibra(ctx):
    """Calibração dos motores 1 e 2 (30 s girando sozinhos)."""
    rel = ctx.rel
    b = _brick(ctx)
    if b is None:
        return
    if not ctx.pode_mover('os motores 1 e 2 por 30 s'):
        rel.pulou('calibração dos motores (rodas no ar não confirmado)')
        return
    try:
        b.calibra_motores()
    except Exception as erro:
        rel.falha(f'o brick não aceitou a calibração ({erro})')
        return
    inicio = time.monotonic()
    while time.monotonic() - inicio < 32:
        ctx.ui.mostra('CALIBRANDO', 'motores 1 e 2', f'{32 - (time.monotonic() - inicio):.0f} s', '', eco=False)
        time.sleep(0.5)
    b.ser.reset_input_buffer()
    try:
        estado = b.estado_calibracao_motores()
        cal = b.obtem_calibracao_motores()
    except Exception as erro:
        rel.falha(f'o brick não voltou depois da calibração ({erro})')
        return
    rel.info(f'calibração nova: motor 1 = {cal[0]}, motor 2 = {cal[1]}')
    if estado is None:
        rel.info('firmware antigo: o resultado só vale depois de desligar e ligar o brick')
        return
    for m, e in enumerate(estado, 1):
        txt = f'motor {m}: {e["resultado"]}' + (' (encoder invertido, corrigido)' if e['encoder_invertido'] else '')
        (rel.ok(txt) if e['resultado'] == 'ok' else rel.falha(txt))


# ---------------------------------------------------------------------------- motores
def _gira_brick(ctx, b, motor, valor, segundos, pid=False):
    """Gira um motor do brick (potência ou velocidade PID) e devolve (graus/s na parte final, delta total)."""
    marcas = []
    b.estado()
    inicio = time.monotonic()
    a0 = b.angulo_motor(motor)
    while time.monotonic() - inicio < segundos:
        if pid:
            b.velocidade_motor(motor, valor)
        else:
            b.potencia_motor(motor, valor)
        marcas.append((time.monotonic(), b.angulo_motor(motor)))
        if ctx.ui.cancelou():
            break
        time.sleep(0.08)
    b.para_motores()
    b.atualiza_motores()
    time.sleep(0.3)
    b.estado()
    delta = b.angulo_motor(motor) - a0
    meio = [m for m in marcas if m[0] - inicio > segundos * 0.4]
    if len(meio) >= 2 and meio[-1][0] > meio[0][0]:
        vel = (meio[-1][1] - meio[0][1]) / (meio[-1][0] - meio[0][0])
    else:
        vel = 0.0
    return vel, delta


def analisa_giro(rel, nome, vel_mais, vel_menos, d_mais, d_menos, minimo=20):
    """Regras comuns ao brick e às placas: contou? para o lado certo? igual nos dois sentidos?"""
    problemas = 0
    if abs(d_mais) < minimo and abs(d_menos) < minimo:
        rel.falha(f'{nome}: o encoder não contou ({d_mais:+.0f} e {d_menos:+.0f})',
                  'motor sem força (ponte H, fio do motor) ou encoder desligado/sem 5 V')
        return 1
    if abs(d_mais) < minimo or abs(d_menos) < minimo:
        rel.falha(f'{nome}: só contou num sentido ({d_mais:+.0f} e {d_menos:+.0f})',
                  'um canal do encoder (A ou B) solto, ou a ponte H só liga num sentido')
        return 1
    if d_mais < 0 < d_menos:
        rel.aviso(f'{nome}: com potência positiva o encoder conta para trás',
                  'motor ou encoder ligado invertido (o firmware de 10/11 corrige na calibração)')
        problemas += 1
    elif not (d_mais > 0 > d_menos):
        rel.falha(f'{nome}: o encoder contou para o mesmo lado nos dois sentidos ({d_mais:+.0f} e {d_menos:+.0f})',
                  'um canal do encoder solto (conta sempre igual)')
        return 1
    a, b = abs(vel_mais), abs(vel_menos)
    if max(a, b) > 0 and abs(a - b) / max(a, b) > 0.25:
        rel.aviso(f'{nome}: velocidade diferente nos dois sentidos ({a:.0f} e {b:.0f} por s)',
                  'atrito, engrenagem ou motor gasto')
        problemas += 1
    return problemas


def motores_brick(ctx):
    rel = ctx.rel
    ui = ctx.ui
    cfg = ctx.perfil.get('brick', {})
    com_encoder = cfg.get('motores_encoder', [1, 2])
    sem_encoder = cfg.get('motores_sem_encoder', [])
    b = _brick(ctx)
    if b is None:
        return
    if not ctx.pode_mover('os motores do brick'):
        rel.pulou('motores do brick (rodas no ar não confirmado)')
        return
    velocidades = {}
    for m in com_encoder:
        ui.mostra('MOTORES DO BRICK', f'motor {m}', 'potencia +40 / -40', '')
        v1, d1 = _gira_brick(ctx, b, m, 40, 1.5)
        v2, d2 = _gira_brick(ctx, b, m, -40, 1.5)
        rel.info(f'motor {m}, potência ±40: {d1:+.0f} / {d2:+.0f} ({v1:.0f} / {v2:.0f} por s)')
        if analisa_giro(rel, f'motor {m}', v1, v2, d1, d2):
            continue
        ui.mostra('MOTORES DO BRICK', f'motor {m}', 'velocidade +50 / -50', '(PID)')
        p1, e1 = _gira_brick(ctx, b, m, 50, 1.5, pid=True)
        p2, e2 = _gira_brick(ctx, b, m, -50, 1.5, pid=True)
        rel.info(f'motor {m}, velocidade ±50 (PID): {p1:.0f} / {p2:.0f} por s')
        if abs(p1) < 5 or abs(p2) < 5:
            rel.falha(f'motor {m}: com velocidade (PID) ele não gira',
                      'sem calibração válida ou PID zerado (pid_motor)')
            continue
        if p1 < 0 < p2:
            rel.aviso(f'motor {m}: com velocidade positiva ele gira para trás')
        if abs(abs(p1) - abs(p2)) / max(abs(p1), abs(p2)) > 0.2:
            rel.aviso(f'motor {m}: o PID não deixa os dois sentidos iguais ({abs(p1):.0f} e {abs(p2):.0f})')
        velocidades[m] = (abs(p1) + abs(p2)) / 2

        # giro por ângulo: o firmware para sozinho (com o freio que o robô usa; as equipes usam HOLD)
        ui.mostra('MOTORES DO BRICK', f'motor {m}', 'move_motor 360', '')
        b.set_modo_freio(b.BREAK if cfg.get('freio', 'HOLD') == 'BREAK' else b.HOLD)
        b.estado()
        a0 = b.angulo_motor(m)
        b.move_motor(m, 40, 360)
        inicio = time.monotonic()
        while time.monotonic() - inicio < 5:
            time.sleep(0.1)
            b.estado()
            if time.monotonic() - inicio > 0.4 and b.estado_motor(m) == b.PARADO:
                break
        else:
            rel.falha(f'motor {m}: move_motor(360) não parou em 5 s')
            ctx.para_tudo()
            continue
        time.sleep(0.3)
        b.estado()
        girou = abs(b.angulo_motor(m) - a0)
        b.set_modo_freio(b.BREAK)       # o HOLD seguraria o motor depois do teste
        b.atualiza_motores()
        txt = f'motor {m}: move_motor(360) girou {girou:.0f}'
        (rel.aviso(txt, 'erro grande: calibração ou freio') if abs(girou - 360) > 30 else rel.ok(txt))
    if len(velocidades) == 2:
        (va, vb) = velocidades.values()
        txt = f'motores {"/".join(map(str, velocidades))} na mesma velocidade PID: {va:.0f} e {vb:.0f} por s'
        if abs(va - vb) / max(va, vb) > 0.15:
            rel.aviso(txt, 'robô vai puxar para um lado: motor diferente, roda presa ou calibração')
        else:
            rel.ok(txt)
    for m in sem_encoder:
        ui.mostra('MOTORES DO BRICK', f'motor {m}', 'potencia +50 / -50', 'olhe o motor')
        for p in (50, -50):
            fim = time.monotonic() + 1.2
            while time.monotonic() < fim:
                b.potencia_motor(m, p)
                time.sleep(0.1)
            ctx.para_tudo()
            time.sleep(0.3)
        r = ctx.ui.pergunta(f'MOTOR {m}', 'Girou para os dois lados?')
        if r is None:
            rel.pulou(f'motor {m} (sem encoder; sem resposta)')
        elif r:
            rel.ok(f'motor {m} gira nos dois sentidos (operador)')
        else:
            rel.falha(f'motor {m} não girou nos dois sentidos (operador)', 'ponte H, fio ou motor')


# ---------------------------------------------------------------------------- LEDs RGB
def leds(ctx):
    rel = ctx.rel
    ui = ctx.ui
    cfg = ctx.perfil.get('brick', {})
    b = _brick(ctx)
    if b is None:
        return
    try:
        for nome, cor in (('vermelho', (60, 0, 0)), ('verde', (0, 60, 0)), ('azul', (0, 0, 60)),
                          ('branco', (40, 40, 40))):
            ui.mostra('LEDS RGB', f'todos em {nome}', '', '')
            b.set_led_rgb_all(*cor)
            time.sleep(0.7)
        b.set_led_rgb_all(0, 0, 0)
        for i in range(10):
            ui.mostra('LEDS RGB', f'so o LED {i}', '', '')
            b.set_led_rgb_one(i, 0, 50, 50)
            time.sleep(0.25)
            b.set_led_rgb_one(i, 0, 0, 0)
    except Exception as erro:
        rel.falha(f'o brick não aceitou o comando dos LEDs ({erro})')
        return
    r = ui.pergunta('LEDS RGB', 'Os 10 acenderam nas 4 cores e um por um?')
    if r is None:
        rel.pulou('LEDs RGB (sem resposta)')
    elif r:
        rel.ok('LEDs RGB funcionam (operador)')
    else:
        rel.falha('LEDs RGB com problema (operador)',
                  'se param num LED, o problema está nele ou na solda entre ele e o seguinte')
    if cfg.get('fita_porta4'):
        try:
            b.set_led_rgb_all_porta4(0, 50, 0)
            time.sleep(1.0)
            b.set_led_rgb_all_porta4(0, 0, 0)
        except Exception as erro:
            rel.falha(f'fita da porta 4 não aceitou o comando ({erro})')
            return
        r = ui.pergunta('FITA PORTA 4', 'A fita acendeu verde?')
        (rel.pulou('fita da porta 4') if r is None else
         rel.ok('fita da porta 4 funciona') if r else rel.falha('fita da porta 4 não acendeu'))


# ---------------------------------------------------------------------------- Timer2
def _avisa_timer2(rel, o_que, erro):
    rel.pulou(f'{o_que}: {erro}', 'o Timer2 fica com o primeiro que usar: desligue e ligue o brick')


def buzzer(ctx):
    rel = ctx.rel
    b = _brick(ctx)
    if b is None:
        return
    esperado = ctx.perfil.get('brick', {}).get('buzzer_nivel')
    try:
        nivel = b.nivel_buzzer()
        nome = {b.BUZZER_LIGA_LOW: 'LOW', b.BUZZER_LIGA_HIGH: 'HIGH'}.get(nivel, str(nivel))
        if esperado and nome != esperado:
            rel.aviso(f'buzzer configurado para ligar em {nome}, o robô usa {esperado}',
                      f'set_nivel_buzzer(Motores.BUZZER_LIGA_{esperado}) (fica na EEPROM)')
        else:
            rel.info(f'buzzer liga em {nome}')
    except Exception as erro:
        rel.info(f'firmware sem consulta do buzzer ({erro})')
    try:
        ctx.ui.mostra('BUZZER', 'tocando...', '', '')
        b.toca_som(b.SOM_BIPE_DUPLO)
        time.sleep(0.8)
        b.toca_tom(1000, 300)
        time.sleep(0.5)
    except Exception as erro:
        _avisa_timer2(rel, 'buzzer', erro)
        return
    r = ctx.ui.pergunta('BUZZER', 'Ouviu 2 bipes e um tom?')
    if r is None:
        rel.pulou('buzzer (sem resposta)')
    elif r:
        rel.ok('buzzer toca (operador)')
    else:
        rel.falha('buzzer não tocou (operador)',
                  'nível LOW/HIGH trocado, buzzer no pino 11 (DEBUG/PWM) ou sem 5 V')


def servos_comuns(ctx):
    rel = ctx.rel
    ui = ctx.ui
    lista = ctx.perfil.get('brick', {}).get('servos_comuns', [])
    if not lista:
        rel.pulou('o robo.json não tem servos comuns')
        return
    b = _brick(ctx)
    if b is None:
        return
    if not ctx.pode_mover('os servos'):
        rel.pulou('servos comuns (não confirmado)')
        return
    for s in lista:
        n, nome = s['servo'], s.get('nome', f'servo {s["servo"]}')
        repouso, teste = s.get('repouso', 90), s.get('teste', 70)
        try:
            ui.mostra('SERVOS COMUNS', f'{n}: {nome}', f'{repouso} -> {teste} -> {repouso}', '')
            b.move_servo(n, repouso)
            time.sleep(0.8)
            b.move_servo(n, teste)
            time.sleep(0.8)
            b.move_servo(n, repouso)
            time.sleep(0.8)
        except Exception as erro:
            _avisa_timer2(rel, f'servo {n}', erro)
            return
        r = ui.pergunta(f'SERVO {n}', f'{nome} foi e voltou?')
        if r is None:
            rel.pulou(f'servo comum {n} ({nome}): sem resposta')
        elif r:
            rel.ok(f'servo comum {n} ({nome}) mexe (operador)')
        else:
            rel.falha(f'servo comum {n} ({nome}) não mexeu (operador)',
                      'conector trocado (pinos 14-17), servo queimado ou sem 5 V')


# ---------------------------------------------------------------------------- estresse
def estresse(ctx, segundos=20):
    """Motores invertendo o sentido sem parar enquanto conversa com o brick e com as placas:
    acha queda de comunicação e resets do hub USB por ruído ou queda dos 5 V."""
    from testes import sistema, barramento
    rel = ctx.rel
    ui = ctx.ui
    b = _brick(ctx)
    if b is None:
        return
    if not ctx.pode_mover(f'tudo por {segundos} s'):
        rel.pulou('teste de estresse (rodas no ar não confirmado)')
        return
    motores = ctx.perfil.get('brick', {}).get('motores_encoder', [1, 2])
    placas = barramento.abre_placas(ctx, reporta=False)
    usb0 = sistema.eventos_usb(sistema.dmesg())
    falhas0 = b.falhas_comunicacao
    perdidas = 0
    placa_perdidas = 0
    tempos = []
    sinal = 1
    inicio = time.monotonic()
    proxima_troca = inicio
    try:
        while time.monotonic() - inicio < segundos:
            agora = time.monotonic()
            if agora >= proxima_troca:
                sinal = -sinal
                proxima_troca = agora + 0.4
            t0 = time.monotonic()
            try:
                for m in motores:
                    b.potencia_motor(m, 80 * sinal)
                tempos.append((time.monotonic() - t0) * 1000)
            except Exception:
                perdidas += 1
            for nome, placa in placas:
                if placa.potencia_motor(80 * sinal) is None:
                    placa_perdidas += 1
            ui.mostra('ESTRESSE', f'{agora - inicio:.0f}/{segundos} s',
                      f'brick: {b.falhas_comunicacao - falhas0} rep {perdidas} perd',
                      f'placas: {placa_perdidas} perdidas', eco=False)
            if ui.cancelou():
                rel.pulou('estresse interrompido pelo VOLTAR')
                break
    finally:
        ctx.para_tudo()
    usb1 = sistema.eventos_usb(sistema.dmesg())
    rep = b.falhas_comunicacao - falhas0
    txt = (f'{segundos} s com os motores invertendo a 80%: brick {rep} repetidas / {perdidas} perdidas, '
           f'máximo {max(tempos) if tempos else 0:.0f} ms; placas {placa_perdidas} perdidas')
    if perdidas or placa_perdidas:
        rel.falha(txt, 'a comunicação cai com os motores fortes: 5 V caindo ou ruído (capacitor nos motores, cabos)')
    elif rep:
        rel.aviso(txt)
    else:
        rel.ok(txt)
    if usb0 is not None and usb1 is not None:
        novos = usb1[0] - usb0[0], usb1[1] - usb0[1]
        if any(novos):
            rel.falha(f'durante o estresse o hub USB reiniciou {novos[0]} vezes ({novos[1]} desconexões)',
                      'é o problema da Maze de 12/11: queda dos 5 V ou ruído dos motores no hub')
        else:
            rel.ok('hub USB não reiniciou durante o estresse')
    else:
        rel.pulou('dmesg não lido: não deu para ver resets do hub')
