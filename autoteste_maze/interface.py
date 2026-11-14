"""Tela (OLED de 4 linhas) e teclado (4 botões e 4 LEDs) do Mariola, para o autoteste.

Botões, da esquerda para a direita: VOLTAR, BAIXO, CIMA, ENTER.
LEDs do teclado: branco, vermelho, laranja, verde (acendem com bit 1).

Sem tela ou sem teclado o autoteste continua:
  * sem tela, tudo sai só no terminal;
  * sem teclado, num terminal (SSH) as respostas vêm pelo teclado do PC (Enter = ENTER,
    v = VOLTAR, c = CIMA, b = BAIXO); sem terminal (rodando pelo menu), vira modo automático.
No modo automático (--automatico) ninguém responde: o que depende de uma pessoa olhar ou apertar
algo fica como "PULOU" no relatório.
"""

import sys
import time

LARGURA = 20          # caracteres que cabem numa linha da tela (fonte DejaVu 12)
LINHAS = 4

VOLTAR, BAIXO, CIMA, ENTER = 1, 2, 3, 4
NOMES_BOTOES = {VOLTAR: 'VOLTAR', BAIXO: 'BAIXO', CIMA: 'CIMA', ENTER: 'ENTER'}

LED_BRANCO, LED_VERMELHO, LED_LARANJA, LED_VERDE = 1, 2, 3, 4


def quebra(texto, largura=LARGURA):
    """Quebra um texto em linhas de até 'largura' caracteres (palavra inteira quando dá)."""
    linhas = []
    for paragrafo in str(texto).split('\n'):
        atual = ''
        for palavra in paragrafo.split(' '):
            while len(palavra) > largura:
                if atual:
                    linhas.append(atual)
                    atual = ''
                linhas.append(palavra[:largura])
                palavra = palavra[largura:]
            if not atual:
                atual = palavra
            elif len(atual) + 1 + len(palavra) <= largura:
                atual += ' ' + palavra
            else:
                linhas.append(atual)
                atual = palavra
        linhas.append(atual)
    return linhas


def _stdin_sem_travar():
    """True se dá para ver se chegou uma linha no terminal sem travar (Linux/SSH)."""
    if sys.platform.startswith('win') or sys.stdin is None or not sys.stdin.isatty():
        return False
    try:
        import select   # noqa: F401
        return True
    except ImportError:
        return False


def _le_linha_pronta(espera):
    """Espera até 'espera' s por uma linha no terminal; devolve a linha ou None."""
    import select
    pronto, _, _ = select.select([sys.stdin], [], [], espera)
    if pronto:
        return sys.stdin.readline()
    return None


class Interface:
    def __init__(self, automatico=False, terminal=False):
        self.automatico = automatico
        self.tela = None
        self.teclado = None
        self.erro_tela = None
        self.erro_teclado = None
        self.erros_leitura_teclado = 0
        try:
            from tela import Tela
            self.tela = Tela()
        except Exception as erro:
            self.erro_tela = f'{type(erro).__name__}: {erro}'
        try:
            from teclado import Teclado
            self.teclado = Teclado(i2c_bus=0, i2c_address=0x38)   # placa atual: tela + teclado no conector TELA
        except Exception as erro:
            self.erro_teclado = f'{type(erro).__name__}: {erro}'
        # sem teclado: num terminal de verdade, responde pelo PC; senão não há quem responda
        # --terminal: responde no terminal mesmo com o teclado do robô funcionando
        self.console = False
        tem_terminal = sys.stdin is not None and sys.stdin.isatty()
        if not automatico and (terminal or self.teclado is None):
            if tem_terminal:
                self.console = True
            elif self.teclado is None:
                self.automatico = True
        self._anterior = set()
        self._linhas = None
        self._estado_leds = None
        self.leds(False, False, False, False)

    # ------------------------------------------------------------------ tela
    def mostra(self, *linhas, eco=True):
        """Escreve até 4 linhas na tela (e no terminal, se eco)."""
        linhas = [str(l)[:LARGURA] for l in linhas][:LINHAS]
        linhas += [''] * (LINHAS - len(linhas))
        if linhas == self._linhas:
            return
        self._linhas = linhas
        if self.tela is not None:
            try:
                self.tela.linhas = list(linhas)
                self.tela._desenha()
            except Exception as erro:
                self.erro_tela = f'{type(erro).__name__}: {erro}'
        if eco:
            print('  | ' + ' | '.join(l for l in linhas if l))

    def mensagem(self, titulo, texto, segundos=None):
        """Título na linha 1 e o texto quebrado nas outras 3."""
        corpo = quebra(texto)[:LINHAS - 1]
        self.mostra(titulo, *corpo)
        if segundos:
            time.sleep(segundos if not self.automatico else min(segundos, 0.2))

    # ------------------------------------------------------------------ LEDs
    def leds(self, branco=None, vermelho=None, laranja=None, verde=None):
        if self.teclado is None:
            return
        novo = (branco, vermelho, laranja, verde)
        for i, valor in enumerate(novo):
            if valor is None:
                continue
            try:
                self.teclado.altera_led(i + 1, 1 if valor else 0)
            except Exception:
                self.erros_leitura_teclado += 1

    def led_resultado(self, nivel):
        """Verde = ok, laranja = aviso, vermelho = falha, branco = testando."""
        self.leds(branco=(nivel == 'TESTANDO'), vermelho=(nivel == 'FALHA'),
                  laranja=(nivel == 'AVISO'), verde=(nivel == 'OK'))

    # ------------------------------------------------------------------ botões
    def apertados(self):
        """Conjunto dos botões apertados agora (lê o teclado uma vez)."""
        if self.teclado is None:
            return set()
        try:
            valor = self.teclado.bus.read_byte(self.teclado.address)
        except Exception:
            self.erros_leitura_teclado += 1
            return set()
        return {b for b in (VOLTAR, BAIXO, CIMA, ENTER) if not (valor >> (b - 1)) & 1}

    def aperto(self):
        """Botão que acabou de ser apertado (borda), ou None."""
        atual = self.apertados()
        novos = atual - self._anterior
        self._anterior = atual
        for b in (VOLTAR, ENTER, CIMA, BAIXO):
            if b in novos:
                return b
        return None

    def solta_tudo(self, timeout=3.0):
        """Espera soltar os botões (para um aperto não valer para a tela seguinte)."""
        fim = time.monotonic() + timeout
        while self.apertados() and time.monotonic() < fim:
            time.sleep(0.02)
        self._anterior = self.apertados()

    def _console(self, prompt):
        try:
            r = input(prompt + ' [Enter=ENTER, v=VOLTAR, c=CIMA, b=BAIXO] ').strip().lower()
        except EOFError:
            self.console = False
            self.automatico = True
            return None
        return {'': ENTER, 'v': VOLTAR, 'c': CIMA, 'b': BAIXO}.get(r[:1], ENTER)

    def espera(self, botoes=(ENTER, VOLTAR), timeout=None):
        """Espera um dos botões. Devolve o botão, ou None no timeout ou no modo automático."""
        if self.automatico:
            return None
        if self.console:
            while True:
                b = self._console('>')
                if b is None or b in botoes:
                    return b
        self.solta_tudo()
        fim = None if timeout is None else time.monotonic() + timeout
        while fim is None or time.monotonic() < fim:
            b = self.aperto()
            if b in botoes:
                return b
            time.sleep(0.02)
        return None

    def cancelou(self):
        """True se o VOLTAR foi apertado (para interromper um teste longo)."""
        if self.automatico or self.console:
            return False
        return self.aperto() == VOLTAR

    def pergunta(self, titulo, texto, sim='ENTER=sim', nao='VOLTAR=nao', timeout=None):
        """Pergunta de sim/não. True = ENTER, False = VOLTAR, None = ninguém respondeu."""
        corpo = quebra(texto)[:LINHAS - 2]
        corpo += [''] * (LINHAS - 2 - len(corpo))
        self.mostra(titulo, *corpo, f'{sim} {nao}'[:LARGURA])
        b = self.espera((ENTER, VOLTAR), timeout)
        if b is None:
            return None
        return b == ENTER

    def escolhe(self, titulo, opcoes, inicial=0):
        """Menu: CIMA/BAIXO andam, ENTER escolhe (devolve o índice), VOLTAR devolve None."""
        if not opcoes:
            return None
        i = max(0, min(inicial, len(opcoes) - 1))
        while True:
            topo = max(0, min(i - 1, len(opcoes) - (LINHAS - 1)))
            linhas = [titulo]
            for j in range(topo, min(topo + LINHAS - 1, len(opcoes))):
                linhas.append(('>' if j == i else ' ') + opcoes[j])
            self.mostra(*linhas, eco=False)
            if self.console:
                print(f'\n{titulo}')
                for j, op in enumerate(opcoes):
                    print(f'  {j + 1:2d}. {op}')
                try:
                    r = input('número (Enter = sair): ').strip()
                except EOFError:
                    return None
                if not r:
                    return None
                if r.isdigit() and 1 <= int(r) <= len(opcoes):
                    return int(r) - 1
                continue
            b = self.espera((CIMA, BAIXO, ENTER, VOLTAR))
            if b is None or b == VOLTAR:
                return None
            if b == ENTER:
                return i
            i = (i + (1 if b == BAIXO else -1)) % len(opcoes)

    def ao_vivo(self, funcao, periodo=0.2, segundos_automatico=2.0, paginas=1):
        """Mostra funcao(pagina) -> 4 linhas, repetindo, até ENTER ou VOLTAR (devolve o botão).
        CIMA/BAIXO trocam de página. No modo automático roda alguns segundos e devolve None."""
        pagina = 0
        fim_auto = time.monotonic() + segundos_automatico
        enter_terminal = self.console and _stdin_sem_travar()
        if self.console:
            if enter_terminal:
                print('  (Enter no terminal para continuar; b + Enter troca de página)')
            else:
                print('  (mostrando por 5 s)')
                fim_auto = time.monotonic() + 5.0
        ultimo_eco = 0.0
        self.solta_tudo()
        while True:
            linhas = funcao(pagina)
            agora = time.monotonic()
            eco = agora - ultimo_eco > (0.5 if self.console else 1.0)
            if eco:
                ultimo_eco = agora
            self._linhas = None if eco else self._linhas
            self.mostra(*linhas, eco=eco)
            if enter_terminal:
                linha = _le_linha_pronta(periodo)
                if linha is not None:
                    if linha.strip().lower().startswith('b') and paginas > 1:
                        pagina = (pagina + 1) % paginas
                        continue
                    return ENTER
                continue
            if self.automatico or self.console:
                if agora > fim_auto:
                    return None
                time.sleep(periodo)
                continue
            fim = time.monotonic() + periodo
            while time.monotonic() < fim:
                b = self.aperto()
                if b in (ENTER, VOLTAR):
                    return b
                if b in (CIMA, BAIXO) and paginas > 1:
                    pagina = (pagina + (1 if b == BAIXO else -1)) % paginas
                    break
                time.sleep(0.02)
