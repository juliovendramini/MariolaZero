"""Pinos digitais P1-P8 (para-choques e botões; só leitura) e câmeras USB."""

import glob
import os
import sys
import time

from interface import VOLTAR

NOMES_PINOS = ('P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8')


def _pinos(ctx):
    try:
        from pinosDigitais import PinosDigitais
        return PinosDigitais()
    except Exception as erro:
        ctx.rel.falha(f'não abriu os pinos digitais ({erro})', 'gpiod / kernel (INSTALACAO.md)')
        return None


def pinos(ctx):
    rel = ctx.rel
    ui = ctx.ui
    lista = ctx.perfil.get('pinos', [])
    nao_mexer = set(ctx.perfil.get('pinos_nao_mexer', []))
    pd = _pinos(ctx)
    if pd is None:
        return
    rel.ok(f'pinos digitais abertos ({pd.chip_name})')
    if not lista:
        rel.pulou('o robo.json não tem para-choques nem botões nos pinos')
        return
    for p in lista:
        nome = p['pino']
        if nome in nao_mexer:
            continue
        pino = getattr(pd, nome)
        try:
            pd.configura_pino(pino, pd.ENTRADA)
        except Exception as erro:
            rel.falha(f'{nome}: não deu para configurar como entrada ({erro})')
    time.sleep(0.05)
    # sem ninguém tocar: algum aparece apertado o tempo todo?
    presos = []
    for p in lista:
        if p['pino'] in nao_mexer:
            continue
        try:
            if all(pd.botao_pressionado(getattr(pd, p['pino'])) for _ in range(10)):
                presos.append(p)
        except Exception:
            pass
    for p in presos:
        rel.aviso(f'{p["pino"]} ({p.get("nome", "")}) aparece apertado sem ninguém tocar',
                  'chave presa, fio em curto com o GND, ou chave ligada no NF')
    if ui.automatico or ui.console:
        rel.pulou('apertar cada para-choque/botão (precisa de alguém)')
        return
    for p in lista:
        if p['pino'] in nao_mexer or p in presos:
            continue
        pino = getattr(pd, p['pino'])
        ui.mostra('PINOS', f'aperte {p.get("nome", p["pino"])}'[:20], f'({p["pino"]}, 10 s)', 'VOLTAR=pula')
        ui.solta_tudo()
        fim = time.monotonic() + 10
        viu = None
        while time.monotonic() < fim:
            if pd.botao_pressionado(pino):
                viu = True
                break
            if ui.aperto() == VOLTAR:
                viu = False
                break
            time.sleep(0.01)
        if viu:
            rel.ok(f'{p["pino"]} ({p.get("nome", "")}) funciona')
            ui.mostra('PINOS', f'{p["pino"]} ok', 'solte...', '')
            fim = time.monotonic() + 3
            while pd.botao_pressionado(pino) and time.monotonic() < fim:
                time.sleep(0.02)
        elif viu is None:
            rel.falha(f'{p["pino"]} ({p.get("nome", "")}) não mudou em 10 s',
                      'chave solta, fio partido ou ligada em outro pino')
        else:
            rel.pulou(f'{p["pino"]} ({p.get("nome", "")})')


def pinos_ao_vivo(ctx):
    pd = _pinos(ctx)
    if pd is None:
        return
    nao_mexer = set(ctx.perfil.get('pinos_nao_mexer', []))
    usaveis = [n for n in NOMES_PINOS if n not in nao_mexer and not (n == 'P8' and pd.PWM)]
    for n in usaveis:
        try:
            if pd.get_direcao(getattr(pd, n)) != pd.ENTRADA:
                pd.configura_pino(getattr(pd, n), pd.ENTRADA)
        except Exception:
            pass

    def tela(_p):
        estados = []
        for n in usaveis:
            try:
                estados.append(n[1] + ('X' if pd.botao_pressionado(getattr(pd, n)) else '.'))
            except Exception:
                estados.append(n[1] + '?')
        return ['PINOS (X=apertado)', ' '.join(estados[:4]), ' '.join(estados[4:]), 'ENTER/VOLTAR sai']
    ctx.ui.ao_vivo(tela, periodo=0.05)


def cameras(ctx):
    rel = ctx.rel
    ui = ctx.ui
    try:
        import cv2
    except ImportError:
        rel.falha('OpenCV (cv2) não está instalado neste Python', 'ative o ~/meu_venv antes de rodar')
        return
    esperadas = ctx.perfil.get('cameras', [])
    linux = sys.platform.startswith('linux')
    outras = sorted(set(glob.glob('/dev/video*')) - set(esperadas)) if linux else []
    if not esperadas and not outras:
        rel.info('nenhuma câmera (/dev/video*)')
        return
    pasta = os.path.join(ctx.raiz, 'fotos')
    for dev in list(esperadas) + outras:
        if linux and not os.path.exists(dev):
            rel.falha(f'câmera {dev} não existe', 'câmera desligada, cabo USB, ou a regra do udev (INSTALACAO.md)')
            continue
        if linux and os.path.islink(dev):
            rel.info(f'{dev} -> {os.path.realpath(dev)}')
        ui.mostra('CAMERAS', dev[-20:], 'abrindo...', '')
        cap = cv2.VideoCapture(dev)
        if not cap.isOpened():
            if dev in esperadas:
                rel.falha(f'câmera {dev} não abriu', 'outro programa usando a câmera, ou cabo USB')
            continue   # /dev/videoN extras: metade são nós de metadados, que não abrem
        quadros, inicio, ultimo = 0, time.monotonic(), None
        while time.monotonic() - inicio < 2.0:
            ok, img = cap.read()
            if ok and img is not None:
                quadros += 1
                ultimo = img
        duracao = time.monotonic() - inicio
        cap.release()
        if ultimo is None:
            rel.falha(f'câmera {dev} abriu mas não mandou imagem')
            continue
        h, w = ultimo.shape[:2]
        cinza = cv2.cvtColor(ultimo, cv2.COLOR_BGR2GRAY) if ultimo.ndim == 3 else ultimo
        brilho, contraste = float(cinza.mean()), float(cinza.std())
        txt = f'câmera {dev}: {w}x{h}, {quadros / duracao:.0f} quadros/s, brilho {brilho:.0f}'
        if brilho < 15:
            rel.aviso(txt, 'imagem quase preta: tampa na lente ou ambiente escuro')
        elif contraste < 4:
            rel.aviso(txt, 'imagem lisa: lente desfocada ou suja')
        elif quadros / duracao < 8:
            rel.aviso(txt, 'poucos quadros por segundo: porta USB lenta ou CPU ocupada')
        else:
            rel.ok(txt)
        try:
            os.makedirs(pasta, exist_ok=True)
            arq = os.path.join(pasta, os.path.basename(dev) + '.jpg')
            cv2.imwrite(arq, ultimo)
            rel.info(f'foto salva em {arq}')
        except Exception:
            pass
