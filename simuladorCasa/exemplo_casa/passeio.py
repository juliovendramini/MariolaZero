"""Teste de localização: o robô passeia pelos cômodos da casa e diz onde acha que está.

    python simulador.py --casa casas/casa_julio.json --programa exemplo_casa/passeio.py
    python simulador.py --casa casas/casa_julio.json --programa exemplo_casa/passeio.py --sem-janela --velocidade 8 --tempo 1500

Ele sai do "inicio" do mapa, visita os cômodos da rota e volta. Na janela, o contorno roxo é onde o
programa acha que o robô está; o painel mostra o erro em relação à pose de verdade (sem janela, o
erro médio e o máximo saem no resultado).

Variáveis de ambiente (opcionais):
    CASA_ROTA    cômodos a visitar, separados por vírgula (padrão: todos, do mais perto para o mais longe)
    CASA_SEM_VL53=1    só odometria e giroscópio, sem corrigir pelos VL53 (para comparar)
"""

import math
import os
import time

from localiza import Localizador
from mapa import Mapa
from navega import Navegador
from robo import Robo, BARRAS_DESCANSO


def rota_padrao(mapa):
    """Todos os cômodos em que o robô cabe, cada vez o mais perto do anterior (pela rota, não em linha reta)."""
    x, y, _ = mapa.inicio
    falta = {n: mapa.lugar(n) for n in mapa.lugares()}
    falta = {n: p for n, p in falta.items() if p is not None}
    ordem = []
    while falta:
        melhor = None
        for n, p in falta.items():
            c = mapa.rota((x, y), p)
            if c is None:
                continue
            d = mapa.comprimento(c)
            if melhor is None or d < melhor[0]:
                melhor = (d, n)
        if melhor is None:
            break
        ordem.append(melhor[1])
        x, y = falta.pop(melhor[1])
    return ordem


def main():
    t0 = time.time()
    mapa = Mapa()
    print(f'mapa: {mapa.nome} ({mapa.largura / 1000:.1f} x {mapa.altura / 1000:.1f} m), '
          f'{len(mapa.lugares())} cômodos, carregado em {time.time() - t0:.1f} s')
    pedido = [n.strip() for n in os.environ.get('CASA_ROTA', '').split(',') if n.strip()]
    t0 = time.time()
    rota = pedido or rota_padrao(mapa)
    print(f'rota ({time.time() - t0:.1f} s para planejar): ' + ' > '.join(rota))

    r = Robo()
    r.espera_botao()
    r.garra(barras=BARRAS_DESCANSO, abertura=0, inclinacao=15, espera=0.8)
    loc = Localizador(r, mapa, usa_vl53=not os.environ.get('CASA_SEM_VL53'))
    nav = Navegador(r, mapa, loc)
    x0, y0, a0 = mapa.inicio

    chegou = 0
    for nome in rota:
        ok = nav.vai_para_comodo(nome)
        x, y, a = loc.pose()
        mm, graus = loc.incerteza()
        chegou += bool(ok)
        print(f'{"cheguei em" if ok else "NÃO cheguei em"} {nome}: acho que estou em x {x:.0f} y {y:.0f} '
              f'rumo {a % 360:.0f}°, incerteza {mm:.0f} mm; já andei {loc.percurso / 1000:.1f} m')
        r.espera(0.5)
    ok = nav.vai_para(x0, y0, rumo=a0)
    x, y, a = loc.pose()
    print(f'{"voltei para o início" if ok else "NÃO consegui voltar para o início"}: '
          f'x {x:.0f} y {y:.0f} rumo {a % 360:.0f}° (saí de x {x0:.0f} y {y0:.0f} rumo {a0 % 360:.0f}°)')
    print(f'fim: {chegou} de {len(rota)} cômodos, {loc.percurso / 1000:.1f} m andados, '
          f'{loc.medidas} medidas dos VL53 usadas')
    r.para()


if __name__ == '__main__':
    main()
