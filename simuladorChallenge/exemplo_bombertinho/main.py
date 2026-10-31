"""Exemplo do Bombertinho (robô real da RCB Challenge 2026): pega o cubo da rua da frente com a garra
da frente e leva até a plataforma da cor dele.

    python simulador.py --robo robo_bombertinho.json --programa exemplo_bombertinho/main.py

A garra é um paralelogramo: a cabeça desce POR CIMA do cubo (aberta embaixo) e a comporta fecha,
apertando o cubo contra a parede de trás. Descendo, a cabeça também chega para perto do robô. Por
isso o robô para com o cubo um pouco à frente do meio da cabeça: se parar perto demais, a parede de
trás bate em cima do cubo; longe demais, a comporta bate.

1. sai da área verde com a garra da frente alta e aberta e acha a rua (linha preta);
2. segue a linha até o VL53 da frente ver o cubo e chega devagar até a DISTANCIA_PEGAR;
3. desce a garra até PEGAR mm e lê a cor do cubo com o TCS da cabeça. Branco não pode ser pego:
   acende os LEDs para o árbitro (+50), sobe a garra e para por aí. Os outros: fecha e sobe;
4. volta de ré até a linha azul, entra na área verde e dá meia-volta;
5. anda até ficar a FOLGA_PLATAFORMA da plataforma da frente (o cubo passa por cima dela);
6. anda de lado pelos locais de descarte lendo a cor de cada plataforma com o TCS baixo da frente;
7. achou a da cor do cubo: centraliza, abre a comporta (o cubo cai em cima dela) e recua.

Com o cenarios/exemplo.json o cubo é o azul do A3 e a plataforma azul é a P1, lá embaixo.
"""

import time

from robo import ABERTA, ALTA, PEGAR, PRETO, Robo

VEL = 40             # velocidade de cruzeiro (-100 a 100)
LENTO = 15
KP = 0.35            # ganho do seguidor de linha
KZ = 1.5             # ganho para manter a direção pelo giroscópio
DISTANCIA_PEGAR = 34     # mm do VL53 da frente até o cubo para descer a garra (A DEFINIR no robô)
FOLGA_PLATAFORMA = 20    # mm entre o VL53 da frente e a plataforma
MEIA_PLATAFORMA = 80     # mm (a plataforma tem 160 de comprimento)
TCS_FRENTE_Y = -31       # o TCS baixo da frente fica 31 mm à direita do centro


def correcao(ir):
    """Giro para a esquerda (+) quando a linha está à esquerda: a soma dos IR do lado da linha cai."""
    return KP * ((ir[2] + ir[3]) - (ir[0] + ir[1])) / 2.0


def anda_mm(r, frente_mm, vel=VEL):
    r.zera_encoder()
    z0 = r.z()
    while abs(r.deslocamento()[0]) < abs(frente_mm):
        r.move(vel if frente_mm > 0 else -vel, 0, KZ * (z0 - r.z()))
        time.sleep(0.01)
    r.para()


def gira(r, graus, vel=35):
    """Gira no lugar até o giroscópio andar 'graus' (+ = esquerda)."""
    alvo = r.z() + graus
    while True:
        erro = alvo - r.z()
        if abs(erro) < 1.5:
            break
        w = max(12, min(vel, abs(erro) * 0.8))
        r.move(0, 0, w if erro > 0 else -w)
        time.sleep(0.01)
    r.para()


def pega_cubo(r):
    """Segue a linha até o cubo e para com ele embaixo da cabeça aberta. Desce, lê a cor: cubo
    branco não pode ser pego (avisa o árbitro com os LEDs e devolve None); os outros, fecha a
    comporta, sobe e devolve a cor."""
    while r.distancia('frente') > 150:
        r.move(VEL, 0, correcao(r.ir()))
    print(f'cubo à frente ({r.dist["frente"]} mm)')
    while r.distancia('frente') > DISTANCIA_PEGAR:
        r.move(LENTO, 0, correcao(r.ir()))
    r.para()
    r.garra('frente', altura=PEGAR)
    cor = r.cor_tcs('garra_frente')
    if cor == 'branco':
        print('cubo branco: aviso com os LEDs e deixo no lugar')
        r.leds(255, 255, 255)
        r.garra('frente', altura=ALTA)
        r.leds(0, 0, 0)
        return None
    r.garra('frente', abertura=0)
    print(f'peguei um cubo {cor}')
    r.garra('frente', altura=ALTA)
    return cor


def procura_plataforma(r, cor):
    """Anda de lado (primeiro para a esquerda, depois para a direita) lendo a plataforma da frente.
    Devolve True parado com a plataforma da cor 'cor' bem na frente da garra."""
    z0 = r.z()
    for sentido in (1, -1):
        r.zera_encoder()
        vistos = 0
        while abs(r.deslocamento()[1]) < 650:
            d = r.distancia('frente')
            tem = d < 60
            vx = 0.4 * (d - FOLGA_PLATAFORMA) if tem else 0.0    # mantém a distância das plataformas
            r.move(max(-10, min(10, vx)), sentido * LENTO, KZ * (z0 - r.z()))
            if tem and r.cor_tcs('frente', leituras=1) == cor:
                vistos += 1
                if vistos >= 2:
                    print(f'plataforma {cor} encontrada')
                    # o TCS não fica no meio do robô: andando para a esquerda ele vê a plataforma
                    # depois do centro do robô passar da ponta dela; para a direita, antes
                    falta = MEIA_PLATAFORMA + sentido * TCS_FRENTE_Y
                    lado0 = r.deslocamento()[1]
                    while abs(r.deslocamento()[1] - lado0) < falta:
                        r.move(0, sentido * LENTO, KZ * (z0 - r.z()))
                        time.sleep(0.01)
                    r.para()
                    return True
            else:
                vistos = 0
        print('não achei por este lado: voltando')
        # volta para onde começou antes de procurar do outro lado
        while abs(r.deslocamento()[1]) > 20:
            r.move(0, -sentido * VEL, KZ * (z0 - r.z()))
            time.sleep(0.01)
    r.para()
    return False


def main():
    r = Robo()
    r.garra('frente', abertura=ABERTA, altura=ALTA)
    r.garra('esquerda', abertura=0, altura=ALTA)
    r.espera_botao()
    t0 = time.time()

    # 1. sai da área verde até o IR do meio ver a linha preta
    print('saindo da área verde')
    while True:
        ir = r.ir()
        if ir[1] < PRETO or ir[2] < PRETO:
            break
        r.move(VEL, 0, 0)
        time.sleep(0.01)

    # 2 e 3. pega o cubo da rua
    cor = pega_cubo(r)
    if cor is None:
        anda_mm(r, -200)
        print(f'terminei em {time.time() - t0:.1f} s')
        r.espera(1.0)
        return

    # 4. de ré até a linha azul, mantendo a direção
    z0 = r.z()
    while r.piso() != 'azul':
        r.move(-VEL, 0, KZ * (z0 - r.z()))
        time.sleep(0.01)
    print('linha azul: voltando para a área verde')
    anda_mm(r, -150)
    gira(r, 180)

    # 5. até a plataforma da frente
    r.zera_encoder()
    z0 = r.z()
    while r.distancia('frente') > FOLGA_PLATAFORMA and r.deslocamento()[0] < 350:
        r.move(LENTO, 0, KZ * (z0 - r.z()))
    r.para()

    # 6 e 7. acha a plataforma da cor do cubo e solta
    if procura_plataforma(r, cor):
        r.garra('frente', abertura=ABERTA)
        print(f'cubo {cor} solto na plataforma')
    else:
        print(f'não achei a plataforma {cor}')
    anda_mm(r, -100)
    print(f'terminei em {time.time() - t0:.1f} s')
    r.espera(1.0)


if __name__ == '__main__':
    main()
