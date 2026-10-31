"""Juiz automático da RCB Challenge 2026 (regra V1.0, seções 7 a 9).

O que é julgado:
* tempo da partida (12 min) e partida completa (todos os cubos de cor entregues);
* robô fora da área permitida: passou da linha vermelha ou da linha azul do outro lado
  (-5, o robô volta para o início dele);
* reinício pedido pela equipe (-15);
* cubo de cor solto em cima da plataforma da mesma cor: +100 (entregue); na plataforma errada,
  -10 (cubo perdido, o árbitro tira na hora); se o cubo novo cair em cima de um que já estava lá,
  o de antes é derrubado (-45) e volta para o lugar dele;
* cubo branco (ou de cor sem plataforma na pista) identificado: +50, uma vez por cubo. Cada aviso
  (um LED do Mariola acendendo ou o buzzer começando a tocar) vale para o cubo branco mais perto, à
  frente do robô, a até 20 cm da frente dele e ainda no lugar;
* empurrões e pegas proibidas: cubo-obstáculo (quadrado marrom) deslocado ou pego (-15), cubo branco
  tirado do lugar ou pego (-15), cubo de cor largado fora da plataforma e fora da área verde da
  equipe (-10, cubo perdido), plataforma deslocada mais de 10 mm (-20). O árbitro devolve o objeto
  ao lugar quando o robô se afasta.
"""

import math

from . import arena as A

TEMPO_PARTIDA = 720.0
LIMITE_CUBO = 25.0          # mm: metade do cubo fora do quadrado
LIMITE_OBSTACULO = 10.0
LIMITE_PLATAFORMA = 10.0    # seção 7: "deslocada mais de 10 mm"
ESPERA_JULGAR = 0.5         # s parado e sem o robô encostando antes de o árbitro decidir
DIST_DEVOLVER = 220.0       # mm: o árbitro só devolve o objeto com o robô longe do lugar dele
DIST_IDENTIFICA = 200.0     # mm da frente do robô até o cubo branco para valer o aviso
DIST_DERRUBA = 40.0         # mm entre centros: o cubo novo caiu em cima do que já estava lá


class Juiz:
    def __init__(self, mundo):
        self.mundo = mundo
        self.on_fim = None            # callback(motivo)
        self.on_reposiciona = None    # callback(robo, motivo): robô volta para o início
        self.reset()

    # ------------------------------------------------------------------ estado
    def reset(self):
        self.ativo = False
        self.t0 = 0.0
        self.t_fim = 0.0
        self.fim = None
        self.eventos = []
        self.positivos = 0
        self.negativos = 0
        self.contagem = {'entregues': 0, 'identificados': 0, 'saídas': 0, 'reinícios': 0,
                         'perdidos': 0, 'derrubados': 0, 'obstáculos': 0, 'brancos': 0, 'plataformas': 0}
        self.estado_obj = {}       # objeto -> estado do árbitro (veja _novo_estado)
        self.identificados = set()
        self.sinal_ant = {}        # robo -> LED/buzzer ligado no passo anterior
        self.mundo.eventos_garra.clear()

    def iniciar(self):
        self.reset()
        self.ativo = True
        self.t0 = self.mundo.t
        self.log('início da partida')

    @property
    def tempo(self):
        if not self.ativo and self.fim is None:
            return 0.0
        return min(TEMPO_PARTIDA, self.mundo.t - self.t0) if self.fim is None else self.t_fim

    def log(self, texto, pontos=0):
        t = self.mundo.t - self.t0 if self.ativo else 0.0
        self.eventos.append((t, texto, pontos))
        if pontos > 0:
            self.positivos += pontos
        elif pontos < 0:
            self.negativos += -pontos

    def encerrar(self, motivo):
        if self.fim is None:
            self.fim = motivo
            self.t_fim = min(TEMPO_PARTIDA, self.mundo.t - self.t0)
            self.log(f'fim da partida: {motivo}')
            if self.on_fim:
                self.on_fim(motivo)

    def reinicio(self, robo):
        """A equipe tocou no robô / reiniciou o programa (seção 7): -15."""
        if not self.ativo or self.fim:
            return
        self.contagem['reinícios'] += 1
        self.log('reinício do robô', -15)

    # ------------------------------------------------------------------ cores
    def cores_com_plataforma(self):
        return {o.cor for o in self.mundo.objetos if o.tipo == 'plataforma'}

    def eh_branco(self, o):
        """Cubo branco ou de uma cor sem plataforma na pista: tratado como branco (seção 7)."""
        return o.cor == 'branco' or o.cor not in self.cores_com_plataforma()

    def _tipo_pos(self, o):
        return A.POSICOES[o.pos]['tipo']

    @staticmethod
    def _nome(o):
        return f'{o.tipo} {o.cor} ({o.pos})'

    # ------------------------------------------------------------------ atualização
    def atualiza(self, dt):
        w = self.mundo
        if not self.ativo or self.fim:
            w.eventos_garra.clear()
            return
        if w.t - self.t0 >= TEMPO_PARTIDA:
            self.encerrar('tempo esgotado (12 min)')
            return
        for r in w.robos:
            motivo = self._fora_da_area(r)
            if motivo:
                self.contagem['saídas'] += 1
                self.log(f'robô fora da área: {motivo}', -5)
                if self.on_reposiciona:
                    self.on_reposiciona(r, motivo)
        self._eventos_garra()
        self._objetos()
        self._identificacao()
        self._completa()

    def _fora_da_area(self, r):
        """O centro do robô passou da linha vermelha (limite da cidade) ou da linha azul do lado
        do adversário."""
        x, y, _ = r.pose()
        if x < A.BORDA or y < A.BORDA or x > A.LARGURA - A.BORDA or y > A.ALTURA - A.BORDA:
            return 'passou da linha vermelha'
        if r.lado == 'esq' and x > A.LARGURA - A.X_AZUL[0]:
            return 'passou da linha azul do adversário'
        if r.lado == 'dir' and x < A.X_AZUL[0]:
            return 'passou da linha azul do adversário'
        return None

    @staticmethod
    def _novo_estado():
        # quieto = desde quando está parado e longe do robô; devolver = o árbitro vai pôr de volta;
        # penalizado = já descontado (pego quando não podia): volta sem novo desconto;
        # robo = o último robô que encostou
        return {'quieto': None, 'devolver': False, 'penalizado': False, 'robo': None}

    def _st(self, o):
        return self.estado_obj.setdefault(o, self._novo_estado())

    # ------------------------------------------------------------------ garra
    def _eventos_garra(self):
        w = self.mundo
        evs, w.eventos_garra[:] = list(w.eventos_garra), []
        for tipo, robo, o, plat in evs:
            st = self._st(o)
            st['robo'] = robo
            if tipo == 'preso':
                st['quieto'] = None
                if self._tipo_pos(o) == 'marrom':
                    self.contagem['obstáculos'] += 1
                    self.log(f'obstáculo não identificado (pego): {self._nome(o)}', -15)
                    st['penalizado'] = True
                elif self.eh_branco(o):
                    self.contagem['brancos'] += 1
                    self.log(f'cubo branco não identificado (pego): {self._nome(o)}', -15)
                    st['penalizado'] = True
            elif tipo == 'plataforma':
                if st['penalizado']:
                    st['devolver'] = True
                elif o.cor == plat.cor:
                    for q in w.cubos_na_plataforma(plat):
                        if q is not o and q.corpo.position.get_distance(o.corpo.position) < DIST_DERRUBA:
                            self.contagem['derrubados'] += 1
                            self.log(f'cubo derrubado da plataforma {plat.cor}: {self._nome(q)}', -45)
                            q.muda_estado('livre')
                            self._st(q)['devolver'] = True
                            self._st(q)['penalizado'] = True
                    self.contagem['entregues'] += 1
                    self.log(f'cubo entregue: {o.cor} ({o.pos}) na plataforma {plat.cor}', 100)
                else:
                    self.contagem['perdidos'] += 1
                    self.log(f'cubo perdido: {o.cor} ({o.pos}) na plataforma {plat.cor}', -10)
                    st['devolver'] = True
                    st['penalizado'] = True
            elif tipo == 'chao':
                if st['penalizado']:
                    st['devolver'] = True
                # senão: cubo no chão é julgado como qualquer outro em _objetos

    # ------------------------------------------------------------------ objetos
    def _objetos(self):
        w = self.mundo
        encostados = set()
        for r in w.robos:
            for s in r.tocando():
                o = getattr(s, 'objeto', None)
                if o is not None:
                    encostados.add(o)
                    self._st(o)['robo'] = r
        for o in w.objetos:
            st = self._st(o)
            if st['devolver'] and o.estado != 'preso':
                if all(math.hypot(r.pose()[0] - o.x0, r.pose()[1] - o.y0) > DIST_DEVOLVER for r in w.robos):
                    o.volta()
                    st['devolver'] = False
                    st['penalizado'] = False
                    st['quieto'] = None
                continue
            if o.estado != 'livre':
                st['quieto'] = None
                continue
            b = o.corpo
            parado = b.velocity.length < 1.0 and abs(b.angular_velocity) < 0.02
            if o in encostados or not parado:
                st['quieto'] = None
                continue
            desl = o.deslocamento()
            tipo_pos = self._tipo_pos(o)
            if o.tipo == 'plataforma':
                lim = LIMITE_PLATAFORMA
            elif tipo_pos == 'marrom':
                lim = LIMITE_OBSTACULO
            else:
                lim = LIMITE_CUBO
            if desl <= lim:
                st['quieto'] = None
                continue
            if st['quieto'] is None:
                st['quieto'] = w.t
                continue
            if w.t - st['quieto'] < ESPERA_JULGAR:
                continue
            if (o.tipo == 'cubo' and tipo_pos == 'cinza' and not self.eh_branco(o) and st['robo'] is not None
                    and self._na_area_livre(o, st['robo'].lado)):
                # cubo de cor solto na área verde da equipe é permitido (seção 7): continua em jogo
                continue
            self._penaliza(o, tipo_pos)
            st['devolver'] = True

    @staticmethod
    def _na_area_livre(o, lado):
        x0, y0, x1, y1 = A.area_livre(lado)
        return all(x0 <= p.x <= x1 and y0 <= p.y <= y1 for p in o.cantos())

    def _penaliza(self, o, tipo_pos):
        nome = self._nome(o)
        if o.tipo == 'plataforma':
            self.contagem['plataformas'] += 1
            self.log(f'plataforma deslocada: {nome}', -20)
        elif tipo_pos == 'marrom':
            self.contagem['obstáculos'] += 1
            self.log(f'obstáculo não identificado: {nome}', -15)
        elif self.eh_branco(o):
            self.contagem['brancos'] += 1
            self.log(f'cubo branco não identificado: {nome}', -15)
        else:
            self.contagem['perdidos'] += 1
            self.log(f'cubo perdido: {nome}', -10)

    # ------------------------------------------------------------------ cubo branco
    def _identificacao(self):
        """Cada aviso (LED acendendo ou buzzer começando a tocar) vale para um cubo só: o cubo branco
        mais perto, à frente do robô e a até 20 cm da frente dele."""
        w = self.mundo
        for r in w.robos:
            sinal = any(any(c) for c in r.leds) or r.fw_mariola.buzzer_tocando(w.t)
            antes = self.sinal_ant.get(r, False)
            self.sinal_ant[r] = sinal
            if not sinal or antes:
                continue
            frente = r.corpo.local_to_world((r.L / 2, 0.0))
            melhor, dmin = None, DIST_IDENTIFICA
            for o in w.objetos:
                if (o.tipo != 'cubo' or o in self.identificados or o.estado != 'livre'
                        or self._tipo_pos(o) != 'cinza' or not self.eh_branco(o)):
                    continue
                if o.deslocamento() > LIMITE_CUBO or self._st(o)['devolver']:
                    continue
                if r.corpo.world_to_local(o.corpo.position).x <= 0:
                    continue                          # atrás do robô
                d = frente.get_distance(o.corpo.position)
                if d <= dmin:
                    melhor, dmin = o, d
            if melhor is not None:
                self.identificados.add(melhor)
                self.contagem['identificados'] += 1
                self.log(f'cubo branco identificado: {melhor.cor} ({melhor.pos})', 50)

    def _completa(self):
        """Partida completa: todos os cubos de cor (com plataforma) entregues na plataforma certa."""
        cores = self.cores_com_plataforma()
        alvo = [o for o in self.mundo.objetos
                if o.tipo == 'cubo' and o.cor in cores and self._tipo_pos(o) == 'cinza']
        if alvo and all(o.estado == 'plataforma' and o.sobre is not None and o.sobre.cor == o.cor
                        for o in alvo):
            self.encerrar('partida completa: todos os cubos entregues')

    def placar(self):
        """(total, partes, info). Pontuação negativa não vale: o total nunca fica abaixo de 0
        (seção 7); positivos e negativos ficam guardados para o desempate."""
        total = max(0, self.positivos - self.negativos)
        partes = {'positivos': self.positivos, 'negativos': -self.negativos}
        info = {k: v for k, v in self.contagem.items() if v}
        return total, partes, info
