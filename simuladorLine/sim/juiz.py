"""Juiz automático da RoboCupJunior Rescue Line 2026.

Pontuação (seção de pontuação da regra 2026 e cálculo do rcj-rescue-cms):
* cada perigo vale uma vez por sentido em que o caminho passa por ele:
  interseção/beco sem saída certo 10, gap 10, obstáculo 20, lombada 10 (por ladrilho),
  rampa 10 (por ladrilho), gangorra 20;
* checkpoint: ladrilhos desde o checkpoint anterior x 5 (1ª tentativa), 3 (2ª), 1 (3ª), 0;
* chegada: parar mais de 5 s no ladrilho de chegada -> bônus de saída 60 - 5 x LoP
  (mínimo 0) + os ladrilhos desde o último checkpoint.

Falta de progresso (LoP): o robô volta ao último checkpoint, virado para a chegada. Depois de 3
tentativas sem chegar ao próximo checkpoint, ele pode ir para o próximo.

Área de resgate (5.6.6 a 5.6.12): cada vítima viva no triângulo verde x1,4; a morta no vermelho
x1,4 só se as duas vivas já foram resgatadas. Cada termo perde 0,05 por LoP no trecho da área
(nunca abaixo de 1,25). Pontuação = (linha + bônus de saída) x multiplicador. A área não conta
como ladrilho nos checkpoints.
"""


from . import ladrilhos as LT
from .mapa import ITENS_PONTOS, TEMPO_RODADA

NOMES_ITENS = {'intersecao': 'interseção', 'gap': 'gap', 'obstaculo': 'obstáculo', 'lombada': 'lombada',
               'rampa': 'rampa', 'gangorra': 'gangorra'}


def pontos_por_ladrilho(lops):
    return max(0, 5 - 2 * lops)


class Juiz:
    def __init__(self, mundo):
        self.mundo = mundo
        self.on_lop = None      # callback(motivo)
        self.on_fim = None      # callback(motivo)
        cfg = mundo.cfg.get('juiz', {})
        self.tempo_fora = float(cfg.get('tempo_fora_do_caminho_s', 10.0))
        self.lop_sem_progresso = float(cfg.get('lop_sem_progresso_s', 0))
        self.pula_apos_3 = bool(cfg.get('pula_checkpoint_apos_3_tentativas', True))
        self.reset()

    # ------------------------------------------------------------------ estado
    def reset(self):
        m = self.mundo.mapa
        self.passos = m.passos()
        self.n = len(self.passos)
        self.cps = [i for i, p in enumerate(self.passos)
                    if i > 0 and m.ladrilhos[p['k']].get('checkpoint')]
        self.idx_chegada = self.n - 1 if self.n and m.eh_chegada(m.ladrilhos[self.passos[-1]['k']]) else None
        self.ativo = False
        self.t0 = 0.0
        self.t_fim = 0.0
        self.fim = None
        self.eventos = []
        self.lop = 0
        self.lops_seg = {}
        self.seg = 0
        self.idx = 0
        self.ultimo_cp = 0
        self.pontuados = set()
        self.pontos = {'checkpoints': 0, 'intersecao': 0, 'gap': 0, 'obstaculo': 0, 'lombada': 0,
                       'rampa': 0, 'gangorra': 0, 'saida': 0}
        self.resgates = []          # (tipo, t) das vítimas que valeram
        self.lops_zona = 0
        self.idx_zona = next((i for i, p in enumerate(self.passos) if p.get('zona')), None)
        self.cel = None
        self.errado_desde = None
        self.fora_desde = None
        self.parado_desde = None
        self.t_progresso = 0.0
        self.chegou = False

    def iniciar(self):
        self.reset()
        self.ativo = True
        self.t0 = self.mundo.t
        self.t_progresso = self.mundo.t
        self.cel = self._cel()
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

    # ------------------------------------------------------------------ LoP
    def falta_progresso(self, motivo):
        if not self.ativo or self.fim:
            return
        self.lop += 1
        self.lops_seg[self.seg] = self.lops_seg.get(self.seg, 0) + 1
        if self._trecho_da_zona():
            self.lops_zona += 1
        n = self.lops_seg[self.seg]
        self.log(f'LoP ({n}ª no trecho): {motivo}')
        destino = self.ultimo_cp
        if self.pula_apos_3 and n >= 3:
            prox = [c for c in self.cps if c > self.ultimo_cp]
            if prox:
                destino = prox[0]
                self.log(f'3 tentativas: robô vai para o próximo checkpoint (passo {destino})')
                self.ultimo_cp = destino
                self.seg += 1
        self.idx = destino
        self.errado_desde = None
        self.fora_desde = None
        self.parado_desde = None
        if self.on_lop:
            self.on_lop(motivo)

    def _trecho_da_zona(self):
        """O robô está no trecho (entre dois checkpoints) que contém a área de resgate?"""
        if self.idx_zona is None:
            return False
        prox = [c for c in self.cps if c > self.ultimo_cp]
        fim = prox[0] if prox else self.n
        return self.ultimo_cp < self.idx_zona < fim

    # ------------------------------------------------------------------ área de resgate
    def vitima(self, bola, triangulo):
        """Chamado pela física quando uma vítima fica inteira num triângulo sem o robô encostar.
        Devolve True se o resgate vale (o juiz tira a vítima do campo)."""
        if not self.ativo or self.fim:
            return False
        tipo = bola['tipo']
        vivas = sum(1 for t, _ in self.resgates if t == 'viva')
        if tipo == 'viva' and triangulo == 'verde':
            self.resgates.append(('viva', self.mundo.t))
            self.log(f'vítima viva resgatada ({vivas + 1}ª): x1,4')
            return True
        if tipo == 'morta' and triangulo == 'vermelho':
            if vivas >= 2:
                self.resgates.append(('morta', self.mundo.t))
                self.log('vítima morta resgatada: x1,4')
                return True
            self.log('vítima morta no vermelho antes das duas vivas: não vale')
            return False
        self.log(f'vítima {tipo} no triângulo {triangulo}: não vale')
        return False

    def multiplicador(self):
        termo = max(1.25, 1.4 - 0.05 * self.lops_zona)
        m = 1.0
        for _ in self.resgates:
            m *= termo
        return m

    def reposicionado(self):
        self.cel = self._cel()
        self.t_progresso = self.mundo.t
        self.errado_desde = None
        self.fora_desde = None

    # ------------------------------------------------------------------ pontuação
    def _pontua_itens(self, i):
        if i in self.pontuados:
            return
        self.pontuados.add(i)
        m = self.mundo.mapa
        t = m.ladrilhos[self.passos[i]['k']]
        for item, qtd in m.itens(t).items():
            p = ITENS_PONTOS[item] * qtd
            self.pontos[item] += p
            self.log(f'{NOMES_ITENS[item]}' + (f' x{qtd}' if qtd > 1 else '') + f' (passo {i})', p)

    def _pontua_checkpoint(self, i, chegada=False):
        lops = self.lops_seg.get(self.seg, 0)
        n = i - self.ultimo_cp - sum(1 for j in range(self.ultimo_cp + 1, i + 1) if self.passos[j].get('zona'))
        p = n * pontos_por_ladrilho(lops)
        self.pontos['checkpoints'] += p
        nome = 'chegada' if chegada else 'checkpoint'
        self.log(f'{nome}: {n} ladrilhos x {pontos_por_ladrilho(lops)} ({lops + 1}ª tentativa)', p)
        self.ultimo_cp = i
        self.seg += 1

    def _avanca(self, novo):
        for i in range(self.idx, novo):
            self._pontua_itens(i)
            if i + 1 in self.cps and i + 1 > self.ultimo_cp:
                self._pontua_checkpoint(i + 1)
        self.idx = novo
        self.t_progresso = self.mundo.t

    # ------------------------------------------------------------------ acompanhamento
    def _cel(self):
        t = self.mundo.lad_centro
        m = self.mundo.mapa
        return m.chave_caminho(m.chave(t)) if t is not None else None

    def _dir(self, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        for d, (px, py) in LT.PASSO.items():
            if (px, py) == (dx, dy):
                return d
        return None

    def _sobre_linha(self):
        """O centro do robô (ou o sensor) está sobre preto num ladrilho?"""
        w = self.mundo
        b = w.corpo
        import numpy as np
        pts = np.array([[b.position.x, b.position.y],
                        list(b.local_to_world((w.sensor.ir[len(w.sensor.ir) // 2][0], 0)))])
        mats = w.materiais(pts)
        return bool((mats == LT.M_PRETO).any())

    def atualiza(self, dt):
        if not self.ativo or self.fim:
            return
        w = self.mundo
        if w.t - self.t0 >= TEMPO_RODADA:
            self.encerrar('tempo esgotado (8 min)')
            return
        if self.n == 0:
            return
        # saiu do campo / caiu de um ladrilho elevado
        if w.fora_da_pista:
            if self.fora_desde is None:
                self.fora_desde = w.t
            elif w.t - self.fora_desde > 0.3:
                self.falta_progresso('robô saiu da pista')
            return
        self.fora_desde = None
        cel = self._cel()
        if cel != self.cel and cel is not None and self.cel is not None:
            self._mudou_celula(self.cel, cel)
        self.cel = cel
        esperado = self.passos[self.idx]['k']
        anterior = self.passos[self.idx - 1]['k'] if self.idx > 0 else None
        if cel in (esperado, anterior):
            self.errado_desde = None
        else:
            if self.errado_desde is None:
                self.errado_desde = w.t
            dur = w.t - self.errado_desde
            if dur > 0.4 and self._sobre_linha():
                self.falta_progresso('chegou numa linha que não é a próxima do caminho')
                return
            if dur > self.tempo_fora:
                self.falta_progresso('perdeu a linha e não voltou para o próximo ladrilho')
                return
        if self.lop_sem_progresso > 0 and w.t - self.t_progresso > self.lop_sem_progresso:
            self.falta_progresso(f'{self.lop_sem_progresso:.0f} s sem avançar')
            return
        # chegada: parar mais de 5 s
        if self.idx_chegada is not None and self.idx == self.idx_chegada and cel == esperado:
            v, om = w.velocidade()
            if v < 6 and om < 0.05:
                if self.parado_desde is None:
                    self.parado_desde = w.t
                elif w.t - self.parado_desde >= 5.0:
                    self._chegada()
            else:
                self.parado_desde = None

    def _mudou_celula(self, de, para):
        """Avança no caminho quando o robô entra no próximo ladrilho (ou no seguinte, ao
        contornar um obstáculo ou cortar um canto na diagonal)."""
        p = self.passos
        i = self.idx
        for j in (i + 1, i + 2):
            if j < self.n and para == p[j]['k']:
                self._avanca(j)
                return

    def _chegada(self):
        if self.chegou:
            return
        self.chegou = True
        self._pontua_itens(self.idx - 1) if self.idx > 0 else None
        self._pontua_checkpoint(self.idx, chegada=True)
        bonus = max(0, 60 - 5 * self.lop)
        self.pontos['saida'] = bonus
        self.log(f'bônus de saída (60 - 5 x {self.lop} LoP)', bonus)
        self.encerrar('robô parou na chegada')

    # ------------------------------------------------------------------ placar
    def placar(self):
        soma = sum(self.pontos.values())
        partes = {('checkpoints' if k == 'checkpoints' else NOMES_ITENS.get(k, 'saída')): v
                  for k, v in self.pontos.items()}
        partes['saída'] = partes.pop('saída', 0)
        info = {'LoP': self.lop, 'passo': f'{self.idx}/{max(0, self.n - 1)}'}
        total = soma
        if self.idx_zona is not None:
            mult = self.multiplicador()
            vivas = sum(1 for t, _ in self.resgates if t == 'viva')
            mortas = len(self.resgates) - vivas
            partes['vítimas'] = f'{vivas} viva(s), {mortas} morta, LoP na área {self.lops_zona}'
            partes['multiplicador'] = f'x{mult:.3f}'
            total = int(round(soma * mult))
            info['linha'] = soma
        return total, partes, info
