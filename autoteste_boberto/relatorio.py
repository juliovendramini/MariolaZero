"""Relatório do autoteste: cada resultado vai para o terminal e para um arquivo na hora
(se o programa travar no meio, o que já foi testado fica gravado).

Níveis: OK, AVISO (funciona, mas tem algo estranho), FALHA (não funciona), INFO (só um valor
medido) e PULOU (não testado: ninguém respondeu, VOLTAR, ou faltou algo para testar).
"""

import datetime
import os

OK, AVISO, FALHA, INFO, PULOU = 'OK', 'AVISO', 'FALHA', 'INFO', 'PULOU'


class Item:
    def __init__(self, secao, nivel, texto, dica):
        self.secao = secao
        self.nivel = nivel
        self.texto = texto
        self.dica = dica


class Relatorio:
    def __init__(self, pasta, cabecalho):
        self.itens = []
        self.secao_atual = ''
        self.caminho = None
        self._arq = None
        try:
            os.makedirs(pasta, exist_ok=True)
            nome = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S') + '.txt'
            self.caminho = os.path.join(pasta, nome)
            self._arq = open(self.caminho, 'a', encoding='utf-8', buffering=1)
        except OSError as erro:
            print(f'[relatório] não deu para criar o arquivo em {pasta}: {erro}')
        self._escreve(f'AUTOTESTE DO MARIOLA - {datetime.datetime.now():%d/%m/%Y %H:%M:%S}')
        for linha in cabecalho:
            self._escreve(linha)

    def _escreve(self, linha):
        print(linha, flush=True)
        if self._arq is not None:
            try:
                self._arq.write(linha + '\n')
            except OSError:
                self._arq = None

    def secao(self, nome):
        self.secao_atual = nome
        self._escreve('')
        self._escreve(f'== {nome} ' + '=' * max(0, 60 - len(nome)))

    def add(self, nivel, texto, dica=None):
        item = Item(self.secao_atual, nivel, texto, dica)
        self.itens.append(item)
        self._escreve(f'[{nivel:5s}] {texto}')
        if dica:
            self._escreve(f'        -> {dica}')
        return item

    def ok(self, texto, dica=None):
        return self.add(OK, texto, dica)

    def aviso(self, texto, dica=None):
        return self.add(AVISO, texto, dica)

    def falha(self, texto, dica=None):
        return self.add(FALHA, texto, dica)

    def info(self, texto, dica=None):
        return self.add(INFO, texto, dica)

    def pulou(self, texto, dica=None):
        return self.add(PULOU, texto, dica)

    @staticmethod
    def conta(itens):
        n = {OK: 0, AVISO: 0, FALHA: 0, PULOU: 0}
        for it in itens:
            if it.nivel in n:
                n[it.nivel] += 1
        return n

    @staticmethod
    def pior(itens):
        niveis = {it.nivel for it in itens}
        for nivel in (FALHA, AVISO, OK):
            if nivel in niveis:
                return nivel
        return None

    def fecha(self):
        n = self.conta(self.itens)
        self._escreve('')
        self._escreve(f'RESUMO: {n[OK]} ok, {n[AVISO]} avisos, {n[FALHA]} falhas, {n[PULOU]} não testados')
        for it in self.itens:
            if it.nivel in (FALHA, AVISO):
                self._escreve(f'  {it.nivel:5s} [{it.secao}] {it.texto}')
        if self._arq is not None:
            self._arq.close()
            self._arq = None
