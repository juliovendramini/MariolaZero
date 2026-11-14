"""Testes próprios da Maze (só aparecem com a chave "maze" no robo.json), com os números da equipe:

* paredes: robô no centro de um ladrilho com paredes dos lados. Cada VL53 lateral (já com o desconto da
  equipe) tem de ficar abaixo da distancia_sem_parede, e o meio e a borda do mesmo lado têm de bater
  (é com essa diferença que o robô anda reto);
* cores_piso: o TCS do chão no branco, preto, azul, prata e vermelho. Mostra o que mede e qual cor as
  faixas da equipe (SensorChao.cor()) dariam; grava média e faixa de cada cor para ajustar o sensores.py;
* andar: de frente para uma parede, anda até 300 mm pelo encoder e confere pelo VL53 da frente quanto
  andou de verdade (dá o CONTAGENS_POR_MM certo); depois 4 giros de 90° à direita com o mesmo controle
  do girar_ate_angulo() da equipe.

Feito em 14/11/2026 a partir do autoteste antigo da Maze (que rodava dentro do código da equipe).
"""

import statistics
import time

from contexto import porta
from testes.seriais import _abre, _troca, _z

LONGE = 8190          # 8190/8191: o VL53 não viu nada


def _cfg(ctx):
    return ctx.perfil.get('maze') or {}


# ---------------------------------------------------------------------------- VL53
def _abre_vl53s(ctx, nomes):
    """{nome: VL53L0X} dos VL53 do robo.json com esses nomes (os que não abrirem ficam de fora)."""
    from vl53 import VL53L0X
    por_nome = {s['nome']: s['porta'] for s in ctx.perfil.get('vl53', [])}
    sensores = {}
    for nome in nomes:
        if nome not in por_nome:
            ctx.rel.falha(f'o robo.json não tem o VL53 "{nome}"', 'confira a chave "maze" do robo.json')
            continue
        try:
            sensores[nome] = VL53L0X(porta(por_nome[nome]))
        except Exception as erro:
            ctx.rel.falha(f'VL53 {nome} ({por_nome[nome]}) não iniciou: {erro}',
                          'rode o teste "Sensores I2C" para ver se o cabo está em outra porta')
    return sensores


def _mm(ctx, nome, sensor, n=10):
    """Mediana de n leituras, com o desconto da equipe. None se não leu nada perto."""
    desconto = _cfg(ctx).get('descontos', {}).get(nome, 0)
    valores = []
    for _ in range(n * 2):
        try:
            v = sensor.read_range_single_millimeters()
        except Exception:
            continue
        if v < LONGE:
            valores.append(v - desconto)
        if len(valores) >= n:
            break
    return statistics.median(valores) if valores else None


# ---------------------------------------------------------------------------- paredes
def paredes(ctx):
    rel, ui, cfg = ctx.rel, ctx.ui, _cfg(ctx)
    limite = cfg.get('distancia_sem_parede', 150)
    if not ui.automatico:
        if not ui.pergunta('PAREDES', 'Robo no centro de um ladrilho com parede dos dois lados?'):
            rel.pulou('paredes no ladrilho (robô não posicionado)')
            return
    nomes = [n for p in cfg.get('paredes', []) for n in (p['meio'], p['borda'])]
    frente = cfg.get('vl53_frente')
    sensores = _abre_vl53s(ctx, nomes + ([frente] if frente else []))
    ui.mensagem('PAREDES', 'medindo...')
    medidas = {n: _mm(ctx, n, s) for n, s in sensores.items()}
    for p in cfg.get('paredes', []):
        a, b = medidas.get(p['meio']), medidas.get(p['borda'])
        if p['meio'] not in sensores or p['borda'] not in sensores:
            continue
        if a is None or b is None:
            txt = f'{p["lado"]}: o VL53 {p["meio"] if a is None else p["borda"]} não viu a parede'
            (rel.info if ui.automatico else rel.falha)(txt, 'sensor torto, sujo, ou não tem parede ali')
            continue
        txt = f'{p["lado"]}: meio {a:.0f} mm, borda {b:.0f} mm (diferença {a - b:+.0f})'
        if ui.automatico:
            rel.info(txt)
        elif max(a, b) >= limite:
            rel.falha(txt, f'acima de {limite} mm o programa acha que NÃO tem parede: robô fora do centro, '
                           'sensor torto ou desconto errado no sensores.py')
        elif abs(a - b) > 10:
            rel.aviso(txt, 'com o robô reto os dois deviam bater: robô torto, sensor torto ou desconto errado. '
                           'O andar reto da equipe corrige por essa diferença')
        else:
            rel.ok(txt)
    if frente in medidas:
        v = medidas[frente]
        rel.info(f'frente: {v:.0f} mm' if v is not None else 'frente: nada perto')


# ---------------------------------------------------------------------------- cores do piso
def _cor_da_equipe(cfg, r, g, b):
    for f in cfg.get('faixas_cor', []):
        if f['r'][0] <= r <= f['r'][1] and f['g'][0] <= g <= f['g'][1] and f['b'][0] <= b <= f['b'][1]:
            return f['cor']
    return 'nenhuma'


def cores_piso(ctx):
    rel, ui, cfg = ctx.rel, ctx.ui, _cfg(ctx)
    linhas = ctx.perfil.get('sensores_linha') or []
    if not linhas:
        rel.pulou('cores do piso (sem sensor de linha no robo.json)')
        return
    if ui.automatico:
        rel.pulou('cores do piso (precisa de alguém pondo o sensor em cada cor)')
        return
    ser = _abre(linhas[0]['porta'])
    if ser is None:
        rel.falha(f'não abriu a porta do sensor de linha ({linhas[0]["porta"]})', 'rode o teste "Sensor de linha"')
        return
    tcs = cfg.get('tcs_chao', 2)
    inicio = 4 * tcs                 # bytes 4-7 = TCS 1, 8-11 = TCS 2, 12-15 = TCS 3
    try:
        for f in cfg.get('faixas_cor', []):
            cor = f['cor']
            if not ui.pergunta('CORES DO PISO', f'TCS {tcs} em cima do {cor.upper()}', 'ENTER=mede', 'VOLTAR=pula'):
                rel.pulou(f'{cor}')
                continue
            amostras = []
            for _ in range(30):
                d = _troca(ser, 0x61, 16)
                if d:
                    amostras.append(list(d[inicio:inicio + 4]))
                time.sleep(0.03)
            if len(amostras) < 10:
                rel.falha(f'{cor}: o sensor de linha quase não respondeu', 'rode o teste "Sensor de linha"')
                continue
            media = [round(statistics.mean(a[i] for a in amostras)) for i in range(4)]
            faixa = [(min(a[i] for a in amostras), max(a[i] for a in amostras)) for i in range(3)]
            vistas = [_cor_da_equipe(cfg, *a[:3]) for a in amostras]
            vista = max(set(vistas), key=vistas.count)
            certas = vistas.count(cor)
            txt = (f'{cor}: RGBC {media[0]} {media[1]} {media[2]} {media[3]}, faixa R{faixa[0][0]}-{faixa[0][1]} '
                   f'G{faixa[1][0]}-{faixa[1][1]} B{faixa[2][0]}-{faixa[2][1]}; faixas da equipe: {vista} '
                   f'({certas}/{len(vistas)} certas)')
            dica = (f'ajuste a faixa do {cor} no SensorChao.cor() (sensores.py) para cobrir o que foi medido '
                    f'(com folga); lembre que a ordem dos if importa e que fora das faixas o código dá branco')
            if certas == len(vistas):
                rel.ok(txt)
            elif certas >= len(vistas) * 0.8:
                rel.aviso(txt, dica)
            else:
                rel.falha(txt, dica)
            ui.mostra(f'{cor}: {"OK" if certas == len(vistas) else "ERRADO"}', f'deu {vista}',
                      f'RGB {media[0]} {media[1]} {media[2]}', 'ENTER: proxima')
            ui.espera()
    finally:
        try:
            ser.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------- andar e girar
class _Motores:
    """Os 4 motores como o Robo.velocidade() da equipe: positivo = para frente."""

    def __init__(self, ctx):
        from placaControleMotor import PlacaControleMotor
        cfg = _cfg(ctx)
        self.brick = ctx.brick()
        self.sinal_brick = {m: (-1 if m in cfg.get('brick_invertidos', []) else 1) for m in (1, 2)}
        self.placas = {}
        bar = ctx.perfil.get('barramento') or {}
        ser = ctx.barramento(bar['porta']) if bar.get('porta') else None
        for lado, chave in (('esq', 'placa_esq'), ('dir', 'placa_dir')):
            pid = cfg.get(chave)
            if ser is None or pid is None:
                continue
            placa = PlacaControleMotor(ser, id_equipamento=pid)
            if placa.atualizar() is not None:
                ctx.placas_abertas.append(placa)
                self.placas[lado] = (placa, -1 if pid in cfg.get('placas_invertidas', []) else 1)

    def velocidade(self, esq, dir):
        esq, dir = int(max(-100, min(100, esq))), int(max(-100, min(100, dir)))
        self.brick.velocidade_motores(esq * self.sinal_brick[1], dir * self.sinal_brick[2])
        for lado, v in (('esq', esq), ('dir', dir)):
            if lado in self.placas:
                placa, sinal = self.placas[lado]
                placa.mover_pid(v * sinal)

    def para(self):
        try:
            self.velocidade(0, 0)
        except Exception:
            pass

    def encoder(self):
        """Média dos dois motores do brick, em contagens, positivo = para frente."""
        self.brick.estado()
        return (self.brick.angulo_motor(1) * self.sinal_brick[1] + self.brick.angulo_motor(2) * self.sinal_brick[2]) / 2


def _gira_ate(ctx, m, ser_giro, alvo, sinal_direita):
    """O girar_ate_angulo() da equipe: velocidade proporcional ao que falta. Devolve o Z final ou None."""
    cfg = _cfg(ctx)
    vmin, vmax = cfg.get('velocidade_giro_min', 14), cfg.get('velocidade_giro_max', 45)
    d = _troca(ser_giro, 0, 8)
    if not d:
        return None
    erro_anterior = alvo - _z(d)[2]
    inicio = time.monotonic()
    while time.monotonic() - inicio < 4.0:
        d = _troca(ser_giro, 0, 8)
        if not d:
            continue
        erro = alvo - _z(d)[2]
        if abs(erro) <= 1 or erro * erro_anterior < 0:
            m.para()
            time.sleep(0.4)
            d = _troca(ser_giro, 0, 8)
            return _z(d)[2] if d else None
        v = max(vmin, min(vmax, abs(erro) * 0.9))
        # erro com o mesmo sinal de "girar à direita" -> gira à direita (esquerda para frente)
        if erro * sinal_direita > 0:
            m.velocidade(v, -v)
        else:
            m.velocidade(-v, v)
        erro_anterior = erro
        ctx.ui.mostra('GIROS', f'falta {erro:+d} graus', '', '', eco=False)
        time.sleep(0.01)
    m.para()
    return None


def andar(ctx):
    rel, ui, cfg = ctx.rel, ctx.ui, _cfg(ctx)
    if ctx.brick() is None:
        rel.falha(f'o brick não respondeu ({ctx.erro_brick})', 'rode o teste "Brick: comunicacao"')
        return
    if ui.automatico and not ctx.pode_motores_automatico:
        rel.pulou('andar e girar (sem --motores)')
        return
    if not ui.automatico and not ui.pergunta('ANDAR', 'Robo NO CHAO, de frente para uma parede a 40-90 cm?'):
        rel.pulou('andar e girar (robô não posicionado)')
        return
    frente = cfg.get('vl53_frente', 'frente')
    sensores = _abre_vl53s(ctx, [frente])
    ser_giro = _abre(ctx.perfil.get('giroscopio')) if ctx.perfil.get('giroscopio') else None
    if frente not in sensores or ser_giro is None or not _troca(ser_giro, 0, 8):
        rel.falha('precisa do VL53 da frente e do giroscópio respondendo', 'rode os testes "Sensores I2C" e "Giroscopio"')
        return
    vl53 = sensores[frente]
    sinal_direita = -1 if ctx.perfil.get('giroscopio_direita', 'diminui') == 'diminui' else 1
    cpm = cfg.get('contagens_por_mm', 2.0)
    m = _Motores(ctx)
    if len(m.placas) < 2:
        rel.aviso(f'só {len(m.placas)} placa(s) de motor responderam: anda só com as que tem',
                  'rode o teste "Placas de motor"')
    try:
        # ------------------------------------------------ andar
        d0 = _mm(ctx, frente, vl53)
        alvo_mm = min(300, (d0 or 0) - 100)              # para 100 mm antes da parede
        if d0 is None or alvo_mm < 150 or d0 > 1200:
            rel.pulou(f'andar: a parede tem de estar a 25-120 cm (VL53 da frente: {d0})')
        else:
            z_alvo = _z(_troca(ser_giro, 0, 8) or bytes(8))[2]
            e0 = m.encoder()
            motivo = 'chegou'
            inicio = time.monotonic()
            while True:
                andado = abs(m.encoder() - e0) / cpm
                if andado >= alvo_mm:
                    break
                if time.monotonic() - inicio > 8:
                    motivo = 'demorou mais de 8 s'
                    break
                if ui.cancelou():
                    motivo = 'VOLTAR'
                    break
                d = _troca(ser_giro, 0, 8)
                correcao = ((_z(d)[2] - z_alvo) * cfg.get('kp_giro', 0.7)) if d else 0
                v = cfg.get('velocidade', 25)
                m.velocidade(v + correcao, v - correcao)
                ui.mostra('ANDAR', f'alvo {alvo_mm:.0f} mm', f'encoder {andado:.0f} mm', '', eco=False)
                time.sleep(0.02)
            m.para()
            time.sleep(0.6)
            contagens = abs(m.encoder() - e0)
            andado = contagens / cpm
            d1 = _mm(ctx, frente, vl53)
            if motivo != 'chegou':
                rel.aviso(f'andar: parou antes ({motivo}) com {andado:.0f} mm pelo encoder')
            if d1 is None or andado < 50:
                rel.falha(f'andar: encoder {andado:.0f} mm, VL53 da frente depois: {d1}',
                          'o robô não andou ou o encoder não contou: rode o teste "Motores do brick"')
            else:
                real = d0 - d1
                medido = contagens / real if real > 0 else 0
                txt = (f'andou {real:.0f} mm de verdade (VL53 {d0:.0f} -> {d1:.0f}) e {andado:.0f} mm pelo encoder: '
                       f'CONTAGENS_POR_MM medido {medido:.3f}, no constantes.py {cpm:.3f}')
                if real <= 0:
                    rel.falha(txt, 'o VL53 da frente não viu o robô chegar perto da parede')
                elif abs(medido / cpm - 1) > 0.05:
                    rel.aviso(txt, f'troque o CONTAGENS_POR_MM do constantes.py por {medido:.2f} (meça 2 ou 3 vezes; '
                                   'roda patinando ou parede torta mudam a conta)')
                else:
                    rel.ok(txt)

        # ------------------------------------------------ 4 giros de 90° à direita
        if not ui.automatico and not ui.pergunta('GIROS', '4 giros de 90 graus a direita. Espaco livre?'):
            rel.pulou('giros de 90°')
            return
        d = _troca(ser_giro, 0, 8)
        alvo = _z(d)[2] if d else 0
        erros = []
        for i in range(4):
            alvo += sinal_direita * 90
            z = _gira_ate(ctx, m, ser_giro, alvo, sinal_direita)
            if z is None:
                rel.falha(f'o giro {i + 1} não terminou em 4 s',
                          'o Z não andou para o lado esperado: confira "giroscopio_direita" no robo.json '
                          'e o teste "Giroscopio"; ou o robô não consegue girar (atrito, velocidade mínima baixa)')
                return
            erros.append(z - alvo)
        txt = 'erro de cada giro de 90°: ' + ', '.join(f'{e:+d}°' for e in erros)
        if max(abs(e) for e in erros) > 3:
            rel.aviso(txt, 'giro passando ou faltando: ajuste VELOCIDADE_GIRO_MINIMA/MAXIMA ou o 0,9 do girar_ate_angulo()')
        else:
            rel.ok(txt)
    finally:
        m.para()
        try:
            ser_giro.close()
        except Exception:
            pass
