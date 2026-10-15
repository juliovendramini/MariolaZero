"""Juiz automático segundo a regra RoboCupJunior Rescue Maze 2026 (seções 5.4 a 5.7)."""

import math

from . import mapa as M
from .fisica import dist_ponto_poligono

TEMPO_RODADA = 480.0
RAIO_VITIMA = 150.0


class Juiz:
    def __init__(self, mundo):
        self.mundo = mundo
        self.on_lop = None      # callback(motivo)
        self.on_fim = None      # callback(motivo)
        self.reset()

    # ------------------------------------------------------------------ estado
    def reset(self):
        m = self.mundo.mapa
        self.ativo = False
        self.t0 = 0.0
        self.fim = None
        self.eventos = []
        self.lop = 0
        self.erros = 0
        self.atual = tuple(m.inicio)
        self.entrada = {}
        self.saiu_inicio = False
        self.checkpoints = set()
        self.ultimo_cp = tuple(m.inicio)
        self.dir_cp = M.ANGULO_DIR[m.inicio_dir]
        self.visitas_azul = {}
        self.azul_ok = set()
        self.azul_pendente = None
        self.azul_parado = 0.0
        self.lombadas = set()
        self.escadas = set()
        self.identificadas = {}     # idx -> t
        self.kits_vitima = {}       # idx -> quantidade válida entregue
        self.kits_vistos = 0
        self.lineares = m.ladrilhos_lineares()
        self.vitimas_lop_saida = False
        self.saida = False
        # detector de piscadas
        self.led_ant = False
        self.t_borda = None
        self.sessao = None          # dict(inicio, meio_periodo, creditada)
        self.parado_desde = None

    def iniciar(self):
        self.reset()
        self.ativo = True
        self.t0 = self.mundo.t
        self.log('início da rodada')

    @property
    def tempo(self):
        if not self.ativo and self.fim is None:
            return 0.0
        return min(TEMPO_RODADA, self.mundo.t - self.t0) if self.fim is None else self.t_fim

    def log(self, texto, pontos=0):
        t = self.mundo.t - self.t0 if self.ativo else 0.0
        self.eventos.append((t, texto, pontos))

    def encerrar(self, motivo):
        if self.fim is None:
            self.fim = motivo
            self.t_fim = min(TEMPO_RODADA, self.mundo.t - self.t0)
            self.log(f'fim da rodada: {motivo}')
            if self.on_fim:
                self.on_fim(motivo)

    def falta_progresso(self, motivo):
        if not self.ativo or self.fim:
            return
        self.lop += 1
        self.log(f'LoP: {motivo}', -15)
        self.azul_pendente = None
        self.sessao = None
        if self.on_lop:
            self.on_lop(motivo)

    def reposicionado(self):
        """Chamado depois que o robô foi colocado no último checkpoint."""
        self.atual = self.ultimo_cp
        self.azul_pendente = None
        self.sessao = None

    # ------------------------------------------------------------------ atualização
    def atualiza(self, dt):
        if not self.ativo or self.fim:
            return
        w = self.mundo
        m = w.mapa
        if w.t - self.t0 >= TEMPO_RODADA:
            self.encerrar('tempo esgotado (8 min)')
            return
        x, y, ang = w.pose()
        v, om = w.velocidade()
        parado = v < 6.0 and om < 0.06
        if parado:
            if self.parado_desde is None:
                self.parado_desde = w.t
        else:
            self.parado_desde = None

        lc = m.ladrilho_em(x, y)
        if lc is not None and lc != self.atual:
            self._mudou_ladrilho(self.atual, lc, ang)
            if self.fim or not self.ativo:
                return

        # ladrilho azul: 5 s consecutivos parado
        if self.azul_pendente is not None and self.azul_pendente == self.atual:
            if parado:
                self.azul_parado += dt
                if self.azul_parado >= 5.0 and self.atual not in self.azul_ok:
                    self.azul_ok.add(self.atual)
                    self.log(f'parada de 5 s no azul {self.atual} ok')
                if self.azul_parado >= 5.0:
                    self.azul_pendente = None
            else:
                self.azul_parado = 0.0

        self._piscadas(parado)
        self._kits()

    def _mudou_ladrilho(self, ant, novo, ang):
        m = self.mundo.mapa
        if self.azul_pendente is not None and self.azul_pendente != novo:
            self.atual = novo
            self.falta_progresso(f'saiu do azul {self.azul_pendente} sem parar 5 s')
            return
        # travessias de lombada / escada
        for lc, tipo in ((ant, 'lombada'), (ant, 'escada')):
            if m.terreno(*lc) == tipo:
                ent = self.entrada.get(lc)
                if ent is not None and ent != novo:
                    if tipo == 'lombada' and lc not in self.lombadas:
                        self.lombadas.add(lc)
                        self.log(f'lombada {lc}', 5)
                    if tipo == 'escada' and lc not in self.escadas:
                        dl = abs(ent[0] - novo[0]) + abs(ent[1] - novo[1])
                        if dl == 2:
                            self.escadas.add(lc)
                            self.log(f'escada {lc}', 10)
        self.entrada[novo] = ant
        self.atual = novo
        if novo != tuple(m.inicio):
            self.saiu_inicio = True
        piso = m.piso(*novo)
        if piso == 'preto':
            self.falta_progresso(f'visitou ladrilho preto {novo}')
            return
        if piso == 'prata':
            self.ultimo_cp = novo
            self.dir_cp = round(ang / (math.pi / 2)) * (math.pi / 2)
            if novo not in self.checkpoints:
                self.checkpoints.add(novo)
                self.log(f'checkpoint {novo}', 10)
        if piso == 'azul':
            n = self.visitas_azul.get(novo, 0) + 1
            self.visitas_azul[novo] = n
            self.log(f'azul {novo} visita {n}', 30 if n == 1 else -10 if n <= 3 else 0)
            self.azul_pendente = novo
            self.azul_parado = 0.0

    # ------------------------------------------------------------------ LED
    def _piscadas(self, parado):
        w = self.mundo
        aceso = w.led_aceso()
        if not parado:
            self.sessao = None
        if aceso != self.led_ant:
            t = w.t
            meio = None if self.t_borda is None else t - self.t_borda
            self.t_borda = t
            self.led_ant = aceso
            if parado:
                s = self.sessao
                if (s is not None and s['meio'] is not None and meio is not None
                        and abs(meio - s['meio']) <= 0.3 * s['meio']):
                    pass
                elif s is not None and s['meio'] is None and meio is not None and not aceso:
                    # primeira metade (aceso) define o período
                    if 0.35 <= meio <= 0.65:
                        s['meio'] = 0.5
                    elif 0.75 <= meio <= 1.25:
                        s['meio'] = 1.0
                    else:
                        self.sessao = None
                elif aceso:
                    self.sessao = {'inicio': t, 'meio': None, 'creditada': False}
                else:
                    self.sessao = None
        s = self.sessao
        if s is None or s['meio'] is None or s['creditada']:
            return
        # a piscada para de contar se o LED ficar muito tempo sem trocar
        if self.t_borda is not None and w.t - self.t_borda > 1.5 * s['meio'] + 0.2:
            self.sessao = None
            return
        dur = w.t - s['inicio']
        if s['meio'] == 0.5 and dur >= 5.0:
            s['creditada'] = True
            self._identificacao()
        elif s['meio'] == 1.0 and dur >= 10.0:
            s['creditada'] = True
            if self.atual == tuple(w.mapa.inicio) and self.saiu_inicio:
                self.saida = True
                self.log('sinal de saída no ladrilho inicial', 0)
                self.encerrar('robô voltou ao início (bônus de saída)')
            else:
                self.log('piscada de 1 s fora do início (ignorada)')

    def _identificacao(self):
        w = self.mundo
        m = w.mapa
        contorno = [(p.x, p.y) for p in w.contorno_robo()]
        melhor = None
        falsa_perto = False
        for idx, v in enumerate(m.vitimas):
            (vx, vy), _ = m.ponto_vitima(v)
            d = dist_ponto_poligono((vx, vy), contorno)
            if d > RAIO_VITIMA:
                continue
            if M.status_vitima(v) is None:
                falsa_perto = True
                continue
            if idx in self.identificadas:
                continue
            if melhor is None or d < melhor[0]:
                melhor = (d, idx, v)
        if melhor is None:
            ja = any(idx in self.identificadas for idx, v in enumerate(m.vitimas)
                     if dist_ponto_poligono(m.ponto_vitima(v)[0], contorno) <= RAIO_VITIMA)
            if ja and not falsa_perto:
                self.log('vítima já identificada (sem pontos)')
                return
            self.erros += 1
            self.log('identificação errada' + (' (vítima falsa)' if falsa_perto else ''), -5)
            return
        _, idx, v = melhor
        self.identificadas[idx] = w.t
        self.log(f'vítima {self._nome_vitima(v)} em ({v["linha"]},{v["coluna"]}) {v["parede"]}',
                 self._pontos_vitima(v))

    def _nome_vitima(self, v):
        if v['tipo'] == 'letra':
            return M.SIMBOLO_LETRA.get(v['letra'], v['letra'])
        return 'cognitiva-' + (M.status_vitima(v) or 'falsa')

    def _pontos_vitima(self, v):
        linear = (v['linha'], v['coluna']) in self.lineares
        if v['tipo'] == 'letra':
            return 5 if linear else 15
        return 10 if linear else 30

    # ------------------------------------------------------------------ kits
    def _kits(self):
        w = self.mundo
        m = w.mapa
        while self.kits_vistos < len(w.kits):
            k = w.kits[self.kits_vistos]
            self.kits_vistos += 1
            melhor = None
            for idx, v in enumerate(m.vitimas):
                if M.status_vitima(v) is None:
                    continue
                (vx, vy), _ = m.ponto_vitima(v)
                d = math.hypot(k['x'] - vx, k['y'] - vy)
                if d <= RAIO_VITIMA and (melhor is None or d < melhor[0]):
                    melhor = (d, idx, v)
            if melhor is None:
                self.log('kit longe de qualquer vítima')
                continue
            _, idx, v = melhor
            t_id = self.identificadas.get(idx)
            if t_id is None or t_id > k['t']:
                self.log('kit para vítima ainda não identificada (sem pontos)')
                continue
            antes = self._pts_kits(idx)
            self.kits_vitima[idx] = self.kits_vitima.get(idx, 0) + 1
            self.log(f'kit entregue à vítima {self._nome_vitima(v)}', self._pts_kits(idx) - antes)

    def _necessarios(self, idx):
        return M.KITS_STATUS[M.status_vitima(self.mundo.mapa.vitimas[idx])]

    def _validos(self, idx):
        return min(self.kits_vitima.get(idx, 0), self._necessarios(idx))

    def _pts_kits(self, idx):
        return {0: 0, 1: 10, 2: 30}[self._validos(idx)]

    # ------------------------------------------------------------------ placar
    def placar(self):
        m = self.mundo.mapa
        p = {}
        p['vítimas'] = sum(self._pontos_vitima(m.vitimas[i]) for i in self.identificadas)
        p['kits'] = sum(self._pts_kits(i) for i in self.kits_vitima)
        p['checkpoints'] = 10 * len(self.checkpoints)
        p['azuis'] = sum(max(0, 30 - 10 * (n - 1)) for n in self.visitas_azul.values())
        p['lombadas'] = 5 * len(self.lombadas)
        p['escadas'] = 10 * len(self.escadas)
        p['erros'] = -5 * self.erros
        svi = len(self.identificadas)
        srd = sum(self._validos(i) for i in self.kits_vitima)
        sbv = len(self.azul_ok)
        ssn = len(self.escadas)
        p['confiabilidade'] = max(0, svi * 10 + srd * 10 + sbv * 10 - self.lop * 15)
        p['saída'] = (svi * 10 + sbv * 10 + ssn * 5) if self.saida else 0
        total = max(0, sum(p.values()))
        info = {'SVI': svi, 'SRD': srd, 'SBV': sbv, 'SSN': ssn, 'LoP': self.lop}
        return total, p, info
