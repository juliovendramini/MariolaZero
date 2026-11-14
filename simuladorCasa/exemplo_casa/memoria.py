"""O caderno do robô: o que as pessoas da casa ensinaram, guardado num arquivo para valer nas próximas
conversas.

O modelo de linguagem não muda nem é treinado de novo. "Aprender", aqui, é anotar: quando alguém
ensina alguma coisa ("o quarto do Miguel é o Quarto 1", "não entra no banheiro", "fala menos"), o
cérebro chama a ferramenta aprender e a nota vai para este arquivo; no começo de cada conversa as
notas entram nas instruções dele (cerebro.texto_sistema). Há também os lugares marcados: um ponto do
mapa com um nome ("o cantinho do cachorro"), que vira destino do ir_para.

O arquivo é um JSON legível, que dá para abrir e arrumar à mão:
    {"notas": [{"n": 1, "texto": "...", "quando": "2026-11-12"}],
     "lugares": [{"nome": "...", "x": 1234, "y": 5678, "comodo": "Sala de estar", "quando": "..."}]}

Onde fica: a variável CEREBRO_MEMORIA, senão memoria/caderno.json ao lado da pasta do programa.
"""

import datetime
import json
import os
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
MAX_NOTAS = 60               # mais que isso o caderno vira bagunça (e gasta instrução): é hora de uma faxina


def _chave(s):
    return ''.join(c for c in unicodedata.normalize('NFD', str(s).lower()) if unicodedata.category(c) != 'Mn').strip(' .!?')


class Memoria:
    def __init__(self, caminho=None):
        self.caminho = caminho or os.environ.get('CEREBRO_MEMORIA') or os.path.join(AQUI, '..', 'memoria', 'caderno.json')
        self.notas, self.lugares = [], []
        self.mudou = False                  # o programa olha isto para refazer as instruções do cérebro
        if os.path.exists(self.caminho):
            try:
                with open(self.caminho, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                self.notas = list(d.get('notas', []))
                self.lugares = list(d.get('lugares', []))
            except (OSError, ValueError) as e:
                print(f'[memória] não consegui ler {self.caminho} ({e}): começo com o caderno vazio')

    def _grava(self):
        self.mudou = True
        os.makedirs(os.path.dirname(os.path.abspath(self.caminho)), exist_ok=True)
        tmp = self.caminho + '.novo'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'notas': self.notas, 'lugares': self.lugares}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.caminho)       # troca de uma vez: uma queda de energia não deixa o arquivo pela metade

    # ------------------------------------------------------------------ notas
    def aprende(self, texto):
        """Guarda uma nota. Devolve o número dela."""
        texto = ' '.join(str(texto).split())
        if not texto:
            raise ValueError('a nota está vazia.')
        for nota in self.notas:
            if _chave(nota['texto']) == _chave(texto):
                return nota['n']             # já sabia
        if len(self.notas) >= MAX_NOTAS:
            raise ValueError(f'o caderno está cheio ({MAX_NOTAS} notas). Peça para a pessoa mandar esquecer alguma.')
        n = max((nota['n'] for nota in self.notas), default=0) + 1
        self.notas.append({'n': n, 'texto': texto, 'quando': datetime.date.today().isoformat()})
        self._grava()
        return n

    def esquece(self, numero):
        """Apaga a nota de número 'numero'. Devolve o texto dela."""
        for i, nota in enumerate(self.notas):
            if nota['n'] == int(numero):
                del self.notas[i]
                self._grava()
                return nota['texto']
        raise ValueError(f'não existe a nota {numero}. As que existem: {", ".join(str(n["n"]) for n in self.notas) or "nenhuma"}.')

    # ------------------------------------------------------------------ lugares
    def marca_lugar(self, nome, x, y, comodo):
        nome = ' '.join(str(nome).split()).strip(' .!?')
        if not nome:
            raise ValueError('o lugar precisa de um nome.')
        self.lugares = [l for l in self.lugares if _chave(l['nome']) != _chave(nome)]      # marcar de novo = mudar de lugar
        self.lugares.append({'nome': nome, 'x': round(float(x)), 'y': round(float(y)), 'comodo': comodo,
                             'quando': datetime.date.today().isoformat()})
        self._grava()

    def lugar(self, nome):
        """O lugar marcado com esse nome (dicionário) ou None."""
        for l in self.lugares:
            if _chave(l['nome']) == _chave(nome):
                return l
        return None

    def esquece_lugar(self, nome):
        l = self.lugar(nome)
        if l is None:
            raise ValueError(f'não tenho nenhum lugar marcado como "{nome}".')
        self.lugares.remove(l)
        self._grava()

    def nomes_dos_lugares(self):
        return [l['nome'] for l in self.lugares]

    # ------------------------------------------------------------------ para as instruções do cérebro
    def texto(self):
        """O caderno em texto, para entrar nas instruções ('' se está vazio)."""
        linhas = [f'{nota["n"]}. {nota["texto"]}' for nota in self.notas]
        if self.lugares:
            linhas.append('Lugares marcados (valem como destino): '
                          + '; '.join(f'{l["nome"]} (fica em {l["comodo"]})' for l in self.lugares) + '.')
        return '\n'.join(linhas)
