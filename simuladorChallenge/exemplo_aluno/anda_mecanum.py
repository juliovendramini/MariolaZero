"""Exemplo de locomoção do robô mecanum na arena da RCB Challenge (sem usar a garra).

    python simulador.py --robo robo_mecanum.json --programa exemplo_aluno/anda_mecanum.py --cenario cenarios/vazio.json

(no cenarios/exemplo.json o cubo do A3 fica no caminho da rua do meio).

O robô começa na área verde da esquerda, olhando para a cidade, e:
1. anda reto, passa pela linha azul e acha a rua (linha preta);
2. segue a linha até o 3º cruzamento e para com o centro do robô em cima dele;
3. anda de lado para a esquerda até a rua de cima (uma quadra, 300 mm);
4. gira 180° pelo giroscópio;
5. segue a linha de volta até a linha azul e para dentro da área verde.

Se aparecer alguma coisa na frente (cubo, outro robô) a menos de 12 cm, ele espera.
"""

import time

from robo import PRETO, Robo

VEL = 45             # velocidade de cruzeiro (-100 a 100)
KP = 0.35            # ganho do seguidor de linha (giro por unidade de diferença de IR)


def correcao(ir):
    """Giro para a esquerda (+) quando a linha está à esquerda: a soma dos IR do lado da linha cai."""
    return KP * ((ir[2] + ir[3]) - (ir[0] + ir[1])) / 2.0


def cruzamento(ir):
    return all(v < PRETO for v in ir)


def espera_caminho_livre(r):
    if r.distancia('frente') < 120:
        r.para()
        print(f'obstáculo a {r.dist["frente"]} mm: esperando')
        while r.distancia('frente') < 120:
            r.para()
        print('caminho livre')


def segue_ate_cruzamento(r):
    """Segue a linha até os 4 IR verem preto (rua cruzando)."""
    n = 0
    while True:
        ir = r.ir()
        if cruzamento(ir):
            return
        r.move(VEL, 0, correcao(ir))
        n += 1
        if n % 10 == 0:
            espera_caminho_livre(r)
        time.sleep(0.01)


def passa_do_cruzamento(r):
    while cruzamento(r.ir()):
        r.move(VEL, 0, 0)
        time.sleep(0.01)


def anda_mm(r, frente_mm, vel=VEL):
    r.zera_encoder()
    while abs(r.deslocamento()[0]) < abs(frente_mm):
        r.move(vel if frente_mm > 0 else -vel, 0, 0)
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


def main():
    r = Robo()
    r.espera_botao()
    t0 = time.time()

    # 1. sai da área verde: reto até o IR do meio ver a linha preta (a linha azul não é tão escura)
    print('saindo da área verde')
    viu_azul = False
    while True:
        ir = r.ir()
        if r.piso() == 'azul' and not viu_azul:
            viu_azul = True
            print('passei pela linha azul')
        if ir[1] < PRETO or ir[2] < PRETO:
            break
        r.move(VEL, 0, 0)
        time.sleep(0.01)

    # 2. segue a rua até o 3º cruzamento
    for k in range(3):
        segue_ate_cruzamento(r)
        print(f'cruzamento {k + 1}')
        if k < 2:
            passa_do_cruzamento(r)
    anda_mm(r, 80)            # o sensor fica 80 mm à frente do centro: centraliza no cruzamento

    # 3. de lado para a esquerda até a rua de cima: pelo menos 200 mm no encoder e depois
    #    até os IR do meio verem a linha
    print('andando de lado')
    r.zera_encoder()
    while True:
        ir = r.ir()
        lado = r.deslocamento()[1]
        if lado > 200 and (ir[1] < PRETO or ir[2] < PRETO):
            break
        r.move(0, VEL, 0)
        time.sleep(0.01)
    r.para()
    print(f'encoder diz {r.deslocamento()[1]:.0f} mm de lado (a rua fica a 300 mm)')

    # 4. meia-volta
    print('girando 180°')
    gira(r, 180)

    # 5. de volta pela rua de cima até a linha azul
    while r.piso() != 'azul':
        ir = r.ir()
        r.move(VEL, 0, correcao(ir) if not cruzamento(ir) else 0)
        time.sleep(0.01)
    print('linha azul: entrando na área verde')
    anda_mm(r, 150)
    r.para()
    print(f'cheguei em {time.time() - t0:.1f} s')
    r.espera(1.0)


if __name__ == '__main__':
    main()
