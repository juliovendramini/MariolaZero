"""AUTOTESTE: testa as peças do robô, uma por uma, para achar problemas.

O robô (o que ele tem e onde está ligado) está no robo.json desta pasta.

No robô, pelo menu principal ou pelo terminal (SSH):
    python3 main.py                        menu na tela do robô (CIMA/BAIXO, ENTER, VOLTAR)
    python3 main.py ?                      lista os testes que dá para pedir
    python3 main.py giroscopio             só o giroscópio
    python3 main.py vl53_vivo              VL53 ao vivo (Ctrl+C ou ENTER/VOLTAR no robô para sair)
    python3 main.py i2c motores            vários, na ordem
    python3 main.py completo               o teste completo, sem o menu
    python3 main.py giroscopio --terminal  as perguntas são respondidas no terminal, não no teclado do robô
    python3 main.py --automatico           tudo sem perguntar nada (motores parados)
    python3 main.py --automatico --motores ...e gira os motores (rodas no ar!)

O resultado de cada rodada fica em relatorios/AAAA-MM-DD_HHMMSS.txt. O LEIAME.md explica tudo.
"""

import argparse
import atexit
import json
import os
import signal
import socket
import sys
import time
import traceback

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(RAIZ, 'libs'))      # as libs do Mariola, iguais às de libs/ do repositório
sys.path.insert(0, RAIZ)
try:
    sys.stdout.reconfigure(line_buffering=True)      # pelo menu, a saída vai para um arquivo
except Exception:
    pass

import interface as I                      # noqa: E402
from contexto import Contexto              # noqa: E402
from relatorio import Relatorio, OK, AVISO, FALHA, PULOU   # noqa: E402
from testes import sistema, painel, brick, barramento, seriais, i2c, pinos_cameras, maze   # noqa: E402

ARQ_ROBO = os.path.join(RAIZ, 'robo.json')


def _estresse_completo(ctx):
    if ctx.automatico:
        brick.estresse(ctx) if ctx.pode_motores_automatico else ctx.rel.pulou('estresse (sem --motores)')
        return
    r = ctx.ui.pergunta('ESTRESSE', 'Motores invertendo a 80% por 20 s. Fazer?')
    if r:
        brick.estresse(ctx)
    else:
        ctx.rel.pulou('teste de estresse')


def _tem(*chaves):
    """Condição: o robo.json tem alguma coisa nessas chaves (ex.: 'barramento.servos')."""
    def condicao(robo):
        for chave in chaves:
            v = robo
            for parte in chave.split('.'):
                v = v.get(parte) if isinstance(v, dict) else None
            if v:
                return True
        return False
    return condicao


def _timer2(dono):
    return lambda robo: robo.get('brick', {}).get('timer2') == dono


def _sempre(robo):
    return True


# (chave, nome no menu, função, entra no teste completo, o robô tem?, descrição para a lista do "?")
TODOS = [
    ('sistema', 'Sistema (Linux/USB)', sistema.roda, True, _sempre,
     'temperatura, memória, disco, rede, conversores USB do hub e resets do hub no dmesg'),
    ('painel', 'Tela e teclado', painel.roda, True, _sempre,
     'tela, os 4 botões (e botão preso) e os 4 LEDs do teclado'),
    ('brick', 'Brick: comunicacao', brick.comunicacao, True, _sempre,
     '200 trocas com o ATmega (tempo, perdidas) e a calibração dos motores 1 e 2'),
    ('leds', 'LEDs RGB', brick.leds, True, _sempre, 'os 10 LEDs RGB nas 4 cores e um por um'),
    ('buzzer', 'Buzzer', brick.buzzer, True, _timer2('buzzer'), 'nível LOW/HIGH, 2 bipes e um tom'),
    ('servos_comuns', 'Servos comuns', brick.servos_comuns, True, _tem('brick.servos_comuns'),
     'cada servo comum do brick vai e volta'),
    ('i2c', 'Sensores I2C', i2c.sensores, True, _tem('vl53', 'tcs'),
     'mux, VL53 e TCS nos 8 canais: quem falta, quem sobra, leituras'),
    ('giroscopio', 'Giroscopio', seriais.giroscopio, True, _tem('giroscopio'),
     'respostas, inclinação, deriva parado, giro de 90° à mão'),
    ('linha', 'Sensor de linha', seriais.sensores_linha, True, _tem('sensores_linha'),
     'respostas, branco e preto nos 4 IR e nos 3 TCS'),
    ('pinos', 'Para-choques', pinos_cameras.pinos, True, _tem('pinos'),
     'chave presa e cada para-choque/botão apertado'),
    ('cameras', 'Cameras', pinos_cameras.cameras, True, _tem('cameras'),
     'resolução, quadros/s, brilho e uma foto de cada câmera'),
    ('placas', 'Placas de motor', barramento.placas_motor, True, _tem('barramento.placas_motor'),
     'cada placa do barramento: responde, calibração, gira e conta nos dois sentidos'),
    ('servos', 'Servos inteligentes', barramento.servos, True, _tem('barramento.servos'),
     'cada servo do barramento: responde, polaridade, mexe um pouco e volta'),
    ('motores', 'Motores do brick', brick.motores_brick, True, _tem('brick.motores_encoder', 'brick.motores_sem_encoder'),
     'potência, velocidade (PID), move_motor(360), os dois na mesma velocidade'),
    ('estresse', 'Teste de estresse', _estresse_completo, True, _sempre,
     '20 s com os motores invertendo a 80%: comunicação perdida e resets do hub USB'),
    # Maze (chave "maze" do robo.json): com os números da equipe
    ('paredes', 'Maze: paredes', maze.paredes, True, _tem('maze'),
     'no centro do ladrilho: VL53 laterais abaixo da distância "sem parede", meio e borda iguais'),
    ('cores_piso', 'Maze: cores do piso', maze.cores_piso, True, _tem('maze'),
     'TCS do chão no branco, preto, azul, prata e vermelho contra as faixas da equipe'),
    # só pelo menu ou pedindo pelo nome
    ('vl53_vivo', 'VL53 ao vivo', i2c.vl53_ao_vivo, False, _tem('vl53'), 'distância de cada VL53 na hora'),
    ('tcs_vivo', 'TCS ao vivo', i2c.tcs_ao_vivo, False, _tem('tcs'), 'RGBC de cada TCS na hora'),
    ('pinos_vivo', 'Pinos ao vivo', pinos_cameras.pinos_ao_vivo, False, _sempre, 'P1 a P8 na hora (só leitura)'),
    ('calibra', 'Calibrar motores', brick.calibra, False, _tem('brick.motores_encoder'),
     'calibração dos motores 1 e 2 do brick (30 s, rodas no ar)'),
    ('procura', 'Procurar placas', barramento.procura, False, _sempre,
     'procura placas de motor e servos (IDs 0-255) no SERIAL1 a 3: acha ID trocado'),
    ('andar', 'Maze: andar e girar', maze.andar, False, _tem('maze'),
     'no chão, de frente para a parede: mede o CONTAGENS_POR_MM e o erro de 4 giros de 90°'),
]
AO_VIVO = {'vl53_vivo', 'tcs_vivo', 'pinos_vivo'}


def testes_do_robo(robo):
    return [(c, n, f, comp, desc) for c, n, f, comp, tem, desc in TODOS if tem(robo)]


def executa(ctx, chave, nome, funcao):
    ui, rel = ctx.ui, ctx.rel
    rel.secao(nome)
    ui.led_resultado('TESTANDO')
    inicio = len(rel.itens)
    try:
        funcao(ctx)
    except KeyboardInterrupt:
        raise
    except Exception as erro:
        traceback.print_exc()
        rel.falha(f'o teste parou com erro: {type(erro).__name__}: {erro}',
                  'veja o relatório/terminal; pode ser defeito ou um caso que o autoteste não previu')
    finally:
        ctx.para_tudo()
    itens = rel.itens[inicio:]
    ui.led_resultado(rel.pior(itens))
    if chave not in AO_VIVO:
        n = rel.conta(itens)
        ui.mostra(nome[:20], f'{n[OK]} ok  {n[AVISO]} aviso', f'{n[FALHA]} falha  {n[PULOU]} pulou', '')
        time.sleep(1.2 if not ui.automatico else 0)
    return itens


def mostra_problemas(ui, itens, titulo):
    """CIMA/BAIXO passam pelos avisos e falhas; ENTER mostra a dica; VOLTAR sai."""
    problemas = [it for it in itens if it.nivel in (FALHA, AVISO)]
    problemas.sort(key=lambda it: 0 if it.nivel == FALHA else 1)
    n = Relatorio.conta(itens)
    resumo = [titulo[:20], f'{n[OK]} ok  {n[AVISO]} aviso', f'{n[FALHA]} falha  {n[PULOU]} pulou',
              'BAIXO=ver ENTER=sai' if problemas else 'tudo certo! ENTER']
    ui.mostra(*resumo)
    if ui.automatico or ui.console:
        return
    i, dica = -1, False
    while True:
        b = ui.espera((I.CIMA, I.BAIXO, I.ENTER, I.VOLTAR))
        if b in (None, I.VOLTAR) or (b == I.ENTER and i < 0):
            return
        if b == I.ENTER:
            dica = not dica
        elif problemas:
            if i < 0:
                i = 0 if b == I.BAIXO else len(problemas) - 1
            else:
                i = (i + (1 if b == I.BAIXO else -1)) % len(problemas)
            dica = False
        if i < 0:
            ui.mostra(*resumo)
            continue
        it = problemas[i]
        texto = (it.dica or '(sem dica)') if dica else it.texto
        ui.mostra(f'{it.nivel} {i + 1}/{len(problemas)} ' + ('dica' if dica else it.secao[:8]), *I.quebra(texto)[:3])


def roda_lista(ctx, testes, chaves=None):
    """Roda os testes pedidos (chaves, na ordem pedida) ou os do teste completo."""
    itens = []
    por_chave = {c: (c, n, f) for c, n, f, _, _ in testes}
    if chaves is None:
        chaves = [c for c, _, _, comp, _ in testes if comp]
    for c in chaves:
        itens += executa(ctx, *por_chave[c])
    return itens


def lista(robo, testes, explicacao=None):
    if explicacao:
        print(explicacao)
    print(f'\nTestes do {robo["nome"]} (python3 main.py NOME [NOME...]):\n')
    largura = max(len(c) for c, *_ in testes)
    for c, n, f, comp, desc in testes:
        print(f'  {c:{largura}s}  {desc}' + ('' if comp else '   [fora do completo]'))
    print(f'  {"completo":{largura}s}  todos os do teste completo, na ordem, sem o menu')
    print('\nOpções: --terminal (responde as perguntas aqui, não no teclado do robô), '
          '--automatico (não pergunta nada), --motores (no automático, gira os motores)')
    print("Se o '?' não funcionar no seu terminal, use '\\?', \"?\" ou lista.")


def menu(ctx, testes):
    ui = ctx.ui
    opcoes = ['Teste completo'] + [n for _, n, _, _, _ in testes] + ['Sair']
    escolha = 0
    while True:
        i = ui.escolhe(ctx.perfil['nome'][:20], opcoes, escolha)
        if i is None or i == len(opcoes) - 1:
            if ui.pergunta('SAIR', 'Sair do autoteste?'):
                return
            continue
        escolha = i
        if i == 0:
            mostra_problemas(ui, roda_lista(ctx, testes), 'TESTE COMPLETO')
        else:
            chave, nome, funcao, _, _ = testes[i - 1]
            itens = executa(ctx, chave, nome, funcao)
            if chave not in AO_VIVO:
                mostra_problemas(ui, itens, nome)


def main():
    with open(ARQ_ROBO, encoding='utf-8') as f:
        robo = json.load(f)
    testes = testes_do_robo(robo)
    chaves_validas = [c for c, *_ in testes]

    ap = argparse.ArgumentParser(description=f'Autoteste do {robo["nome"]}. Use "?" para a lista de testes.',
                                 add_help=True)
    ap.add_argument('testes', nargs='*', help='testes a rodar (? = lista)')
    ap.add_argument('--terminal', action='store_true', help='responde as perguntas no terminal')
    ap.add_argument('--automatico', action='store_true', help='roda sem perguntar nada')
    ap.add_argument('--motores', action='store_true', help='no automático, gira os motores (rodas no ar!)')
    a = ap.parse_args()
    if os.environ.get('AUTOTESTE_AUTOMATICO'):      # o simulador não passa argumentos ao programa
        a.automatico = True
    if os.environ.get('AUTOTESTE_MOTORES'):
        a.motores = True
    if not a.testes and os.environ.get('AUTOTESTE_TESTES'):
        a.testes = os.environ['AUTOTESTE_TESTES'].replace(',', ' ').split()

    # "?" (ou lista/ajuda) mostra o que dá para pedir
    pedidos = [t.strip().lower() for t in a.testes if t.strip()]
    if any(t in ('?', '\\?', 'lista', 'ajuda', 'help') for t in pedidos):
        lista(robo, testes)
        return
    chaves = None
    if pedidos:
        chaves = []
        for t in pedidos:
            if t == 'completo':
                chaves += [c for c, _, _, comp, _ in testes if comp]
            elif t in chaves_validas:
                chaves.append(t)
            else:
                lista(robo, testes, f'Não conheço o teste "{t}".')
                sys.exit(2)

    ui = I.Interface(automatico=a.automatico, terminal=a.terminal)
    ui.mostra('AUTOTESTE', robo['nome'][:20], 'iniciando...', '')
    modo = ('automático' + (' com motores' if a.motores else ' sem motores') if ui.automatico
            else 'respostas no terminal' if ui.console else 'tela e teclado')
    cabecalho = [f'robô: {robo["nome"]} (robo.json)',
                 f'brick: {socket.gethostname()}   python {sys.version.split()[0]}',
                 f'modo: {modo}' + (f'   testes: {" ".join(chaves)}' if chaves else '')]
    rel = Relatorio(os.path.join(RAIZ, 'relatorios'), cabecalho)
    ctx = Contexto(ui, rel, robo, automatico=ui.automatico, motores=a.motores, raiz=RAIZ)

    def sai(*_):
        raise SystemExit(1)
    signal.signal(signal.SIGTERM, sai)        # o envia.bat faz killall main.py
    atexit.register(ctx.fecha)

    codigo = 0
    try:
        if chaves is not None or ui.automatico:
            itens = roda_lista(ctx, testes, chaves)
            if not (chaves and all(c in AO_VIVO for c in chaves)):
                mostra_problemas(ui, itens, 'RESULTADO')
            codigo = 1 if any(it.nivel == FALHA for it in itens) else 0
        else:
            menu(ctx, testes)
    except KeyboardInterrupt:
        print('\ninterrompido (Ctrl+C)')
    finally:
        ctx.fecha()
        rel.fecha()
        if rel.caminho:
            print(f'\nrelatório: {rel.caminho}')
        ui.mostra('AUTOTESTE', 'terminou', 'relatorio em', 'relatorios/')
    sys.exit(codigo)


if __name__ == '__main__':
    main()
