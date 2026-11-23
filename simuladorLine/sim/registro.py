"""Registro da volta (18/11/2026, para o robô tutor: tutor/PLANO.md).

`simulador.py --sem-janela --registro arq.jsonl` grava, a cada 50 ms de tempo simulado e só com a
rodada valendo, o que o robô fez e o que o programa leu e mandou. Quem lê é o tutor/resumo.py.

Só LÊ o estado do simulador: não sorteia nada (o ruído dos sensores tem geradores próprios e uma
leitura a mais mudaria a rodada) e não muda nada. Mesma semente = mesmo registro.

Formato (JSON por linha):
  1ª linha  {"cabecalho": {...}}: mapa, robô, sensor, motores e os passos do caminho
            (forma reta/curva/área, itens, checkpoint, chegada)
  amostras  {"t", "x", "y", "a" (graus), "v" (mm/s, + = para a frente), "w" (graus/s, + = girando
             para a esquerda), "passo", "fora", "chao", "ir", "rgbc", "giro", "vl53",
             "cmd", "vel", "leu"}
            chao = material de verdade debaixo de cada canal de IR e de cada TCS (b, p, v, r, s,
                   m = madeira, f = fora), sem ruído; ir/rgbc = o último valor que o PROGRAMA leu
            cmd = o que o programa mandou em cada motor, em % da velocidade máxima, com positivo
                  = para a frente (None = desligado); vel = o que o motor fez, na mesma escala;
            leu = leituras pedidas nos últimos 50 ms (cor = sensor de linha, giro, vl53, brick...);
            obst = posição (mm) de cada obstáculo solto, na ordem do "obstaculos" do cabeçalho
  {"saida": texto, "t": ...}   o que o programa imprimiu
  {"evento": texto, "t": ..., "pontos": ...}   eventos do juiz (no fim)
  {"fim": {"motivo", "total", "lop", "chegou", "tempo", "passo", "passos"}}   última linha
"""

import json
import math

import numpy as np

from . import ladrilhos as LT
from .fisica import FREQ_PID

LETRA = {LT.M_BRANCO: 'b', LT.M_PRETO: 'p', LT.M_VERDE: 'v', LT.M_VERMELHO: 'r', LT.M_PRATA: 's',
         LT.M_MADEIRA: 'm', LT.M_FORA: 'f'}


class Registro:
    PERIODO = 0.05

    def __init__(self, sim):
        self.sim = sim
        self.linhas = []
        self.prox = 0.0
        self.lidos = {}            # último valor que o programa leu de cada coisa
        self.contas = {}           # leituras desde a última amostra
        self.cabecalho = None

    # ------------------------------------------------------------------ chamados pelo simulador
    def inicio(self):
        """Rodada começando (com a trava do mundo)."""
        self.linhas = []
        self.prox = 0.0
        self.lidos = {}
        self.contas = {}
        self.cabecalho = self._cabecalho()

    def pedido(self, op, r, resp):
        """O programa pediu algo ao simulador (servidor.trata, com a trava do mundo)."""
        if not isinstance(resp, dict) or 'erro' in resp:
            return
        nome = {'mariola_quadro': 'brick', 'placa_quadro': 'placa', 'gpio_le': 'pino'}.get(op, op)
        if op in ('relogio', 'ola', 'sinc_inicio', 'avanca', 'entrada', 'entrada_estado', 'debug'):
            return
        self.contas[nome] = self.contas.get(nome, 0) + 1
        if op == 'giro':
            self.lidos['giro'] = resp.get('v')
        elif op == 'vl53':
            w = self.sim.mundo
            idx = r.get('idx')
            if idx is None:
                idx = w.vl53_por_canal(r['canal'])
            vl = w.cfg.get('vl53') or []
            nome = vl[idx].get('nome', str(idx)) if idx is not None and idx < len(vl) else str(idx)
            self.lidos.setdefault('vl53', {})[nome] = resp.get('d')

    def amostra(self):
        """Depois de cada passo da física (com a trava do mundo)."""
        j = self.sim.juiz
        w = self.sim.mundo
        if not j.ativo or j.fim:
            return
        t = w.t - j.t0
        if t + 1e-9 < self.prox:
            return
        self.prox = math.floor(t / self.PERIODO + 1e-6) * self.PERIODO + self.PERIODO
        b = w.corpo
        # com sinal (o Mundo.velocidade() devolve os módulos): v > 0 = para a frente, w > 0 = para a esquerda
        v = b.velocity.x * math.cos(b.angle) + b.velocity.y * math.sin(b.angle)
        om = b.angular_velocity
        d = {'t': round(t, 3), 'x': round(b.position.x, 1), 'y': round(b.position.y, 1),
             'a': round(math.degrees(b.angle), 1), 'v': round(v, 1), 'w': round(math.degrees(om), 1),
             'passo': j.idx, 'fora': j.errado_desde is not None}
        if w.sensor is not None:
            locais = w.sensor.canais_ir() + w.sensor.tcs
            c, s = math.cos(b.angle), math.sin(b.angle)
            px, py = b.position.x, b.position.y
            pts = np.array([(px + lx * c - ly * s, py + lx * s + ly * c) for lx, ly in locais])
            d['chao'] = ''.join(LETRA.get(int(m), '?') for m in w.materiais(pts))
            if w.cor_cache is not None:
                n = len(w.sensor.canais_ir())
                d['ir'] = list(w.cor_cache[:n])
                d['rgbc'] = list(w.cor_cache[n:n + 4 * len(w.sensor.tcs)])
        if 'giro' in self.lidos:
            d['giro'] = self.lidos['giro']
        if 'vl53' in self.lidos:
            d['vl53'] = dict(self.lidos['vl53'])
        cmd, vel = [], []
        for m in w.motores:
            if m.dc:
                f, r_, _, _ = m.frac
                cmd.append(round((f - r_) * 100))
                vel.append(round(m.vel / max(1e-9, m.vlivre) * 100) if m.vlivre else None)
            else:
                # na escala do velocidade_motores(): 100 = a velocidade que a calibração dá a 100
                escala = max(1e-9, m.cal[0] * FREQ_PID)
                if m.desligado:
                    cmd.append(None)
                elif m.modo == 'pwm':
                    cmd.append(round(m.pwm * m.sentido))
                else:
                    cmd.append(round(m.setpoint * 100 / max(1, m.cal[0]) * m.sentido))
                vel.append(round(m.vel / escala * 100 * m.sentido))
        d['cmd'] = cmd
        d['vel'] = vel
        obs = [o for o in getattr(w, 'obstaculos', []) if not o['ob'].get('fixo')]
        if obs:
            d['obst'] = [[round(o['corpo'].position.x), round(o['corpo'].position.y)] for o in obs]
        if self.contas:
            d['leu'] = self.contas
            self.contas = {}
        self.linhas.append(d)

    def saida(self, texto):
        """Uma linha que o programa imprimiu (thread da saída do programa)."""
        j = self.sim.juiz
        t = (self.sim.mundo.t - j.t0) if j.ativo else 0.0
        self.linhas.append({'saida': texto[:300], 't': round(t, 3)})

    def grava(self, arq, fim=None):
        """fim: placar e motivo do fim da rodada (última linha, {"fim": {...}})."""
        j = self.sim.juiz
        with open(arq, 'w', encoding='utf-8') as f:
            f.write(json.dumps({'cabecalho': self.cabecalho or self._cabecalho()}, ensure_ascii=False) + '\n')
            for d in list(self.linhas):
                f.write(json.dumps(d, ensure_ascii=False) + '\n')
            for (t, txt, p) in j.eventos:
                f.write(json.dumps({'evento': txt, 't': round(t, 3), 'pontos': p}, ensure_ascii=False) + '\n')
            if fim is not None:
                f.write(json.dumps({'fim': fim}, ensure_ascii=False) + '\n')

    # ------------------------------------------------------------------ cabeçalho
    def _cabecalho(self):
        w = self.sim.mundo
        j = self.sim.juiz
        m = w.mapa
        passos = []
        for i, p in enumerate(j.passos):
            t = m.ladrilhos.get(p['k'])
            e, s = p.get('entrada'), p.get('saida')
            if p.get('zona'):
                forma = 'área de resgate'
            elif s is None:
                forma = 'fim'
            elif e is None:
                forma = 'início'
            elif LT.OPOSTA.get(e) == s:
                forma = 'reta'
            else:
                forma = 'curva'
            item = {'i': i, 'forma': forma}
            if t is not None:
                info = m.cat.info(t['tipo'])
                itens = m.itens(t)
                if itens:
                    item['itens'] = itens
                try:                     # o catálogo não guarda o tem_verde: olha o desenho do ladrilho
                    if info.get('intersecoes') and (m.cat.material(t['tipo']) == LT.M_VERDE).any():
                        item['verde'] = True
                except Exception:
                    pass
                if m.eh_chegada(t):
                    item['chegada'] = True
                if t.get('z'):
                    item['andar'] = t['z']
            if i in j.cps:
                item['checkpoint'] = True
            passos.append(item)
        cab = {'mapa': m.nome, 'robo': w.cfg.get('nome', ''), 'periodo_s': self.PERIODO,
               'motores': [{'nome': mo.nome, 'y': mo.y} for mo in w.motores], 'passos': passos}
        if w.sensor is not None:
            cab['sensor'] = {'canais_ir_y': [round(y, 1) for _, y in w.sensor.canais_ir()],
                             'x_ir': round(w.sensor.ir[0][0], 1),
                             'tcs_y': [y for _, y in w.sensor.tcs], 'x_tcs': w.sensor.tcs[0][0],
                             'ordem_chao': 'canais de IR e depois os TCS, da esquerda para a direita'}
        obs = [o for o in getattr(w, 'obstaculos', []) if not o['ob'].get('fixo')]
        if obs:
            idx = {p['k']: i for i, p in enumerate(j.passos)}
            cab['obstaculos'] = [{'passo': idx.get(o['lad']), 'x': round(o['corpo'].position.x),
                                  'y': round(o['corpo'].position.y)} for o in obs]
        vl = w.cfg.get('vl53') or []
        if vl:
            cab['vl53'] = [{k: s.get(k) for k in ('nome', 'x', 'y', 'angulo', 'mux') if k in s} for s in vl]
        return cab
