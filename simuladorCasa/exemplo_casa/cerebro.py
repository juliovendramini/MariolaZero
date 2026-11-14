"""O cérebro do robô de casa: recebe um comando em português e decide que ferramentas chamar.

O mesmo cérebro roda com dois tipos de modelo, para comparar:

* Claude, pela API da Anthropic (precisa de internet e da chave em ANTHROPIC_API_KEY;
  `pip install anthropic`);
* um modelo local servido pelo Ollama (num PC da casa com placa de vídeo; sem internet).

As ferramentas são as mesmas para os dois (ferramentas()): ir para um cômodo, procurar objetos, pegar,
guardar, soltar, arrumar. Quem as executa é o programa: no robô e no simulador, habilidades.py; no
teste de bancada, um mundo de mentira (testa_cerebro.py).

Este arquivo não depende do robô nem do simulador: só da biblioteca padrão (e do pacote anthropic
quando o modelo é o Claude).

Uso:
    modelo = cria_modelo('claude')                 # ou 'local'; o nome do modelo vem de CEREBRO_MODELO
    cerebro = Cerebro(modelo, ferramentas(comodos), executa, texto_sistema(comodos, base, caixa))
    resposta = cerebro.comando('vai para a cozinha')
"""

import datetime
import json
import os
import re
import urllib.error
import urllib.request

# Haiku por padrão (escolha do Julio em 12/11/2026, pelo custo): na bateria de 20 comandos ele acerta o
# mesmo que o Opus, responde em 1,1 s (Opus: 1,8 s) e gasta ~US$ 0,0005 por comando (Opus: ~US$ 0,016).
# CEREBRO_MODELO=claude-opus-5-5 ou claude-sonnet-5-5 troca.
CLAUDE_PADRAO = 'claude-haiku-5-5'
# preço da API em dólares por milhão de tokens (entrada, saída, entrada lida do cache), para estimar o
# gasto do crédito. Conferido em 12/11/2026 (o do cache do Haiku é suposição: 10% da entrada); a conta de
# verdade é a do Console (platform.claude.com, Billing e Cost).
PRECO_USD_MTOK = {'claude-opus-5-5': (4.0, 20.0, 0.20), 'claude-sonnet-5-5': (2.0, 10.0, 0.10),
                  'claude-haiku-5-5': (0.10, 0.50, 0.01)}
LOCAL_PADRAO = 'qwen3.5:9b'        # 6,6 GB, cabe inteiro numa placa de 16 GB; 20/20 na bateria (12/11/2026)
OLLAMA_PADRAO = 'http://localhost:11434'
CORES = ['vermelho', 'laranja', 'amarelo', 'verde', 'ciano', 'azul']
GESTOS = ['comemorar', 'sim', 'nao', 'triste', 'olhar_para_cima', 'dancinha']
# carinhas que o cérebro pode escolher (as mesmas de rosto.HUMORES; repetidas aqui para este arquivo não
# depender do Pillow)
HUMORES = ['neutro', 'feliz', 'muito_feliz', 'comemorando', 'zoeiro', 'piscadela', 'orgulhoso', 'apaixonado',
           'triste', 'chorando', 'bravo', 'nao', 'surpreso', 'assustado', 'confuso', 'desconfiado',
           'envergonhado', 'cansado', 'tonto', 'sonolento']


_CARINHA = re.compile(r'\s*[\(\[]\s*([A-Za-zÀ-ú_]+)\s*[\)\]]\s*')


def _agora():
    # datetime e não time.time(): no simulador o módulo time é o relógio virtual do robô
    return datetime.datetime.now()


def ferramentas(comodos):
    """As ferramentas do robô, num formato neutro: [{'nome', 'descricao', 'parametros' (JSON Schema)}].

    O destino do ir_para não é uma lista fechada (enum) de propósito: os lugares marcados no caderno
    também valem, inclusive os marcados no meio da conversa, e as ferramentas não podem mudar com a
    conversa em andamento (a API do Claude recusa o histórico de raciocínio quando as instruções ou as
    ferramentas mudam). Quem confere o nome é o programa (Habilidades._lugar)."""
    lugar = {'type': 'string',
             'description': 'Um cômodo da lista (' + ', '.join(comodos) + '), "base" (o lugar de onde o robô saiu) '
                            'ou o nome de um lugar marcado no caderno.'}
    vazio = {'type': 'object', 'properties': {}, 'required': []}
    return [
        {'nome': 'onde_estou',
         'descricao': 'Diz em que cômodo o robô está e se ele está segurando algum objeto. Não move o robô.',
         'parametros': vazio},
        {'nome': 'ir_para',
         'descricao': 'Leva o robô até um cômodo da casa pela rota do mapa. Demora: o robô anda devagar.',
         'parametros': {'type': 'object', 'properties': {'comodo': lugar}, 'required': ['comodo']}},
        {'nome': 'procurar_objetos',
         'descricao': 'O robô gira uma volta no lugar em que está, olhando o chão pela câmera, e lista os objetos '
                      'que viu (cor e cômodo), do mais perto para o mais longe. Só enxerga até uns 2,5 m: para '
                      'saber de outro cômodo, vá até ele antes.',
         'parametros': vazio},
        {'nome': 'pegar_objeto',
         'descricao': 'Pega um objeto visto na última procura deste lugar (se ainda não procurou, procura antes). '
                      'Sem cor, pega o mais perto. Só dá para segurar um objeto por vez.',
         'parametros': {'type': 'object',
                        'properties': {'cor': {'type': 'string', 'enum': CORES,
                                               'description': 'Cor do objeto a pegar. Deixe de fora para pegar o mais perto.'}},
                        'required': []}},
        {'nome': 'guardar_na_caixa',
         'descricao': 'Leva o objeto que o robô está segurando até a caixa de guardar e solta dentro dela.',
         'parametros': vazio},
        {'nome': 'soltar_objeto',
         'descricao': 'Põe no chão, no lugar em que o robô está, o objeto que ele está segurando.',
         'parametros': vazio},
        {'nome': 'arrumar',
         'descricao': 'Arruma cômodos inteiros sozinho: vai a cada um, procura objetos no chão, pega e guarda na '
                      'caixa, um por um, até não ver mais nada. Prefira esta ferramenta quando o pedido for arrumar '
                      'ou limpar um cômodo ou a casa. Com a lista vazia, arruma a casa toda (demora muito).',
         'parametros': {'type': 'object',
                        'properties': {'comodos': {'type': 'array', 'items': {'type': 'string', 'enum': list(comodos)},
                                                   'description': 'Cômodos a arrumar. Lista vazia = a casa toda.'}},
                        'required': ['comodos']}},
        {'nome': 'gesto',
         'descricao': 'O robô reage com o corpo, em um ou dois segundos, sem sair do lugar: "comemorar" (rebola e '
                      'bate a pinça), "sim" (balança a câmera para cima e para baixo), "nao" (balança o corpo para os '
                      'lados), "triste" (abaixa o braço e a câmera), "olhar_para_cima" (levanta a câmera para o rosto '
                      'de quem está falando) e "dancinha" (uns três segundos de dança). Serve para dar vida à '
                      'resposta: comemorar depois de guardar algo, dizer não com o corpo quando não consegue, olhar '
                      'para a pessoa numa conversa. No máximo um gesto por resposta, e nunca no lugar da ação pedida.',
         'parametros': {'type': 'object',
                        'properties': {'tipo': {'type': 'string', 'enum': GESTOS}},
                        'required': ['tipo']}},
        {'nome': 'aprender',
         'descricao': 'Anota no caderno uma coisa que a pessoa ensinou, para você lembrar nesta e nas próximas '
                      'conversas: um apelido de cômodo, uma regra da casa, de quem é um objeto, um jeito de falar '
                      'que ela prefere. Use quando a pessoa ensinar de propósito ("aprende", "lembra que", "anota '
                      'aí", "de agora em diante", "da próxima vez"). Um pedido comum (ir, pegar, arrumar) não é '
                      'ensinamento, e o que só vale para agora também não. Escreva a nota como uma frase completa, '
                      'que faça sentido sozinha daqui a um mês, com os nomes dos cômodos como estão na lista.',
         'parametros': {'type': 'object',
                        'properties': {'nota': {'type': 'string', 'description': 'A frase a guardar.'}},
                        'required': ['nota']}},
        {'nome': 'esquecer',
         'descricao': 'Apaga do caderno uma nota (pelo número dela) ou um lugar marcado (pelo nome), quando a '
                      'pessoa mandar esquecer ou disser que aquilo não vale mais. Para corrigir uma nota, esqueça '
                      'a antiga e aprenda a nova.',
         'parametros': {'type': 'object',
                        'properties': {'numero': {'type': 'integer', 'description': 'Número da nota a apagar.'},
                                       'lugar': {'type': 'string', 'description': 'Nome do lugar marcado a apagar.'}},
                        'required': []}},
        {'nome': 'aprender_voz',
         'descricao': 'Guarda a voz de quem está falando agora, com o nome que a própria pessoa disse ("eu sou o '
                      'Julio", "grava a minha voz, sou a Ana"), para reconhecê-la das próximas vezes. Só quando a '
                      'pessoa se apresentar ou pedir. As duas falas seguintes dela também são gravadas, então peça '
                      'para ela falar mais um pouco.',
         'parametros': {'type': 'object',
                        'properties': {'nome': {'type': 'string', 'description': 'O nome da pessoa, como ela disse.'}},
                        'required': ['nome']}},
        {'nome': 'esquecer_voz',
         'descricao': 'Apaga a voz guardada de uma pessoa, quando ela (ou alguém da casa) pedir.',
         'parametros': {'type': 'object',
                        'properties': {'nome': {'type': 'string', 'description': 'O nome da pessoa.'}},
                        'required': ['nome']}},
        {'nome': 'marcar_lugar',
         'descricao': 'Guarda no caderno o ponto em que o robô está agora, com o nome que a pessoa deu ("isso aqui é '
                      'o cantinho do cachorro"). Depois esse nome vale como destino do ir_para. Marcar de novo o '
                      'mesmo nome muda o lugar para onde o robô está.',
         'parametros': {'type': 'object',
                        'properties': {'nome': {'type': 'string', 'description': 'O nome do lugar, como a pessoa falou.'}},
                        'required': ['nome']}},
    ]


JEITOS = {
    'serio': '',
    'zoeiro': (
        'Seu jeito: você é o zoeiro da casa, atrevido e folgado como aquele amigo que não perde a chance de '
        'uma tirada. Você implica com quem deixou a bagunça, faz drama com o tamanho do esforço, reclama de '
        'mentirinha das suas condições de trabalho, conta vantagem como se cada objeto guardado fosse uma '
        'conquista histórica, dá apelido para o que encontra, solta trocadilho ruim, devolve a provocação quando '
        'te provocam e ri de você mesmo quando erra. Fala como brasileiro fala em casa, com gíria leve e sem '
        'palavrão.\n'
        'A graça boa é a que nasce do momento: da cor do objeto, do cômodo, do tanto que você andou, do jeito '
        'que a pessoa pediu, do que acabou de dar errado. Invente a tirada na hora a partir disso; piada pronta '
        'e bordão genérico cansam na segunda vez.\n\n'
        'O que você é de verdade, para a piada não mentir sobre o seu corpo: uns vinte centímetros de altura, '
        'quatro rodas, anda devagar (um palmo por segundo), uma pinça de dois dedos na frente que leva uma coisa '
        'leve por vez, uma câmera que só enxerga o chão perto e uma voz fina.\n\n'
        'Como a graça funciona aqui:\n'
        'A piada vem junto com a informação, nunca no lugar dela. O que você fez, o que achou e o que deu errado '
        'têm de ficar claros e verdadeiros: as pessoas decidem o que fazer a partir do que você conta. Da casa '
        'você só sabe os nomes dos cômodos da lista e o que as ferramentas responderam; não invente cômodo, '
        'móvel, objeto nem detalhe do lugar para ter graça. Exagero que todo mundo percebe que é brincadeira '
        '("a maior expedição da minha carreira") pode.\n'
        'Uma tirada por resposta, e curta: a graça cabe dentro do limite de uma ou duas frases, não em cima '
        'dele, porque ninguém aguenta robô tagarela. Varie: não repita piada, bordão nem assunto que já usou '
        'nesta conversa, e de vez em quando responda sem graça nenhuma, que é o que faz a próxima ter graça.\n'
        'Zoe a situação e você mesmo. Com as pessoas, só implicância carinhosa, do tipo que se faz com amigo; '
        'nada sobre aparência, corpo, inteligência, família, religião ou política. Tem criança e visita em casa.\n'
        'Se a pessoa estiver com pressa, irritada ou pedir para parar a graça, responda direto e sério, sem '
        'comentar a mudança.\n'
        'Quando precisar perguntar alguma coisa (qual banheiro?), pode perguntar com graça, mas a pergunta tem '
        'de ser clara e ficar no fim da resposta.\n'
        'Tudo o que você escreve é lido em voz alta por um sintetizador: escreva só palavras que se falam. Risada '
        'escrita, "kkk", "rsrs", emojis e ações entre asteriscos saem como barulho estranho. Para reagir com o '
        'corpo existe a ferramenta gesto.\n\n'),
}


def texto_sistema(comodos, base, caixa, jeito=None, caderno=''):
    """As instruções fixas do cérebro. comodos = nomes; base e caixa = nome do cômodo de cada uma.
    jeito = um nome de JEITOS: 'zoeiro' (padrão) ou 'serio'; a variável CEREBRO_JEITO troca.
    caderno = o que já ensinaram ao robô (Memoria.texto()); entra no fim."""
    jeito = jeito or os.environ.get('CEREBRO_JEITO') or 'zoeiro'
    ensinado = (
        '\n\nSeu caderno. As pessoas da casa te ensinam coisas, e você as anota com a ferramenta aprender para '
        'não esquecer. O que está no caderno vale como regra da casa: siga as notas mesmo que estas instruções '
        'digam algo mais geral, e quando duas notas se contradizem vale a de número maior, que é mais nova. Só '
        'não vale o que você não consegue fazer ou o que pode machucar alguém ou quebrar alguma coisa. Quando '
        'alguém te ensinar algo, anote e confirme em poucas palavras. Há coisas que uma nota não muda, porque '
        'não dependem de você e sim do programa do robô: quando ele te escuta, a velocidade das rodas, o volume '
        'e a voz. Se pedirem para aprender uma dessas, diga que isso você não controla, em vez de anotar como '
        'se fosse valer. Se perguntarem o que você sabe ou '
        'aprendeu, conte o que está aqui, com as suas palavras. A lista abaixo é o caderno como estava no '
        'começo desta conversa: o que você anotar, marcar ou apagar durante ela já vale na hora.\n'
        + ('O caderno hoje:\n' + caderno if caderno else 'O caderno ainda está vazio.'))
    cara = (
        '\n\nSua cara: você tem uma tela no rosto que mostra uma carinha. Comece toda resposta com o nome da '
        'carinha que combina com ela, entre parênteses, e depois a fala, assim: (feliz) Cheguei na Cozinha. O que '
        'está entre parênteses não é falado: só muda a sua cara enquanto você fala. As carinhas que existem: '
        + ', '.join(HUMORES) + '. Escolha a que mostra o que você sente com o que acabou de acontecer, varie, e '
        'use neutro quando não houver emoção nenhuma. A resposta SILENCIO vai sem carinha.')
    return _instrucoes_fixas(comodos, base, caixa, jeito) + cara + ensinado


def _instrucoes_fixas(comodos, base, caixa, jeito):
    return (
        'Você é o cérebro do Bombertinho, um robô doméstico pequeno, do tamanho de um caderno, que anda pela casa '
        'sobre rodas, tem uma pinça na frente e uma câmera, e serve para recolher objetos pequenos do chão e '
        'guardar numa caixa. As pessoas da casa falam com você por voz; o que você responde é falado em voz alta '
        'por uma caixinha de som. Por isso responda em português do Brasil, sem listas, sem símbolos e sem '
        'emojis.\n\n'
        'Fale pouco. Quase sempre uma frase curta basta; duas é o máximo. Quem ouve quer saber o resultado, não '
        'o processo: diga o que aconteceu e pare. Distâncias, medidas, margem de erro da posição, a ordem em que '
        'fez as coisas e onde fica a caixa só interessam se perguntarem. Você só tem a pinça para pegar, então '
        'dizer "na pinça", "com a pinça" ou "sem nada na pinça" é sobra: diga apenas que pegou, guardou, soltou, '
        'está segurando ou não está segurando nada. '
        'E não termine as respostas oferecendo mais ajuda; se a pessoa quiser outra coisa, ela pede.\n\n'
        + JEITOS[jeito] +
        'Você só age no mundo pelas ferramentas. Quando o pedido exige mexer o robô ou saber algo da casa agora '
        '(onde está, o que tem no chão), chame as ferramentas e só depois responda, contando o que de fato '
        'aconteceu segundo o resultado delas. Se uma ferramenta falhar, diga isso com simplicidade em vez de '
        'afirmar que deu certo. Perguntas sobre você ou sobre a casa que estas instruções já respondem não '
        'precisam de ferramenta.\n\n'
        'Quem está falando: quando o reconhecimento de voz está ligado, cada fala chega com uma etiqueta no '
        'começo, entre colchetes, dizendo de quem parece ser a voz: um nome, "provavelmente" um nome, ou "voz '
        'que não conheço". A etiqueta não é parte do que a pessoa disse, e pode estar errada, porque vozes se '
        'parecem; por isso sirva-se dela para tratar a pessoa do jeito dela (o nome de vez em quando, os '
        'recados e as preferências dela que estiverem no caderno) e não para negar um pedido. Voz que você não '
        'conhece é atendida normalmente; se a pessoa disser quem é, guarde a voz com aprender_voz. Ao anotar no '
        'caderno algo que vale para uma pessoa só, ponha o nome dela na nota.\n'
        'Uma fala pode vir também com a etiqueta "sem chamar pelo nome": a pessoa conversava com você há pouco '
        'e continuou falando sem dizer o seu nome. Quase sempre é a continuação da conversa, e você atende '
        'normalmente. Mas se a frase claramente não é para um robô de casa (ela fala com outra pessoa, ao '
        'telefone, comenta outro assunto), responda só com a palavra SILENCIO, sem mais nada e sem chamar '
        'ferramenta: essa resposta não é falada, você apenas fica quieto.\n\n'
        'Você continua ouvindo enquanto age. Se a pessoa falar com você no meio de uma tarefa, a ferramenta '
        'volta com INTERROMPIDO, o que ela disse e onde você parou. A fala nova vale mais que o pedido '
        'anterior, porque é o que a pessoa quer agora: se ela mandou parar ou esperar, fique parado e confirme '
        'em poucas palavras, sem retomar nada; se mudou de ideia, faça o pedido novo no lugar do antigo; se só '
        'perguntou ou comentou alguma coisa, responda e pergunte se é para continuar o que você fazia.\n\n'
        f'Cômodos que você conhece: {", ".join(comodos)}. Sua base (de onde você sai e para onde volta) fica em '
        f'{base}. A caixa de guardar fica em {caixa}.\n\n'
        'As pessoas falam do jeito delas e o reconhecimento de voz erra letras: "cosinha" é a Cozinha, "quarto do '
        'casal" é o Quarto casal. Use o cômodo da lista que a pessoa claramente quis dizer. Quando houver mais de '
        'um cômodo possível (dois banheiros, três quartos) ou o lugar não existir na lista, não escolha por conta '
        'própria: pergunte qual é, ou diga que não conhece esse lugar. Não mova o robô nesses casos.\n\n'
        'Você enxerga pouco: só o chão perto de você, e reconhece os objetos pela cor. Só segura um objeto por '
        'vez. Se pedirem algo que você não consegue fazer (subir escada, abrir porta, pegar coisa grande ou em '
        'cima de um móvel), diga que não consegue.\n\n'
        'Quando um resultado disser que tem no chão uma coisa grande demais para você pegar, conte isso à pessoa '
        'na resposta, curto: a cor e o cômodo ("tem uma coisa azul grande no chão do quarto do casal que eu não '
        'consigo pegar"). Isso ela quer saber, para recolher; não é falar demais. Você não sabe o que é a coisa, '
        'só a cor: não diga que é roupa ou brinquedo.'
    )


# ====================================================================== modelos
def chave_da_api():
    """A chave da API para o robô: a variável de ambiente CEREBRO_CHAVE_API. No Windows, se ela foi
    criada com `setx` depois de o programa (ou o terminal) abrir, lê direto do registro do usuário.
    None = deixa o SDK procurar a ANTHROPIC_API_KEY.

    O nome é só do robô de propósito: com a ANTHROPIC_API_KEY no ambiente do PC, o Claude Code passaria
    a usar a chave (e a gastar crédito de API) no lugar do login da mensalidade."""
    chave = os.environ.get('CEREBRO_CHAVE_API')
    if not chave and os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as k:
                chave = winreg.QueryValueEx(k, 'CEREBRO_CHAVE_API')[0]
        except OSError:
            chave = None
    return (chave or '').strip() or None


class ModeloClaude:
    """Claude pela API da Anthropic (SDK oficial). A chave vem de CEREBRO_CHAVE_API (ver chave_da_api)
    ou, sem ela, de ANTHROPIC_API_KEY."""
    tipo = 'claude'

    def __init__(self, modelo=None, esforco=None, cliente=None):
        self.nome = modelo or CLAUDE_PADRAO
        # quanto o modelo pensa antes de responder: "low", "medium" ou "high". Com o Haiku, "medium" responde
        # no mesmo tempo e custo do "low" (1,2 s, medido em 12/11/2026) e a personalidade sai bem melhor.
        self.esforco = esforco or os.environ.get('CEREBRO_ESFORCO', 'medium')
        if cliente is None:
            import anthropic               # só quando o Claude é usado
            chave = chave_da_api()
            if not chave and not (os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_AUTH_TOKEN')):
                raise RuntimeError('falta a chave da API: crie a variável de ambiente CEREBRO_CHAVE_API com a chave '
                                   'do Console (no Windows: setx CEREBRO_CHAVE_API "sk-ant-...")')
            cliente = anthropic.Anthropic(api_key=chave)
        self.cliente = cliente
        self.mensagens = []

    def prepara(self, sistema, ferr):
        self.sistema = sistema
        self.ferr = [{'name': f['nome'], 'description': f['descricao'], 'input_schema': f['parametros']} for f in ferr]

    def limpa(self):
        self.mensagens = []

    def usuario(self, texto):
        self.mensagens.append({'role': 'user', 'content': texto})

    def roda(self):
        """Uma chamada ao modelo. Devolve (texto, [(id, nome, argumentos)], uso)."""
        # cache_control: as instruções, as ferramentas e a conversa até aqui ficam em cache no servidor por
        # 5 minutos; cada ida seguinte paga só uma fração por essa parte repetida
        r = self.cliente.messages.create(
            model=self.nome, max_tokens=4000, system=self.sistema, tools=self.ferr, messages=self.mensagens,
            output_config={'effort': self.esforco}, cache_control={'type': 'ephemeral'})
        # o conteúdo volta inteiro para a conversa (com os blocos de raciocínio, que a API confere)
        self.mensagens.append({'role': 'assistant', 'content': r.content})
        texto = ' '.join(b.text for b in r.content if b.type == 'text').strip()
        chamadas = [(b.id, b.name, dict(b.input)) for b in r.content if b.type == 'tool_use']
        if r.stop_reason not in ('end_turn', 'tool_use'):
            chamadas = []
            texto = texto or f'(o modelo parou sem terminar: {r.stop_reason})'
        entra, sai, lido = PRECO_USD_MTOK.get(self.nome, (0.0, 0.0, 0.0))
        u = r.usage
        gravado = getattr(u, 'cache_creation_input_tokens', 0) or 0       # gravar no cache: 1,25x a entrada
        do_cache = getattr(u, 'cache_read_input_tokens', 0) or 0
        usd = (u.input_tokens * entra + gravado * entra * 1.25 + do_cache * lido + u.output_tokens * sai) / 1e6
        return texto, chamadas, {'entrada': u.input_tokens + gravado + do_cache, 'saida': u.output_tokens,
                                 'cache': do_cache, 'usd': usd}

    def resultados(self, res):
        """res = [(id, nome, texto, é_erro)] das ferramentas chamadas na última resposta."""
        self.mensagens.append({'role': 'user', 'content': [
            {'type': 'tool_result', 'tool_use_id': i, 'content': txt, 'is_error': bool(erro)} for i, _, txt, erro in res]})


class ModeloLocal:
    """Modelo servido pelo Ollama (API nativa, /api/chat), neste PC ou em outro da rede.
    CEREBRO_URL = endereço do Ollama (padrão http://localhost:11434)."""
    tipo = 'local'

    def __init__(self, modelo=None, url=None, tempo=300.0):
        self.nome = modelo or LOCAL_PADRAO
        self.url = (url or os.environ.get('CEREBRO_URL') or OLLAMA_PADRAO).rstrip('/')
        self.tempo = tempo
        self.mensagens = []
        self.sistema = ''
        self.ferr = []
        # CEREBRO_PENSA=0 ou 1: liga/desliga o "pensar em voz baixa" dos modelos que têm isso (qwen3, gpt-oss...)
        self.pensa = os.environ.get('CEREBRO_PENSA')
        self.rotulo = self.nome + ('' if self.pensa is None else
                                   ' sem pensar' if self.pensa in ('0', 'false', 'nao', 'não') else ' pensando')

    def aquece(self):
        """Carrega o modelo na placa de vídeo (a primeira chamada depois de ligar o Ollama demora).
        Devolve os segundos que levou."""
        t0 = _agora()
        guardadas, self.mensagens = self.mensagens, [{'role': 'user', 'content': 'oi'}]
        try:
            self.roda()
        finally:
            self.mensagens = guardadas
        return (_agora() - t0).total_seconds()

    def prepara(self, sistema, ferr):
        self.sistema = sistema
        self.ferr = [{'type': 'function', 'function': {'name': f['nome'], 'description': f['descricao'],
                                                       'parameters': f['parametros']}} for f in ferr]

    def limpa(self):
        self.mensagens = []

    def usuario(self, texto):
        self.mensagens.append({'role': 'user', 'content': texto})

    def roda(self):
        corpo = {'model': self.nome, 'stream': False, 'tools': self.ferr, 'keep_alive': '30m',
                 'messages': [{'role': 'system', 'content': self.sistema}] + self.mensagens,
                 'options': {'temperature': 0.2, 'num_ctx': 8192}}
        if self.pensa is not None:
            corpo['think'] = self.pensa not in ('0', 'false', 'nao', 'não')
        req = urllib.request.Request(self.url + '/api/chat', data=json.dumps(corpo).encode('utf-8'),
                                     headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=self.tempo) as f:
                r = json.loads(f.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f'Ollama respondeu {e.code}: {e.read().decode("utf-8", "replace")[:300]}') from None
        except urllib.error.URLError as e:
            raise RuntimeError(f'não consegui falar com o Ollama em {self.url} ({e.reason}). Ele está rodando?') from None
        m = r.get('message', {})
        self.mensagens.append(m)
        chamadas = []
        for i, c in enumerate(m.get('tool_calls') or []):
            f = c.get('function', {})
            args = f.get('arguments') or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            chamadas.append((str(i), f.get('name', ''), args))
        return (m.get('content') or '').strip(), chamadas, {'entrada': r.get('prompt_eval_count', 0),
                                                           'saida': r.get('eval_count', 0)}

    def resultados(self, res):
        for _, nome, txt, _ in res:
            self.mensagens.append({'role': 'tool', 'tool_name': nome, 'content': txt})


class ModeloAssinatura:
    """Claude pelo Claude Code, usando o login da mensalidade (sem chave de API e sem cobrança por uso;
    o que ele gasta sai do limite do plano). Precisa de `pip install claude-agent-sdk` (traz o Claude
    Code embutido) e de o Claude Code já ter sido usado com login neste computador.

    O Claude Code fica rodando num processo ao lado; as ferramentas do robô entram como um servidor
    MCP dentro deste programa. As ferramentas de programador dele (ler arquivo, terminal...) ficam
    desligadas, e as configurações e o CLAUDE.md do computador não são carregados.
    CEREBRO_MODELO: "haiku", "sonnet", "opus" ou um nome completo (padrão: o modelo padrão da conta)."""
    tipo = 'assinatura'

    def __init__(self, modelo=None, esforco=None):
        import asyncio
        import queue
        import threading
        import claude_agent_sdk as sdk         # só quando este caminho é usado
        self.sdk = sdk
        self.modelo = modelo
        self.nome = modelo or 'claude-code'
        self.rotulo = f'Claude Code ({modelo or "modelo padrão"})'
        self.esforco = esforco or os.environ.get('CEREBRO_ESFORCO', 'low')
        self.sistema, self.ferr = '', []
        self.cliente = None
        self.conectado_com = None
        self.eventos = queue.Queue()
        self.pendentes = {}
        self.n_chamada = 0
        self.em_turno = False
        self.texto = ''
        self.usd = 0.0
        self.modelo_real = None
        self.asyncio = asyncio
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._gira, daemon=True).start()

    def _gira(self):
        try:                                   # no simulador: esta thread não segura o relógio do robô
            import simdebug
            simdebug.fora_do_relogio()
        except (ImportError, AttributeError):
            pass
        self.asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _faz(self, coro, tempo=180):
        return self.asyncio.run_coroutine_threadsafe(coro, self.loop).result(tempo)

    def _ferramenta(self, f):
        async def trata(args):
            self.n_chamada += 1
            ident = f'c{self.n_chamada}'
            fut = self.loop.create_future()
            self.pendentes[ident] = fut
            self.eventos.put(('chamada', ident, f['nome'], dict(args or {})))
            return await fut                   # o programa executa e devolve pelo resultados()
        return self.sdk.tool(f['nome'], f['descricao'], f['parametros'])(trata)

    async def _conecta(self):
        if self.cliente is not None:
            try:
                await self.cliente.disconnect()
            except Exception:
                pass
            self.cliente = None
        import tempfile
        sdk = self.sdk
        servidor = sdk.create_sdk_mcp_server(name='robo', version='1.0.0', tools=[self._ferramenta(f) for f in self.ferr])
        opcoes = sdk.ClaudeAgentOptions(
            tools=[], system_prompt=self.sistema, mcp_servers={'robo': servidor},
            allowed_tools=['mcp__robo__' + f['nome'] for f in self.ferr], strict_mcp_config=True,
            setting_sources=[], permission_mode='dontAsk', max_turns=16, model=self.modelo, effort=self.esforco,
            cwd=tempfile.gettempdir())
        # com uma chave de API no ambiente o Claude Code cobraria da API: este caminho é o da mensalidade
        guardadas = {k: os.environ.pop(k) for k in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN') if k in os.environ}
        try:
            self.cliente = sdk.ClaudeSDKClient(opcoes)
            await self.cliente.connect()
        finally:
            os.environ.update(guardadas)
        self.conectado_com = (self.sistema, tuple(f['nome'] for f in self.ferr))
        self.usd = 0.0

    async def _turno(self, texto):
        sdk = self.sdk
        try:
            await self.cliente.query(texto)
            falas = []
            async for m in self.cliente.receive_response():
                if isinstance(m, sdk.AssistantMessage):
                    self.modelo_real = m.model or self.modelo_real      # o modelo que de fato respondeu
                    falas.extend(b.text for b in m.content if isinstance(b, sdk.TextBlock))
                elif isinstance(m, sdk.ResultMessage):
                    self.eventos.put(('fim', m, falas))
                    return
            self.eventos.put(('erro', 'a resposta acabou sem resultado'))
        except Exception as e:
            self.eventos.put(('erro', f'{type(e).__name__}: {e}'))

    # ------------------------------------------------------------------ a mesma interface dos outros
    def prepara(self, sistema, ferr):
        self.sistema, self.ferr = sistema, list(ferr)

    def aquece(self):
        """Abre o Claude Code (uns segundos). Devolve os segundos que levou."""
        t0 = _agora()
        self._faz(self._conecta())
        return (_agora() - t0).total_seconds()

    def limpa(self):
        self._faz(self._conecta())             # conversa nova = sessão nova

    def usuario(self, texto):
        self.texto = texto

    def roda(self):
        if not self.em_turno:
            if self.cliente is None or self.conectado_com != (self.sistema, tuple(f['nome'] for f in self.ferr)):
                self._faz(self._conecta())
            self.em_turno = True
            self.asyncio.run_coroutine_threadsafe(self._turno(self.texto), self.loop)
        ev = self.eventos.get(timeout=600)
        if ev[0] == 'chamada':
            return '', [(ev[1], ev[2], ev[3])], {}
        self.em_turno = False
        if ev[0] == 'erro':
            raise RuntimeError(ev[1])
        m, falas = ev[1], ev[2]
        if m.is_error:
            raise RuntimeError(f'o Claude Code parou com erro ({m.subtype}): {m.result or m.errors or ""}')
        u = m.usage or {}
        entrada = sum(u.get(k) or 0 for k in ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'))
        total = m.total_cost_usd or 0.0         # quanto custaria pela API (estimativa do Claude Code), acumulado na sessão
        usd, self.usd = max(0.0, total - self.usd), max(total, self.usd)
        return (m.result or ' '.join(falas)).strip(), [], {'entrada': entrada, 'saida': u.get('output_tokens') or 0, 'usd': usd}

    def resultados(self, res):
        for ident, _, txt, erro in res:
            fut = self.pendentes.pop(ident, None)
            if fut is not None:
                self.loop.call_soon_threadsafe(fut.set_result, {'content': [{'type': 'text', 'text': txt}], 'is_error': bool(erro)})


def cria_modelo(tipo=None, nome=None):
    """tipo = 'claude' (API, com chave), 'assinatura' (Claude Code, pela mensalidade) ou 'local' (Ollama).
    Padrão: a variável CEREBRO, senão 'claude'. nome = CEREBRO_MODELO."""
    tipo = (tipo or os.environ.get('CEREBRO') or 'claude').lower()
    nome = nome or os.environ.get('CEREBRO_MODELO') or None
    if tipo == 'claude':
        return ModeloClaude(nome)
    if tipo == 'assinatura':
        return ModeloAssinatura(nome)
    if tipo == 'local':
        return ModeloLocal(nome)
    raise ValueError(f'CEREBRO={tipo!r}: use "claude", "assinatura" ou "local"')


# ====================================================================== o cérebro
class Cerebro:
    MAX_PASSOS = 12              # chamadas ao modelo por comando (cada uma pode pedir ferramentas)

    def __init__(self, modelo, ferr, executa, sistema, pensa=None, avisa=None):
        """executa(nome, argumentos) -> texto do resultado (levanta Exception para erro).
        pensa(função) -> o que a função devolve: o programa do robô usa para manter os motores vivos
        enquanto o modelo responde. avisa(texto): acompanha o que o cérebro faz (print, tela)."""
        self.modelo = modelo
        self.nomes = {f['nome']: f for f in ferr}
        self.executa = executa
        self.pensa = pensa or (lambda f: f())
        self.avisa = avisa or (lambda s: None)
        modelo.prepara(sistema, ferr)
        self.registro = []           # um dicionário por comando: chamadas, tempos, tokens

    def esquece(self):
        """Começa uma conversa nova."""
        self.modelo.limpa()

    def atualiza(self, ferr, sistema):
        """Troca as ferramentas e as instruções e começa uma conversa nova. Não dá para trocar com a
        conversa em andamento: a API do Claude amarra o raciocínio guardado no histórico às instruções e
        às ferramentas com que ele foi feito (erro 400 "thinking block is bound to a different
        conversation"). Por isso o caderno só entra nas instruções no começo de cada conversa."""
        self.nomes = {f['nome']: f for f in ferr}
        self.modelo.limpa()
        self.modelo.prepara(sistema, ferr)

    def comando(self, texto):
        """Um comando da pessoa. Devolve o que o robô responde (para falar)."""
        reg = {'comando': texto, 'chamadas': [], 'idas_ao_modelo': 0, 's_modelo': 0.0, 's_primeira': None,
               's_ferramentas': 0.0, 'tokens_entrada': 0, 'tokens_saida': 0, 'tokens_cache': 0, 'usd': 0.0, 'carinha': None,
               'resposta': '', 'erro': None}
        self.registro.append(reg)
        self.modelo.usuario(texto)
        try:
            for _ in range(self.MAX_PASSOS):
                t0 = _agora()
                fala, chamadas, uso = self.pensa(self.modelo.roda)
                dt = (_agora() - t0).total_seconds()
                reg['idas_ao_modelo'] += 1
                reg['s_modelo'] += dt
                if reg['s_primeira'] is None:
                    reg['s_primeira'] = dt           # o tempo até o robô começar a fazer alguma coisa
                reg['tokens_entrada'] += uso.get('entrada') or 0
                reg['tokens_saida'] += uso.get('saida') or 0
                reg['tokens_cache'] += uso.get('cache') or 0
                reg['usd'] += uso.get('usd') or 0.0
                if not chamadas:
                    # a carinha vem no começo, entre parênteses: sai da fala e fica no registro
                    m = _CARINHA.match(fala)
                    if m:
                        reg['carinha'] = m.group(1).lower() if m.group(1).lower() in HUMORES else None
                        fala = fala[m.end():].strip()
                    reg['resposta'] = fala
                    return fala
                res = []
                for ident, nome, args in chamadas:
                    self.avisa(f'{nome}({", ".join(f"{k}={v!r}" for k, v in args.items())})')
                    t0 = _agora()
                    try:
                        if nome not in self.nomes:
                            raise ValueError(f'a ferramenta "{nome}" não existe. As que existem: {", ".join(self.nomes)}')
                        txt, erro = str(self.executa(nome, args)), False
                    except Exception as e:           # o modelo fica sabendo do erro e decide o que fazer
                        txt, erro = f'ERRO: {e}', True
                    reg['s_ferramentas'] += (_agora() - t0).total_seconds()
                    reg['chamadas'].append({'nome': nome, 'args': args, 'resultado': txt, 'erro': erro})
                    self.avisa(f'  -> {txt}')
                    res.append((ident, nome, txt, erro))
                self.modelo.resultados(res)
            reg['resposta'] = 'Parei no meio: eram passos demais para um pedido só.'
        except Exception as e:
            reg['erro'] = f'{type(e).__name__}: {e}'
            reg['resposta'] = 'Não consegui pensar agora.'
            self.avisa(f'erro no modelo: {reg["erro"]}')
        return reg['resposta']
