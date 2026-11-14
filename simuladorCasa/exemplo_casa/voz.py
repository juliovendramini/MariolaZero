"""A voz do robô: falar (Boca) e ouvir (Ouvido). Ouvir roda no próprio computador, sem internet.

* boca_do_robo(): a voz do robô, escolhida em VOZES_ROBO pela variável VOZ_ROBO. A padrão
  ('thalita_robo', 14/11/2026) é uma voz do edge-tts (`pip install edge-tts`), que **precisa de internet**,
  com rouquidão e metal por cima (BocaEdge). Sem internet ela fala com a 'cadu_desenho' do Piper.
* Boca: Piper (`pip install piper-tts`), com uma voz em português do Brasil da pasta vozes/
  (`python -m piper.download_voices --download-dir vozes pt_BR-faber-medium`). Leve: roda no Banana Pi.
* Ouvido: faster-whisper (`pip install faster-whisper`). No PC usa a placa de vídeo com o modelo
  large-v3-turbo; sem placa cai para a CPU com o modelo small. No robô de verdade o microfone fica
  nele e o reconhecimento num PC da casa (a fazer: hoje é tudo na mesma máquina).
* Som: sounddevice (`pip install sounddevice`), para tocar e para gravar do microfone.

Não há "palavra de chamada" treinada. O robô ouve cada frase (gravada do primeiro som até o silêncio),
transcreve e só obedece se a frase começar pelo nome dele (chamou()) ou vier logo depois de uma
pergunta que ele mesmo fez.

Variáveis de ambiente: VOZ_ROBO (padrão thalita_robo; cadu_desenho = a de antes, sem internet),
VOZ_NOME (padrão pt_BR-cadu-medium) e VOZ_EFEITO (padrão "desenho"; "nenhum" = a voz como ela é), que
trocam a voz do robô por uma do Piper, VOZ_PASTA, VOZ_OUVIDO (modelo do whisper), VOZ_DISPOSITIVO ("cuda" ou "cpu").
"""

import difflib
import os
import unicodedata
import wave

import numpy as np

try:
    # o tqdm (barras de progresso do huggingface e do whisper) cria uma thread de vigia que fica viva para
    # sempre; aqui ela não serve para nada, e no simulador atrapalha o relógio do robô
    import tqdm
    tqdm.tqdm.monitor_interval = 0
except ImportError:
    pass

AQUI = os.path.dirname(os.path.abspath(__file__))
PASTA_VOZES = os.environ.get('VOZ_PASTA') or os.path.join(AQUI, '..', 'vozes')
# a voz do robô: cadu com o tom bem mais fino ("cadu_desenho"), escolha do Julio em 12/11/2026, "por enquanto"
VOZ_PADRAO = 'pt_BR-cadu-medium'
EFEITO_PADRAO = 'desenho'
TAXA_OUVIDO = 16000                 # o whisper trabalha em 16 kHz
NOMES = ('bombertinho', 'bombertino', 'bombetinho', 'bombeirinho', 'bomber', 'robô', 'robozinho')


def _sem_acento(s):
    return ''.join(c for c in unicodedata.normalize('NFD', str(s).lower()) if unicodedata.category(c) != 'Mn')


def reamostra(audio, de, para):
    """Muda a taxa de amostragem de um áudio (vetor float32) por interpolação linear."""
    if de == para or len(audio) == 0:
        return audio.astype(np.float32)
    n = int(round(len(audio) * para / de))
    return np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype(np.float32)


def le_wav(wav, pula_s=0.0):
    """O áudio de um .wav (o caminho ou os bytes; 8 ou 16 bits, qualquer taxa, mono ou estéreo) pronto
    para o Whisper e o Quem: vetor float32 mono a 16 kHz, sem o nível contínuo que vai mudando (tira a
    média de cada 50 ms) e com o volume no máximo. pula_s = começo a jogar fora (o estalo do microfone
    da webcam UC60 ao ligar).

    A primeira versão (no teste_brick, 13/11/2026) tirava a média de cada 10 ms: cortava o grave da voz,
    soava pior (o Julio achou o original melhor) e o Whisper perdia palavras; com 50 ms entende igual
    ao áudio só sem o estalo."""
    import io
    with wave.open(io.BytesIO(wav) if isinstance(wav, (bytes, bytearray)) else wav) as w:
        taxa, canais, larg = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if larg == 1:
        a = np.frombuffer(raw, np.uint8).astype(np.float32) - 128.0
    else:
        a = np.frombuffer(raw, np.int16).astype(np.float32)
    a = a.reshape(-1, canais).mean(axis=1)[int(taxa * pula_s):]
    if len(a) == 0:
        return np.zeros(0, np.float32)
    n = max(1, taxa // 20)
    a = a - np.convolve(a, np.ones(n, np.float32) / n, mode='same')
    pico = float(np.abs(a).max())
    return reamostra(a / pico * 0.9 if pico > 0 else a, taxa, TAXA_OUVIDO)


def wav_bytes(audio, taxa):
    """Um vetor float32 (-1 a 1) como os bytes de um .wav mono de 16 bits."""
    import io
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(taxa))
        w.writeframes((np.clip(np.asarray(audio, np.float32), -1, 1) * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


def chamou(texto, nomes=NOMES):
    """Se a frase começa chamando o robô pelo nome ("Bombertinho, vai para a cozinha"), devolve o resto
    ("vai para a cozinha"); se é só o nome, devolve ''; se não chamou, None. Aceita o nome um pouco
    errado, porque o reconhecimento de fala não o conhece."""
    palavras = texto.strip().split()
    for i, p in enumerate(palavras[:3]):                 # "ô Bombertinho", "ei, Bombertinho"
        limpa = _sem_acento(p).strip('.,!?:;"\'')
        if any(difflib.SequenceMatcher(None, limpa, _sem_acento(n)).ratio() >= 0.78 for n in nomes):
            return ' '.join(palavras[i + 1:]).lstrip('.,!?:; ').strip()
    return None


def _acha_cuda():
    """No Windows o faster-whisper precisa das DLLs do CUDA (cublas, cudnn) no caminho de busca. Elas
    vêm com o PyTorch (torch/lib) ou com os pacotes nvidia-*-cu12 do pip: põe essas pastas no PATH."""
    if os.name != 'nt':
        return
    import importlib.util
    pastas = []
    spec = importlib.util.find_spec('torch')
    if spec and spec.origin:
        pastas.append(os.path.join(os.path.dirname(spec.origin), 'lib'))
    spec = importlib.util.find_spec('nvidia')
    for raiz in (spec.submodule_search_locations or []) if spec else []:
        for sub in os.listdir(raiz):
            pastas.append(os.path.join(raiz, sub, 'bin'))
    for p in pastas:
        if os.path.isdir(p) and p not in os.environ.get('PATH', ''):
            os.environ['PATH'] = p + os.pathsep + os.environ.get('PATH', '')
            try:
                os.add_dll_directory(p)
            except OSError:
                pass


# Efeitos para a voz ficar "de robô": (agudo, anel_hz, anel_forca, eco_ms, eco_forca, degrau_hz)
#   agudo      quanto a voz sobe de tom (1.0 = normal; 1.3 = bem mais fina), sem mudar a velocidade
#   anel       multiplica a fala por uma onda (modulação em anel): o zumbido clássico de robô
#   eco        eco muito curto que se repete (filtro pente): som de tubo de metal
#   degrau_hz  segura cada amostra por um tempo (som "de brinquedo eletrônico"); 0 = desligado
EFEITOS = {
    'nenhum': (1.0, 0, 0.0, 0, 0.0, 0),
    'agudo': (1.20, 0, 0.0, 0, 0.0, 0),             # só o tom mais fino, sem distorção: personagem pequeno
    'desenho': (1.40, 0, 0.0, 0, 0.0, 0),           # bem fino, voz de desenho animado
    # os de baixo distorcem a voz; o Julio ouviu em 12/11/2026 e achou que ficou pior
    'robozinho': (1.30, 0, 0.0, 5, 0.45, 0),        # fino e levemente metálico: robô pequeno e simpático
    'metalico': (1.0, 55, 0.80, 7, 0.50, 0),        # zumbido grave, robô de filme antigo
    'lata': (1.15, 90, 0.50, 4, 0.40, 7000),        # fino, com zumbido e som de brinquedo
    'grave': (0.80, 40, 0.60, 9, 0.50, 0),          # robô grande
}


def aplica_efeito(a, taxa, anel_hz, anel_forca, eco_ms, eco_forca, degrau_hz):
    """Os efeitos que vêm depois da fala pronta (o tom é mudado antes, na síntese)."""
    a = a.astype(np.float32)
    if anel_hz and anel_forca:
        t = np.arange(len(a)) / taxa
        a = a * (1.0 - anel_forca + anel_forca * np.sin(2 * np.pi * anel_hz * t)).astype(np.float32)
    if eco_ms and eco_forca:
        d = max(1, int(taxa * eco_ms / 1000.0))
        y = a.copy()
        for i in range(d, len(y), d):                  # y[n] = x[n] + g * y[n - d], em blocos de d amostras
            y[i:i + d] += eco_forca * y[i - d:i][:len(y[i:i + d])]
        a = y
    if degrau_hz and degrau_hz < taxa:
        passo = max(1, int(round(taxa / degrau_hz)))
        a = np.repeat(a[::passo], passo)[:len(a)]
    pico = float(np.max(np.abs(a))) if len(a) else 0.0
    return (a * (0.9 / pico)).astype(np.float32) if pico > 0 else a


def _faixa(x, taxa, de, ate):
    """Filtro passa-faixa pela FFT (corta o que está fora de de..ate Hz)."""
    f = np.fft.rfft(x)
    hz = np.fft.rfftfreq(len(x), 1.0 / taxa)
    f[(hz < de) | (hz > ate)] = 0
    return np.fft.irfft(f, len(x)).astype(np.float32)


def rouco(a, taxa, saturacao, sopro, aspereza, semente=7):
    """Deixa a voz rouca, com três coisas juntas:
    saturacao  distorção suave (tanh; 1 = nenhuma): a voz fica mais áspera
    sopro      chiado de ar (ruído de 1,2 a 7 kHz) que só aparece onde tem fala
    aspereza   tremor rápido e irregular (30 a 80 Hz) no volume: a voz "arranhada"
    """
    if len(a) == 0:
        return a.astype(np.float32)
    rng = np.random.default_rng(semente)
    a = a.astype(np.float32) / (float(np.max(np.abs(a))) + 1e-9)
    n = max(1, int(taxa * 0.010))
    env = np.convolve(np.abs(a), np.ones(n, np.float32) / n, mode='same').astype(np.float32)
    if aspereza:
        m = _faixa(rng.standard_normal(len(a)).astype(np.float32), taxa, 30, 80)
        a = a * (1.0 + aspereza * m / (float(np.max(np.abs(m))) + 1e-9))
    if saturacao > 1:
        a = np.tanh(saturacao * a) / np.tanh(saturacao)
    if sopro:
        r = _faixa(rng.standard_normal(len(a)).astype(np.float32), taxa, 1200, 7000)
        a = a + sopro * env / (float(np.max(env)) + 1e-9) * r / (float(np.max(np.abs(r))) + 1e-9)
    return (a / (float(np.max(np.abs(a))) + 1e-9) * 0.9).astype(np.float32)


# As vozes do robô. VOZ_ROBO escolhe (padrão: VOZ_ROBO_PADRAO).
#   'edge'   voz neural da Microsoft pelo edge-tts (pip install edge-tts; precisa de internet), com o tom,
#            a velocidade, a rouquidão (rouco()) e o metal (aplica_efeito()) por cima
#   'piper'  voz do Piper da pasta vozes/, com um efeito de EFEITOS (sem internet; é a que roda no brick)
VOZES_ROBO = {
    # escolha do Julio em 14/11/2026 (amostra 30): a Thalita meio tom acima do normal (+26 Hz; a "fina" de
    # +40 Hz ficou aguda demais), metal com zumbido leve e rouquidão leve. Parecida com a do robô Titã
    # (@tit.bott, que usa o Xiaozhi)
    'thalita_robo': {'motor': 'edge', 'voz': 'pt-BR-ThalitaMultilingualNeural', 'tom': '+26Hz',
                     'velocidade': '+8%', 'rouco': (2.0, 0.12, 0.15), 'metal': (60, 0.25, 5, 0.45, 0)},
    # a de antes (12/11/2026): cadu com o tom bem mais fino. Fica de reserva sem internet
    'cadu_desenho': {'motor': 'piper', 'voz': 'pt_BR-cadu-medium', 'efeito': 'desenho'},
}
# a thalita_robo foi a padrão só por algumas horas em 14/11/2026: o Julio não quer voz pela internet ("tem que
# ser gerada localmente"). Fica aqui só para comparar
VOZ_ROBO_PADRAO = 'cadu_desenho'
VOZ_ROBO_RESERVA = 'cadu_desenho'


class BocaEdge:
    """Fala com uma voz do edge-tts (a mesma cara da Boca: .audio, .taxa, .grava, .fala). Sem internet (ou
    sem o edge-tts) fala com a Boca do Piper de VOZ_ROBO_RESERVA e tenta a internet de novo depois de
    TENTA_DE_NOVO_S."""

    TENTA_DE_NOVO_S = 60.0
    GUARDA = 200                                        # quantas falas ficam guardadas (repetidas saem na hora)
    taxa = 24000                                        # o edge-tts manda MP3 mono de 24 kHz

    def __init__(self, nome='thalita_robo'):
        self.nome = nome
        self.conf = VOZES_ROBO[nome]
        self.efeito = nome
        self._reserva = None
        self._falhou_em = None
        self._guardadas = {}                            # texto -> áudio (a internet leva de 1 a 3 s por fala)
        self.usou_reserva = False                       # a última fala saiu da reserva?

    def _edge(self, texto):
        import io
        import av
        import edge_tts
        c = self.conf
        com = edge_tts.Communicate(texto, c['voz'], pitch=c.get('tom', '+0Hz'), rate=c.get('velocidade', '+0%'))
        mp3 = b''.join(p['data'] for p in com.stream_sync() if p.get('type') == 'audio')
        if not mp3:
            raise RuntimeError('o edge-tts não devolveu áudio')
        arq = av.open(io.BytesIO(mp3))
        taxa = arq.streams.audio[0].rate
        partes = []
        for q in arq.decode(audio=0):
            x = q.to_ndarray().astype(np.float32)
            partes.append(x.mean(axis=0) if x.ndim > 1 else x)
        arq.close()
        a = np.concatenate(partes)
        if np.max(np.abs(a)) > 1.5:                     # veio em inteiro de 16 bits
            a = a / 32768.0
        if taxa != self.taxa:
            a = reamostra(a, taxa, self.taxa)
        if c.get('rouco'):
            a = rouco(a, self.taxa, *c['rouco'])
        if c.get('metal'):
            a = aplica_efeito(a, self.taxa, *c['metal'])
        return a.astype(np.float32)

    def audio(self, texto):
        """O texto falado: vetor float32 de -1 a 1, na taxa self.taxa."""
        import time as _t
        texto = str(texto).strip()
        if not texto:
            return np.zeros(0, np.float32)
        if texto in self._guardadas:
            self.usou_reserva = False
            return self._guardadas[texto]
        if self._falhou_em is None or _t.monotonic() - self._falhou_em > self.TENTA_DE_NOVO_S:
            try:
                a = self._edge(texto)
                self._falhou_em, self.usou_reserva = None, False
                if len(self._guardadas) >= self.GUARDA:
                    self._guardadas.pop(next(iter(self._guardadas)))
                self._guardadas[texto] = a
                return a
            except Exception as e:
                if self._falhou_em is None:
                    print(f'[voz] sem a voz {self.nome} ({type(e).__name__}: {e}); falo com a {VOZ_ROBO_RESERVA}')
                self._falhou_em = _t.monotonic()
        if self._reserva is None:
            self._reserva = boca_do_robo(VOZ_ROBO_RESERVA)
        self.usou_reserva = True
        a = self._reserva.audio(texto)
        return reamostra(a, self._reserva.taxa, self.taxa)

    grava = None                                        # preenchidas depois da Boca (são as mesmas)
    fala = None


def boca_do_robo(nome=None):
    """A boca com a voz do robô: nome de VOZES_ROBO, ou a variável VOZ_ROBO, ou VOZ_ROBO_PADRAO.
    VOZ_NOME / VOZ_EFEITO, quando existem, ainda valem para uma voz do Piper (como antes)."""
    if nome is None and (os.environ.get('VOZ_NOME') or os.environ.get('VOZ_EFEITO')) and not os.environ.get('VOZ_ROBO'):
        return Boca()
    nome = nome or os.environ.get('VOZ_ROBO') or VOZ_ROBO_PADRAO
    if nome not in VOZES_ROBO:
        raise ValueError(f'voz do robô {nome!r} não existe. As que existem: {", ".join(VOZES_ROBO)}')
    c = VOZES_ROBO[nome]
    if c['motor'] == 'edge':
        return BocaEdge(nome)
    return Boca(c['voz'], efeito=c.get('efeito', 'nenhum'))


class Boca:
    """Fala um texto com o Piper. efeito = um nome de EFEITOS (ou a variável VOZ_EFEITO)."""

    def __init__(self, voz=None, pasta=None, efeito=None):
        from piper import PiperVoice
        self.efeito = efeito or os.environ.get('VOZ_EFEITO') or EFEITO_PADRAO
        if self.efeito not in EFEITOS:
            raise ValueError(f'efeito de voz {self.efeito!r} não existe. Os que existem: {", ".join(EFEITOS)}')
        self.nome = voz or os.environ.get('VOZ_NOME') or VOZ_PADRAO
        caminho = os.path.join(pasta or PASTA_VOZES, self.nome + '.onnx')
        if not os.path.exists(caminho):
            raise FileNotFoundError(f'não achei a voz {caminho}. Baixe com: python -m piper.download_voices '
                                    f'--download-dir vozes {self.nome}')
        self.voz = PiperVoice.load(caminho)
        self.taxa = int(self.voz.config.sample_rate)

    def audio(self, texto):
        """O texto falado: vetor float32 de -1 a 1, na taxa self.taxa."""
        agudo, *resto = EFEITOS[self.efeito]
        conf = None
        if agudo != 1.0:
            # para mudar o tom sem mudar a velocidade: o Piper fala mais devagar (ou mais rápido) e o
            # áudio é encolhido (ou esticado) de volta para a duração normal
            from piper import SynthesisConfig
            conf = SynthesisConfig(length_scale=agudo)
        partes = [c.audio_int16_array for c in self.voz.synthesize(texto, conf)]
        if not partes:
            return np.zeros(0, np.float32)
        a = np.concatenate(partes).astype(np.float32) / 32768.0
        if agudo != 1.0:
            a = reamostra(a, self.taxa * agudo, self.taxa)
        return aplica_efeito(a, self.taxa, *resto) if self.efeito != 'nenhum' else a

    def grava(self, texto, caminho):
        """Grava o texto falado num arquivo .wav."""
        a = (np.clip(self.audio(texto), -1, 1) * 32767).astype(np.int16)
        with wave.open(caminho, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.taxa)
            w.writeframes(a.tobytes())
        return caminho

    def fala(self, texto):
        """Fala pelo alto-falante e espera terminar."""
        import sounddevice as sd
        a = self.audio(texto)
        if len(a):
            sd.play(a, self.taxa)
            sd.wait()


BocaEdge.grava = Boca.grava
BocaEdge.fala = Boca.fala


class Ouvido:
    """Transforma fala em texto com o faster-whisper."""

    def __init__(self, modelo=None, dispositivo=None, palavras=()):
        """palavras: nomes que o robô precisa entender (o dele, os cômodos); entram como dica."""
        from faster_whisper import WhisperModel
        dispositivo = dispositivo or os.environ.get('VOZ_DISPOSITIVO')
        modelo = modelo or os.environ.get('VOZ_OUVIDO')
        tentativas = [(dispositivo, modelo)] if dispositivo else [('cuda', modelo), ('cpu', modelo)]
        erro = None
        for disp, mod in tentativas:
            mod = mod or ('large-v3-turbo' if disp == 'cuda' else 'small')
            try:
                if disp == 'cuda':
                    _acha_cuda()
                self.modelo = WhisperModel(mod, device=disp, compute_type='float16' if disp == 'cuda' else 'int8')
                # as bibliotecas da placa só são carregadas na primeira transcrição: testa já
                list(self.modelo.transcribe(np.zeros(TAXA_OUVIDO // 2, np.float32), language='pt')[0])
                self.nome, self.dispositivo = mod, disp
                break
            except Exception as e:                # sem placa de vídeo ou sem as bibliotecas dela: tenta a CPU
                erro = e
        else:
            raise RuntimeError(f'não consegui carregar o reconhecimento de fala: {erro}')
        # a dica é o nome em frases curtas (como as pessoas falam com ele) e depois as outras palavras. A
        # antiga, "Comandos para o robô Bombertinho. <cômodos>.", diluía o nome: numa gravação do microfone
        # da webcam no brick (13/11/2026) o Whisper escrevia "Humberto" ou pulava o nome; com esta, saiu
        # "Bombertinho" em todas as combinações testadas (com e sem filtro de voz e carimbos de tempo)
        self.dica = 'Bombertinho, vai para a cozinha. Bombertinho, me ajuda.'
        if palavras:
            self.dica += ' ' + ', '.join(palavras) + '.'

    def transcreve(self, audio, taxa=TAXA_OUVIDO):
        """audio = vetor float32 (-1 a 1) ou o caminho de um .wav. Devolve o texto ('' = não era fala)."""
        if not isinstance(audio, str):
            audio = reamostra(np.asarray(audio, np.float32), taxa, TAXA_OUVIDO)
        # o nome vem da dica (veja o __init__); a hotwords reforça
        trechos, info = self.modelo.transcribe(audio, language='pt', beam_size=5, vad_filter=True,
                                               condition_on_previous_text=False, initial_prompt=self.dica,
                                               hotwords='Bombertinho', without_timestamps=True)
        texto = ' '.join(t.text.strip() for t in trechos).strip()
        self.fala_s = float(info.duration_after_vad)
        if self.fala_s < self.MIN_FALA_S:
            # um barulho curto que o filtro de voz deixou passar: o Whisper "ouve" nele uma palavra da dica
            # ou uma das invenções típicas dele ("Obrigado.", "Bombertinho."), e o robô responderia do nada
            return ''
        return texto

    # menos fala que isto (pelo filtro de voz do Whisper, que já soma uma folga em volta) é barulho. Teste de
    # 13/11/2026 com o microfone da webcam no brick: um barulho que virou "Obrigado." tinha 0,46 s; palavras
    # soltas de verdade ("Para!", "Sim.", "Não.", "Vai.", 6 vozes, com e sem ruído) dão 1,38 s ou mais
    MIN_FALA_S = 0.8
    fala_s = 0.0                     # quanto de fala a última transcrição tinha

    BLOCO_S = 0.03

    @staticmethod
    def _abre_microfone():
        import sounddevice as sd
        return sd.InputStream(samplerate=TAXA_OUVIDO, channels=1, dtype='float32', blocksize=int(TAXA_OUVIDO * Ouvido.BLOCO_S))

    @staticmethod
    def _mede_ruido(mic, blocos=16):
        bloco = int(TAXA_OUVIDO * Ouvido.BLOCO_S)
        return float(np.median([float(np.sqrt(np.mean(mic.read(bloco)[0] ** 2))) for _ in range(blocos)]))

    @staticmethod
    def _captura(mic, ruido, espera_s=None, max_s=12.0, silencio_s=0.9, cancela=None):
        """Com o microfone aberto: espera alguém começar a falar, grava e para depois de 'silencio_s' sem
        som. Devolve (áudio ou None, ruído atualizado). cancela() -> True larga tudo (devolve None)."""
        bloco = int(TAXA_OUVIDO * Ouvido.BLOCO_S)
        antes, gravado, falando = [], [], False
        quietos = altos = n = 0
        while True:
            x = mic.read(bloco)[0][:, 0].copy()
            n += 1
            if cancela is not None and cancela():
                return None, ruido
            volume = float(np.sqrt(np.mean(x ** 2)))
            alto = volume > max(0.012, 2.2 * ruido)
            if not falando:
                antes = (antes + [x])[-25:]                  # guarda 0,75 s antes da fala (o começo é baixo)
                altos = altos + 1 if alto else 0
                if not alto:
                    ruido += 0.02 * (volume - ruido)         # o ruído do ambiente muda devagar: acompanha
                if altos >= 3:
                    falando, gravado, quietos = True, list(antes), 0
                elif espera_s is not None and n * Ouvido.BLOCO_S > espera_s:
                    return None, ruido
            else:
                gravado.append(x)
                quietos = 0 if alto else quietos + 1
                if quietos * Ouvido.BLOCO_S >= silencio_s or len(gravado) * Ouvido.BLOCO_S >= max_s:
                    return np.concatenate(gravado), ruido

    def grava_frase(self, espera_s=None, max_s=12.0, silencio_s=0.9, avisa=None):
        """Grava do microfone uma frase: espera alguém começar a falar, grava e para depois de
        'silencio_s' sem som. Devolve o áudio (float32, 16 kHz) ou None se ninguém falou em 'espera_s'
        segundos (None = espera para sempre).

        O começo e o fim da fala são achados pelo volume, comparado com o ruído do ambiente medido no
        primeiro meio segundo. É simples: num lugar barulhento ele corta errado."""
        with self._abre_microfone() as mic:
            ruido = self._mede_ruido(mic)
            if avisa:
                avisa(f'ouvindo (ruído {ruido:.4f}, limite {max(0.012, 2.2 * ruido):.4f})')
            return self._captura(mic, ruido, espera_s, max_s, silencio_s)[0]

    def escuta(self, **kw):
        """Grava uma frase do microfone e devolve o texto ('' se não era fala; None se ninguém falou)."""
        a = self.grava_frase(**kw)
        return None if a is None else self.transcreve(a)


class Escuta:
    """Ouve o tempo todo, numa thread: cada frase entendida vai, como texto, para a fila self.fila.

    Serve para o robô ouvir enquanto anda ou pensa: o programa olha a fila a cada movimento e interrompe a
    tarefa quando a frase é com ele. Enquanto o robô fala, chame surdo.set() (e surdo.clear() depois):
    ele não ouve a própria voz, e o que estava sendo gravado nessa hora é jogado fora."""

    def __init__(self, ouvido, avisa=None, quem=None):
        """quem = um Quem (reconhece a pessoa pela voz): cada frase da fila vem como Fala, com .quem."""
        import queue
        import threading
        self.ouvido = ouvido
        self.quem = quem
        self.avisa = avisa
        self.fila = queue.Queue()
        self.surdo = threading.Event()
        self.fim = threading.Event()
        self.erro = None
        self.th = threading.Thread(target=self._laco, daemon=True)
        self.th.start()

    def _laco(self):
        try:                                   # no simulador: esta thread não segura o relógio do robô
            import simdebug
            simdebug.fora_do_relogio()
        except (ImportError, AttributeError):
            pass
        try:
            with self.ouvido._abre_microfone() as mic:
                ruido = self.ouvido._mede_ruido(mic)
                bloco = int(TAXA_OUVIDO * Ouvido.BLOCO_S)
                while not self.fim.is_set():
                    if self.surdo.is_set():
                        mic.read(bloco)                    # continua lendo para o som do robô não se acumular
                        continue
                    audio, ruido = self.ouvido._captura(mic, ruido, cancela=lambda: self.surdo.is_set() or self.fim.is_set())
                    if audio is None or self.surdo.is_set():
                        continue
                    texto = self.ouvido.transcreve(audio)
                    if texto and not self.surdo.is_set():
                        self.fila.put(ouvida(texto, audio, self.quem))
        except Exception as e:                 # sem microfone, por exemplo: o programa fica sabendo
            self.erro = e
            if self.avisa:
                self.avisa(f'a escuta parou: {type(e).__name__}: {e}')
            self.fila.put(None)

    def para(self):
        self.fim.set()


class Fala(str):
    """Uma frase ouvida: é o texto (uma str), com quem falou pendurado.
    quem = nome da pessoa reconhecida pela voz, ou None; certeza = semelhança da voz (0 a 1); audio = o som."""
    quem = None
    certeza = 0.0
    audio = None
    palpite = None
    curta = False


def ouvida(texto, audio, quem=None, taxa=TAXA_OUVIDO):
    """Monta a Fala de uma frase transcrita: o texto, o som e (com um Quem) a pessoa que falou."""
    f = Fala(texto)
    f.audio = reamostra(np.asarray(audio, np.float32), taxa, TAXA_OUVIDO)
    if quem is not None:
        f.quem, f.certeza = quem.quem(f.audio)
        notas = quem.notas(f.audio)
        f.curta = not notas and bool(quem.pessoas)          # curta demais para dizer qualquer coisa
        # palpite: a pessoa mais parecida, quando a semelhança não basta para afirmar mas não é desprezível
        f.palpite = notas[0][1] if notas and notas[0][0] >= quem.LIMITE * 0.6 else None
    return f


class Quem:
    """Reconhece quem está falando pela voz.

    Um modelo pequeno (ECAPA-TDNN do speechbrain, `pip install speechbrain`) transforma cada frase numa
    assinatura de 192 números. A pessoa se apresenta uma vez (apresenta()), a assinatura dela fica
    guardada, e cada frase nova é comparada com as guardadas (quem()).

    Serve para o robô tratar cada um pelo nome e ter recados por pessoa. Não é trava de segurança: frase
    curta erra, vozes parecidas da mesma família se confundem, e uma gravação engana.

    As assinaturas são dados biométricos das pessoas da casa: ficam só neste computador, no arquivo
    memoria/vozes.json (ou VOZ_PESSOAS), e esquece() apaga a de uma pessoa."""

    # semelhança mínima com a pessoa para dizer que é ela. A CALIBRAR com as vozes de verdade da casa
    # (testa_voz.py --quem-fala): com vozes de máquina, a própria voz dá 0,70 em média (10% das frases abaixo
    # de 0,45) e uma voz desconhecida chega a 0,55 com a pessoa mais parecida. Mais alto = mais "não sei quem
    # é"; mais baixo = mais visita chamada pelo nome de alguém da casa.
    LIMITE = 0.45
    FOLGA = 0.07               # e tem de ganhar da segunda colocada por pelo menos isto
    MIN_S = 1.0                # com menos de 1 s de fala não dá para dizer nada
    MAX_AMOSTRAS = 30

    def __init__(self, caminho=None, dispositivo=None):
        import torch
        from speechbrain.inference.speaker import EncoderClassifier
        from speechbrain.utils.fetching import LocalStrategy
        self.torch = torch
        self.caminho = caminho or os.environ.get('VOZ_PESSOAS') or os.path.join(AQUI, '..', 'memoria', 'vozes.json')
        disp = dispositivo or os.environ.get('VOZ_DISPOSITIVO') or ('cuda:0' if torch.cuda.is_available() else 'cpu')
        if disp == 'cuda':
            disp = 'cuda:0'
        self.modelo = EncoderClassifier.from_hparams(
            source='speechbrain/spkrec-ecapa-voxceleb', savedir=os.path.join(PASTA_VOZES, 'ecapa'),
            run_opts={'device': disp}, local_strategy=LocalStrategy.COPY)     # COPY: no Windows atalho precisa de permissão
        self.pessoas = {}          # nome -> lista de assinaturas (vetores de norma 1)
        if os.path.exists(self.caminho):
            try:
                import json
                with open(self.caminho, 'r', encoding='utf-8') as f:
                    self.pessoas = {n: [np.array(v, np.float32) for v in vs] for n, vs in json.load(f).items()}
            except (OSError, ValueError) as e:
                print(f'[voz] não consegui ler {self.caminho} ({e}): começo sem conhecer ninguém')

    def _grava(self):
        import json
        os.makedirs(os.path.dirname(os.path.abspath(self.caminho)), exist_ok=True)
        tmp = self.caminho + '.novo'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({n: [[round(float(x), 5) for x in v] for v in vs] for n, vs in self.pessoas.items()}, f)
        os.replace(tmp, self.caminho)

    def assinatura(self, audio, taxa=TAXA_OUVIDO):
        """A assinatura (vetor de norma 1) de um trecho de fala, ou None se ele é curto demais."""
        a = reamostra(np.asarray(audio, np.float32), taxa, TAXA_OUVIDO)
        if len(a) < self.MIN_S * TAXA_OUVIDO:
            return None
        with self.torch.no_grad():
            e = self.modelo.encode_batch(self.torch.from_numpy(a).unsqueeze(0)).squeeze().cpu().numpy()
        return (e / (np.linalg.norm(e) + 1e-9)).astype(np.float32)

    def nomes(self):
        return list(self.pessoas)

    def _nome(self, nome):
        """O nome como está guardado (sem ligar para maiúsculas e acentos), ou None."""
        return next((n for n in self.pessoas if _sem_acento(n).strip() == _sem_acento(nome).strip()), None)

    def apresenta(self, nome, audio, taxa=TAXA_OUVIDO):
        """Guarda mais uma amostra da voz dessa pessoa. Devolve quantas amostras ela tem agora
        (0 = o trecho era curto demais e não foi guardado)."""
        e = self.assinatura(audio, taxa)
        nome = self._nome(nome) or ' '.join(str(nome).split())
        if e is None:
            return len(self.pessoas.get(nome, []))
        self.pessoas[nome] = (self.pessoas.get(nome, []) + [e])[-self.MAX_AMOSTRAS:]
        self._grava()
        return len(self.pessoas[nome])

    def esquece(self, nome):
        achado = self._nome(nome)
        if achado is None:
            raise ValueError(f'não conheço a voz de "{nome}". Conheço: {", ".join(self.pessoas) or "ninguém"}.')
        del self.pessoas[achado]
        self._grava()
        return achado

    def notas(self, audio, taxa=TAXA_OUVIDO):
        """[(semelhança, nome)] de cada pessoa conhecida, da mais parecida para a menos ([] = trecho curto)."""
        e = self.assinatura(audio, taxa)
        if e is None:
            return []
        res = []
        for nome, amostras in self.pessoas.items():
            centro = np.mean(amostras, axis=0)
            res.append((float(e @ (centro / (np.linalg.norm(centro) + 1e-9))), nome))
        return sorted(res, reverse=True)

    def quem(self, audio, taxa=TAXA_OUVIDO):
        """(nome, semelhança) de quem falou, ou (None, semelhança da mais parecida) se não dá para dizer."""
        n = self.notas(audio, taxa)
        if not n:
            return None, 0.0
        melhor = n[0]
        segunda = n[1][0] if len(n) > 1 else -1.0
        if melhor[0] >= self.LIMITE and melhor[0] - segunda >= self.FOLGA:
            return melhor[1], melhor[0]
        return None, melhor[0]


class BocaKokoro:
    """Uma voz do Kokoro (pf_dora, pm_alex, pm_santa), com a mesma cara da Boca. Só para os testes: são
    'pessoas' diferentes falando com o robô."""

    _motor = None

    def __init__(self, voz='pf_dora'):
        from kokoro_onnx import Kokoro
        if BocaKokoro._motor is None:
            k = os.path.join(PASTA_VOZES, 'kokoro')
            BocaKokoro._motor = Kokoro(os.path.join(k, 'kokoro-v1.0.onnx'), os.path.join(k, 'voices-v1.0.bin'))
        self.nome, self.taxa, self.efeito = voz, 24000, 'nenhum'

    def audio(self, texto):
        a, self.taxa = BocaKokoro._motor.create(texto, voice=self.nome, speed=1.0, lang='pt-br')
        return np.asarray(a, np.float32)


def vozes_de_teste():
    """As 'pessoas' de mentira dos testes: nome -> objeto com .audio(texto) e .taxa. Duas vozes do Piper,
    uma terceira feita da faber com o tom mais grave ('grave', para servir de visita) e, se o Kokoro estiver
    instalado (pip install kokoro-onnx + vozes/kokoro/), mais três. Dentro do simulador o Kokoro não carrega
    (as travas vigiadas do fake_hw não têm o que ele procura): lá ficam só as três primeiras."""
    v = {}
    for nome in ('faber', 'cadu'):
        if os.path.exists(os.path.join(PASTA_VOZES, f'pt_BR-{nome}-medium.onnx')):
            v[nome] = Boca(f'pt_BR-{nome}-medium', efeito='nenhum')
    if 'faber' in v:
        v['grave'] = Boca('pt_BR-faber-medium', efeito='grave')
    if os.path.exists(os.path.join(PASTA_VOZES, 'kokoro', 'kokoro-v1.0.onnx')) and not os.environ.get('SIM_PORTA'):
        try:
            for nome in ('dora', 'alex', 'santa'):
                v[nome] = BocaKokoro(('pf_' if nome == 'dora' else 'pm_') + nome)
        except Exception as e:
            print(f'[voz] sem as vozes do Kokoro ({e})')
    return v
