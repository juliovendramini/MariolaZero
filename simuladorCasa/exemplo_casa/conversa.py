"""O robô obedece a comandos em português: o cérebro (cerebro.py) decide e as habilidades executam.

    python simulador.py --casa casas/casa_julio.json --programa exemplo_casa/conversa.py

Na janela do simulador, quando aparecer a faixa amarela "Comando:", digite o pedido e aperte Enter
("vai para a cozinha", "tem alguma coisa no chão do quarto 1?", "arruma a sala de jantar").
"sair" termina. No robô, pelo ssh, é o input() normal do terminal.

Variáveis de ambiente:
    CEREBRO          "claude" (API com chave; padrão), "assinatura" (Claude Code, pela mensalidade) ou "local"
    CEREBRO_MODELO   nome do modelo (padrão: claude-haiku-5-5, o da conta ou o LOCAL_PADRAO do cerebro.py)
    CEREBRO_URL      endereço do Ollama quando ele está em outro PC (http://192.168.x.x:11434)
    CASA_COMANDOS    comandos separados por ";" para rodar sem digitar (teste sem janela)
    CASA_VOZ         "fala" = o robô fala as respostas (o comando continua digitado);
                     "ouve" = fala e ouve pelo microfone: comece a frase com "Bombertinho" ("Bombertinho,
                     vai para a cozinha"); depois de uma pergunta dele a resposta não precisa do nome;
                     "simulada" = teste sem microfone: os CASA_COMANDOS são falados por outra voz
    VOZ_MUDO=1       gera a fala mas não toca (teste)

O Claude pela API precisa de `pip install anthropic` e da chave em CEREBRO_CHAVE_API.
A voz (voz.py) precisa de piper-tts, faster-whisper e sounddevice.
"""

import datetime
import os
import queue
import re
import threading
import time

from cerebro import Cerebro, cria_modelo, ferramentas, texto_sistema
from habilidades import Habilidades
from localiza import Localizador
from mapa import Mapa
from memoria import Memoria
from navega import Navegador
from robo import Robo, BARRAS_DESCANSO

try:
    import simdebug
except ImportError:
    simdebug = None

# depois de o robô responder a uma pessoa que ele reconhece pela voz, as falas dela nos próximos segundos
# valem como conversa com ele, sem precisar dizer "Bombertinho" de novo (pedido do Julio, 12/11/2026)
JANELA_CONVERSA_S = 40


def main():
    mapa = Mapa()
    modelo = cria_modelo()
    print(f'cérebro: {modelo.tipo}, modelo {modelo.nome}; mapa: {mapa.nome}')

    r = Robo()
    r.espera_botao()
    r.garra(barras=BARRAS_DESCANSO, abertura=0, inclinacao=15, espera=0.8)
    loc = Localizador(r, mapa)
    nav = Navegador(r, mapa, loc)
    caderno = Memoria()          # o que já ensinaram ao robô (memoria.py); CEREBRO_MEMORIA troca o arquivo
    print(f'caderno: {len(caderno.notas)} nota(s) e {len(caderno.lugares)} lugar(es) marcado(s), em {caderno.caminho}')
    hab = Habilidades(r, mapa, loc, nav, avisa=lambda s: print('      ' + s), memoria=caderno)

    def montado():
        """As ferramentas e as instruções do cérebro, com o caderno como está agora. O caderno entra nas
        instruções uma vez, no começo: o que o robô aprende durante a conversa ele já tem no histórico."""
        return (ferramentas(hab.comodos),
                texto_sistema(hab.comodos, hab.base, hab.caixa or 'lugar nenhum (não há caixa no mapa)',
                              caderno=caderno.texto()))

    def pensa(funcao):
        """Chama o modelo numa thread e, enquanto ele não responde, mantém o robô vivo: sem comando por
        5 s o Mariola solta os motores, e as placas de motor reiniciam (e zeram o encoder) em 12 s."""
        caixa = {}

        def alvo():
            try:
                caixa['valor'] = funcao()
            except BaseException as e:
                caixa['erro'] = e

        th = threading.Thread(target=alvo, daemon=True)
        th.start()
        while th.is_alive():
            r.para()                    # também redesenha o rosto (piscar, boca falando)
            time.sleep(0.12)
        if 'erro' in caixa:
            raise caixa['erro']
        return caixa['valor']

    rosto = None
    if os.environ.get('CASA_ROSTO', '1') not in ('0', 'nao', 'não'):
        try:
            from rosto import Rosto
            rosto = Rosto()
            r.rosto = hab.rosto = rosto          # o Robo redesenha a cada movimento; as habilidades mudam a carinha
            rosto.momento('feliz', 2.0)
        except Exception as e:                   # sem o Pillow, por exemplo
            print(f'sem o rosto ({type(e).__name__}: {e})')

    def pensa_modelo(funcao):
        """O modelo pensando: carinha de quem pensa enquanto a resposta não vem."""
        if rosto is not None:
            rosto.estado('pensando')
        try:
            return pensa(funcao)
        finally:
            if rosto is not None:
                rosto.estado(None)

    ferr, sistema = montado()
    cer = Cerebro(modelo, ferr, hab.executa, sistema, pensa=pensa_modelo, avisa=lambda s: print('   ' + s))
    caderno.mudou = False
    if hasattr(modelo, 'aquece'):
        print('preparando o modelo...')     # carregar na placa de vídeo (local) ou abrir o Claude Code (assinatura)
        print(f'modelo pronto em {pensa(modelo.aquece):.0f} s')

    # ------------------------------------------------------------------ voz (opcional)
    modo_voz = os.environ.get('CASA_VOZ', '').lower()
    boca = ouvido = escuta = quem = None
    pessoas = {}                 # teste simulado: as "pessoas" de mentira (vozes de máquina) que falam com o robô
    mudo = bool(os.environ.get('VOZ_MUDO'))
    if modo_voz:
        from voz import Escuta, Ouvido, Quem, boca_do_robo, chamou, ouvida, vozes_de_teste, _sem_acento
        boca = boca_do_robo()
        print(f'voz: falo com a {boca.nome}, efeito {boca.efeito}' + (' (sem som)' if mudo else ''))
        if modo_voz != 'fala':
            print('carregando o reconhecimento de fala...')
            ouvido = pensa(lambda: Ouvido(palavras=hab.comodos))
            print(f'ouvido: {ouvido.nome} em {ouvido.dispositivo}')
            if os.environ.get('VOZ_QUEM', '1') not in ('0', 'nao', 'não'):
                try:                                   # reconhecer quem fala é opcional (pip install speechbrain)
                    quem = pensa(Quem)
                    hab.quem = quem
                    print(f'vozes que conheço: {", ".join(quem.nomes()) or "nenhuma ainda"} ({quem.caminho})')
                except Exception as e:
                    print(f'sem reconhecimento de quem fala ({type(e).__name__}: {e})')
        if modo_voz == 'simulada':      # teste: os comandos da fila são falados por vozes de máquina
            pessoas = vozes_de_teste()
        if simdebug is not None and hasattr(simdebug, 'fora_do_relogio'):
            # threads que as bibliotecas de fala deixam vivas não são do robô: saem do relógio do simulador
            for th in threading.enumerate():
                if th is not threading.main_thread():
                    simdebug.fora_do_relogio(th.ident)
        if ouvido is not None and not pessoas:
            escuta = Escuta(ouvido, avisa=print, quem=quem)       # daqui em diante ouve o tempo todo, numa thread

    def diz(texto):
        print(f'robô: {texto}')
        if rosto is not None:
            rosto.fala(True)                           # a boca mexe, com a carinha que o cérebro escolheu
        try:
            if boca is not None:
                if escuta is not None:
                    escuta.surdo.set()                     # não ouve a própria voz
                try:
                    if mudo:
                        som = boca.audio(texto)
                        r.espera(min(6.0, len(som) / boca.taxa))   # sem som, espera o tempo que a fala levaria
                    else:
                        pensa(lambda: boca.fala(texto))
                finally:
                    if escuta is not None:
                        escuta.fim.wait(0.3)               # espera o eco da sala
                        escuta.surdo.clear()
            elif rosto is not None:
                r.espera(min(4.0, 0.6 + len(texto) * 0.05))    # sem voz: fica "falando" o tempo de ler
        finally:
            if rosto is not None:
                rosto.fala(False)

    PARADA = ('para', 'pare', 'parou', 'espera', 'espere', 'chega', 'calma', 'stop')

    def para_mim(texto, atento=False, agindo=False):
        """A frase ouvida é com o robô? Devolve o pedido (sem o nome dele), '' se foi só o nome, ou None.
        atento = ele acabou de fazer uma pergunta; agindo = está no meio de uma tarefa, e aí um "para!"
        curto vale mesmo sem o nome."""
        pedido = chamou(texto)
        if pedido is not None:
            return pedido
        if atento:
            return str(texto)
        if agindo:
            palavras = [p.strip('.,!?') for p in _sem_acento(texto).split()]
            if palavras and len(palavras) <= 4 and palavras[0] in PARADA:
                return str(texto)
        return None

    recente = [None, None]       # quem falou por último com o robô, e quando (relógio de verdade)

    def etiqueta(fala):
        """'[quem falou: Julio] ' para pôr na frente do pedido que vai ao cérebro ('' sem reconhecimento de voz).
        Fala curta que a voz não decide, logo depois de outra da mesma conversa: provavelmente a mesma pessoa."""
        if quem is None or not isinstance(fala, str) or getattr(fala, 'audio', None) is None:
            return ''
        agora = datetime.datetime.now()
        if fala.quem:
            recente[:] = [fala.quem, agora]
            return f'[quem falou: {fala.quem}] '
        # sem certeza pela voz: vale quem acabou de falar, se a fala é curta demais para comparar ou se a
        # pessoa mais parecida é ela mesma (uma voz diferente logo em seguida continua sendo desconhecida)
        if recente[0] and (agora - recente[1]).total_seconds() < 25 and (fala.curta or fala.palpite == recente[0]):
            recente[1] = agora
            return f'[quem falou: provavelmente {recente[0]}] '
        return '[quem falou: voz que não conheço] '

    def fala_de_teste(frase):
        """Teste simulado: '@dora: frase' é dita pela voz de teste 'dora' (sem @, pela primeira da lista).
        Devolve a Fala que o robô ouviu."""
        nome = next(iter(pessoas))
        m = re.match(r'@(\w+):\s*(.*)', frase)
        if m and m.group(1) in pessoas:
            nome, frase = m.group(1), m.group(2)
        p = pessoas[nome]
        som = p.audio(frase)
        print(f'{nome} (falando): {frase}')
        return ouvida(ouvido.transcreve(som, p.taxa), som, quem, p.taxa)

    no_meio = []                 # teste simulado: [segundos depois do começo da tarefa, frase] a falar no meio dela
    t_tarefa = [0.0]

    def interrompe():
        """Consultada a cada movimento durante uma tarefa: a pessoa falou com o robô? Devolve a fala."""
        ouvidas = []
        if escuta is not None:
            while True:
                try:
                    t = escuta.fila.get_nowait()
                except queue.Empty:
                    break
                if t:
                    ouvidas.append(t)
        elif no_meio and time.time() - t_tarefa[0] >= no_meio[0][0]:
            ouvidas.append(fala_de_teste(no_meio.pop(0)[1]))
        for t in ouvidas:
            pedido = para_mim(t, agindo=True)
            print(f'   (ouvi no meio da tarefa: {str(t)!r}' + ('' if pedido is not None else '; não era comigo') + ')')
            if pedido is not None:
                hab.ouviu(t)
                return etiqueta(t) + (pedido or str(t))
        return None

    if ouvido is not None:
        hab.interrompe = interrompe

    fila = [c.strip() for c in os.environ.get('CASA_COMANDOS', '').split(';') if c.strip()]
    automatico = bool(fila)
    atento_ate = None            # depois de uma pergunta do robô, a resposta não precisa do nome dele
    conversa_com = [None, None]  # pessoa (pela voz) que acabou de conversar com o robô, e até quando vale
    falante = None
    vazios = 0
    while True:
        if automatico:
            if not fila:
                break
            # "comando >>8>> fala": no teste simulado, 8 s depois de a tarefa começar a pessoa diz a fala
            partes = re.split(r'\s*>>\s*([\d.]+)\s*>>\s*', fila.pop(0))
            texto = partes[0]
            no_meio[:] = [[float(partes[i]), partes[i + 1]] for i in range(1, len(partes) - 1, 2)] if pessoas else []
            if pessoas:
                texto = pensa(lambda: fala_de_teste(partes[0]))
                print(f'   (ouvi: {str(texto)!r}' + (f'; voz: {texto.quem or "não sei de quem"} {texto.certeza:.2f}' if quem else '') + ')')
        elif escuta is not None:
            print('   (ouvindo: fale começando por "Bombertinho")')
            texto = pensa(escuta.fila.get)           # espera alguém falar uma frase
            if texto is None:
                print('sem microfone: termino aqui')
                break
            print(f'   (ouvi: {str(texto)!r}' + (f'; voz: {texto.quem or "não sei de quem"} {texto.certeza:.2f}' if quem else '') + ')')
        else:
            texto = (input('Comando:') or '').strip()
            if not texto:
                vazios += 1
                if vazios == 3:
                    print('(digite o comando na faixa amarela da janela e aperte Enter; "sair" termina)')
                r.espera(0.3)
                continue
        de_quem = ''
        sem_nome = False
        if ouvido is not None:
            # por voz o robô só obedece quando chamam pelo nome, ou logo depois de uma pergunta dele, ou
            # quando a mesma pessoa (reconhecida pela voz) continua a conversa que acabou de ter com ele
            agora = datetime.datetime.now()          # relógio de verdade (no simulador o time é o do robô)
            pedido = para_mim(texto, atento=bool(atento_ate and agora < atento_ate))
            if (pedido is None and quem is not None and conversa_com[0] and agora < conversa_com[1]
                    and (texto.quem == conversa_com[0]
                         or (texto.quem is None and (texto.curta or texto.palpite == conversa_com[0])))):
                pedido, sem_nome = str(texto), True
            if pedido is None:
                print('   (não era comigo)')
                continue
            if pedido == '':
                diz('Oi?')
                if rosto is not None:
                    rosto.momento('ouvindo', 6.0)
                atento_ate = datetime.datetime.now() + datetime.timedelta(seconds=15)
                continue
            hab.ouviu(texto)                         # guarda o som desta fala (apresentação de voz)
            de_quem = etiqueta(texto)
            falante = texto.quem or (recente[0] if 'provavelmente' in de_quem else None)
            if sem_nome:
                # o cérebro decide se é mesmo com ele; se não for, responde SILENCIO e o robô fica quieto
                de_quem += '[sem chamar pelo nome] '
            texto = pedido
        print(f'pessoa: {de_quem}{texto}')
        if texto.lower().strip(' .!') in ('sair', 'fim', 'tchau', 'pode desligar'):
            break
        hab.humor_escolhido = False
        t0 = t_tarefa[0] = time.time()
        resposta = cer.comando(de_quem + texto)
        reg = cer.registro[-1]
        if ouvido is not None and _sem_acento(resposta).strip(' .!"').upper().startswith('SILENCIO'):
            print('   (fiquei quieto: essa não era comigo)')
            continue
        if rosto is not None and reg.get('carinha'):
            rosto.humor(reg['carinha'])              # a carinha que o cérebro pôs no começo da resposta
            print(f'   (carinha: {reg["carinha"]})')
        diz(resposta)
        if ouvido is not None and not falante and hab.reforco:
            falante = hab.reforco[0]                 # acabou de se apresentar neste pedido: agora tem nome
        if ouvido is not None and falante:
            # quem acabou de conversar com o robô pode continuar sem dizer o nome dele por um tempo
            conversa_com[:] = [falante, datetime.datetime.now() + datetime.timedelta(seconds=JANELA_CONVERSA_S)]
        print(f'   [o modelo levou {reg["s_primeira"] or 0:.1f} s para decidir e {reg["s_modelo"]:.1f} s ao todo, em '
              f'{reg["idas_ao_modelo"]} idas; o pedido inteiro levou {time.time() - t0:.0f} s do robô]')
        atento_ate = (datetime.datetime.now() + datetime.timedelta(seconds=20)) if resposta.rstrip().endswith('?') else None
        if simdebug is not None:
            simdebug.texto(f'pessoa: {texto[:56]}\nrobô: {resposta[:54]}\n{resposta[54:112]}')
    r.para()
    if escuta is not None:
        escuta.para()
    n = len(cer.registro)
    if n:
        print(f'fim: {n} comando(s); o modelo levou em média {sum(x["s_primeira"] or 0 for x in cer.registro) / n:.1f} s '
              f'para decidir; tokens: {sum(x["tokens_entrada"] for x in cer.registro)} de entrada, '
              f'{sum(x["tokens_saida"] for x in cer.registro)} de saída; ~US$ {sum(x["usd"] for x in cer.registro):.4f} de API')


if __name__ == '__main__':
    main()
