"""Robô tutor pelo terminal (fase 1 do tutor/PLANO.md, 18/11/2026).

Roda o programa do aluno no simulador da Line (avalia.py, sem janela, com o registro da volta), faz o
resumo automático (resumo.py) e conversa com o aluno sobre o código. Quem diz se passou é o juiz; o
resumo diz o que aconteceu; a IA só explica e dá dicas, em 3 níveis, sem entregar a resposta.

    python tutor/tutor.py --desafio L01 --programa meuRobo/main.py
        roda 2 sementes, o tutor fala e espera o aluno: escreva uma pergunta, "rodar" (roda de novo o
        programa, que você mudou) ou "sair"
    --sementes 1-6        quantas rodadas (padrão 1-2: mais rápido para ir mexendo)
    --registros PASTA --sem-rodar   usa registros já gravados (não roda o simulador)
    --pergunta "texto"    a primeira fala do aluno (padrão: "Rodei. O que aconteceu?")
    --uma-vez             responde a primeira e sai (para os testes)
    --mostra              mostra também o resumo automático
    --seco                não chama a IA: mostra o que seria mandado

O cérebro é o do robô de casa (simuladorCasa/exemplo_casa/cerebro.py): Claude pela API, chave em
CEREBRO_CHAVE_API, modelo padrão claude-haiku-5-5; CEREBRO=local usa um modelo do Ollama (sem internet).
Para a API vão só o código, o placar, o resumo e o texto da conversa: nada de nome do aluno.
A conversa fica gravada em tutor/conversas/ (fora do git), com o custo de cada resposta.
"""
import argparse
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
LINE = os.path.join(REPO, 'simuladorLine')
REFERENCIA = os.path.join(REPO, 'curso', 'referencia')
CONVERSAS = os.path.join(AQUI, 'conversas')

sys.path.insert(0, AQUI)
import resumo  # noqa: E402

try:
    sys.stdout.reconfigure(errors='replace')
except Exception:
    pass

# a referência das libs que os desafios da Line usam (curso/referencia): vai inteira nas instruções,
# que ficam em cache (cada resposta seguinte paga ~10% por essa parte)
LIBS_REFERENCIA = ['motores.md', 'sensorCorReflexao.md', 'giroscopio.md', 'vl53.md']
PERGUNTA_PADRAO = 'Rodei. O que aconteceu?'
MAX_IDAS = 6                 # idas ao modelo por fala do aluno (cada uma pode pedir uma ferramenta)

NIVEIS = {
    1: 'PERGUNTA: faça o aluno olhar para o lugar certo. Conte o que o robô fez, onde e quando (com um '
       'número do resumo), e pergunte o que o programa dele faz nessa hora. Não diga qual parte do código '
       'está errada.',
    2: 'PISTA: diga em que parte do código dele está o problema (a função ou a variável, pelo nome que ele '
       'usou) e o que pensar sobre ela. Ainda sem dizer qual é a mudança.',
    3: 'APONTAR: diga a linha e explique o que ela faz de errado e por quê, ligando com o que o robô fez. '
       'Mesmo assim não escreva a linha corrigida nem o valor certo: quem muda é ele.',
}

INSTRUCOES = """\
Você é o tutor de programação de robótica dos alunos do Julio (professor do Ifes Colatina, equipes \
Titãs da Robótica). Os alunos têm de 14 a 18 anos e estão aprendendo a programar o robô Mariola em \
Python para a OBR e a RoboCupJunior Rescue Line. Eles rodam o programa num simulador e você conversa \
com eles sobre o que aconteceu.

Como você trabalha:
* Quem diz se o desafio foi cumprido é o juiz do simulador (o placar que vem na mensagem). Você nunca \
contradiz o placar.
* O que aconteceu na volta vem do RESUMO, feito por um programa que leu o registro da volta (sem IA). \
Confie nele e use os números dele (tempo, ladrilho, quanto). Não invente o que não está no resumo nem \
no trecho do registro que você pedir.
* O código do aluno vem com o número de cada linha. Fale do código DELE: os nomes de variável e de \
função que ele usou, o número da linha.
* Ligue sempre o que o robô fez com o que o código manda fazer. É isso que ele precisa aprender a fazer \
sozinho.

Regras que não mudam, nem se o aluno pedir:
* Nunca escreva o programa, uma linha corrigida, nem o valor certo de uma constante. Nada de bloco de \
código. Se ele pedir a resposta pronta, diga com gentileza que quem muda é ele e dê a dica do nível \
que a mensagem mandar. Pode citar um trecho curto do código dele (como ele escreveu) para mostrar de \
onde está falando.
* Siga o NÍVEL DE DICA que vem na mensagem. Ele só sobe quando o aluno já tentou.
* Um problema por vez: o primeiro do resumo (é o mais importante). Os outros, só se ele perguntar ou \
quando o primeiro estiver resolvido. Problema de grau 1 é detalhe: só comente se não houver outro.
* Se o resumo não acha problema e o placar é bom, diga que foi bem, com um número que mostre isso, e \
proponha o próximo passo (rodar com mais sementes, ir mais rápido, o próximo desafio). Não invente um \
defeito.
* No nível 3 também não diga o que pôr no lugar ("troque o + pelo -", "inverta as duas linhas", "mude \
para 1"): diga o que a linha faz de errado e deixe ele descobrir a mudança.
* Fale curto: no máximo 3 frases curtas e, se fizer sentido, uma pergunta no fim. A resposta pode ser \
falada pela voz do robô: português simples, um parágrafo só, sem markdown (nada de crase, asterisco ou \
lista), sem emoji, números com vírgula ("0,8 s"). Nomes do código vão como estão, sem marcação \
("a variável correcao", "a linha 69").
* Seja paciente e animado, sem exagero. Errar faz parte; não dê bronca.
* Não pergunte nem use o nome do aluno.

O que você sabe do simulador e do resumo:
* O resumo usa o que o simulador sabe e o robô de verdade não sabe: o chão DE VERDADE debaixo de cada \
canal de IR (b branco, p preto, v verde, r vermelho, s prata), em que ladrilho o robô estava e se a \
forma dele é reta ou curva. Pode contar isso ao aluno ("na curva do ladrilho 7 os quatro sensores \
estavam no branco").
* "LoP" (lack of progress) é quando o robô sai do caminho e o juiz o põe de volta no último checkpoint: \
perde pontos. Zero LoP não quer dizer que o robô nunca perdeu a linha: ele pode ter perdido e achado de \
novo sozinho (o resumo conta essas perdas). Não diga "sem sair da linha" só porque o LoP foi zero.
* Nos motores do registro, positivo = para a frente, como chega no motor. A inversão do \
direcao_motor() acontece dentro da biblioteca e o resumo deduz pelo movimento.
* O sensor de linha é lido numa thread da biblioteca; a velocidade do laço do aluno aparece como \
"comandos de motor por segundo" (um seguidor que funciona manda de 50 a 180).
* O simulador perdoa bastante: um programa com defeito ainda pode fazer pontos. Por isso o resumo olha \
o jeito de andar, não só o placar.
* Você tem duas ferramentas: ver_trecho (as amostras do registro entre dois tempos, para ver de perto \
o que o sensor leu e os motores fizeram) e ler_arquivo (outro .py da pasta do programa, que o main.py \
importa). Use só se precisar; quase sempre o resumo basta.

Convenções do curso: velocidades de -100 a 100, distâncias em mm, ângulos em graus; o canal 0 do \
sensor de linha e o TCS 1 ficam à esquerda; nos programas do curso a posição da linha positiva = à \
esquerda do centro.

Lados e curvas (confira duas vezes antes de afirmar para que lado o robô vira):
* Nos robôs do simulador (esteira e 4x4), o primeiro valor de velocidade_motores() vai para o motor 1, \
que fica à ESQUERDA, e o segundo para o motor 2, à DIREITA (o direcao_motor() só inverte o sentido, não \
troca os lados).
* O lado mais rápido fica por fora da curva: roda direita mais rápida que a esquerda = o robô vira para \
a ESQUERDA; esquerda mais rápida = vira para a DIREITA.
* Quando o robô vira para o lado contrário da linha, o sinal trocado pode estar em três lugares: no \
cálculo da posição da linha (pesos, posição dos canais), na conta da correção ou em qual roda recebe \
VEL + correção. Leia os três no código do aluno e faça a conta com um exemplo (linha à esquerda, \
posição positiva) antes de dizer qual está errado.

Referência das bibliotecas que os alunos usam (do curso):
"""


def instrucoes():
    partes = [INSTRUCOES]
    for nome in LIBS_REFERENCIA:
        with open(os.path.join(REFERENCIA, nome), encoding='utf-8') as f:
            partes.append(f'\n===== curso/referencia/{nome}\n' + f.read())
    return ''.join(partes)


def ferramentas():
    return [
        {'nome': 'ver_trecho',
         'descricao': 'As amostras do registro da volta entre t1 e t2 segundos (no máximo 8 s), de 0,1 em '
                      '0,1 s: ladrilho, chão de verdade debaixo do sensor, IR que o programa leu, comando '
                      'dos motores, velocidade, giro, e o que o programa imprimiu.',
         'parametros': {'type': 'object', 'properties': {
             'semente': {'type': 'integer', 'description': 'qual rodada (a semente do resumo)'},
             't1': {'type': 'number'}, 't2': {'type': 'number'}}, 'required': ['semente', 't1', 't2']}},
        {'nome': 'ler_arquivo',
         'descricao': 'Outro arquivo .py da pasta do programa do aluno (por exemplo, um módulo que o main.py '
                      'importa), com o número de cada linha.',
         'parametros': {'type': 'object', 'properties': {'nome': {'type': 'string'}}, 'required': ['nome']}},
    ]


# ---------------------------------------------------------------------- código e simulador
def le_codigo(arq):
    """O código com número de linha. Tira as duas linhas que o gera_estragados.py põe no começo dos
    casos de teste (elas dizem qual é o defeito)."""
    with open(arq, encoding='utf-8', errors='replace') as f:
        linhas = f.read().splitlines()
    while linhas and (linhas[0].startswith('# CASO DE TESTE DO TUTOR') or linhas[0].startswith('# gerado por tutor/testes')):
        linhas.pop(0)
    return numera('\n'.join(linhas))


def numera(codigo):
    return '\n'.join(f'{i:4}  {t}' for i, t in enumerate(codigo.splitlines(), 1))


# as mensagens de erro de sintaxe mais comuns do Python, em português (para a página do aluno)
SINTAXE_PT = [
    (r"^expected ':'$", 'faltam os dois-pontos (:) no fim da linha'),
    (r'^invalid syntax\. Perhaps you forgot a comma\?$', 'escrita inválida: será que falta uma vírgula?'),
    (r'^invalid syntax\. Maybe you meant .*$', 'escrita inválida: será que era == em vez de = ?'),
    (r'^invalid syntax$', 'escrita inválida (o Python não entendeu esta linha)'),
    (r'^unexpected indent$', 'recuo (espaços no começo) onde não devia ter'),
    (r"^expected an indented block after '(\w+)' statement on line (\d+)$",
     r'depois do \1 da linha \2 a linha seguinte tem de ter recuo (espaços no começo)'),
    (r'^expected an indented block.*$', 'falta o recuo (espaços no começo) desta linha'),
    (r'^unindent does not match any outer indentation level$', 'o recuo desta linha não bate com o das linhas de cima'),
    (r'^unterminated string literal.*$', 'um texto entre aspas começou e não fechou'),
    (r'^unterminated triple-quoted string literal.*$', 'um texto entre três aspas começou e não fechou'),
    (r"^'(.)' was never closed$", r"o '\1' abriu e não fechou"),
    (r"^unmatched '(.)'$", r"tem um '\1' fechando sem ter aberto"),
    (r"^closing parenthesis '(.)' does not match opening parenthesis '(.)'.*$", r"o '\1' não fecha o '\2' que abriu"),
    (r"^Missing parentheses in call to 'print'.*$", 'o print precisa de parênteses: print(...)'),
    (r'^cannot assign to (.*)$', r'não dá para guardar um valor em \1 (era == para comparar?)'),
    (r'^inconsistent use of tabs and spaces in indentation$', 'misturou tab e espaços no recuo'),
    (r"^'return' outside function$", 'return fora de uma função'),
    (r"^'break' outside loop$", 'break fora de um laço'),
]


def traduz_sintaxe(msg):
    for padrao, pt in SINTAXE_PT:
        if re.match(padrao, msg):
            return re.sub(padrao, pt, msg)
    return msg


def erro_de_sintaxe(codigo):
    """None se o Python lê o programa; senão "linha N: mensagem" (em português, quando é das comuns)."""
    try:
        compile(codigo, 'main.py', 'exec')
        return None
    except SyntaxError as e:
        return f'linha {e.lineno}: {traduz_sintaxe(e.msg)}'


def outros_arquivos(programa):
    pasta = os.path.dirname(os.path.abspath(programa))
    return sorted(os.path.basename(a) for a in glob.glob(os.path.join(pasta, '*.py'))
                  if os.path.basename(a) != os.path.basename(programa))


def roda_simulador(desafio, programa, pasta, sementes='1-2', robo=None):
    """avalia.py com --registros; devolve os .jsonl gravados (uma rodada por semente)."""
    os.makedirs(pasta, exist_ok=True)
    for a in glob.glob(os.path.join(pasta, '*.jsonl')):
        os.remove(a)
    cmd = [sys.executable, 'avalia.py', '--desafio', desafio, '--programa', os.path.abspath(programa),
           '--sementes', sementes, '--registros', pasta, '--paralelo', '2']
    if robo:
        cmd += ['--robo', robo]
    import chave
    env = dict(chave.ambiente_sem_chave(), PYTHONIOENCODING='utf-8')   # o programa do aluno roda lá dentro
    r = subprocess.run(cmd, cwd=LINE, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    arqs = sorted(glob.glob(os.path.join(pasta, '*.jsonl')))
    if not arqs:
        raise RuntimeError('o simulador não gravou o registro da volta:\n' + (r.stdout + r.stderr)[-2000:])
    return arqs


def desafio_info(desafio):
    sys.path.insert(0, LINE)
    import avalia
    d = avalia.carrega_desafios().get(desafio.upper())
    if d is None:
        raise SystemExit(f'desafio {desafio} não existe (python simuladorLine/avalia.py --lista)')
    return d


def placar(d, r):
    """O que o juiz disse, em texto, a partir do fim de cada registro e da meta do desafio."""
    import avalia
    ms = []
    for rd in r['rodadas']:
        ms.append(avalia.metricas({'total': rd['total'] or 0, 'lop': rd['lop'] or 0, 'tempo': rd['tempo'] or 0,
                                   'chegou': rd['chegou'], 'passo': 0, 'passos': 1,
                                   'erro_programa': 'erro_programa' in rd['problemas']}))
    linhas = []
    for rd in r['rodadas']:
        linhas.append(f'  semente {rd["semente"]}: {rd["total"]} pontos, {rd["lop"]} LoP, '
                      f'{"chegou e parou na chegada" if rd["chegou"] else "não chegou"}, {resumo._br(rd["tempo"] or 0)} s')
    aprovado = None
    if d.get('meta'):
        aprovado, expl = avalia.confere_meta(d['meta'], ms)
        linhas += [f'  {e}' for e in expl if not e.startswith('só rodaram')]
        n = len(r['rodadas'])
        minimo = int(d['meta'].get('minimo', n))
        if n < minimo:
            linhas.append(f'  (nesta tentativa rodaram só {n} sementes; o desafio valendo roda {minimo}: '
                          f'{"todas as que rodaram cumpriram" if all(avalia.avalia_expr(d["meta"]["rodada"], m) for m in ms if m) else "ainda não"})')
        else:
            linhas.append('  DESAFIO CUMPRIDO' if aprovado else '  desafio ainda não cumprido')
    return '\n'.join(linhas), aprovado


# ---------------------------------------------------------------------- o tutor
class Tutor:
    def __init__(self, desafio, programa, modelo=None, registrar=None):
        self.desafio = desafio.upper()
        self.d = desafio_info(desafio)
        self.programa = programa
        self.arqs = []
        self.nivel = 1
        self.principal = None            # código do problema mais importante da última volta
        self.modelo = modelo
        self.registro = []               # uma entrada por fala: quem, texto, uso
        self.registrar = registrar or (lambda: None)
        if modelo is not None:
            modelo.prepara(instrucoes(), ferramentas())

    # ---- o que vai para o modelo
    def mensagem_volta(self, arqs, pergunta, tentativa):
        r = resumo.resume(arqs)
        self.arqs = arqs
        self.res = r
        txt_placar, self.aprovado = placar(self.d, r)
        cod = r['problemas'][0]['codigo'] if r['problemas'] and r['problemas'][0]['grau'] >= 2 else None
        if tentativa > 1:
            # o mesmo problema de antes: ele tentou e não resolveu, a dica sobe; outro problema: volta ao 1
            self.nivel = min(3, self.nivel + 1) if cod is not None and cod == self.principal else 1
        self.principal = cod
        outros = outros_arquivos(self.programa)
        d = self.d
        partes = [
            f'TENTATIVA {tentativa}' + (' (o aluno mudou o código e rodou de novo)' if tentativa > 1 else ''),
            f'DESAFIO {self.desafio}: {d.get("titulo")} ({d.get("nivel")}). {d.get("descricao")} '
            f'Meta: {d.get("meta_texto")}.',
            'PLACAR (juiz do simulador):\n' + txt_placar,
            'RESUMO DA VOLTA (automático):\n' + resumo.texto(r),
            f'CÓDIGO DO ALUNO ({os.path.basename(self.programa)}):\n' + le_codigo(self.programa),
        ]
        if outros:
            partes.append('Outros arquivos na pasta (peça com ler_arquivo se precisar): ' + ', '.join(outros))
        partes.append(self._fala(pergunta))
        return '\n\n'.join(partes)

    def _fala(self, texto):
        return f'NÍVEL DE DICA: {self.nivel} = {NIVEIS[self.nivel]}\n\nFALA DO ALUNO: "{texto}"'

    # ---- conversa
    def volta(self, arqs, pergunta=PERGUNTA_PADRAO, tentativa=1):
        """Uma volta nova (registros novos) e a primeira fala do aluno sobre ela."""
        msg = self.mensagem_volta(arqs, pergunta, tentativa)
        return self._conversa(msg, pergunta, tentativa=tentativa)

    def pergunta(self, texto, codigo_novo=None):
        """O aluno fala sem rodar de novo: a dica sobe um nível (ele já leu a anterior).
        codigo_novo = o código do editor, quando ele mudou desde a última volta (página do aluno)."""
        if not self.arqs:
            return self.sem_volta(texto, codigo_novo)
        self.nivel = min(3, self.nivel + 1)
        msg = self._fala(texto)
        if codigo_novo is not None:
            msg = ('O ALUNO MUDOU O CÓDIGO DEPOIS DA ÚLTIMA VOLTA (ainda não rodou; o placar e o resumo são da '
                   'versão anterior). O código agora:\n' + numera(codigo_novo) + '\n\n' + msg)
        return self._conversa(msg, texto)

    def sem_volta(self, texto, codigo):
        """O aluno pergunta antes de rodar (ou o programa nem compila): o tutor só tem o desafio e o código."""
        d = self.d
        partes = []
        if not self.registro:
            partes.append(f'DESAFIO {self.desafio}: {d.get("titulo")} ({d.get("nivel")}). {d.get("descricao")} '
                          f'Meta: {d.get("meta_texto")}.')
        partes.append('O ALUNO AINDA NÃO RODOU ESTA VERSÃO NO SIMULADOR: não há placar nem resumo. Não diga o que '
                      'o robô vai fazer como se tivesse visto; ajude pelo código e, se fizer sentido, sugira rodar.')
        erro = erro_de_sintaxe(codigo or '')
        if erro:
            partes.append(f'O PYTHON NÃO CONSEGUE LER O PROGRAMA: {erro}')
        partes.append('CÓDIGO DO ALUNO:\n' + numera(codigo or ''))
        partes.append(self._fala(texto))
        return self._conversa('\n\n'.join(partes), texto)

    def _conversa(self, msg, fala_aluno, tentativa=None):
        self.registro.append({'quem': 'aluno', 'texto': fala_aluno, 'nivel': self.nivel, 'tentativa': tentativa,
                              'placar': [{k: rd[k] for k in ('semente', 'total', 'lop', 'chegou', 'tempo')}
                                         for rd in self.res['rodadas']] if tentativa else None,
                              'problemas': [p['codigo'] for p in self.res['problemas']] if tentativa else None})
        if self.modelo is None:
            self.registro.append({'quem': 'seco', 'texto': msg})
            return msg
        self.modelo.usuario(msg)
        uso_total = {'entrada': 0, 'saida': 0, 'cache': 0, 'usd': 0.0}
        ferr_usadas = []
        t0 = datetime.datetime.now()
        texto = ''
        for _ in range(MAX_IDAS):
            texto, chamadas, uso = self.modelo.roda()
            for k in uso_total:
                uso_total[k] += uso.get(k, 0)
            if not chamadas:
                break
            res = []
            for i, nome, args in chamadas:
                ferr_usadas.append({'nome': nome, 'args': args})
                try:
                    res.append((i, nome, self._executa(nome, args), False))
                except Exception as e:
                    res.append((i, nome, f'erro: {e}', True))
            self.modelo.resultados(res)
        else:
            texto = texto or '(o tutor não chegou a uma resposta)'
        # a fala pode ir para a voz: sem crase nem asterisco de ênfase (o "KP * erro" do código fica)
        texto = re.sub(r'`|\*\*|(?<![\s(])\*|\*(?![\s)])', '', texto).strip()
        segundos = (datetime.datetime.now() - t0).total_seconds()
        self.registro.append({'quem': 'tutor', 'texto': texto, 'ferramentas': ferr_usadas, 'uso': uso_total,
                              'segundos': round(segundos, 2), 'modelo': getattr(self.modelo, 'nome', '?')})
        self.registrar()
        return texto

    def _executa(self, nome, args):
        if nome == 'ver_trecho':
            arq = next((a for a in self.arqs if resumo.Volta(a).semente == int(args['semente'])), None)
            if arq is None:
                raise ValueError(f'não há a semente {args["semente"]}; as rodadas são '
                                 + ', '.join(str(rd['semente']) for rd in self.res['rodadas']))
            t1, t2 = float(args['t1']), float(args['t2'])
            t2 = min(t2, t1 + 8)
            return resumo.trecho(arq, t1, t2)
        if nome == 'ler_arquivo':
            n = os.path.basename(str(args['nome']))
            if n not in outros_arquivos(self.programa) + [os.path.basename(self.programa)]:
                raise ValueError('esse arquivo não está na pasta do programa; os que tem: '
                                 + ', '.join(outros_arquivos(self.programa)))
            return le_codigo(os.path.join(os.path.dirname(os.path.abspath(self.programa)), n))
        raise ValueError(f'ferramenta desconhecida: {nome}')

    def custo(self):
        return sum(e['uso']['usd'] for e in self.registro if e['quem'] == 'tutor')


def cria_modelo(tipo=None, nome=None):
    """O cérebro do robô de casa (Claude pela API, Claude pela mensalidade ou modelo local)."""
    pasta = os.path.join(REPO, 'simuladorCasa', 'exemplo_casa')
    if pasta not in sys.path:
        sys.path.append(pasta)           # no fim: os módulos de lá não escondem os daqui
    import cerebro
    tipo = (tipo or os.environ.get('CEREBRO') or 'claude').lower()
    if tipo == 'claude':
        # a chave vem da variável do PC ou da chave_tutor.dll, e vai direto para o cliente (nunca para
        # os.environ, que o programa do aluno, num processo filho, leria)
        import anthropic
        import chave
        k = chave.da_api()
        if not k:
            raise RuntimeError('falta a chave da API: CEREBRO_CHAVE_API ou tutor/chave_tutor.dll '
                               '(python tutor/ferramentas/faz_chave.py)')
        return cerebro.ModeloClaude(nome or os.environ.get('CEREBRO_MODELO') or None,
                                    cliente=anthropic.Anthropic(api_key=k))
    return cerebro.cria_modelo(tipo, nome)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--desafio', required=True)
    ap.add_argument('--programa', required=True)
    ap.add_argument('--robo', default=None)
    ap.add_argument('--sementes', default='1-2')
    ap.add_argument('--registros', default=None, help='pasta dos registros (padrão: uma pasta nova em tutor/conversas/)')
    ap.add_argument('--sem-rodar', action='store_true', help='usa os registros que já estão na pasta')
    ap.add_argument('--pergunta', default=PERGUNTA_PADRAO)
    ap.add_argument('--uma-vez', action='store_true')
    ap.add_argument('--mostra', action='store_true', help='mostra o resumo automático')
    ap.add_argument('--seco', action='store_true', help='não chama a IA')
    ap.add_argument('--cerebro', default=None, help='claude (padrão), local ou assinatura')
    ap.add_argument('--modelo', default=None)
    a = ap.parse_args()

    agora = datetime.datetime.now()
    sessao = os.path.join(CONVERSAS, f'{agora:%Y%m%d-%H%M%S}_{a.desafio.upper()}')
    pasta_reg = a.registros or os.path.join(sessao, 'tentativa1')
    modelo = None if a.seco else cria_modelo(a.cerebro, a.modelo)
    arq_conversa = os.path.join(sessao, 'conversa.json')

    def grava():
        os.makedirs(sessao, exist_ok=True)
        with open(arq_conversa, 'w', encoding='utf-8') as f:
            json.dump({'desafio': tutor.desafio, 'programa': os.path.abspath(a.programa), 'data': agora.isoformat(timespec='seconds'),
                       'custo_usd': round(tutor.custo(), 5), 'falas': tutor.registro}, f, ensure_ascii=False, indent=1)

    tutor = Tutor(a.desafio, a.programa, modelo, registrar=grava)
    tentativa = 1

    def roda(pasta):
        if a.sem_rodar and tentativa == 1:
            arqs = sorted(glob.glob(os.path.join(pasta, '*.jsonl')))
            if not arqs:
                raise SystemExit(f'nenhum registro em {pasta}')
            return arqs
        print(f'[rodando o programa no simulador: {tutor.desafio}, sementes {a.sementes}...]', flush=True)
        return roda_simulador(tutor.desafio, a.programa, pasta, a.sementes, a.robo)

    arqs = roda(pasta_reg)
    fala = a.pergunta
    while True:
        try:
            resposta = tutor.volta(arqs, fala, tentativa)
        except Exception as e:
            print(f'[erro ao falar com o tutor: {e}]')
            return 1
        print('[placar]\n' + placar(tutor.d, tutor.res)[0])
        if a.mostra:
            print('[resumo]\n' + resumo.texto(tutor.res))
        print(f'\ntutor> {resposta}\n', flush=True)
        if a.uma_vez or a.seco:
            break
        nova_volta = False
        while True:
            try:
                fala = input('você> ').strip()
            except EOFError:
                fala = 'sair'
            if fala.lower() in ('sair', 'tchau', 'q'):
                break
            if fala.lower() in ('rodar', 'r', 'rodei', 'rodar de novo'):
                nova_volta = True
                break
            if fala:
                print(f'\ntutor> {tutor.pergunta(fala)}\n', flush=True)
        if not nova_volta:
            break
        tentativa += 1
        arqs = roda(os.path.join(sessao, f'tentativa{tentativa}'))
        fala = 'Mudei o código e rodei de novo.'
    if modelo is not None:
        print(f'[conversa gravada em {os.path.relpath(arq_conversa, REPO)}; custo estimado US$ {tutor.custo():.4f}]')
    return 0


if __name__ == '__main__':
    sys.exit(main())
