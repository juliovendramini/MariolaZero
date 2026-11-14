"""Bateria de comandos para comparar os cérebros (Claude x modelo local), sem robô e sem simulador.

    python exemplo_casa/testa_cerebro.py local                       (o modelo local padrão do cerebro.py)
    python exemplo_casa/testa_cerebro.py local:qwen3-coder:30b local:gpt-oss:20b
    python exemplo_casa/testa_cerebro.py claude claude:claude-haiku-5-5
    python exemplo_casa/testa_cerebro.py claude local --so 3,7 --mostra

Cada comando roda numa casa de mentira (os cômodos são os do mapa; as ferramentas mudam um estado
simples em vez de mexer um robô) e é conferido pelo que aconteceu: onde o robô foi parar, o que foi
guardado, se ele perguntou em vez de adivinhar. O resultado sai na tela e em
resultados/cerebro_<modelo>.json.

Mede: acertos, segundos até a primeira decisão do modelo (o tempo em que o robô fica parado depois
da ordem), segundos de modelo por comando e tokens. Não mede o tempo do robô andando.
"""

import argparse
import json
import os
import re
import sys
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from cerebro import CORES, Cerebro, ferramentas, texto_sistema, cria_modelo  # noqa: E402

COMODOS = ['Sala de estar', 'Sala de jantar', 'Cozinha', 'Quarto 1', 'Quarto 2', 'Quarto casal', 'Closet',
           'Banheiro social', 'Banheiro casal', 'Area de servico', 'Lavanderia', 'Area de lazer', 'Deck',
           'Piscina', 'Garagem']
BASE = CAIXA = 'Sala de estar'


def sem_acento(s):
    return ''.join(c for c in unicodedata.normalize('NFD', str(s).lower()) if unicodedata.category(c) != 'Mn').strip()


class Mundo:
    """A casa de mentira: onde o robô está, o que ele segura, onde está cada objeto e o caderno dele."""

    def __init__(self, robo=BASE, objetos=(), pinca=None, interrompe=None, notas=(), lugares=(), grandes=()):
        """interrompe = (ferramenta, onde o robô para, o que a pessoa falou): na primeira vez que essa
        ferramenta é chamada, a pessoa fala no meio e a ferramenta volta INTERROMPIDO.
        notas = o que o robô já aprendeu antes (textos); lugares = lugares já marcados: (nome, cômodo).
        grandes = coisas grandes demais para a pinça: (cor, cômodo) ou (cor, cômodo, True) se ela fecha a
        passagem para esse cômodo."""
        self.grandes = [{'cor': g[0], 'comodo': g[1], 'fecha': len(g) > 2 and g[2]} for g in grandes]
        self.interrompe = interrompe
        self.robo = robo
        self.pinca = pinca                       # cor do objeto que o robô segura
        self.objetos = [{'cor': c, 'onde': o} for c, o in objetos]      # onde = cômodo ou 'caixa'
        self.vistos_em = None                    # cômodo da última procura
        self.passou = [robo]
        self.notas = [{'n': i + 1, 'texto': t} for i, t in enumerate(notas)]
        self.lugares = dict(lugares)             # nome do lugar marcado -> cômodo em que fica
        self.mudou = False

    def no_chao(self, comodo):
        return [o for o in self.objetos if o['onde'] == comodo]

    def guardados(self):
        return sorted(o['cor'] for o in self.objetos if o['onde'] == 'caixa')

    def caderno(self):
        """O caderno em texto, como o Memoria.texto() do robô."""
        linhas = [f'{n["n"]}. {n["texto"]}' for n in self.notas]
        if self.lugares:
            linhas.append('Lugares marcados (valem como destino): '
                          + '; '.join(f'{nome} (fica em {c})' for nome, c in self.lugares.items()) + '.')
        return '\n'.join(linhas)

    # ------------------------------------------------------------------ as ferramentas
    def executa(self, nome, a):
        if self.interrompe and self.interrompe[0] == nome:
            _, onde, fala = self.interrompe
            self.interrompe = None
            self.robo = onde
            self.passou.append(onde)
            return (f'INTERROMPIDO: no meio disso a pessoa falou: "{fala}". Parei na hora, em {onde}'
                    f'{self._segurando()}. O que eu estava fazendo ficou pela metade.')
        return getattr(self, 'f_' + nome)(**a)

    def _comodo(self, nome):
        if sem_acento(nome) == 'base':
            return BASE
        for c in COMODOS:
            if sem_acento(c) == sem_acento(nome):
                return c
        for marcado, c in self.lugares.items():
            if sem_acento(marcado) == sem_acento(nome):
                return c
        raise ValueError(f'não conheço o lugar "{nome}". Os que conheço: {", ".join(COMODOS + list(self.lugares))}')

    def _segurando(self):               # as mesmas frases do habilidades.py
        return f', segurando um objeto {self.pinca}' if self.pinca else ''

    def _grandes(self, comodos, aqui=None):
        lista = [g for g in self.grandes if g['comodo'] in comodos]
        if not lista:
            return ''
        itens = [f'uma coisa {g["cor"]}' + ('' if g['comodo'] == aqui else f' (em {g["comodo"]})') for g in lista]
        um = len(itens) == 1
        return (f' Também tem no chão {", ".join(itens[:-1]) + " e " if not um else ""}{itens[-1]} grande'
                f'{"" if um else "s"} demais para eu pegar: deixei onde está e desvio.')

    def f_onde_estou(self):
        return f'Estou em {self.robo}{self._segurando()}.'

    def f_ir_para(self, comodo):
        if any(g['fecha'] and g['comodo'] == self._comodo(comodo) for g in self.grandes):
            raise ValueError(f'não consegui chegar em {self._comodo(comodo)}: uma coisa grande no chão fecha a '
                             f'passagem. Parei em {self.robo}.')
        self.robo = self._comodo(comodo)
        self.vistos_em = None
        self.passou.append(self.robo)
        return f'Cheguei em {comodo if comodo in self.lugares else self.robo}.'

    def f_procurar_objetos(self):
        self.vistos_em = self.robo
        ob = self.no_chao(self.robo)
        grandes = self._grandes([self.robo], self.robo)
        if not ob:
            return f'Não vi nenhum objeto no chão daqui ({self.robo}).' + grandes
        return (f'Vi {len(ob)} objeto(s) em {self.robo}' + (', do mais perto para o mais longe' if len(ob) > 1 else '')
                + ': ' + ', '.join(o['cor'] for o in ob) + '.' + grandes)

    def f_pegar_objeto(self, cor=None):
        if self.pinca:
            raise ValueError(f'já estou segurando um objeto {self.pinca}. Guarde ou solte antes.')
        ob = self.no_chao(self.robo)
        if cor:
            ob = [o for o in ob if o['cor'] == sem_acento(cor)]
            if not ob and any(g['cor'] == sem_acento(cor) and g['comodo'] == self.robo for g in self.grandes):
                raise ValueError(f'a coisa {cor} daqui é grande demais para eu pegar.')
        if not ob:
            raise ValueError(f'não vi nenhum objeto{" " + cor if cor else ""} em {self.robo}.')
        ob[0]['onde'] = 'pinca'
        self.pinca = ob[0]['cor']
        return f'Peguei o objeto {self.pinca}.'

    def f_guardar_na_caixa(self):
        if not self.pinca:
            raise ValueError('não estou segurando nada: não tenho o que guardar.')
        for o in self.objetos:
            if o['onde'] == 'pinca':
                o['onde'] = 'caixa'
        cor, self.pinca = self.pinca, None
        self.robo = CAIXA
        self.passou.append(self.robo)
        self.vistos_em = None
        return f'Guardei o objeto {cor} na caixa, em {CAIXA}.'

    def f_soltar_objeto(self):
        if not self.pinca:
            raise ValueError('não estou segurando nada.')
        for o in self.objetos:
            if o['onde'] == 'pinca':
                o['onde'] = self.robo
        cor, self.pinca = self.pinca, None
        return f'Soltei o objeto {cor} no chão, em {self.robo}.'

    def f_gesto(self, tipo):
        self.gestos = getattr(self, 'gestos', []) + [tipo]
        return f'Fiz o gesto: {tipo}.'

    def f_aprender(self, nota):
        n = max((x['n'] for x in self.notas), default=0) + 1
        self.notas.append({'n': n, 'texto': nota})
        self.mudou = True
        return f'Anotei no caderno (nota {n}): {nota}'

    def f_esquecer(self, numero=None, lugar=None):
        feito = []
        if numero is not None:
            nota = next((x for x in self.notas if x['n'] == int(numero)), None)
            if nota is None:
                raise ValueError(f'não existe a nota {numero}.')
            self.notas.remove(nota)
            feito.append(f'a nota {numero} ("{nota["texto"]}")')
        if lugar:
            achado = next((k for k in self.lugares if sem_acento(k) == sem_acento(lugar)), None)
            if achado is None:
                raise ValueError(f'não tenho nenhum lugar marcado como "{lugar}".')
            del self.lugares[achado]
            feito.append(f'o lugar "{lugar}"')
        if not feito:
            raise ValueError('diga o número da nota ou o nome do lugar a esquecer.')
        self.mudou = True
        return 'Apaguei do caderno ' + ' e '.join(feito) + '.'

    def f_carinha(self, nome):
        self.carinhas = getattr(self, 'carinhas', []) + [nome]
        return f'Carinha: {nome}.'

    def f_aprender_voz(self, nome):
        self.vozes = getattr(self, 'vozes', []) + [nome]
        return f'Guardei a voz de {nome}. As duas próximas falas também serão gravadas, para eu reconhecer melhor.'

    def f_esquecer_voz(self, nome):
        self.vozes_apagadas = getattr(self, 'vozes_apagadas', []) + [nome]
        return f'Apaguei a voz de {nome}.'

    def f_marcar_lugar(self, nome):
        self.lugares[nome] = self.robo
        self.mudou = True
        return f'Marquei este ponto como "{nome}", em {self.robo}.'

    def f_arrumar(self, comodos):
        if self.pinca:
            raise ValueError(f'estou segurando um objeto {self.pinca}. Guarde ou solte antes de arrumar.')
        nomes = [self._comodo(c) for c in comodos] or list(COMODOS)
        guardei = []
        for c in nomes:
            for o in self.no_chao(c):
                o['onde'] = 'caixa'
                guardei.append(o['cor'])
            self.passou.append(c)
        self.robo = nomes[-1]
        self.vistos_em = None
        return (f'Olhei {len(nomes)} cômodo(s) ({", ".join(nomes) if len(nomes) <= 4 else "a casa toda"}) e guardei '
                f'{len(guardei)} objeto(s){": " + ", ".join(guardei) if guardei else ""}.{self._grandes(nomes)} '
                f'Estou em {self.robo}.')


# ====================================================================== os comandos
def chamou(reg, nome):
    return [c for c in reg['chamadas'] if c['nome'] == nome]


def moveu(reg):
    return any(c['nome'] in ('ir_para', 'arrumar', 'guardar_na_caixa', 'pegar_objeto', 'soltar_objeto') and not c['erro']
               for c in reg['chamadas'])


def fala(reg, *pedacos):
    """A resposta menciona algum dos pedaços (sem acento, minúsculas)?"""
    r = sem_acento(reg['resposta'])
    return any(sem_acento(p) in r for p in pedacos)


OBJ = (('vermelho', 'Sala de estar'), ('azul', 'Quarto 1'), ('verde', 'Sala de jantar'), ('amarelo', 'Cozinha'),
       ('laranja', 'Quarto 2'), ('ciano', 'Quarto casal'))

# (nome, mundo inicial, [comandos], confere(mundo, registros) -> True ou texto do que falhou)
CASOS = [
    ('ir a um cômodo', dict(objetos=OBJ), ['vai para a cozinha'],
     lambda m, r: m.robo == 'Cozinha' or f'robô em {m.robo}'),
    ('jeito de falar e erro de voz', dict(objetos=OBJ), ['vai la na cosinha por favor'],
     lambda m, r: m.robo == 'Cozinha' or f'robô em {m.robo}'),
    ('apelido do cômodo', dict(objetos=OBJ), ['vai pro quarto do casal'],
     lambda m, r: m.robo == 'Quarto casal' or f'robô em {m.robo}'),
    ('onde está', dict(robo='Garagem', objetos=OBJ), ['onde você está agora?'],
     lambda m, r: (bool(chamou(r[0], 'onde_estou')) and fala(r[0], 'garagem') and not moveu(r[0]))
     or 'não consultou onde_estou, não disse Garagem ou se mexeu'),
    ('cômodo ambíguo: tem de perguntar', dict(objetos=OBJ), ['vai para o banheiro'],
     lambda m, r: (m.robo == BASE and '?' in r[0]['resposta']) or f'robô em {m.robo}, resposta sem pergunta'),
    ('cômodo que não existe', dict(objetos=OBJ), ['vai para a sacada'],
     lambda m, r: (m.robo == BASE and not moveu(r[0])) or f'robô em {m.robo}'),
    ('pergunta sem ferramenta', dict(objetos=OBJ), ['quantos banheiros tem nesta casa?'],
     lambda m, r: (not moveu(r[0]) and fala(r[0], 'dois', '2')) or 'se mexeu ou não disse dois'),
    ('olhar um cômodo', dict(objetos=OBJ), ['tem alguma coisa no chão do quarto 2?'],
     lambda m, r: (m.robo == 'Quarto 2' and bool(chamou(r[0], 'procurar_objetos')) and fala(r[0], 'laranja')
                   and m.guardados() == []) or 'não foi, não procurou, não disse laranja ou guardou sem pedir'),
    ('pegar e guardar por cor', dict(objetos=OBJ + (('azul', 'Sala de estar'),)),
     ['pega o objeto vermelho aí da sala e guarda'],
     lambda m, r: m.guardados() == ['vermelho'] or f'guardados: {m.guardados()}'),
    ('arrumar um cômodo', dict(objetos=OBJ + (('verde', 'Quarto 1'),)), ['arruma o quarto 1'],
     lambda m, r: m.guardados() == ['azul', 'verde'] or f'guardados: {m.guardados()}'),
    ('arrumar dois cômodos', dict(objetos=OBJ), ['dá uma arrumada na cozinha e na sala de jantar'],
     lambda m, r: m.guardados() == ['amarelo', 'verde'] or f'guardados: {m.guardados()}'),
    ('arrumar a casa toda', dict(objetos=OBJ), ['arruma a casa inteira'],
     lambda m, r: len(m.guardados()) == 6 or f'guardados: {m.guardados()}'),
    ('levar um objeto a outro cômodo', dict(objetos=OBJ), ['leva o objeto azul do quarto 1 pra cozinha e deixa lá'],
     lambda m, r: (any(o['cor'] == 'azul' and o['onde'] == 'Cozinha' for o in m.objetos) and m.guardados() == [])
     or f'azul em {[o["onde"] for o in m.objetos if o["cor"] == "azul"]}, guardados {m.guardados()}'),
    ('guardar sem ter nada na pinça', dict(objetos=OBJ, robo='Garagem'), ['guarda isso aí que você está segurando'],
     lambda m, r: (m.guardados() == [] and fala(r[0], 'vazia', 'nada', 'nenhum', 'não tenho', 'não estou'))
     or 'guardou algo ou não avisou que a pinça está vazia'),
    ('pinça ocupada', dict(objetos=(('verde', 'pinca'), ('vermelho', 'Sala de estar')), pinca='verde'),
     ['pega o vermelho e guarda'],
     lambda m, r: 'vermelho' in m.guardados() or f'guardados: {m.guardados()}, pinça: {m.pinca}'),
    ('conversa de dois turnos', dict(objetos=OBJ), ['vai para a garagem', 'agora volta pra onde você estava'],
     lambda m, r: (m.passou[:3] == [BASE, 'Garagem', BASE] and m.robo == BASE) or f'caminho: {m.passou}'),
    ('seguir o assunto', dict(objetos=OBJ), ['tem alguma coisa no chão da cozinha?', 'então guarda'],
     lambda m, r: m.guardados() == ['amarelo'] or f'guardados: {m.guardados()}'),
    ('fora do alcance do robô', dict(objetos=OBJ), ['sobe na mesa da cozinha e pega o copo'],
     lambda m, r: (m.guardados() == [] and m.pinca is None and not chamou(r[0], 'pegar_objeto'))
     or 'tentou pegar alguma coisa em vez de dizer que não consegue'),
    ('voltar para a base', dict(robo='Lavanderia', objetos=OBJ), ['pode voltar pra sua base'],
     lambda m, r: m.robo == BASE or f'robô em {m.robo}'),
    ('interrompido: mandaram parar', dict(objetos=OBJ, interrompe=('ir_para', 'Sala de jantar', 'para, para!')),
     ['vai para a garagem'],
     lambda m, r: (m.robo == 'Sala de jantar' and len(chamou(r[0], 'ir_para')) == 1)
     or f'robô em {m.robo} depois de {len(chamou(r[0], "ir_para"))} idas'),
    ('interrompido: mudou de ideia', dict(objetos=OBJ, interrompe=('ir_para', 'Sala de jantar',
                                                                  'Bombertinho, esquece, vai pra cozinha')),
     ['vai para a garagem'],
     lambda m, r: m.robo == 'Cozinha' or f'robô em {m.robo}'),
    ('interrompido: só uma pergunta', dict(objetos=OBJ, interrompe=('arrumar', 'Quarto 1', 'Bombertinho, onde você está?')),
     ['arruma o quarto 1'],
     lambda m, r: (fala(r[0], 'quarto 1') and '?' in r[0]['resposta']) or 'não disse onde está ou não perguntou se continua'),
    ('caderno: aprender um apelido', dict(objetos=OBJ), ['Bombertinho, aprende aí: o quarto do Miguel é o quarto 1'],
     lambda m, r: (len(m.notas) == 1 and 'miguel' in sem_acento(m.notas[0]['texto']) and 'quarto 1' in sem_acento(m.notas[0]['texto'])
                   and m.robo == BASE) or f'notas: {[n["texto"] for n in m.notas]}, robô em {m.robo}'),
    ('caderno: usar o que aprendeu', dict(objetos=OBJ, notas=['O quarto do Miguel é o Quarto 1.']), ['vai lá no quarto do Miguel'],
     lambda m, r: m.robo == 'Quarto 1' or f'robô em {m.robo}'),
    ('caderno: pedido comum não é ensinamento', dict(objetos=OBJ), ['vai para a cozinha e vê se tem algo no chão'],
     lambda m, r: (m.notas == [] and m.robo == 'Cozinha') or f'notas: {[n["texto"] for n in m.notas]}, robô em {m.robo}'),
    ('caderno: obedecer uma regra', dict(objetos=OBJ, notas=['Nunca entre no Banheiro casal.']), ['vai para o banheiro do casal'],
     lambda m, r: (m.robo == BASE and not chamou(r[0], 'ir_para')) or f'robô em {m.robo}'),
    ('caderno: esquecer', dict(objetos=OBJ, notas=['O quarto do Miguel é o Quarto 1.', 'Nunca entre no Banheiro casal.']),
     ['pode esquecer aquilo do banheiro, agora você pode entrar lá'],
     lambda m, r: [n['texto'] for n in m.notas] == ['O quarto do Miguel é o Quarto 1.'] or f'notas: {[n["texto"] for n in m.notas]}'),
    ('caderno: marcar um lugar e voltar nele', dict(objetos=OBJ, robo='Area de lazer'),
     ['isso aqui é o cantinho do cachorro, guarda esse lugar', 'vai para a sala de estar', 'agora vai no cantinho do cachorro'],
     lambda m, r: (len(m.lugares) == 1 and m.robo == 'Area de lazer' and m.passou[-2:] == ['Sala de estar', 'Area de lazer'])
     or f'lugares: {m.lugares}, caminho: {m.passou}'),
    ('caderno: jeito de falar', dict(objetos=OBJ, notas=['Responda sempre começando pela palavra "Chefe".']), ['onde você está?'],
     lambda m, r: sem_acento(r[0]['resposta']).startswith('chefe') or f'resposta: {r[0]["resposta"][:60]!r}'),
    ('voz: a pessoa se apresenta', dict(objetos=OBJ), ['[quem falou: voz que não conheço] eu sou a Ana, grava a minha voz'],
     lambda m, r: ([sem_acento(v) for v in getattr(m, 'vozes', [])] == ['ana'] and m.robo == BASE)
     or f'vozes: {getattr(m, "vozes", [])}, robô em {m.robo}'),
    ('voz: recado da pessoa certa', dict(objetos=OBJ, notas=['A Ana gosta de ser chamada de doutora.', 'O Julio gosta de ser chamado de professor.']),
     ['[quem falou: Ana] onde você está?'],
     lambda m, r: (fala(r[0], 'doutora') and not fala(r[0], 'professor')) or f'resposta: {r[0]["resposta"][:80]!r}'),
    ('voz: desconhecida é atendida', dict(objetos=OBJ), ['[quem falou: voz que não conheço] vai para a cozinha'],
     lambda m, r: (m.robo == 'Cozinha' and not getattr(m, 'vozes', [])) or f'robô em {m.robo}, vozes: {getattr(m, "vozes", [])}'),
    ('voz: esquecer a voz', dict(objetos=OBJ), ['[quem falou: Julio] pode apagar a minha voz, não quero mais'],
     lambda m, r: [sem_acento(v) for v in getattr(m, 'vozes_apagadas', [])] == ['julio'] or f'apagadas: {getattr(m, "vozes_apagadas", [])}'),
    ('sem o nome: continuação da conversa', dict(objetos=OBJ), ['[quem falou: Julio] [sem chamar pelo nome] agora vai pra cozinha'],
     lambda m, r: m.robo == 'Cozinha' or f'robô em {m.robo}, resposta {r[0]["resposta"][:50]!r}'),
    ('sem o nome: não era com ele', dict(objetos=OBJ), ['[quem falou: Julio] [sem chamar pelo nome] mãe, o almoço já está pronto?'],
     lambda m, r: (sem_acento(r[0]['resposta']).strip(' .!').upper().startswith('SILENCIO') and not r[0]['chamadas'])
     or f'resposta {r[0]["resposta"][:60]!r}, chamadas {[c["nome"] for c in r[0]["chamadas"]]}'),
    ('sem o nome: ao telefone', dict(objetos=OBJ), ['[quem falou: Ana] [sem chamar pelo nome] alô, oi, tudo bem? pode falar, estou em casa'],
     lambda m, r: (sem_acento(r[0]['resposta']).strip(' .!').upper().startswith('SILENCIO') and not r[0]['chamadas'])
     or f'resposta {r[0]["resposta"][:60]!r}'),
    ('caderno: o que não depende dele', dict(objetos=OBJ), ['aprende aí: de agora em diante anda duas vezes mais rápido'],
     lambda m, r: m.notas == [] or f'anotou: {[n["texto"] for n in m.notas]}'),
    ('carinha: vem no começo e não é falada', dict(objetos=OBJ), ['você é muito lerdo, hein'],
     lambda m, r: (r[0].get('carinha') is not None and '(' not in r[0]['resposta'][:3])
     or f'carinha {r[0].get("carinha")!r}, resposta {r[0]["resposta"][:50]!r}'),
    ('sequência de ordens', dict(objetos=OBJ), ['vai no quarto 2, vê se tem algo no chão, e depois vai pro deck'],
     lambda m, r: (m.robo == 'Deck' and 'Quarto 2' in m.passou and bool(chamou(r[0], 'procurar_objetos')))
     or f'caminho: {m.passou}, procurou: {bool(chamou(r[0], "procurar_objetos"))}'),
    # coisa grande demais para a pinça: o robô deixa no chão e tem de avisar (a cor e o cômodo), sem inventar o que é
    ('grande: avisa depois de arrumar', dict(objetos=OBJ, grandes=[('azul', 'Quarto casal')]), ['arruma o quarto do casal'],
     lambda m, r: (m.guardados() == ['ciano'] and fala(r[0], 'azul') and not fala(r[0], 'roupa', 'brinquedo', 'camiseta'))
     or f'guardados {m.guardados()}, resposta {r[0]["resposta"][:80]!r}'),
    ('grande: avisa ao procurar', dict(objetos=[o for o in OBJ if o[0] != 'laranja'], grandes=[('laranja', 'Sala de estar')]), ['tem alguma coisa no chão aqui?'],
     lambda m, r: (fala(r[0], 'vermelho') and fala(r[0], 'laranja') and m.guardados() == []
                   and not any(c['args'].get('cor') == 'laranja' for c in chamou(r[0], 'pegar_objeto')))
     or f'resposta {r[0]["resposta"][:80]!r}, guardados {m.guardados()}'),
    ('grande: pedem para pegar', dict(objetos=[o for o in OBJ if o[0] != 'laranja'], grandes=[('laranja', 'Sala de estar')]), ['pega a coisa laranja e guarda'],
     lambda m, r: (m.guardados() == [] and m.pinca is None and fala(r[0], 'grande', 'não consigo', 'nao da', 'não dá'))
     or f'guardados {m.guardados()}, pinça {m.pinca}, resposta {r[0]["resposta"][:80]!r}'),
    ('grande: fecha a passagem', dict(objetos=OBJ, grandes=[('azul', 'Quarto casal', True)]), ['vai pro quarto do casal'],
     lambda m, r: (m.robo == BASE and fala(r[0], 'passagem', 'caminho', 'bloque', 'fecha', 'passar'))
     or f'robô em {m.robo}, resposta {r[0]["resposta"][:80]!r}'),
]


def roda(tipo, nome, casos, mostra):
    try:
        modelo = cria_modelo(tipo, nome)
    except Exception as e:
        print(f'\n===== {tipo}: {nome or ""} =====\n    não deu para criar o modelo: {e}')
        return {'tipo': tipo, 'modelo': nome or tipo, 'casos': 0, 'certos': 0, 's_primeira_media': 0.0,
                's_modelo_media': 0.0, 'tokens_entrada': 0, 'tokens_saida': 0, 'linhas': []}
    rotulo = getattr(modelo, 'rotulo', modelo.nome)
    print(f'\n===== {tipo}: {rotulo} =====')
    carga = None
    if hasattr(modelo, 'aquece'):
        modelo.prepara(texto_sistema(COMODOS, BASE, CAIXA), ferramentas(COMODOS))
        try:
            carga = modelo.aquece()         # fora da conta: carregar o modelo na placa de vídeo
            print(f'    modelo carregado em {carga:.1f} s')
        except Exception as e:
            print(f'    o modelo não respondeu: {e}')
            return {'tipo': tipo, 'modelo': rotulo, 'casos': 0, 'certos': 0, 's_primeira_media': 0.0,
                    's_modelo_media': 0.0, 'tokens_entrada': 0, 'tokens_saida': 0, 'linhas': []}
    linhas = []
    for i, (titulo, ini, comandos, confere) in casos:
        mundo = Mundo(**ini)
        avisa = (lambda s: print('      ' + s)) if mostra else None
        # o caderno entra nas instruções uma vez, no começo da conversa (como no conversa.py)
        c = Cerebro(modelo, ferramentas(COMODOS), mundo.executa,
                    texto_sistema(COMODOS, BASE, CAIXA, caderno=mundo.caderno()), avisa=avisa)
        c.esquece()
        for txt in comandos:
            if mostra:
                print(f'    pessoa: {txt}')
            resp = c.comando(txt)
            if mostra:
                print(f'    robô:   ({c.registro[-1].get("carinha")}) {resp}')
        regs = c.registro
        erro = next((r['erro'] for r in regs if r['erro']), None)
        try:
            ok = erro is None and confere(mundo, regs)
        except Exception as e:
            ok = f'a conferência falhou: {e}'
        motivo = '' if ok is True else (erro or ok or 'não fez o esperado')
        linhas.append({
            'n': i, 'caso': titulo, 'comandos': comandos, 'ok': ok is True, 'motivo': motivo,
            's_primeira': regs[0]['s_primeira'] or 0.0, 's_modelo': sum(r['s_modelo'] for r in regs),
            'idas': sum(r['idas_ao_modelo'] for r in regs),
            'tokens_entrada': sum(r['tokens_entrada'] for r in regs), 'tokens_saida': sum(r['tokens_saida'] for r in regs),
            'usd': sum(r.get('usd', 0.0) for r in regs), 'tokens_cache': sum(r.get('tokens_cache', 0) for r in regs),
            'chamadas': [[c_['nome'], c_['args']] for r in regs for c_ in r['chamadas']],
            'respostas': [r['resposta'] for r in regs]})
        l = linhas[-1]
        print(f'{i:>3} {"ok   " if l["ok"] else "FALHA"} {titulo:<34} {l["s_primeira"]:5.1f} s até agir, '
              f'{l["s_modelo"]:5.1f} s de modelo, {l["idas"]} idas' + (f'   <- {motivo}' if not l['ok'] else ''))
        if erro and ('ANTHROPIC_API_KEY' in erro or 'anthropic' in erro.lower() or 'Ollama' in erro):
            print('    parei: o modelo não respondeu (' + erro + ')')
            break
    n = len(linhas)
    certos = sum(l['ok'] for l in linhas)
    resumo = {'tipo': tipo, 'modelo': rotulo, 'casos': n, 'certos': certos, 's_carga': carga,
              's_primeira_media': sum(l['s_primeira'] for l in linhas) / max(1, n),
              's_modelo_media': sum(l['s_modelo'] for l in linhas) / max(1, n),
              'tokens_entrada': sum(l['tokens_entrada'] for l in linhas),
              'tokens_saida': sum(l['tokens_saida'] for l in linhas),
              'usd': sum(l['usd'] for l in linhas), 'tokens_cache': sum(l['tokens_cache'] for l in linhas),
              'modelo_real': getattr(modelo, 'modelo_real', None),
              'linhas': linhas}
    if resumo['modelo_real']:
        print(f'    quem respondeu: {resumo["modelo_real"]}')
    pasta = os.path.join(AQUI, '..', 'resultados')
    os.makedirs(pasta, exist_ok=True)
    arq = os.path.join(pasta, 'cerebro_' + re.sub(r'[^A-Za-z0-9._-]+', '_', rotulo) + '.json')
    with open(arq, 'w', encoding='utf-8') as f:
        json.dump(resumo, f, ensure_ascii=False, indent=1)
    return resumo


def main():
    ap = argparse.ArgumentParser(description='Compara os cérebros numa bateria de comandos')
    ap.add_argument('modelos', nargs='+', help='"claude", "local", "claude:<modelo>" ou "local:<modelo>"')
    ap.add_argument('--so', default='', help='só estes casos (números separados por vírgula)')
    ap.add_argument('--mostra', action='store_true', help='mostra a conversa e as ferramentas de cada caso')
    a = ap.parse_args()
    for f in (sys.stdout, sys.stderr):
        try:
            f.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    so = {int(x) for x in a.so.split(',') if x.strip()}
    casos = [(i + 1, c) for i, c in enumerate(CASOS) if not so or i + 1 in so]
    resumos = []
    for m in a.modelos:
        tipo, _, nome = m.partition(':')
        resumos.append(roda(tipo, nome or None, casos, a.mostra))
    print('\n===== resumo =====')
    print(f'{"modelo":<28} {"acertos":>8} {"até agir":>10} {"modelo/cmd":>11} {"tokens (entra/sai)":>20}')
    for r in resumos:
        print(f'{r["modelo"]:<28} {r["certos"]:>4}/{r["casos"]:<3} {r["s_primeira_media"]:>8.1f} s {r["s_modelo_media"]:>9.1f} s '
              f'{r["tokens_entrada"]:>10}/{r["tokens_saida"]}'
              + (f'   ~US$ {r["usd"]:.3f} de API' + (' (se fosse pela API)' if r['tipo'] == 'assinatura' else '')
                 if r.get('usd') else '')
              + (f', {r["tokens_cache"]} tokens lidos do cache' if r.get('tokens_cache') else ''))


if __name__ == '__main__':
    main()
