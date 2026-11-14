"""Acompanha a tarefa do robô de casa: o que ele pegou, o que guardou na caixa e quanto tempo levou.

Não é uma competição: não há penalidade nem tempo máximo (o --tempo do simulador.py corta a rodada
sem janela). A rodada termina quando todos os objetos da casa estão guardados na caixa.
"""


class Juiz:
    def __init__(self, mundo):
        self.mundo = mundo
        self.on_reposiciona = None
        self.on_fim = None
        self.reset()

    def reset(self):
        self.ativo = False
        self.fim = None
        self.t0 = 0.0
        self.t_fim = None
        self.eventos = []            # (tempo, texto, pontos)
        self.pegos = 0
        self.guardados = 0
        self.largados = 0

    def iniciar(self):
        self.ativo = True
        self.fim = None
        self.t0 = self.mundo.t
        self.t_fim = None
        self.log('início')

    @property
    def tempo(self):
        if not self.ativo:
            return 0.0
        return (self.t_fim if self.t_fim is not None else self.mundo.t) - self.t0

    def log(self, texto, pontos=0):
        self.eventos.append((self.tempo, texto, pontos))

    def encerrar(self, motivo):
        if self.fim:
            return
        self.fim = motivo
        self.t_fim = self.mundo.t
        self.log(f'fim: {motivo}')
        if self.on_fim:
            self.on_fim(motivo)

    def reinicio(self, robo):
        self.log('robô devolvido ao início')

    def atualiza(self, dt):
        if not self.ativo or self.fim:
            self.mundo.eventos_garra.clear()
            return
        w = self.mundo
        for (tipo, robo, o, _) in w.eventos_garra:
            if tipo == 'preso':
                self.pegos += 1
                self.log(f'pegou o objeto {o.cor}')
            elif tipo == 'guardado':
                self.guardados += 1
                self.log(f'guardou o objeto {o.cor} na caixa', 1)
            elif tipo == 'chao':
                self.largados += 1
                self.log(f'largou o objeto {o.cor} no chão')
        w.eventos_garra.clear()
        pequenos = [o for o in w.objetos if not o.grande]
        if pequenos and all(o.estado == 'guardado' for o in pequenos):
            self.encerrar('tudo guardado')

    def placar(self):
        """Conta só os objetos que cabem na pinça; os grandes (camiseta, brinquedo grande) ficam no chão."""
        pequenos = [o for o in self.mundo.objetos if not o.grande]
        g = sum(1 for o in pequenos if o.estado == 'guardado')
        partes = {'positivos': g, 'negativos': 0}
        info = {'guardados': f'{g}/{len(pequenos)}', 'pegos': self.pegos, 'largados no chão': self.largados}
        grandes = len(self.mundo.objetos) - len(pequenos)
        if grandes:
            info['grandes (ficam no chão)'] = grandes
        return g, partes, info
