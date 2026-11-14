"""Barramento serial das placas de controle de motor e dos servos inteligentes (one-wire, 250000)."""

import time

from contexto import porta, PORTAS_USB


def abre_placas(ctx, reporta=True):
    """[(nome, PlacaControleMotor)] das placas do robo.json que responderam."""
    from placaControleMotor import PlacaControleMotor
    bar = ctx.perfil.get('barramento') or {}
    if not bar.get('placas_motor'):
        return []
    ser = ctx.barramento(bar['porta'])
    if ser is None:
        if reporta:
            ctx.rel.falha(f'não abriu a porta do barramento ({bar["porta"]})',
                          'conversor USB do barramento ausente (veja o teste Sistema)')
        return []
    placas = []
    for p in bar['placas_motor']:
        nome = f'placa {p["id"]} ({p.get("nome", "")})'
        placa = PlacaControleMotor(ser, id_equipamento=p['id'])
        resp = placa.atualizar()
        if resp is None:
            if reporta:
                ctx.rel.falha(f'{nome} não respondeu no {bar["porta"]}',
                              'cabo do barramento, placa sem bateria, ou o ID mudou (menu: Procurar placas)')
            continue
        ctx.placas_abertas.append(placa)
        placas.append((nome, placa))
    return placas


def _gira_placa(ctx, placa, valor, segundos, pid=False):
    marcas = []
    inicio = time.monotonic()
    r = placa.atualizar()
    p0 = r['pulsos'] if r else 0
    perdidas = 0
    while time.monotonic() - inicio < segundos:
        r = placa.mover_pid(valor) if pid else placa.mover_pwm(valor)
        if r is None:
            perdidas += 1
        else:
            marcas.append((time.monotonic(), r['pulsos']))
        if ctx.ui.cancelou():
            break
        time.sleep(0.08)
    placa.mover_pid(0)
    time.sleep(0.3)
    r = placa.atualizar()
    delta = (r['pulsos'] if r else p0) - p0
    meio = [m for m in marcas if m[0] - inicio > segundos * 0.4]
    vel = 0.0
    if len(meio) >= 2 and meio[-1][0] > meio[0][0]:
        vel = (meio[-1][1] - meio[0][1]) / (meio[-1][0] - meio[0][0])
    return vel, delta, perdidas


def placas_motor(ctx):
    from testes.brick import analisa_giro
    rel = ctx.rel
    ui = ctx.ui
    bar = ctx.perfil.get('barramento') or {}
    if not bar.get('placas_motor'):
        rel.pulou('o robo.json não tem placas de motor')
        return
    ui.mensagem('PLACAS DE MOTOR', f'procurando no {bar["porta"]}...')
    placas = abre_placas(ctx)
    for nome, placa in placas:
        rel.ok(f'{nome} respondeu')
        cal = placa.obter_calibracao()
        if cal is None:
            rel.aviso(f'{nome}: não respondeu a calibração')
        else:
            rel.info(f'{nome}: calibração {cal}')
            if cal.get('encoder_invertido'):
                rel.info(f'{nome}: encoder ligado ao contrário do motor (a placa corrige sozinha)')
            if 'calibrado' in cal and not cal['calibrado']:
                rel.aviso(f'{nome}: sem calibração válida', 'o programa da equipe faz calibracao_manual()?')
            if cal.get('resultado', 'ok') not in ('ok', None):
                rel.falha(f'{nome}: a última calibração deu "{cal["resultado"]}"')
    if not placas or not ctx.pode_mover('as placas de motor'):
        if placas:
            rel.pulou('giro das placas de motor (rodas no ar não confirmado)')
        return
    for nome, placa in placas:
        ui.mostra('PLACAS DE MOTOR', nome[:20], 'potencia +40 / -40', '')
        v1, d1, x1 = _gira_placa(ctx, placa, 40, 1.5)
        v2, d2, x2 = _gira_placa(ctx, placa, -40, 1.5)
        rel.info(f'{nome}, potência ±40: {d1:+d} / {d2:+d} pulsos ({v1:.0f} / {v2:.0f} por s)')
        if x1 or x2:
            rel.aviso(f'{nome}: {x1 + x2} respostas perdidas girando', 'ruído no barramento com o motor ligado')
        if analisa_giro(rel, nome, v1, v2, d1, d2):
            continue
        ui.mostra('PLACAS DE MOTOR', nome[:20], 'velocidade +50 / -50', '(PID)')
        p1, _, _ = _gira_placa(ctx, placa, 50, 1.5, pid=True)
        p2, _, _ = _gira_placa(ctx, placa, -50, 1.5, pid=True)
        rel.info(f'{nome}, velocidade ±50 (PID): {p1:.0f} / {p2:.0f} pulsos por s')
        if abs(p1) < 5 or abs(p2) < 5:
            rel.falha(f'{nome}: com velocidade (PID) não gira', 'sem calibração (calibracao_manual) ou PID zerado')
        elif abs(abs(p1) - abs(p2)) / max(abs(p1), abs(p2)) > 0.2:
            rel.aviso(f'{nome}: o PID não deixa os dois sentidos iguais ({abs(p1):.0f} e {abs(p2):.0f})')
        else:
            rel.ok(f'{nome}: gira e conta nos dois sentidos')


def servos(ctx):
    from placaControleServo import PlacaControleServo
    rel = ctx.rel
    ui = ctx.ui
    bar = ctx.perfil.get('barramento') or {}
    lista = bar.get('servos', [])
    if not lista:
        rel.pulou('o robo.json não tem servos inteligentes')
        return
    achados = []
    for s in lista:
        nome = f'servo {s["id"]} ({s.get("nome", "")})'
        ui.mostra('SERVOS', nome[:20], 'consultando...', '')
        try:
            servo = PlacaControleServo(porta(bar['porta']), id_equipamento=s['id'])
        except Exception as erro:
            rel.falha(f'não abriu a porta dos servos ({erro})')
            return
        ctx.servos_abertos.append(servo)
        pos = servo.consulta_posicao()
        firmware_novo = pos is not None
        if pos is None:
            pos = servo.le_posicao()     # firmware antigo: lê com potência 0 (solta o servo)
        if pos is None:
            rel.falha(f'{nome} não respondeu no {bar["porta"]}',
                      'cabo do servo, ID mudou (menu: Procurar placas) ou servo sem bateria')
            continue
        rel.ok(f'{nome} respondeu, posição {pos}' + ('' if firmware_novo else ' (firmware antigo)'))
        if firmware_novo:
            pol = servo.consulta_polaridade()
            if pol == PlacaControleServo.POLARIDADE_NAO_CALIBRADA:
                rel.aviso(f'{nome}: polaridade não calibrada', 'autodetecta_polaridade() com o servo livre')
            elif pol is not None:
                rel.info(f'{nome}: polaridade {"invertida" if pol else "normal"}')
        if pos <= 5 or pos >= 1018:
            rel.aviso(f'{nome}: posição {pos} no fim da escala', 'potenciômetro solto ou fora da faixa')
        achados.append((nome, servo, pos, s, firmware_novo))
    if not achados or not ctx.pode_mover('os servos inteligentes (um pouco)'):
        if achados:
            rel.pulou('movimento dos servos (não confirmado)')
        return
    for nome, servo, pos, s, firmware_novo in achados:
        passo = int(s.get('passo', 60))
        alvo = pos + passo if pos < 512 else pos - passo
        ui.mostra('SERVOS', nome[:20], f'{pos} -> {alvo} -> {pos}', '')
        servo.move_servo(alvo, 200, 5)
        chegou = None
        fim = time.monotonic() + 1.5
        while time.monotonic() < fim:
            time.sleep(0.1)
            # firmware novo: só consulta; antigo: repete o comando (a resposta traz a posição)
            r = servo.consulta_posicao() if firmware_novo else servo.move_servo(alvo, 200, 5)
            if r is not None:
                chegou = r
                if abs(r - alvo) <= 15:
                    break
        servo.move_servo(pos, 200, 5)
        time.sleep(1.0)
        if chegou is None:
            rel.falha(f'{nome}: parou de responder ao mexer', 'queda de tensão ao ligar o motor do servo?')
        elif abs(chegou - pos) < passo / 2:
            rel.falha(f'{nome}: mandei ir de {pos} para {alvo} e ficou em {chegou}',
                      'motor do servo sem força, travado, ou polaridade errada')
        elif abs(chegou - alvo) > 25:
            rel.aviso(f'{nome}: foi de {pos} para {chegou} (pedi {alvo})', 'zona morta grande ou travou no caminho')
        else:
            rel.ok(f'{nome}: foi de {pos} a {chegou} e voltou')


def procura(ctx):
    """Procura placas de motor (IDs 0-255) e servos (0-253) em SERIAL1 a SERIAL3."""
    from placaControleMotor import PlacaControleMotor
    from placaControleServo import PlacaControleServo
    from testes.sistema import conversores_usb
    import sys
    rel = ctx.rel
    ui = ctx.ui
    # fecha a porta do barramento aberta por outros testes (a busca abre a dela)
    for nome, ser in list(ctx._barramento.items()):
        try:
            ser.close()
        except Exception:
            pass
    ctx._barramento.clear()
    ctx.placas_abertas.clear()
    presentes = conversores_usb() if sys.platform.startswith('linux') else {}
    candidatas = [p for p in PORTAS_USB[1:] if p in presentes] or list(PORTAS_USB[1:])
    usadas = {s['porta'] for s in ctx.perfil.get('sensores_linha', [])} | {ctx.perfil.get('giroscopio')}
    for nome_porta in candidatas:
        if nome_porta in usadas:
            continue
        ui.mostra('PROCURANDO', nome_porta, 'placas de motor', '(~6 s)')
        try:
            placas = PlacaControleMotor.buscar_motores(porta(nome_porta))
        except Exception as erro:
            rel.info(f'{nome_porta}: não abriu ({erro})')
            continue
        ui.mostra('PROCURANDO', nome_porta, 'servos', '(~6 s)')
        try:
            servos_ = PlacaControleServo.buscar_servos(porta(nome_porta))
        except Exception:
            servos_ = []
        if placas or servos_:
            rel.info(f'{nome_porta}: placas de motor {[p["id"] for p in placas]}, servos {[s["id"] for s in servos_]}')
        else:
            rel.info(f'{nome_porta}: nenhuma placa nem servo')
        bar = ctx.perfil.get('barramento') or {}
        if bar.get('porta') == nome_porta:
            for tipo, achados, esperados in (('placa de motor', placas, bar.get('placas_motor', [])),
                                             ('servo', servos_, bar.get('servos', []))):
                ids = {p['id'] for p in achados}
                ids_perfil = {p['id'] for p in esperados}
                extras = sorted(ids - ids_perfil)
                for p in esperados:
                    if p['id'] not in ids:
                        rel.falha(f'{tipo} {p["id"]} ({p.get("nome", "")}) não está no {nome_porta}',
                                  f'responde {"uma" if tipo.startswith("placa") else "um"} {tipo} com ID {", ".join(map(str, extras))} que o robo.json não tem: '
                                  'ID trocado (ou placa trocada)?' if extras else None)
                if extras and ids_perfil <= ids:
                    rel.info(f'{tipo}: o {nome_porta} tem também {extras}, que o robo.json não tem')
    rel.info('a busca de servos manda "freio solto" para as placas de motor: o programa da equipe '
             'configura de novo ao começar')
