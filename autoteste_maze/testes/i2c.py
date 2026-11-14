"""Sensores no I2C 1, atrás do mux TCA9548A (0x70): VL53L0X (distância) e TCS34725 (cor).

Os dois respondem no 0x29 (o VL53 vai para o 0x30 depois que a lib o inicia). Quem é quem sai do
registrador de identificação: VL53 = 0xC0 vale 0xEE; TCS = 0x92 (comando + 0x12) vale 0x44/0x4D/0x10.
"""

import statistics
import time

from contexto import NOME_CANAL

MUX = 0x70
IDS_TCS = (0x44, 0x4D, 0x10)


def _bus():
    from smbus2 import SMBus
    return SMBus(1)


def _le(bus, addr, reg):
    try:
        return bus.read_byte_data(addr, reg)
    except OSError:
        return None


def varre(bus):
    """{canal: [('VL53', addr) ou ('TCS', addr)]} e None se o mux não respondeu."""
    try:
        bus.write_byte(MUX, 0)
    except OSError:
        return None
    achados = {}
    for canal in range(8):
        try:
            bus.write_byte(MUX, 1 << canal)
        except OSError:
            return None
        time.sleep(0.002)
        lista = []
        for addr in (0x29, 0x30):
            if _le(bus, addr, 0xC0) == 0xEE:
                lista.append(('VL53', addr))
            elif addr == 0x29 and _le(bus, addr, 0x92) in IDS_TCS:
                lista.append(('TCS', addr))
        if lista:
            achados[canal] = lista
    try:
        bus.write_byte(MUX, 0)
    except OSError:
        pass
    return achados


def _canal(nome_porta):
    from contexto import porta
    return porta(nome_porta)


def sensores(ctx):
    rel = ctx.rel
    ui = ctx.ui
    ui.mensagem('SENSORES I2C', 'procurando VL53 e TCS nos 8 canais do mux...')
    try:
        bus = _bus()
    except Exception as erro:
        rel.falha(f'não abriu o /dev/i2c-1 ({erro})', 'overlay do I2C1 faltando (INSTALACAO.md)')
        return
    achados = varre(bus)
    if achados is None:
        rel.falha('o mux TCA9548A (0x70) não respondeu no I2C 1',
                  'sem o mux nenhum VL53/TCS funciona: cabo do I2C, 5 V ou a placa do mux')
        return
    rel.ok('mux TCA9548A respondeu')
    tipos = {c: {t for t, _ in lista} for c, lista in achados.items()}
    esperados = [('VL53', s) for s in ctx.perfil.get('vl53', [])] + [('TCS', s) for s in ctx.perfil.get('tcs', [])]
    usados = set()
    faltando = []
    for tipo, s in esperados:
        c = _canal(s['porta'])
        if tipo in tipos.get(c, set()):
            usados.add((tipo, c))
        else:
            faltando.append((tipo, s))
    sobrando = [(t, c) for c, ts in tipos.items() for t in ts if (t, c) not in usados]
    explicados = set()
    for tipo, s in faltando:
        palpite = [NOME_CANAL[c] for t, c in sobrando if t == tipo]
        explicados |= {(t, c) for t, c in sobrando if t == tipo}
        rel.falha(f'{tipo} "{s.get("nome", "")}" não respondeu no {s["porta"]}',
                  (f'tem um {tipo} sobrando no {", ".join(palpite)}: cabo trocado de porta?' if palpite
                   else 'cabo solto, sensor sem 3,3/5 V ou queimado'))
    for tipo, c in sobrando:
        if (tipo, c) in explicados:
            continue
        if not ctx.perfil.get('procurar_tudo') and esperados:
            rel.aviso(f'tem um {tipo} no {NOME_CANAL[c]} que o robo.json não tem')
        else:
            rel.info(f'{tipo} no {NOME_CANAL[c]}')
    for c, lista in achados.items():
        for t, addr in lista:
            if t == 'VL53' and addr == 0x30:
                rel.info(f'VL53 do {NOME_CANAL[c]} já estava no 0x30 (iniciado por outro programa)')

    # medidas
    nomes = {(_canal(s['porta']), t): s.get('nome', '') for t, s in esperados}
    ctx.vl53 = []
    ctx.tcs = []
    for c in sorted(tipos, key=lambda c: NOME_CANAL[c]):
        for t in sorted(tipos[c]):
            rotulo = f'{t} {NOME_CANAL[c]}' + (f' ({nomes[(c, t)]})' if nomes.get((c, t)) else '')
            ui.mostra('SENSORES I2C', rotulo[:20], 'medindo...', '')
            if t == 'VL53':
                _testa_vl53(ctx, c, rotulo)
            else:
                _testa_tcs(ctx, c, rotulo)


def _abre_vl53(canal):
    from vl53 import VL53L0X
    return VL53L0X(canal)


def _testa_vl53(ctx, canal, rotulo):
    rel = ctx.rel
    try:
        sensor = _abre_vl53(canal)
    except Exception as erro:
        try:
            sensor = _abre_vl53(canal)
            rel.aviso(f'{rotulo}: só iniciou na 2ª tentativa ({erro})', 'sensor travando: mau contato?')
        except Exception as erro2:
            rel.falha(f'{rotulo}: não iniciou ({erro2})', 'sensor travado ou com defeito: desligue e ligue o robô')
            return
    medidas, erros = [], 0
    for _ in range(30):
        try:
            medidas.append(sensor.read_range_single_millimeters())
        except Exception:
            erros += 1
            try:
                sensor.recover()
            except Exception:
                pass
    ctx.vl53.append((rotulo, canal, sensor))
    validas = [m for m in medidas if m < 8000]
    if not medidas:
        rel.falha(f'{rotulo}: as 30 leituras falharam', 'sensor travando: cabo ou sensor')
        return
    if erros:
        rel.aviso(f'{rotulo}: {erros} de 30 leituras falharam', 'mau contato no cabo ou ruído')
    if not validas:
        rel.aviso(f'{rotulo}: não viu nada (fora de alcance nas {len(medidas)} leituras)',
                  'aponte para uma parede a < 1 m, ou a lente está tampada/suja')
        return
    media = statistics.mean(validas)
    desvio = statistics.pstdev(validas) if len(validas) > 1 else 0
    txt = f'{rotulo}: {media:.0f} mm (±{desvio:.0f}), {len(validas)}/{len(medidas)} dentro do alcance'
    if media < 25:
        rel.aviso(txt, 'tem algo encostado na lente (película de proteção? peça do robô?)')
    elif desvio > max(15, media * 0.05):
        rel.aviso(txt, 'leitura instável: alvo ruim, luz forte ou sensor solto')
    else:
        rel.ok(txt)


def _testa_tcs(ctx, canal, rotulo):
    rel = ctx.rel
    try:
        from tcs34725 import TCS34725
        sensor = TCS34725(canal)
        time.sleep(0.15)
        leituras = []
        for _ in range(5):
            leituras.append(sensor.le_valores())
            time.sleep(0.07)
    except Exception as erro:
        rel.falha(f'{rotulo}: não deu para ler ({erro})')
        return
    ctx.tcs.append((rotulo, canal, sensor))
    r, g, b, c = [round(statistics.mean(x)) for x in zip(*leituras)]
    txt = f'{rotulo}: R {r} G {g} B {b} C {c}'
    if c == 0:
        rel.aviso(txt, 'não mede luz nenhuma: ponha algo claro a ~1 cm e veja no "TCS ao vivo"; '
                       'se continuar 0, LED do módulo apagado ou sensor com defeito')
    elif c >= 65000:
        rel.aviso(txt, 'saturado: luz forte demais ou ganho alto')
    elif len({x[3] for x in leituras}) == 1 and c > 0:
        rel.aviso(txt, 'as 5 leituras deram igual: o sensor pode estar parado')
    else:
        rel.ok(txt)


def vl53_ao_vivo(ctx):
    if not getattr(ctx, 'vl53', None):
        sensores(ctx)
    lista = getattr(ctx, 'vl53', [])
    if not lista:
        return
    paginas = (len(lista) + 2) // 3

    def tela(p):
        linhas = [f'VL53 ao vivo {p + 1}/{paginas}']
        for rotulo, canal, s in lista[p * 3:p * 3 + 3]:
            try:
                mm = s.read_range_single_millimeters()
                txt = 'longe' if mm >= 8000 else f'{mm} mm'
            except Exception:
                txt = 'ERRO'
            linhas.append(f'{rotulo.split("(")[-1].rstrip(")")[:10]:10s} {txt}')
        return linhas
    ctx.ui.ao_vivo(tela, periodo=0.1, paginas=paginas)


def tcs_ao_vivo(ctx):
    if not getattr(ctx, 'tcs', None):
        sensores(ctx)
    lista = getattr(ctx, 'tcs', [])
    if not lista:
        return
    paginas = len(lista)

    def tela(p):
        rotulo, canal, s = lista[p]
        try:
            r, g, b, c = s.le_valores()
            return [f'{rotulo[:20]}', f'R {r} G {g}', f'B {b} C {c}', f'{p + 1}/{paginas} CIMA/BAIXO']
        except Exception:
            return [rotulo[:20], 'ERRO', '', '']
    ctx.ui.ao_vivo(tela, periodo=0.15, paginas=paginas)
