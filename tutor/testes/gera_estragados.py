"""Gera os programas estragados de propósito para testar o resumo (e depois o tutor).

Os casos 00-16 partem do seguidor PD do curso (curso/codigos/04_linha/seguidor_p.py, robô de
esteira) e os 17-20 do programa de exemplo do simulador (simuladorLine/exemplo_aluno, robô 4x4,
que trata verde, gap e obstáculo). Cada um troca um trecho e fica em estragados/NN_nome/main.py. O que o resumo deve achar está em casos.json ("esperado":
códigos do tutor/resumo.py). Rode de novo se o seguidor do curso mudar:

    python tutor/testes/gera_estragados.py
"""
import json
import os
import shutil

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
BASE = os.path.join(REPO, 'curso', 'codigos', '04_linha', 'seguidor_p.py')
SAIDA = os.path.join(AQUI, 'estragados')

PERDA = 'anda(-25 * ultimo_lado, 25 * ultimo_lado)'
CORRECAO = 'anda(VEL - correcao, VEL + correcao)'
VERMELHO = '''        if sum(eh_vermelho(k) for k in (1, 2, 3)) >= 2:   # fita vermelha da chegada
            print('Chegada!')
            anda(0, 0)
            time.sleep(6)                              # a regra pede mais de 5 s parado
            break
'''

# nome, desafio, [(trecho, troca)], esperado, o defeito (para quem lê)
CASOS = [
    ('00_certo', 'L01', [], [], 'nenhum: o seguidor PD do curso'),
    ('01_kp_alto', 'L01', [('KP = 1.4', 'KP = 15.0'), ('KD = 5.0', 'KD = 0.0')], ['ziguezague'],
     'KP alto demais e sem KD: o robô corrige demais e ziguezagueia (com KP 6 e KD 5 a esteira ainda anda lisa)'),
    ('02_kp_baixo', 'L01', [('KP = 1.4', 'KP = 0.2'), ('KD = 5.0', 'KD = 0.0')], ['perde_linha'],
     'KP baixo demais: não vira o bastante nas curvas'),
    ('03_correcao_trocada', 'L01', [(CORRECAO, 'anda(VEL + correcao, VEL - correcao)')], ['correcao_ao_contrario'],
     'sinal da correção trocado: vira para o lado contrário da linha'),
    ('04_rapido', 'L01', [('VEL = 35', 'VEL = 90')], ['rapido_demais', 'perde_linha'],
     'velocidade alta demais para as curvas de 90°'),
    ('05_perdeu_segue_reto', 'L01', [(PERDA, 'anda(VEL, VEL)')], ['perdeu_seguiu_reto'],
     'quando perde a linha, continua reto'),
    ('06_perdeu_gira_errado', 'L01', [(PERDA, 'anda(25 * ultimo_lado, -25 * ultimo_lado)')], ['perdeu_girou_errado'],
     'quando perde a linha, gira para o lado contrário de onde ela foi vista'),
    ('07_ultimo_lado_fixo', 'L01', [('            ultimo_lado = 1 if erro > 0 else -1\n', '')], ['perdeu_girou_errado'],
     'não guarda o lado em que viu a linha: quando perde, gira sempre para a esquerda'),
    ('08_laco_lento', 'L01', [('        time.sleep(0.01)\nfinally', '        time.sleep(0.3)\nfinally')], ['laco_lento'],
     'pausa de 0,3 s no laço: lê o sensor poucas vezes por segundo'),
    ('09_le_uma_vez', 'L01', [('        pos = posicao_linha()\n', ''), ('try:\n    erro_anterior', 'pos = posicao_linha()\ntry:\n    erro_anterior')],
     ['sensor_parado'], 'lê o sensor uma vez só, antes do laço'),
    ('10_erro_digitacao', 'L01', [(CORRECAO, 'anda(VEL - correcao, VEL + corecao)')], ['erro_programa'],
     'erro de digitação (corecao): NameError'),
    ('11_sem_inverter_motor', 'L01', [('motores.direcao_motor(2, Motores.INVERTIDO)\n', '')], ['gira_no_lugar'],
     'esqueceu de inverter o motor 2: o robô gira no lugar'),
    ('12_lento', 'L01', [('VEL = 35', 'VEL = 4')], ['lento'],
     'velocidade baixa demais: não chega a tempo'),
    ('13_nao_para_chegada', 'L01', [(VERMELHO, '')], ['passou_da_chegada'],
     'não procura a fita vermelha: passa da chegada'),
    ('14_programa_curto', 'L01', [('time.time() + 180', 'time.time() + 12')], ['programa_terminou'],
     'o laço só dura 12 s'),
    ('15_pesos_invertidos', 'L01', [('pesos = [max(0, min(100, 100 - v)) / 100 for v in ir]',
                                     'pesos = [max(0, min(100, v)) / 100 for v in ir]')], ['correcao_ao_contrario'],
     'peso do branco no lugar do preto: a "posição da linha" sai do lado contrário e o robô vira para longe dela'),
    ('16_kd_negativo', 'L01', [('KD = 5.0', 'KD = -20.0')], ['ziguezague'],
     'KD com o sinal trocado: o derivativo aumenta o zigue-zague (com -8 a esteira ainda anda lisa)'),
]

# a partir do programa de exemplo do simulador da Line (trata verde, gap e obstáculo; robô 4x4)
CASOS_EXEMPLO = [
    ('17_verde_trocado', 'L04', [('            self.verde_esq = agora', '            self.VERDE_X = agora'),
                                 ('            self.verde_dir = agora', '            self.verde_esq = agora'),
                                 ('            self.VERDE_X = agora', '            self.verde_dir = agora')],
     ['intersecao_verde'], 'troca o verde da esquerda pelo da direita: vira para o lado errado na interseção'),
    ('18_gap_desiste', 'L05', [('r.anda_mm(GAP_MAX_MM, vel=30, para_se=achou)', 'r.anda_mm(30, vel=30, para_se=achou)')],
     ['gap'], 'no gap só anda 3 cm antes de desistir e procurar a linha girando'),
    ('19_sem_obstaculo', 'L05', [('if r.para_choque() or r.frente_mm() < DIST_OBSTACULO:', 'if False:')],
     ['obstaculo'], 'não desvia do obstáculo (nem olha o VL53 nem o para-choque)'),
    ('20_exemplo_certo_L05', 'L05', [], [], 'nenhum: o programa de exemplo, no L05'),
]
EXEMPLO = os.path.join(REPO, 'simuladorLine', 'exemplo_aluno')


def main():
    with open(BASE, encoding='utf-8') as f:
        base = f.read()
    if os.path.isdir(SAIDA):
        shutil.rmtree(SAIDA)
    with open(os.path.join(EXEMPLO, 'main.py'), encoding='utf-8') as f:
        base_ex = f.read()
    casos = []
    for lista, texto, robo in ((CASOS, base, 'robo_esteira.json'), (CASOS_EXEMPLO, base_ex, 'robo_4x4.json')):
        for nome, desafio, trocas, esperado, defeito in lista:
            txt = texto
            for de, para in trocas:
                assert de in txt, f'{nome}: não achei {de!r} no programa de base'
                txt = txt.replace(de, para, 1)
            pasta = os.path.join(SAIDA, nome)
            if lista is CASOS_EXEMPLO:
                shutil.copytree(EXEMPLO, pasta, ignore=shutil.ignore_patterns('__pycache__', '*.json'))
            else:
                os.makedirs(pasta)
            cab = f'# CASO DE TESTE DO TUTOR ({nome}): {defeito}\n# gerado por tutor/testes/gera_estragados.py, não edite\n'
            with open(os.path.join(pasta, 'main.py'), 'w', encoding='utf-8', newline='\n') as f:
                f.write(cab + txt)
            casos.append({'nome': nome, 'desafio': desafio, 'robo': robo, 'esperado': esperado,
                          'defeito': defeito, 'programa': f'estragados/{nome}/main.py'})
    with open(os.path.join(AQUI, 'casos.json'), 'w', encoding='utf-8') as f:
        json.dump(casos, f, ensure_ascii=False, indent=1)
    print(f'{len(casos)} casos em {SAIDA}')


if __name__ == '__main__':
    main()
