"""Tutorial 8 — usar a câmera (módulo visao) para achar uma vítima e chegar perto dela.

No simulador a câmera é um stub que já devolve as detecções (90% de acerto).
No robô real, copie simuladorLine/robo_real/visao.py e coloque a sua YOLO nele.
Mapa do curso: o robô começa na frente da entrada da área de resgate.
    python simulador.py --mapa mapas/curso_area.json --programa CAMINHO/08_camera/procura_vitima.py
"""
import time

from giroscopio import Giroscopio
from motores import Motores
from placaControleMotor import PlacaControleMotor
from portas import Portas
from visao import Visao

motores = Motores(False)
motores.direcao_motor(2, Motores.INVERTIDO)
barramento = Portas().abre_porta_serial(Portas.SERIAL1, 250000, timeout=0.005)
placas = [PlacaControleMotor(barramento, 8), PlacaControleMotor(barramento, 51)]
placas[1].direcao_motor(PlacaControleMotor.INVERTIDO)
giro = Giroscopio(Portas.SERIAL5)
camera = Visao()


def anda(ve, vd):
    motores.velocidade_motores(int(ve), int(vd))
    motores.atualiza_motores()
    placas[0].velocidade_motor(int(ve))
    placas[1].velocidade_motor(int(vd))


def z():
    return -giro.le_angulo_z()            # + = esquerda


def gira(graus):
    alvo = z() + graus
    fim = time.time() + 3
    while time.time() < fim and abs(alvo - z()) > 2:
        v = max(18, min(45, abs(alvo - z()) * 0.8)) * (1 if alvo > z() else -1)
        anda(-v, v)
        time.sleep(0.01)
    anda(0, 0)


try:
    # entra na área: ~45 cm para frente
    fim = time.time() + 2.5
    while time.time() < fim:
        anda(40, 40)
        time.sleep(0.02)
    anda(0, 0)

    for tentativa in range(18):              # gira no máximo 360° em passos de 20°
        vitimas = camera.vitimas()           # espera o próximo quadro da IA (~4 por segundo)
        if vitimas:
            break
        gira(20)
    else:
        raise SystemExit('nenhuma vítima à vista')

    alvo = vitimas[0]                         # a lista vem da mais perto para a mais longe
    print(f'vi uma vítima {alvo.tipo} a {alvo.distancia} mm, {alvo.angulo:+.0f}°')
    # aproxima: corrige o ângulo e anda até ~15 cm
    perdidas = 0
    while True:
        vs = camera.vitimas()
        if not vs:
            # 90% de acerto: um quadro sem a vítima é normal. Continue andando (parado, a
            # câmera vê a mesma cena e tende a errar de novo) e só desista depois de vários
            perdidas += 1
            if perdidas > 6:
                print('perdi a vítima de vista')
                break
            continue
        perdidas = 0
        v = vs[0]
        if v.distancia < 150:
            print(f'cheguei: vítima {v.tipo} a {v.distancia} mm')
            break
        correcao = max(-20, min(20, v.angulo * 0.8))   # ângulo + = vítima à esquerda
        anda(30 - correcao, 30 + correcao)
    anda(0, 0)

    for t in camera.triangulos():               # OpenCV: ~30 quadros por segundo
        print(f'triângulo {t.cor}: {t.angulo:+.0f}°, parede a {t.distancia} mm')
finally:
    anda(0, 0)
