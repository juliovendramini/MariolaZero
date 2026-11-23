"""Resumo da volta para o robô tutor (fase 0 do tutor/PLANO.md). Sem IA: só conta e mede.

Lê o registro da volta que o simulador da Line grava (`simulador.py --registro`, `avalia.py
--registros PASTA`; formato em simuladorLine/sim/registro.py) e diz o que deu errado, onde e com
os números. É isso que o tutor (a IA) recebe, em vez das milhares de linhas do registro.

    python tutor/resumo.py REGISTRO.jsonl [mais.jsonl ...]     texto (várias rodadas juntas)
    python tutor/resumo.py PASTA                                todos os .jsonl da pasta
      --json        os problemas como JSON (para os testes e para o tutor)
      --trecho T1 T2   as amostras entre T1 e T2 s da primeira rodada (o que o tutor pede para ver)

Cada problema tem um código (lista em CODIGOS), um grau (3 = impede o desafio, 2 = atrapalha,
1 = detalhe), o texto e um trecho (t1, t2) para ver de perto.

Convenções do registro que importam aqui: "chao" = material de verdade debaixo dos canais de IR e
dos TCS (b branco, p preto, v verde, r vermelho, s prata), da esquerda para a direita; "w" positivo =
o robô girando para a esquerda; "cmd"/"vel" com positivo = para a frente, na escala do
velocidade_motores(); y positivo = à esquerda.
"""
import argparse
import copy
import glob
import json
import os
import re
import statistics as st
import sys

# do mais provável de ser a causa para o mais provável de ser consequência
CODIGOS = {
    'erro_programa': 'o programa deu erro',
    'laco_lento': 'o laço do programa é lento',
    'gira_no_lugar': 'os motores giram em sentidos opostos',
    'correcao_ao_contrario': 'vira para o lado contrário da linha',
    'sensor_parado': 'os comandos não mudam com a linha',
    'programa_terminou': 'o programa terminou antes da hora',
    'intersecao_verde': 'errou na interseção com verde',
    'gap': 'não passou o gap',
    'obstaculo': 'não passou o obstáculo',
    'perdeu_seguiu_reto': 'perdeu a linha e seguiu reto',
    'perdeu_girou_errado': 'perdeu a linha e girou para o lado errado',
    'rapido_demais': 'rápido demais para as curvas',
    'ziguezague': 'ziguezague nas retas',
    'passou_da_chegada': 'passou da chegada sem parar',
    'lento': 'devagar demais',
    'perde_linha': 'perde a linha',
    'sem_avanco': 'ficou muito tempo no mesmo ladrilho',
    'parado': 'ficou parado',
    'tempo_esgotado': 'o tempo acabou',
}
ORDEM = list(CODIGOS)

# referência: o seguidor PD do curso no L01 (18/11/2026): 5 perdas de no máximo 0,3 s por volta,
# todas nas curvas de 90°; 0 trocas de lado por segundo nas retas; 113 mm/s nas retas; ~50 comandos
# de motor por segundo
V_REFERENCIA = 113         # mm/s nas retas do seguidor PD do curso
PERDA_MIN_S = 0.5          # perda de linha mais curta que isso é normal numa curva de 90°
DT = 0.05


def _br(x, casas=1):
    """Número com vírgula, como no curso."""
    return f'{x:.{casas}f}'.replace('.', ',')


class Volta:
    def __init__(self, arq):
        self.arq = arq
        self.cab, self.am, self.saidas, self.eventos, self.fim = {}, [], [], [], {}
        with open(arq, encoding='utf-8') as f:
            for linha in f:
                d = json.loads(linha)
                if 'cabecalho' in d:
                    self.cab = d['cabecalho']
                elif 'saida' in d:
                    self.saidas.append(d)
                elif 'evento' in d:
                    self.eventos.append(d)
                elif 'fim' in d:
                    self.fim = d['fim']
                elif 'x' in d:
                    self.am.append(d)
        m = re.search(r'_s(\d+)\.jsonl$', arq)
        self.semente = int(m.group(1)) if m else None
        self.passos = self.cab.get('passos', [])
        sen = self.cab.get('sensor') or {}
        self.y_ir = sen.get('canais_ir_y', [26.6, 8.9, -8.9, -26.6])
        self.n_ir = len(self.y_ir)
        ys = [mo['y'] for mo in self.cab.get('motores', [])]
        self.esq = [i for i, y in enumerate(ys) if y > 0]
        self.dir = [i for i, y in enumerate(ys) if y < 0]

    # ------------------------------------------------------------------ ajudantes
    def passo(self, d):
        i = d.get('passo', 0)
        return self.passos[i] if 0 <= i < len(self.passos) else {}

    def onde(self, d):
        p = self.passo(d)
        txt = p.get('forma', '?')
        itens = p.get('itens') or {}
        extra = [NOMES_ITENS.get(k, k) for k in itens]
        if p.get('verde'):
            extra.append('verde')
        if p.get('chegada'):
            extra.append('chegada')
        return f'ladrilho {d.get("passo", 0) + 1} ({txt}' + (', ' + ', '.join(extra) if extra else '') + ')'

    def linha_debaixo(self, d):
        """Posição da linha preta debaixo dos IR (mm, + = esquerda) de verdade, ou None."""
        ch = d.get('chao', '')[:self.n_ir]
        ys = [y for c, y in zip(ch, self.y_ir) if c == 'p']
        return sum(ys) / len(ys) if ys else None

    def lado(self, cmds, lado):
        vs = [cmds[i] for i in lado if i < len(cmds) and cmds[i] is not None]
        return sum(vs) / len(vs) if vs else 0.0

    def amostra_em(self, t):
        ant = None
        for d in self.am:
            if d['t'] > t:
                break
            ant = d
        return ant or (self.am[0] if self.am else None)

    def entre(self, t1, t2):
        return [d for d in self.am if t1 <= d['t'] <= t2]

    def lops(self):
        return [e for e in self.eventos if e['evento'].startswith('LoP')]


NOMES_ITENS = {'intersecao': 'interseção', 'gap': 'gap', 'obstaculo': 'obstáculo', 'lombada': 'lombada',
               'rampa': 'rampa', 'gangorra': 'gangorra'}


def problema(codigo, grau, texto, t1=None, t2=None, **extra):
    p = {'codigo': codigo, 'grau': grau, 'texto': texto}
    if t1 is not None:
        p['trecho'] = [round(max(0.0, t1), 2), round(t2 if t2 is not None else t1, 2)]
    p.update(extra)
    return p


# ---------------------------------------------------------------------- análise de uma rodada
def analisa(v):
    """Lista de problemas de uma rodada (do registro) e alguns números gerais."""
    ps = []
    am = v.am
    if not am:
        return [problema('programa_terminou', 3, 'o robô não chegou a andar: a rodada não tem amostras')], {}
    dur = am[-1]['t']
    numeros = _numeros(v)

    # passou da fita vermelha sem parar: o que vem depois (pista acabou) é consequência
    ps += _chegada(v)
    if ps:
        corte = ps[0]['trecho'][0] + 1.5
        v = copy.copy(v)
        v.am = [d for d in v.am if d['t'] <= corte]
        v.eventos = [e for e in v.eventos if e['t'] <= corte]
        v.fim = dict(v.fim or {}, motivo='passou da chegada')

    ps += _erro_programa(v)
    ps += _fim(v, numeros)
    ps += _gira_no_lugar(v)
    ps += _correcao(v)
    ps += _comando_constante(v)
    ps += _laco(v, numeros)
    ps += _perdas(v)
    ps += _itens(v)
    ps += _sem_avanco(v, ps)
    ps += _ziguezague(v, numeros)
    ps += _lento(v, numeros)
    ps += _parado(v)
    # o programa terminou depois de o robô se perder: é consequência, não a causa
    outros = {p['codigo'] for p in ps if p['grau'] >= 2} - {'programa_terminou', 'tempo_esgotado'}
    for p in ps:
        if p['codigo'] == 'programa_terminou' and outros:
            p['grau'] = 1
            p['texto'] += ' (provavelmente por causa dos outros problemas)'
    # perde a linha nas curvas andando muito mais rápido que o seguidor do curso: a velocidade é a suspeita
    vr = numeros.get('v_retas_mm_s')
    perde = next((p for p in ps if p['codigo'] == 'perde_linha'), None)
    if perde is not None and 'curva' in perde['texto'] and vr and vr > 1.8 * V_REFERENCIA:
        ps.append(problema('rapido_demais', perde['grau'],
                           f'nas retas o robô anda a {vr} mm/s, {_br(vr / V_REFERENCIA)} vezes a do seguidor do curso '
                           f'(~{V_REFERENCIA} mm/s), e perde a linha nas curvas (o problema "perde a linha" logo abaixo)',
                           *perde['trecho']))
    ps.sort(key=lambda p: (-p['grau'], ORDEM.index(p['codigo'])))
    numeros['duracao_s'] = dur
    return ps, numeros


def _numeros(v):
    am = v.am
    retas = [d for d in am if v.passo(d).get('forma') == 'reta' and d['v'] > 20]
    dist = sum(abs(d['v']) for d in am) * DT
    mot = sum(d.get('leu', {}).get('brick', 0) + d.get('leu', {}).get('placa', 0) for d in am)
    # do primeiro comando em diante (antes o programa ainda está subindo)
    t_cmd = next((d['t'] for d in am if any(c for c in d['cmd'] if c)), am[0]['t'])
    vivo = max(DT, am[-1]['t'] - t_cmd)
    return {'distancia_mm': round(dist), 'v_retas_mm_s': round(st.mean(d['v'] for d in retas)) if retas else None,
            'v_media_mm_s': round(dist / max(DT, am[-1]['t'])),
            'comandos_motor_por_s': round(mot / vivo, 1), 'leu_vl53': any('vl53' in d.get('leu', {}) for d in am)}


def _erro_programa(v):
    txt = [s['saida'] for s in v.saidas]
    if not any('Traceback (most recent call last)' in s for s in txt):
        return []
    i = max(k for k, s in enumerate(txt) if 'Traceback (most recent call last)' in s)
    bloco = txt[i:]
    onde = None
    for s in bloco:
        m = re.search(r'File "([^"]+)", line (\d+)', s)
        if m and 'libs_mariola' not in m.group(1) and 'fake_hw' not in m.group(1) and 'rodar.py' not in m.group(1):
            onde = (os.path.basename(m.group(1)), int(m.group(2)))
    msg = next((s.strip() for s in reversed(bloco) if re.match(r'\s*\w*(Error|Exception|Interrupt)\b', s)), bloco[-1].strip())
    t = v.saidas[i]['t']
    lugar = f' no {onde[0]}, linha {onde[1]}' if onde else ''
    quando = 'logo no começo' if t < 0.5 else f'aos {_br(t)} s'
    return [problema('erro_programa', 3, f'o programa parou com erro {quando}{lugar}: {msg}', t - 1, t,
                     arquivo=onde[0] if onde else None, linha=onde[1] if onde else None, mensagem=msg)]


def _fim(v, numeros):
    f = v.fim or {}
    if f.get('chegou'):
        return []
    passos = f.get('passos') or max(1, len(v.passos) - 1)
    onde = f'no ladrilho {f.get("passo", 0) + 1} de {passos + 1}'
    motivo = f.get('motivo', '')
    if motivo == 'o programa terminou':
        if any('Traceback' in s['saida'] for s in v.saidas):
            return []
        t = v.am[-1]['t']
        return [problema('programa_terminou', 3, f'o programa terminou sozinho (sem erro) aos {_br(t)} s, {onde}, '
                         'sem chegar ao fim da pista', t - 2, t)]
    if 'tempo' in motivo:
        return [problema('tempo_esgotado', 1, f'o tempo acabou ({motivo}) {onde}', v.am[-1]['t'] - 2, v.am[-1]['t'])]
    return []


def _gira_no_lugar(v):
    """Lado esquerdo e direito em sentidos opostos com a linha NO MEIO do sensor (quando o programa
    quer ir reto). Girar no lugar sem ver a linha é procurar a linha, e isso é normal."""
    def oposto(d):
        # quase o mesmo valor nos dois lados, com o sinal trocado: o programa queria ir reto
        e, r = v.lado(d['cmd'], v.esq), v.lado(d['cmd'], v.dir)
        return e * r < 0 and min(abs(e), abs(r)) >= 10 and min(abs(e), abs(r)) >= 0.5 * max(abs(e), abs(r)) \
            and abs(d['v']) < 30

    def no_meio(d):
        pos = v.linha_debaixo(d)
        return pos is not None and abs(pos) <= 12

    def re_reto(d):
        # o outro lado da mesma troca: o "gira para procurar a linha" do programa vira andar reto de ré
        e, r = v.lado(d['cmd'], v.esq), v.lado(d['cmd'], v.dir)
        return e <= -10 and r <= -10 and abs(e - r) <= 0.2 * max(abs(e), abs(r)) and d['v'] < -20

    com_linha = [d for d in v.am if no_meio(d)]
    giros = [d for d in com_linha if oposto(d)]
    s = len(giros) * DT
    total = len(com_linha) * DT
    # a sequência do motor trocado: gira no lugar em cima da linha, perde a linha e, logo em seguida,
    # anda reto de ré (o "girar para procurar" do programa). Ré depois de andar para a frente é manobra.
    s_re, t_giro, ini = 0.0, -9.0, None
    for d in v.am:
        if no_meio(d) and oposto(d):
            t_giro = d['t']
        if re_reto(d):
            if ini is None:
                ini = d['t'] if d['t'] - t_giro <= 0.5 else -1
        elif ini is not None:
            if ini >= 0:
                s_re += d['t'] - ini
            ini = None
    if not ((s >= 3 and s >= 0.5 * total) or (giros and s_re >= 1.0)):
        return []
    d0 = giros[0]
    sinal = 'esquerdo para a frente e direito para trás' if v.lado(d0['cmd'], v.esq) > 0 else \
        'esquerdo para trás e direito para a frente'
    exemplo = f'{_br(v.lado(d0["cmd"], v.esq), 0)} e {_br(v.lado(d0["cmd"], v.dir), 0)}'
    return [problema('gira_no_lugar', 3,
                     f'com a linha no meio do sensor (onde era para ir reto), os motores giraram em sentidos opostos '
                     f'durante {_br(s)} s ({_br(100 * s / total, 0)}% do tempo em cima da linha; {sinal}, ex.: {exemplo} '
                     f'aos {_br(d0["t"])} s) e o robô girou no lugar'
                     + (f'; e quando o programa mandou girar (procurando a linha), o robô andou reto de ré por {_br(s_re)} s'
                        if s_re >= 1.0 else '') +
                     '. Se o programa mandou os dois para a frente, um dos motores está com a direção trocada',
                     d0['t'], d0['t'] + 2, segundos=round(s, 1), re_s=round(s_re, 1))]


def _correcao(v):
    """Com a linha visível fora do centro: o robô vira para ela ou para longe dela?"""
    perto = longe = 0
    ex = None
    for d in v.am:
        pos = v.linha_debaixo(d)
        if pos is None or abs(pos) < 8 or abs(d['w']) < 15 or d['v'] < 20:
            continue
        if (pos > 0) == (d['w'] > 0):
            perto += 1
        else:
            longe += 1
            ex = ex or d
    if longe < 10 or longe < 1.5 * perto:
        return []
    lado = 'à esquerda' if v.linha_debaixo(ex) > 0 else 'à direita'
    vira = 'para a direita' if ex['w'] < 0 else 'para a esquerda'
    return [problema('correcao_ao_contrario', 3,
                     f'quando a linha sai do centro do sensor, o robô vira para o lado contrário dela: em {longe} '
                     f'momentos ele se afastou da linha e em {perto} se aproximou (ex.: aos {_br(ex["t"])} s a linha '
                     f'estava {lado} e ele virou {vira}). Algum sinal está trocado entre a leitura do sensor e os '
                     f'motores: no cálculo da posição da linha, na correção ou em qual roda recebe o quê '
                     f'(o resumo não sabe qual dos três; o código diz)',
                     ex['t'] - 0.5, ex['t'] + 1, afastou=longe, aproximou=perto)]


def _comando_constante(v):
    """Motores andando sempre com o mesmo comando, enquanto a linha muda de lugar debaixo do sensor."""
    # pares de amostras seguidas, com o robô andando, em que a linha mudou de lugar debaixo do sensor:
    # num programa que usa o sensor, o comando muda junto; aqui ele fica igual
    mudou = igual = 0
    ex = None
    am = v.am
    for a, b in zip(am, am[1:]):
        if abs(a['v']) < 10 or abs(b['v']) < 10 or not any(c for c in b['cmd'] if c):
            continue
        pa, pb = v.linha_debaixo(a), v.linha_debaixo(b)
        if not ((pa is None) != (pb is None) or (pa is not None and abs(pa - pb) > 5)):
            continue
        mudou += 1
        da = v.lado(a['cmd'], v.esq) - v.lado(a['cmd'], v.dir)
        db = v.lado(b['cmd'], v.esq) - v.lado(b['cmd'], v.dir)
        if abs(da - db) < 0.5:
            igual += 1
            ex = ex or b
    if mudou < 10 or igual < 0.85 * mudou:
        return []
    return [problema('sensor_parado', 3,
                     f'a linha mudou de lugar debaixo do sensor {mudou} vezes com o robô andando e, em {igual} delas, os '
                     f'motores continuaram com o mesmo comando (ex.: {_br(v.lado(ex["cmd"], v.esq), 0)} e '
                     f'{_br(v.lado(ex["cmd"], v.dir), 0)} aos {_br(ex["t"])} s): o programa não está usando a leitura nova '
                     'do sensor (leu uma vez só, ou a conta não usa o valor lido no laço)', ex['t'] - 1, ex['t'] + 2,
                     mudou=mudou, igual=igual)]


def _laco(v, numeros):
    n = numeros['comandos_motor_por_s']
    if n >= 10 or not any(any(c for c in d['cmd'] if c) for d in v.am):
        return []
    return [problema('laco_lento', 3,
                     f'o programa mandou só {_br(n)} comandos por segundo para os motores (um seguidor que funciona manda '
                     'uns 50): entre um comando e outro o robô anda "às cegas". Provavelmente há uma pausa (time.sleep) '
                     'grande no laço', v.am[0]['t'] + 2, v.am[0]['t'] + 4, comandos_por_s=n)]


def _perdas(v):
    """Momentos em que nenhum canal de IR estava em cima do preto (de verdade)."""
    am = v.am
    eps, ini = [], None
    for k, d in enumerate(am):
        sem = 'p' not in d.get('chao', 'p')[:v.n_ir]
        if sem and ini is None:
            ini = k
        elif not sem and ini is not None:
            eps.append((ini, k))
            ini = None
    if ini is not None:
        eps.append((ini, len(am) - 1))
    lops = v.lops()
    ps = []
    contas = {}
    for a, b in eps:
        d0, d1 = am[a], am[b]
        dur = d1['t'] - d0['t']
        lop = next((e for e in lops if d0['t'] - 0.1 <= e['t'] <= d1['t'] + 0.2), None)
        if dur < PERDA_MIN_S and not lop:
            continue
        p = v.passo(d0)
        prox = v.passos[d0['passo'] + 1] if d0['passo'] + 1 < len(v.passos) else {}
        if (p.get('itens') or {}).get('gap') or p.get('forma') == 'área de resgate':
            continue                      # no gap a linha falta de verdade (ver _itens)
        if (prox.get('itens') or {}).get('gap') and not lop:
            continue                      # a linha acaba na borda antes do gap: atravessou sem LoP
        ant = v.passos[d0['passo'] - 1] if d0['passo'] >= 1 else {}
        if not lop and any((x.get('itens') or {}).get('obstaculo') for x in (ant, p, prox)):
            continue                      # contornando o obstáculo (e voltando para a linha), sair dela é o esperado
        if not lop and (p.get('itens') or {}).get('intersecao'):
            continue                      # na interseção o robô manobra (verde): se errar, o juiz dá LoP (_itens)
        antes = [am[k] for k in range(max(0, a - 10), a)]
        pos_antes = next((v.linha_debaixo(x) for x in reversed(antes) if v.linha_debaixo(x) is not None), None)
        giro = sum(x['w'] for x in am[a:b + 1]) * DT
        andou = sum(abs(x['v']) for x in am[a:b + 1]) * DT
        if not lop and andou < 30 and abs(giro) < 20:
            continue                      # parado (na fita da chegada, por exemplo): não é perder a linha
        if p.get('chegada') and ((v.fim or {}).get('chegou') or (v.fim or {}).get('motivo') == 'passou da chegada'):
            continue                      # na chegada a linha acaba: perder a linha ali não é o problema
        vel = st.mean(x['v'] for x in antes) if antes else d0['v']
        fim = 'e voltou para a linha' if b < len(am) - 1 and not lop else ('e levou LoP' if lop else 'e não voltou')
        if pos_antes is not None and abs(pos_antes) >= 5 and abs(giro) >= 20 and (giro > 0) != (pos_antes > 0):
            cod = 'perdeu_girou_errado'
            txt = (f'aos {_br(d0["t"])} s, no {v.onde(d0)}, a linha saiu pelo lado '
                   f'{"esquerdo" if pos_antes > 0 else "direito"} do sensor e o robô girou {_br(abs(giro), 0)}° para a '
                   f'{"esquerda" if giro > 0 else "direita"} (o lado contrário), por {_br(dur)} s, {fim}')
        elif abs(giro) < 20 and sum(x['v'] for x in am[a:b + 1]) * DT > 80:      # para a frente
            cod = 'perdeu_seguiu_reto'
            txt = (f'aos {_br(d0["t"])} s, no {v.onde(d0)}, o sensor saiu da linha e o robô seguiu quase reto '
                   f'({_br(andou, 0)} mm, girou só {_br(abs(giro), 0)}°) por {_br(dur)} s, {fim}')
        else:
            cod = 'perde_linha'
            lado = '' if pos_antes is None else f' pelo lado {"esquerdo" if pos_antes > 0 else "direito"}'
            txt = (f'aos {_br(d0["t"])} s, no {v.onde(d0)}, o sensor saiu da linha{lado} vindo a {_br(vel, 0)} mm/s; '
                   f'ficou {_br(dur)} s sem ver a linha (girou {_br(abs(giro), 0)}° para a '
                   f'{"esquerda" if giro > 0 else "direita"}, andou {_br(andou, 0)} mm) {fim}')
        contas[cod] = contas.get(cod, 0) + 1
        # perder a linha um instante e voltar sozinho é detalhe; muito tempo fora (ou LoP), não
        grau = 3 if lop else (2 if dur >= 1.5 else 1)
        ps.append(problema(cod, grau, txt, d0['t'] - 1.5, d1['t'] + 0.5, ladrilho=d0['passo'] + 1,
                           forma=p.get('forma'), segundos=round(dur, 2), lop=bool(lop)))
    # muitas perdas iguais viram uma só, com a contagem (a primeira como exemplo)
    juntos = []
    for cod in contas:
        lista = [p for p in ps if p['codigo'] == cod]
        p = dict(max(lista, key=lambda q: (q['grau'], -q['trecho'][0])))
        if len(lista) > 1:
            formas = sorted({q['forma'] for q in lista if q.get('forma')})
            com_lop = sum(1 for q in lista if q['lop'])
            p['texto'] = (f'{len(lista)} vezes' + (f' (em {", ".join(formas)})' if formas else '') +
                          (f', {com_lop} com LoP' if com_lop else '') + '. Exemplo: ' + p['texto'])
        p['vezes'] = len(lista)
        if len(lista) >= 5:
            p['grau'] = max(p['grau'], 2)     # muitas vezes: atrapalha, mesmo voltando sozinho
        juntos.append(p)
    return juntos


def _itens(v):
    """LoP perto de verde, gap ou obstáculo."""
    ps = []
    for e in v.lops():
        d = v.amostra_em(e['t'] - 0.1)
        if d is None:
            continue
        janela = v.entre(e['t'] - 4, e['t'])
        idxs = {x['passo'] for x in janela}
        if idxs:
            idxs.add(max(idxs) + 1)       # o ladrilho para onde ele ia (perdeu a linha antes de entrar)
        perto = [v.passos[i] for i in sorted(idxs) if 0 <= i < len(v.passos)]
        motivo = e['evento'].split(':', 1)[-1].strip()
        verde = next((p for p in perto if p.get('verde')), None) or \
            next((p for p in perto if (p.get('itens') or {}).get('intersecao') and 'não é a próxima' in motivo), None)
        gap = next((p for p in perto if (p.get('itens') or {}).get('gap')), None)
        obst = next((p for p in perto if (p.get('itens') or {}).get('obstaculo')), None)
        if obst is not None:
            vl = [x['vl53'].get('frente') for x in janela if x.get('vl53') and x['vl53'].get('frente') is not None]
            parado = sum(1 for x in janela if abs(x['v']) < 10 and any(c and abs(c) > 15 for c in x['cmd'])) * DT
            usa = (f'o VL53 da frente chegou a {min(vl)} mm' if vl else 'o programa não leu o sensor de distância da frente')
            ps.append(problema('obstaculo', 3, f'no obstáculo (ladrilho {obst["i"] + 1}) levou LoP aos {_br(e["t"])} s '
                               f'({motivo}); {usa}' + (f'; ficou {_br(parado)} s empurrando sem andar' if parado >= 0.5 else ''),
                               e['t'] - 4, e['t'], ladrilho=obst['i'] + 1))
        elif gap is not None:
            giro = sum(x['w'] for x in janela) * DT
            ps.append(problema('gap', 3, f'no gap (ladrilho {gap["i"] + 1}) levou LoP aos {_br(e["t"])} s ({motivo}); '
                               f'sem a linha, o robô girou {_br(abs(giro), 0)}° procurando em vez de seguir reto até '
                               'o outro lado', e['t'] - 4, e['t'], ladrilho=gap['i'] + 1))
        elif verde is not None:
            # o verde pode ter ficado para trás muito antes do LoP (o robô vira errado e vaga): procura
            # desde a tentativa anterior (o LoP anterior ou o começo), no ladrilho da interseção
            antes = max([x['t'] for x in v.lops() if x['t'] < e['t'] - 0.01] + [0.0])
            tcs_v = lambda x: x.get('chao', '')[v.n_ir:]
            viu = [x for x in v.entre(antes, e['t']) if 'v' in tcs_v(x) and x['passo'] in (verde['i'], verde['i'] - 1)]
            com = 'com verde ' if verde.get('verde') else ''
            if viu:
                lados = {'esquerda' if k == 0 else 'direita' if k == len(tcs_v(x)) - 1 else 'meio'
                         for x in viu for k, c in enumerate(tcs_v(x)) if c == 'v'}
                lado_v = ' e '.join(sorted(lados - {'meio'})) or 'meio'
                t0 = viu[0]['t']
                giro = sum(x['w'] for x in v.entre(t0, t0 + 3)) * DT
                visto = (f'o TCS da {lado_v} passou por cima do verde aos {_br(t0)} s (verde à {lado_v}); nos 3 s '
                         f'seguintes o robô girou {_br(abs(giro), 0)}° para a {"esquerda" if giro > 0 else "direita"}')
                t1 = t0 - 1
            else:
                giro = sum(x['w'] for x in janela) * DT
                visto = (f'nenhum TCS passou por cima do verde; nos 4 s antes o robô girou {_br(abs(giro), 0)}° '
                         f'para a {"esquerda" if giro > 0 else "direita"}')
                t1 = e['t'] - 6
            ps.append(problema('intersecao_verde', 3, f'na interseção {com}(ladrilho {verde["i"] + 1}) levou LoP '
                               f'aos {_br(e["t"])} s ({motivo}); {visto}', t1, min(e['t'], t1 + 8),
                               ladrilho=verde['i'] + 1))
    # obstáculo empurrado (no simulador ele é solto: o robô pode tirá-lo do caminho e passar)
    cab_obs = v.cab.get('obstaculos') or []
    if cab_obs and not any(p['codigo'] == 'obstaculo' for p in ps):
        for k, o in enumerate(cab_obs):
            maior, quando = 0.0, None
            for d in v.am:
                if d.get('obst') and k < len(d['obst']):
                    x, y = d['obst'][k]
                    dd = ((x - o['x']) ** 2 + (y - o['y']) ** 2) ** 0.5
                    if dd > 30 and quando is None:
                        quando = d
                    maior = max(maior, dd)
            if quando is None:
                continue
            vl = [x['vl53'].get('frente') for x in v.entre(quando['t'] - 3, quando['t'])
                  if x.get('vl53') and x['vl53'].get('frente') is not None]
            usa = (f'o VL53 da frente chegou a {min(vl)} mm antes' if vl
                   else 'o programa não leu o sensor de distância da frente')
            lad = f'do ladrilho {o["passo"] + 1}' if o.get('passo') is not None else ''
            ps.append(problema('obstaculo', 2, f'empurrou o obstáculo {lad} em vez de desviar: aos {_br(quando["t"])} s '
                               f'ele começou a sair do lugar e acabou {_br(maior, 0)} mm longe de onde estava ({usa}). '
                               'Num obstáculo pesado ou preso o robô ficaria parado ali', quando['t'] - 2, quando['t'] + 1,
                               ladrilho=(o.get('passo') or 0) + 1, empurrou_mm=round(maior)))
    # o mesmo item várias vezes: um problema só
    juntos = {}
    for p in ps:
        k = (p['codigo'], p.get('ladrilho'))
        if k in juntos:
            juntos[k]['vezes'] = juntos[k].get('vezes', 1) + 1
        else:
            juntos[k] = p
    for p in juntos.values():
        if p.get('vezes', 1) > 1:
            p['texto'] += f' (aconteceu {p["vezes"]} vezes)'
    return list(juntos.values())


def _sem_avanco(v, ja):
    """Muito tempo no mesmo passo do caminho, sem LoP (indo e voltando, ou girando sem sair dali)."""
    am = v.am
    longo, ini = None, 0
    for k in range(1, len(am) + 1):
        if k == len(am) or am[k]['passo'] != am[ini]['passo']:
            if am[k - 1]['t'] - am[ini]['t'] >= 30 and (longo is None or
                                                       am[k - 1]['t'] - am[ini]['t'] > longo[1]['t'] - longo[0]['t']):
                longo = (am[ini], am[k - 1], ini, k)
            ini = k
    if longo is None:
        return []
    d0, d1, a, b = longo
    p = v.passo(d0)
    if p.get('chegada') or p.get('forma') == 'área de resgate':
        return []
    prox = v.passos[d0['passo'] + 1] if d0['passo'] + 1 < len(v.passos) else {}
    frente = sum(x['v'] for x in am[a:b] if x['v'] > 0) * DT
    re = -sum(x['v'] for x in am[a:b] if x['v'] < 0) * DT
    giro = sum(abs(x['w']) for x in am[a:b]) * DT
    dur = d1['t'] - d0['t']
    mov = f'andou {_br(frente, 0)} mm para a frente e {_br(re, 0)} mm de ré e girou {_br(giro, 0)}° ao todo'
    itens = {**(prox.get('itens') or {}), **(p.get('itens') or {})}
    lad = d0['passo'] + 1
    if itens.get('gap'):
        cod, txt = 'gap', (f'ficou {_br(dur, 0)} s no ladrilho {lad}, antes do outro lado do gap, sem conseguir '
                           f'atravessar ({mov}): parece ir até o gap, desistir e voltar')
    elif itens.get('obstaculo'):
        cod, txt = 'obstaculo', f'ficou {_br(dur, 0)} s no ladrilho {lad}, no obstáculo, sem conseguir passar ({mov})'
    elif itens.get('intersecao'):
        cod, txt = 'intersecao_verde', f'ficou {_br(dur, 0)} s na interseção do ladrilho {lad} sem seguir em frente ({mov})'
    else:
        cod, txt = 'sem_avanco', f'ficou {_br(dur, 0)} s no ladrilho {lad} ({p.get("forma", "?")}) sem avançar ({mov})'
    if any(q['codigo'] == cod for q in ja):
        return []
    # sem um item que explique, é consequência de outro problema (perder a linha, girar errado...)
    return [problema(cod, 2 if cod == 'sem_avanco' else 3, txt, d0['t'], d0['t'] + 10, ladrilho=lad, segundos=round(dur))]


def _ziguezague(v, numeros):
    """Trocas de lado do giro nas retas, com a linha debaixo do sensor."""
    retas = [d for d in v.am if v.passo(d).get('forma') == 'reta' and d['v'] > 20 and v.linha_debaixo(d) is not None]
    if len(retas) < 40:
        return []
    trocas, s0 = 0, 0
    for d in retas:
        s = 1 if d['w'] > 15 else (-1 if d['w'] < -15 else 0)
        if s and s0 and s != s0:
            trocas += 1
        if s:
            s0 = s
    seg = len(retas) * DT
    por_s = trocas / seg
    w_med = st.mean(abs(d['w']) for d in retas)
    if por_s < 0.8 or w_med < 20:
        return []
    ex = max(retas, key=lambda d: abs(d['w']))
    return [problema('ziguezague', 2,
                     f'nas retas o robô troca de lado {_br(por_s)} vezes por segundo (giro médio de {_br(w_med, 0)}°/s; '
                     'um seguidor afinado fica perto de 0 trocas e ~12°/s): corrige demais e passa do ponto',
                     ex['t'] - 1, ex['t'] + 1, trocas_por_s=round(por_s, 2), giro_medio=round(w_med))]


def _chegada(v):
    if (v.fim or {}).get('chegou'):
        return []
    viu = [d for d in v.am if d.get('chao', '')[v.n_ir:].count('r') >= 2]
    if not viu:
        return []
    d0 = viu[0]
    depois = [d for d in v.am if d0['t'] < d['t'] <= d0['t'] + 5]
    andou = sum(abs(d['v']) for d in depois) * DT
    girou = sum(abs(d['w']) for d in depois) * DT
    if andou < 100 and girou < 45:
        return []
    return [problema('passou_da_chegada', 2, f'os sensores de cor passaram pela fita vermelha da chegada aos '
                     f'{_br(d0["t"])} s e o robô não parou: nos 5 s seguintes andou {_br(andou, 0)} mm e girou '
                     f'{_br(girou, 0)}° (a regra pede ficar parado mais de 5 s na chegada)', d0['t'] - 1, d0['t'] + 2)]


def _lento(v, numeros):
    vr = numeros.get('v_retas_mm_s')
    f = v.fim or {}
    if vr is None or vr >= 50:
        return []
    if f.get('chegou') and f.get('tempo', 0) < 200:
        return []
    return [problema('lento', 2, f'o robô anda a {vr} mm/s nas retas (o seguidor do curso anda a ~113): '
                     f'em {_br(v.am[-1]["t"], 0)} s chegou só ao ladrilho {f.get("passo", 0) + 1}', 5, 7, v_retas=vr)]


def _parado(v):
    am = v.am
    fim = v.passos[-1].get('chegada') if v.passos else False
    ini, longos = None, []
    for k, d in enumerate(am):
        p = abs(d['v']) < 5 and abs(d['w']) < 5 and d['t'] > 2
        if p and ini is None:
            ini = k
        elif not p and ini is not None:
            longos.append((ini, k))
            ini = None
    if ini is not None:
        longos.append((ini, len(am) - 1))
    for a, b in longos:
        if am[b]['t'] - am[a]['t'] < 3:
            continue
        if fim and am[a]['passo'] == len(v.passos) - 1:
            continue                      # parado na chegada: é o certo
        return [problema('parado', 1, f'ficou parado {_br(am[b]["t"] - am[a]["t"])} s aos {_br(am[a]["t"])} s, '
                         f'no {v.onde(am[a])}', am[a]['t'] - 1, am[a]['t'] + 2)]
    return []


# ---------------------------------------------------------------------- várias rodadas
def resume(arqs):
    """{'rodadas': [...], 'problemas': [...]} juntando as rodadas (o mesmo código = um problema)."""
    voltas = [Volta(a) for a in arqs]
    rodadas, todos = [], {}
    for v in voltas:
        ps, num = analisa(v)
        f = v.fim or {}
        rodadas.append({'semente': v.semente, 'total': f.get('total'), 'lop': f.get('lop'), 'chegou': f.get('chegou'),
                        'tempo': f.get('tempo'), 'fim': f.get('motivo'), 'numeros': num,
                        'problemas': [p['codigo'] for p in ps]})
        for p in ps:
            q = todos.setdefault(p['codigo'], dict(p, rodadas=[], semente=v.semente))
            q['rodadas'].append(v.semente)
            q['grau'] = max(q['grau'], p['grau'])
    ps = sorted(todos.values(), key=lambda p: (-p['grau'], -len(p['rodadas']), ORDEM.index(p['codigo'])))
    return {'mapa': voltas[0].cab.get('mapa') if voltas else None, 'robo': voltas[0].cab.get('robo') if voltas else None,
            'rodadas': rodadas, 'problemas': ps}


def texto(r):
    n = len(r['rodadas'])
    out = [f'Mapa {r["mapa"]}, robô {r["robo"]}, {n} rodada{"s" if n > 1 else ""}:']
    for rd in r['rodadas']:
        num = rd['numeros']
        out.append(f'  semente {rd["semente"]}: {rd["total"]} pontos, {rd["lop"]} LoP, '
                   f'{"chegou" if rd["chegou"] else "não chegou"}, {_br(rd["tempo"] or 0)} s ({rd["fim"]}); '
                   f'{num.get("v_retas_mm_s")} mm/s nas retas, {_br(num.get("comandos_motor_por_s", 0))} comandos de motor/s')
    if not r['problemas']:
        out.append('Nenhum problema encontrado.')
    else:
        out.append('Problemas (do mais importante para o menos):')
        for k, p in enumerate(r['problemas'], 1):
            quantas = f'{len(p["rodadas"])} de {n} rodadas'
            out.append(f'{k}. [{p["codigo"]}, grau {p["grau"]}, {quantas}] {CODIGOS[p["codigo"]]}: {p["texto"]}'
                       + (f' (semente {p["semente"]}, trecho {_br(p["trecho"][0])}-{_br(p["trecho"][1])} s)' if p.get('trecho') else ''))
    return '\n'.join(out)


def trecho(arq, t1, t2, passo=0.1):
    """As amostras entre t1 e t2 (de passo em passo), para o tutor ver de perto."""
    v = Volta(arq)
    out = ['   t (s)  ladrilho          chão*   IR lido          motores esq/dir  vel. (mm/s)  giro (°/s)']
    prox = t1
    for d in v.entre(t1, t2):
        if d['t'] + 1e-9 < prox:
            continue
        prox = d['t'] + passo
        p = v.passo(d)
        out.append(f'{_br(d["t"], 2):>8}  {d["passo"] + 1:>3} {p.get("forma", "?")[:12]:12}  {d.get("chao", ""):7} '
                   f'{str(d.get("ir", "")):16} {_br(v.lado(d["cmd"], v.esq), 0):>5} {_br(v.lado(d["cmd"], v.dir), 0):>5}'
                   f'      {_br(d["v"], 0):>6}      {_br(d["w"], 0):>6}')
    for s in v.saidas:
        if t1 <= s['t'] <= t2:
            out.append(f'{_br(s["t"], 2):>8}  (print) {s["saida"]}')
    out.append('* chão de verdade debaixo dos canais de IR e dos TCS, da esquerda para a direita: '
               'b branco, p preto, v verde, r vermelho, s prata')
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('registros', nargs='+')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--trecho', nargs=2, type=float, metavar=('T1', 'T2'))
    a = ap.parse_args()
    arqs = []
    for x in a.registros:
        arqs += sorted(glob.glob(os.path.join(x, '*.jsonl'))) if os.path.isdir(x) else [x]
    if not arqs:
        print('nenhum registro (.jsonl)')
        return 2
    if a.trecho:
        print(trecho(arqs[0], *a.trecho))
        return 0
    r = resume(arqs)
    if a.json:
        json.dump(r, sys.stdout, ensure_ascii=False, indent=1)
        print()
    else:
        print(texto(r))
    return 0


if __name__ == '__main__':
    sys.exit(main())
