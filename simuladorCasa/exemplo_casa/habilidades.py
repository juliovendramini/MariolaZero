"""As ferramentas do cérebro, feitas com o robô de verdade (ou o do simulador).

O cerebro.py descreve as ferramentas para o modelo (ferramentas()); aqui está o que cada uma faz:
navega pelo mapa (navega.py), olha pela câmera e pega/guarda (arruma.py). Cada função devolve uma
frase curta com o que aconteceu, que volta para o modelo. Erro = exceção com uma frase que o modelo
entende ("a pinça está vazia").
"""

import math

from arruma import (Arrumador, INCLINACAO_PROCURA, busca, larga_no_chao, leva_para_a_caixa, olha_em_volta)
from mapa import _sem_acento
from robo import ABERTA, BARRAS_DESCANSO, Interrompido


class Habilidades:
    def __init__(self, r, mapa, loc, nav, avisa=print, memoria=None):
        self.r, self.mapa, self.loc, self.nav = r, mapa, loc, nav
        self.memoria = memoria          # o caderno (memoria.Memoria); None = o robô não aprende nada
        self.quem = None                # voz.Quem (reconhece a pessoa pela voz), posto pelo programa da conversa
        self.fala_atual = None          # a fala que está sendo atendida (voz.Fala, com o som)
        self.reforco = None             # (nome, quantas falas ainda gravar) depois de um aprender_voz
        self.rosto = None               # rosto.Rosto, posto pelo programa da conversa (None = sem tela)
        self.humor_escolhido = False    # o cérebro chamou a ferramenta carinha neste pedido
        self.arr = Arrumador(r, mapa, loc, nav, avisa)
        self.comodos = [n for n in mapa.lugares() if mapa.lugar(n) is not None]
        self.base = mapa.comodo(mapa.inicio[0], mapa.inicio[1])
        self.caixa = mapa.comodo(mapa.caixa['x'], mapa.caixa['y']) if mapa.caixa else None
        self.na_pinca = None            # cor do objeto que está na pinça
        self.vistos = []                # objetos da última procura: [(x, y, cor)]
        self.vistos_de = None           # de onde o robô olhou
        # interrompe() -> a fala da pessoa, se ela falou com o robô agora (senão None). O programa da
        # conversa põe aqui a função que olha a fila da escuta; None = as tarefas não são interrompidas.
        self.interrompe = None

    def executa(self, nome, args):
        """Roda uma ferramenta. Se a pessoa falar com o robô no meio (self.interrompe devolve a fala), a
        ferramenta para na hora e o resultado conta ao cérebro o que ela disse, para ele decidir."""
        self.r.interrompe = self.interrompe
        antes = len(self.arr.guardados)
        self._cara(estado=self.CARA_DA_TAREFA.get(nome))
        try:
            res = getattr(self, 'f_' + nome)(**args)
            self._cara(momento=self.CARA_DO_SUCESSO.get(nome))
            return res
        except Interrompido as e:
            self._cara(momento='surpreso')
            return self._interrompido(nome, e.fala, antes)
        except Exception:
            if nome in self.CARA_DA_TAREFA:
                self._cara(momento='triste')
            raise
        finally:
            self.r.interrompe = None
            self._cara(estado=None)

    # a carinha de cada tarefa enquanto ela dura, e a de quando dá certo (por 3 s)
    CARA_DA_TAREFA = {'procurar_objetos': 'procurando', 'pegar_objeto': 'fazendo_forca', 'arrumar': 'procurando',
                      'aprender': 'pensando', 'aprender_voz': 'ouvindo', 'marcar_lugar': 'pensando'}
    CARA_DO_SUCESSO = {'guardar_na_caixa': 'comemorando', 'pegar_objeto': 'feliz', 'arrumar': 'orgulhoso',
                       'aprender': 'piscadela', 'aprender_voz': 'feliz', 'marcar_lugar': 'piscadela'}
    CARA_DO_GESTO = {'comemorar': 'comemorando', 'sim': 'feliz', 'nao': 'nao', 'triste': 'triste',
                     'olhar_para_cima': 'olhando_para_cima', 'dancinha': 'muito_feliz'}

    def _cara(self, estado='', momento=None):
        """Muda o rosto, se houver rosto. estado='' = não mexe no estado."""
        if self.rosto is None:
            return
        if estado != '':
            self.rosto.estado(estado)
        if momento:
            self.rosto.momento(momento)

    def f_carinha(self, nome):
        if self.rosto is None:
            raise RuntimeError('estou sem a tela do rosto.')
        nome = _sem_acento(nome).replace(' ', '_')
        self.rosto.humor(nome)
        self.humor_escolhido = True
        return f'Carinha: {nome}.'

    def _interrompido(self, nome, fala, guardados_antes):
        r = self.r
        r.interrompe = None
        self.nav.ao_andar = None
        r.para()
        self.vistos = []
        if self.arr.carregando:                    # estava levando um objeto para a caixa: continua com ele
            self.na_pinca, self.arr.carregando = self.arr.carregando, None
        if self.na_pinca:
            r.garra(barras=BARRAS_DESCANSO, inclinacao=INCLINACAO_PROCURA, espera=0.6)
        elif nome in ('pegar_objeto', 'arrumar', 'gesto'):
            # podia estar com a pinça no chão, aberta ou fechando em cima de um objeto: abre (se pegou,
            # solta), levanta e só então fecha, para não sair carregando algo sem saber
            r.garra(abertura=ABERTA, espera=0.5)
            r.garra(barras=BARRAS_DESCANSO, inclinacao=INCLINACAO_PROCURA, espera=0.7)
            r.garra(abertura=0, espera=0.4)
        x, y, _ = self.loc.pose()
        feito = ''
        novos = self.arr.guardados[guardados_antes:]
        if novos:
            feito = f' Antes de parar eu já tinha guardado {len(novos)} objeto(s): {", ".join(novos)}.'
        return (f'INTERROMPIDO: no meio disso a pessoa falou: "{fala}". Parei na hora, em {self.mapa.comodo(x, y)}'
                f'{self._segurando()}.{feito} O que eu estava fazendo ficou pela metade.')

    # ------------------------------------------------------------------ apoio
    def _lugar(self, nome):
        """(nome certo, (x, y)) de um cômodo dito pelo modelo."""
        if _sem_acento(nome) == 'base':
            return 'a base', self.mapa.inicio[:2]
        for c in self.comodos:
            if _sem_acento(c) == _sem_acento(nome):
                return c, self.mapa.lugar(c)
        marcado = self.memoria.lugar(nome) if self.memoria else None
        if marcado:
            return marcado['nome'], (marcado['x'], marcado['y'])
        extras = self.memoria.nomes_dos_lugares() if self.memoria else []
        raise ValueError(f'não conheço o lugar "{nome}". Os que conheço: {", ".join(self.comodos + extras)}')

    def _caderno(self):
        if self.memoria is None:
            raise RuntimeError('estou sem o caderno: não tenho onde anotar.')
        return self.memoria

    def _grandes(self, lista, aqui=None):
        """' Também tem no chão uma coisa azul grande demais para eu pegar (em Quarto casal).' ou ''.
        lista = dicionários do Arrumador.grandes. O cérebro conta isso à pessoa (ela vai querer recolher)."""
        if not lista:
            return ''
        itens = [f'uma coisa {g["cor"]}' + ('' if g['comodo'] == aqui else f' (em {g["comodo"]})') for g in lista]
        um = len(itens) == 1
        return (f' Também tem no chão {", ".join(itens[:-1]) + " e " if not um else ""}{itens[-1]} grande'
                f'{"" if um else "s"} demais para eu pegar: deixei onde está e desvio.')

    def _segurando(self):
        """', segurando um objeto verde' ou ''. Os resultados das ferramentas são curtos de propósito: o
        modelo repete na fala o que lê aqui (distâncias, margem de erro, "na pinça"), e o Julio não quer
        o robô falando isso."""
        return f', segurando um objeto {self.na_pinca}' if self.na_pinca else ''

    # ------------------------------------------------------------------ ferramentas
    def f_onde_estou(self):
        x, y, _ = self.loc.pose()
        mm, _ = self.loc.incerteza()
        duvida = f' Mas posso estar enganado: perdi a noção de onde estou em uns {mm / 10:.0f} cm.' if mm > 300 else ''
        return f'Estou em {self.mapa.comodo(x, y)}{self._segurando()}.{duvida}'

    def f_ir_para(self, comodo):
        nome, (x, y) = self._lugar(comodo)
        self.vistos = []
        rumo = self.mapa.inicio[2] if nome == 'a base' else None
        self.arr.grandes_novos = []
        # viaja olhando o chão (sem pegar nada): coisa grande no caminho vai para o mapa e ele desvia
        if not self.arr.viaja(x, y, pega=False, rumo=rumo):
            px, py, _ = self.loc.pose()
            por = ('uma coisa grande no chão fecha a passagem' if self.mapa.fechado_por_obstaculo((px, py), (x, y))
                   else 'fiquei preso ou não há caminho')
            raise RuntimeError(f'não consegui chegar em {nome}: {por}. Parei em '
                               f'{self.mapa.comodo(px, py)}.{self._grandes(self.arr.grandes_novos)}')
        txt = f'Cheguei em {nome}.' if nome != 'a base' else f'Voltei para a base, em {self.base}.'
        return txt + self._grandes(self.arr.grandes_novos)

    def f_procurar_objetos(self):
        if self.na_pinca:
            raise RuntimeError(f'segurando um objeto ({self.na_pinca}) eu não consigo procurar: guarde ou solte antes.')
        gr = []
        self.vistos = olha_em_volta(self.r, self.loc, self.mapa, ignora=self.arr.desistidos, grandes=gr)
        x, y, _ = self.loc.pose()
        self.arr.anota_grandes(gr, olhou_de=(x, y))
        self.vistos_de = (x, y)
        aqui = self.mapa.comodo(x, y)
        # as grandes desta olhada (as novas e as que já estavam no mapa)
        grandes = self._grandes([g for g in self.arr.grandes
                                 if any(math.hypot(g['x'] - v[0], g['y'] - v[1]) < 1.0 for v in gr)], aqui)
        if not self.vistos:
            return f'Não vi nenhum objeto no chão daqui ({aqui}).' + grandes
        itens = [c + ('' if self.mapa.comodo(ox, oy) == aqui else f' (em {self.mapa.comodo(ox, oy)})')
                 for ox, oy, c in self.vistos]
        return (f'Vi {len(self.vistos)} objeto(s) em {aqui}' + (', do mais perto para o mais longe' if len(itens) > 1 else '')
                + ': ' + ', '.join(itens) + '.' + grandes)

    def f_pegar_objeto(self, cor=None):
        if self.na_pinca:
            raise RuntimeError(f'já estou segurando um objeto {self.na_pinca}. Guarde ou solte antes.')
        x, y, _ = self.loc.pose()
        if not self.vistos or self.vistos_de is None or math.hypot(x - self.vistos_de[0], y - self.vistos_de[1]) > 300:
            self.f_procurar_objetos()
        candidatos = [v for v in self.vistos if not cor or v[2] == _sem_acento(cor)]
        if not candidatos and cor and any(g['cor'] == _sem_acento(cor) and math.hypot(g['x'] - x, g['y'] - y) < 3000
                                          for g in self.arr.grandes):
            raise RuntimeError(f'a coisa {cor} daqui é grande demais para eu pegar.')
        if not candidatos:
            ha = ', '.join(v[2] for v in self.vistos) or 'nenhum'
            raise RuntimeError(f'não vi nenhum objeto{" " + cor if cor else ""} daqui. Objetos à vista: {ha}.')
        alvo = candidatos[0]
        self.vistos = []                 # depois de mexer, as posições mudam
        if not busca(self.r, self.nav, self.loc, alvo):
            raise RuntimeError(f'não consegui pegar o objeto {alvo[2]}.')
        self.na_pinca = alvo[2]
        return f'Peguei o objeto {alvo[2]}.'

    def f_guardar_na_caixa(self):
        if not self.na_pinca:
            raise RuntimeError('não estou segurando nada: não tenho o que guardar.')
        if not self.mapa.caixa:
            raise RuntimeError('esta casa não tem caixa de guardar no mapa.')
        self.vistos = []
        if not leva_para_a_caixa(self.r, self.nav, self.loc, self.mapa):
            raise RuntimeError(f'não consegui chegar na caixa. Continuo segurando o objeto {self.na_pinca}.')
        cor, self.na_pinca = self.na_pinca, None
        return f'Guardei o objeto {cor} na caixa, em {self.caixa}.'

    def f_soltar_objeto(self):
        if not self.na_pinca:
            raise RuntimeError('não estou segurando nada.')
        larga_no_chao(self.r)
        cor, self.na_pinca = self.na_pinca, None
        self.vistos = []
        x, y, _ = self.loc.pose()
        return f'Soltei o objeto {cor} no chão, em {self.mapa.comodo(x, y)}.'

    def f_aprender(self, nota):
        n = self._caderno().aprende(nota)
        return f'Anotei no caderno (nota {n}): {" ".join(str(nota).split())}'

    def f_esquecer(self, numero=None, lugar=None):
        m = self._caderno()
        if numero is None and not lugar:
            raise ValueError('diga o número da nota ou o nome do lugar a esquecer.')
        feito = []
        if numero is not None:
            feito.append(f'a nota {numero} ("{m.esquece(numero)}")')
        if lugar:
            m.esquece_lugar(lugar)
            feito.append(f'o lugar "{lugar}"')
        return 'Apaguei do caderno ' + ' e '.join(feito) + '.'

    def ouviu(self, fala):
        """O programa avisa de cada fala dirigida ao robô (uma voz.Fala). Depois de uma apresentação, as
        duas falas seguintes da pessoa reforçam a voz dela: uma frase só é pouco para reconhecer depois."""
        self.fala_atual = fala
        if self.reforco and self.quem is not None and getattr(fala, 'audio', None) is not None:
            nome, faltam = self.reforco
            self.quem.apresenta(nome, fala.audio)
            self.reforco = (nome, faltam - 1) if faltam > 1 else None
            if getattr(fala, 'quem', None) is None:
                fala.quem, fala.certeza = nome, 1.0          # acabou de se apresentar: é ela

    def f_aprender_voz(self, nome):
        if self.quem is None:
            raise RuntimeError('o reconhecimento de voz não está ligado: não tenho como guardar vozes.')
        audio = getattr(self.fala_atual, 'audio', None)
        if audio is None:
            raise RuntimeError('não tenho o som desta fala (o pedido veio digitado).')
        nome = ' '.join(str(nome).split())
        dono, certeza = self.quem.quem(audio)
        if dono is not None and _sem_acento(dono) != _sem_acento(nome):
            # a mesma voz com dois nomes estraga o reconhecimento das duas pessoas
            raise RuntimeError(f'esta voz já está guardada como {dono}, então não gravei como {nome}. Se {nome} é outra '
                               f'pessoa, ela mesma precisa falar; se é a mesma pessoa com outro nome, apague antes a voz de {dono}.')
        total = self.quem.apresenta(nome, audio)
        self.reforco = (nome, 2)
        if total == 0:
            return (f'A fala foi curta demais para guardar a voz de {nome}. Vou gravar as duas próximas falas: '
                    'peça uma frase comprida.')
        return f'Guardei a voz de {nome}. As duas próximas falas também serão gravadas, para eu reconhecer melhor.'

    def f_esquecer_voz(self, nome):
        if self.quem is None:
            raise RuntimeError('o reconhecimento de voz não está ligado.')
        return f'Apaguei a voz de {self.quem.esquece(nome)}.'

    def f_marcar_lugar(self, nome):
        x, y, _ = self.loc.pose()
        if self.mapa.folga(x, y) < 150:
            raise RuntimeError('estou encostado demais numa parede ou num móvel para marcar este ponto.')
        comodo = self.mapa.comodo(x, y)
        self._caderno().marca_lugar(nome, x, y, comodo)
        return f'Marquei este ponto como "{nome}", em {comodo}.'

    def f_gesto(self, tipo):
        """Reações com o corpo, sem sair do lugar. Com um objeto na pinça, ela não abre."""
        r = self.r
        tipo = _sem_acento(tipo).replace(' ', '_')
        fechada = 0 if not self.na_pinca else None        # None = não mexe na pinça
        self._cara(momento=self.CARA_DO_GESTO.get(tipo))

        def pinca(aberta):
            if fechada is not None:
                r.garra(abertura=45 if aberta else 0, espera=0.25)

        if tipo == 'comemorar':
            for lado in (18, -36, 18):
                r.gira(lado, vel=45)
                pinca(True)
                pinca(False)
        elif tipo == 'sim':
            for incl in (45, -10, 45, -10, 15):
                r.garra(inclinacao=incl, espera=0.3)
        elif tipo == 'nao':
            for lado in (14, -28, 28, -14):
                r.gira(lado, vel=45)
        elif tipo == 'triste':
            r.garra(barras=-20, inclinacao=70, espera=1.6)
            r.garra(barras=BARRAS_DESCANSO, inclinacao=INCLINACAO_PROCURA, espera=0.5)
        elif tipo == 'olhar_para_cima':
            r.garra(inclinacao=-40, espera=0.6)           # fica olhando para a pessoa até a próxima ação
            return 'Levantei a câmera para olhar para a pessoa.'
        elif tipo == 'dancinha':
            for lado, barras in ((25, 30), (-50, -10), (50, 30), (-50, -10), (25, 0)):
                r.garra(barras=barras)
                r.gira(lado, vel=50)
            r.garra(barras=BARRAS_DESCANSO, espera=0.3)
        else:
            raise ValueError(f'não sei fazer o gesto "{tipo}".')
        r.garra(inclinacao=INCLINACAO_PROCURA)
        return f'Fiz o gesto: {tipo}.'

    def f_arrumar(self, comodos=()):
        if self.na_pinca:
            raise RuntimeError(f'estou segurando um objeto {self.na_pinca}. Guarde ou solte antes de arrumar.')
        if not self.mapa.caixa:
            raise RuntimeError('esta casa não tem caixa de guardar no mapa.')
        nomes = [self._lugar(c)[0] for c in comodos] or list(self.comodos)
        antes, desist = len(self.arr.guardados), len(self.arr.desistidos)
        self.arr.grandes_novos = []
        olhados, sem_chegar = self.arr.arruma(nomes)
        self.r.garra(barras=BARRAS_DESCANSO, abertura=0, inclinacao=INCLINACAO_PROCURA)
        self.vistos = []
        novos = self.arr.guardados[antes:]
        x, y, _ = self.loc.pose()
        txt = (f'Olhei {len(olhados)} cômodo(s)' + (f' ({", ".join(olhados)})' if len(olhados) <= 4 else '')
               + f' e guardei {len(novos)} objeto(s)' + (': ' + ', '.join(novos) if novos else '') + '.')
        if len(self.arr.desistidos) > desist:
            txt += f' Não consegui pegar ou guardar {len(self.arr.desistidos) - desist}.'
        fechados = [n for n in sem_chegar if n in self.arr.fechados]
        if fechados:
            txt += f' Não consegui chegar em {", ".join(fechados)}: uma coisa grande no chão fecha a passagem.'
        resto = [n for n in sem_chegar if n not in fechados]
        if resto:
            txt += f' Não cheguei em: {", ".join(resto)}.'
        # as grandes que ainda estão no chão dos cômodos olhados (as novas e as que já estavam no mapa)
        grandes = [g for g in self.arr.grandes if g in self.arr.grandes_novos or g['comodo'] in olhados]
        return txt + self._grandes(grandes) + f' Estou em {self.mapa.comodo(x, y)}.'
