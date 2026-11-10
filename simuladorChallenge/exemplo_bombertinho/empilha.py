"""Exemplo do Bombertinho empilhando: 5 cubos na mesma plataforma, 3 embaixo e 2 em cima.

    python simulador.py --robo robo_bombertinho.json --programa exemplo_bombertinho/empilha.py --cenario cenarios/empilha.json

A regra (seção 6) deixa a plataforma (160 x 50 x 50 mm) com até cinco cubos "de qualquer forma, desde
que fiquem em cima da plataforma"; derrubar um cubo que já estava lá custa -45. Em fila só cabem 3.

O plano, com as medidas do robo_bombertinho.json (posições ao longo da plataforma, + = para o P5):

* EMBAIXO, garra da FRENTE: cubos em -55, +55 e 0 mm, nessa ordem. Os braços do "V" da cabeça vão
  até 40 mm do centro do cubo e começam 38 mm acima da base dele: soltando com a base a 54 mm do
  lado de outro cubo (topo a 100), eles batem nele. Por isso as pontas primeiro e o do meio por
  último, solto mais alto (base a 65 mm, cai 15).
* EM CIMA, garra da ESQUERDA: cubos em -40 e +40 mm (30 mm entre eles: os braços do "V" passam), com
  a base a 108 mm (o topo da 1ª camada fica a 100). Subindo, a cabeça do paralelogramo chega para
  perto do robô: a da frente, na altura da 2ª camada, pediria a plataforma a 96 mm do centro do
  robô, e as rodas da frente vão até 97,5. A da esquerda (barra mais comprida) alcança com a
  lateral do robô a uns 23 mm da plataforma.
* A garra da esquerda não pega o cubo da rua: o robô traz o cubo na da frente, larga no chão da área
  verde (a regra deixa ajustar o cubo lá, até 30 s), gira 90° e pega com a da esquerda.
* Nunca passar com a cabeça (ou o cubo preso) do lado da pilha e na altura dela: os ajustes ao longo
  da plataforma são feitos longe dela, e só depois o robô chega perto.
* Depois de soltar, levantar a garra antes de recuar: a comporta aberta fica do outro lado do cubo e,
  na altura dele, puxaria o cubo da plataforma.

No cenarios/empilha.json os 5 cubos azuis estão na rua do meio (A3, B3, C3, B3' e A3') e a plataforma
azul na P3, bem em frente a ela: voltando pela rua, o robô chega na frente do meio da plataforma. Na
competição a plataforma muda de lugar: ache a da cor (procura_plataforma do main.py) enquanto ela
ainda está vazia e guarde quanto o robô andou de lado. As distâncias e alturas são do simulador:
confira no robô (EFICIENCIA_LATERAL, os VL53 e o ângulo das barras na horizontal estão A DEFINIR).
"""

import math
import time

from main import pega_cubo
from robo import ABERTA, ALTA, PEGAR, PRETO, SOLTOU, Robo

VEL = 40
LENTO = 15
KZ = 1.5                   # ganho para manter o rumo pelo giroscópio
KP_LADO = 0.25             # ganho para manter o sensor de linha em cima da linha andando de ré
EFICIENCIA_LATERAL = 0.9   # de lado a mecanum escorrega: anda isto do que o encoder diz (A MEDIR)
RECUO = 150                # mm de ré depois de ver a linha azul: o cubo largado fica dentro da área verde

# (mm ao longo da plataforma, altura da base do cubo ao soltar, mm do VL53 até a plataforma)
CAMADA1 = [(-55, ALTA, 29), (55, ALTA, 29), (0, 65, 28)]     # garra da frente, VL53 da frente
CAMADA2 = [(-40, 108, 26), (40, 108, 26)]                    # garra da esquerda, VL53 da esquerda

ABERTA_MAX = 37            # mm: comporta toda aberta (o "V" fica mais longe do cubo)
SOBE_ESQ = 128             # depois de soltar em cima: a comporta (23 mm acima da base) passa do topo (150)
RECOLHIDA = 120            # garra da frente lá no alto: a cabeça não passa da frente do robô
PEGA_ESQ = 52              # mm do VL53 da esquerda até o cubo largado no chão para descer a garra


def segura(r, rumo):
    """Correção de giro para manter o rumo (graus do giroscópio: 0 = como saiu, + = esquerda)."""
    return KZ * (rumo - r.z())


def gira_para(r, rumo, vel=35):
    """Gira no lugar até o rumo (0 = olhando para a cidade, 180 = para as plataformas)."""
    while True:
        erro = rumo - r.z()
        if abs(erro) < 0.5:
            break
        w = max(8, min(vel, abs(erro) * 0.8))
        r.move(0, 0, w if erro > 0 else -w)
        time.sleep(0.01)
    r.para()


def freia(falta, vel):
    """Velocidade perto do fim: cai com o que falta (mm) para o robô não passar do ponto."""
    return max(8.0, min(vel, 0.4 * falta))


def anda_frente(r, rumo, mm, vel=VEL):
    r.zera_encoder()
    while True:
        falta = abs(mm) - abs(r.deslocamento()[0])
        if falta <= 0:
            break
        r.move(math.copysign(freia(falta, vel), mm), 0, segura(r, rumo))
        time.sleep(0.01)
    r.para()


def anda_lado(r, rumo, mm, vel=25):
    """mm para a esquerda do robô (negativo = direita), descontando o escorregamento."""
    r.zera_encoder()
    while True:
        falta = abs(mm) / EFICIENCIA_LATERAL - abs(r.deslocamento()[1])
        if falta <= 0:
            break
        r.move(0, math.copysign(freia(falta, vel), mm), segura(r, rumo))
        time.sleep(0.01)
    r.para()


def vai_y(r, rumo, dy):
    """Anda dy mm ao longo das plataformas (+ = para o P5) com o robô parado no rumo 0, 180, 90 ou -90."""
    if dy == 0:
        return
    if rumo == 0:
        anda_lado(r, rumo, dy)
    elif rumo == 180:
        anda_lado(r, rumo, -dy)
    elif rumo == 90:
        anda_frente(r, rumo, dy, vel=25)
    else:
        anda_frente(r, rumo, -dy, vel=25)


def busca_cubo(r):
    """Da área verde, olhando para a cidade em frente à rua: acha a linha e pega o próximo cubo dela."""
    r.garra('frente', abertura=ABERTA, altura=ALTA)
    while True:
        ir = r.ir()
        if ir[1] < PRETO or ir[2] < PRETO:
            break
        r.move(VEL, 0, segura(r, 0))
        time.sleep(0.01)
    return pega_cubo(r)


def volta_pela_rua(r):
    """De ré pela rua até a linha azul, mantendo o rumo 0 e andando de lado (mecanum) para o sensor de
    linha ficar em cima da linha: o robô chega na área verde em frente à rua. Depois, mais RECUO mm."""
    while r.piso() != 'azul':
        ir = r.ir()
        lado = KP_LADO * ((ir[2] + ir[3]) - (ir[0] + ir[1])) / 2.0
        r.move(-VEL, lado, segura(r, 0))
        time.sleep(0.01)
    anda_frente(r, 0, -RECUO)


def entrega_embaixo(r, dy, altura, dist):
    """1ª camada, com a garra da frente: gira para as plataformas, anda de lado até a posição (ainda
    longe da pilha), chega perto, solta, levanta a garra e volta para onde estava."""
    gira_para(r, 180)
    vai_y(r, 180, dy)
    if altura != ALTA:
        r.garra('frente', altura=altura)
    r.zera_encoder()
    while r.distancia('frente') > dist:
        r.move(LENTO, 0, segura(r, 180))
    r.para()
    chegou = r.deslocamento()[0]
    r.garra('frente', abertura=ABERTA)
    r.garra('frente', altura=SOLTOU)
    anda_frente(r, 180, -chegou, vel=25)
    vai_y(r, 180, -dy)
    gira_para(r, 0)


def troca_de_garra(r):
    """Na área verde, olhando para a cidade: larga o cubo da garra da frente no chão (cai 4 mm), gira
    90° para a direita (o cubo fica do lado esquerdo) e pega com a garra da esquerda."""
    r.garra('esquerda', abertura=ABERTA_MAX, altura=ALTA)
    r.garra('frente', abertura=ABERTA)
    r.garra('frente', altura=RECOLHIDA)
    gira_para(r, -90)
    # o VL53 da esquerda acerta a distância do cubo (a cabeça desce certo numa faixa de poucos mm)
    while True:
        erro = r.distancia('esquerda') - PEGA_ESQ
        if abs(erro) <= 1:
            break
        r.move(0, 8 if erro > 0 else -8, segura(r, -90))
    r.para()
    r.garra('esquerda', altura=PEGAR)
    r.garra('esquerda', abertura=0)
    r.espera(0.3)              # de 37 mm até fechar o servo anda 177°: ~0,6 s
    r.garra('esquerda', altura=ALTA)
    print(f'troquei de garra: cubo {r.cor_tcs("garra_esquerda")} na garra da esquerda')


def entrega_em_cima(r, dy, altura, dist):
    """2ª camada, com a garra da esquerda: gira para a esquerda do robô ficar para as plataformas, anda
    até a posição ao longo delas (longe), sobe a garra, chega de lado, solta, sobe mais e volta."""
    gira_para(r, 90)
    vai_y(r, 90, dy)
    r.garra('esquerda', altura=altura)
    r.zera_encoder()
    while r.distancia('esquerda') > dist:
        r.move(0, LENTO, segura(r, 90))
    r.para()
    chegou = r.deslocamento()[1] * EFICIENCIA_LATERAL
    r.garra('esquerda', abertura=ABERTA_MAX)
    r.espera(0.3)              # toda aberta antes de subir: subindo, a cabeça chega 30 mm para perto do robô
    r.garra('esquerda', altura=SOBE_ESQ)
    anda_lado(r, 90, -chegou)
    r.garra('esquerda', abertura=0, altura=ALTA)
    vai_y(r, 90, -dy)
    gira_para(r, 0)


def main():
    r = Robo()
    r.garra('frente', abertura=ABERTA, altura=ALTA)
    r.garra('esquerda', abertura=0, altura=ALTA)
    r.espera_botao()
    t0 = time.time()
    for i, (dy, altura, dist) in enumerate(CAMADA1 + CAMADA2):
        print(f'--- cubo {i + 1} ({time.time() - t0:.0f} s)')
        cor = busca_cubo(r)
        if cor is None:
            print('cubo branco: paro aqui')
            break
        volta_pela_rua(r)
        if i < len(CAMADA1):
            entrega_embaixo(r, dy, altura, dist)
        else:
            troca_de_garra(r)
            entrega_em_cima(r, dy, altura, dist)
        print(f'cubo {i + 1} ({cor}) solto em {dy:+d} mm, base a {altura} mm')
    print(f'terminei em {time.time() - t0:.1f} s')
    r.espera(1.0)


if __name__ == '__main__':
    main()
