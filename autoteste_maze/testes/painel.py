"""Tela OLED e teclado (4 botões e 4 LEDs), na placa do conector TELA (I2C 0)."""

import time

import interface as I


def roda(ctx):
    rel = ctx.rel
    ui = ctx.ui
    if ui.tela is None:
        rel.falha(f'tela não respondeu ({ui.erro_tela})', 'cabo do conector TELA, ou tela fora do 0x3C')
    else:
        rel.ok('tela respondeu (0x3C no I2C 0)')
    if ui.teclado is None:
        rel.falha(f'teclado não respondeu ({ui.erro_teclado})', 'cabo do conector TELA, ou teclado fora do 0x38')
        return
    rel.ok('teclado respondeu (0x38 no I2C 0)')

    # botão preso: apertado o tempo todo sem ninguém tocar
    ui.mensagem('TECLADO', 'nao toque nos botoes...', 1.0)
    presos = set(I.NOMES_BOTOES)
    for _ in range(20):
        presos &= ui.apertados()
        time.sleep(0.02)
    for b in sorted(presos):
        rel.falha(f'botão {I.NOMES_BOTOES[b]} aparece apertado o tempo todo', 'botão preso ou trilha em curto')

    if ui.automatico:
        rel.pulou('botões e LEDs do teclado (precisa de alguém apertando e olhando)')
        return
    if ui.console:
        rel.pulou('botões e LEDs do teclado: rodando com respostas pelo terminal')
        return

    # cada botão, na ordem; VOLTAR por último (antes dele, VOLTAR não pula: é um dos testados)
    for b in (I.ENTER, I.CIMA, I.BAIXO, I.VOLTAR):
        nome = I.NOMES_BOTOES[b]
        ui.mostra('TECLADO', f'aperte {nome}', '(10 s)', '')
        ui.solta_tudo()
        fim = time.monotonic() + 10
        visto = None
        outros = set()
        while time.monotonic() < fim:
            agora = ui.apertados()
            if b in agora:
                visto = True
                break
            outros |= agora
            time.sleep(0.02)
        if visto:
            rel.ok(f'botão {nome} funciona')
            ui.mostra('TECLADO', f'{nome} ok', '', '')
        else:
            extra = (' (apareceu ' + ', '.join(I.NOMES_BOTOES[o] for o in sorted(outros)) + ')') if outros else ''
            rel.falha(f'botão {nome} não respondeu em 10 s{extra}',
                      'botões trocados no firmware do teclado?' if outros else 'botão ou solda')
        time.sleep(0.3)

    # LEDs: um por vez, com o nome na tela
    nomes = ('branco', 'vermelho', 'laranja', 'verde')
    for volta in range(2):
        for i, nome in enumerate(nomes):
            ui.leds(*(j == i for j in range(4)))
            ui.mostra('LEDS DO TECLADO', f'aceso: {nome}', f'({i + 1}o da esquerda)', '')
            time.sleep(0.6)
    ui.leds(True, True, True, True)
    r = ui.pergunta('LEDS DO TECLADO', 'Acenderam um por vez, na ordem? (agora os 4)')
    ui.leds(False, False, False, False)
    if r is None:
        rel.pulou('LEDs do teclado (sem resposta)')
    elif r:
        rel.ok('LEDs do teclado acendem na ordem')
    else:
        rel.falha('LEDs do teclado com problema (resposta do operador)', 'LED, resistor ou transistor NPN')

    # tela: padrão
    ui.mostra('#' * I.LARGURA, '0123456789ABCDEFGHIJ', 'abcdefghij jklmnopqr', '#' * I.LARGURA)
    time.sleep(3)
    r = ui.pergunta('TELA', 'As 4 linhas de antes apareceram inteiras?')
    if r is None:
        rel.pulou('tela (sem resposta)')
    elif r:
        rel.ok('tela mostra as 4 linhas')
    else:
        rel.falha('tela com linhas faltando ou borradas (resposta do operador)')
    if ui.erros_leitura_teclado:
        rel.aviso(f'{ui.erros_leitura_teclado} leituras do teclado falharam', 'mau contato no conector TELA')
