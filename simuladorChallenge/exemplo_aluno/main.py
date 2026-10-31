"""Exemplo da RCB Challenge com a garra: pega o cubo da rua da frente e leva até a plataforma da cor dele.

O robô começa na área verde da esquerda, olhando para a cidade, com a garra aberta e embaixo:
1. anda reto, passa pela linha azul e acha a rua (linha preta);
2. segue a linha até o VL53 da frente ver um cubo; chega devagar até ele ficar entre os dedos;
3. lê a cor do cubo (TCS entre os dedos). Branco não pode ser pego: acende os LEDs para o árbitro
   (+50) e para por aí. Os outros: fecha a garra e sobe o braço;
4. volta de ré até a linha azul (direção pelo giroscópio), entra na área verde e dá meia-volta;
5. anda até encostar quase na plataforma da frente (VL53);
6. anda de lado pelos locais de descarte lendo a cor de cada plataforma com o TCS;
7. achou a da cor do cubo: centraliza, abre a garra (o cubo cai em cima dela) e recua.

Com o cenarios/exemplo.json o cubo é o azul do A3 e a plataforma azul é a P1, lá embaixo.
"""

import time

from robo import PRETO, Robo

VEL = 40             # velocidade de cruzeiro (-100 a 100)
LENTO = 20
KP = 0.35            # ganho do seguidor de linha
KZ = 1.5             # ganho para manter a direção pelo giroscópio
FOLGA_PLATAFORMA = 15    # mm entre a frente do robô e a plataforma
MEIA_PLATAFORMA = 80     # mm (a plataforma tem 160 de comprimento)


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
    """Segue a linha até o cubo e encosta nele com a garra aberta. Lê a cor: cubo branco não pode
    ser pego (avisa o árbitro com os LEDs e devolve None); os outros, fecha a garra, sobe e devolve a cor."""
    while r.distancia('frente') > 150:
        r.move(VEL, 0, correcao(r.ir()))
    print(f'cubo à frente ({r.dist["frente"]} mm)')
    while r.distancia('frente') > 6:
        r.move(LENTO, 0, correcao(r.ir()))
    r.para()
    cor = r.cor_frente()
    if cor == 'branco':
        print('cubo branco: aviso com os LEDs e deixo no lugar')
        r.leds(255, 255, 255)
        r.espera(1.0)
        r.leds(0, 0, 0)
        return None
    r.garra(abre=False)
    print(f'peguei um cubo {cor}')
    r.garra(sobe=True)
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
            if tem and r.cor_frente(leituras=1) == cor:
                vistos += 1
                if vistos >= 2:
                    print(f'plataforma {cor} encontrada')
                    lado0 = r.deslocamento()[1]
                    while abs(r.deslocamento()[1] - lado0) < MEIA_PLATAFORMA:
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
    r.garra(abre=True, sobe=False)
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
        r.garra(abre=True)
        print(f'cubo {cor} solto na plataforma')
    else:
        print(f'não achei a plataforma {cor}')
    anda_mm(r, -100)
    r.garra(sobe=False)
    print(f'terminei em {time.time() - t0:.1f} s')
    r.espera(1.0)


if __name__ == '__main__':
    main()
