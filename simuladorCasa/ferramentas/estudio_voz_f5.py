"""A voz do Julio (F5-TTS ajustado no projeto D:\\voz_claude) para o estúdio de voz.

Roda com o Python do projeto da voz (D:\\voz_claude\\.venv\\Scripts\\python.exe), chamado pelo
estudio_voz.py, e fica carregado: lê um pedido JSON por linha na entrada e responde uma linha JSON.
    {"texto": ..., "ref": "robo_curta", "nfe": 16, "speed": 1.0, "semente": 2026, "saida": "x.wav"}
    -> {"ok": true, "taxa": 24000, "s": 0.6}   ou   {"ok": false, "erro": "..."}
Primeira linha: {"pronto": true, "refs": [...]} quando o modelo carregou (de ~10 s a ~3 min: o mais demorado
são os imports da .venv no HD).

O modelo e as gravações ficam só no PC (biometria do Julio): nada disso vai para o git.
Modelo: robo_ema_fp16.safetensors (só os pesos EMA em fp16, 674 MB, feito em 16/11/2026 a partir do
model_last.pt da fase 2); sem ele, o model_last.pt."""
import json
import os
import re
import sys

PASTA = os.environ.get('VOZ_JULIO_PASTA', r'D:\voz_claude')
sys.path.insert(0, os.path.join(PASTA, 'scripts'))

RESPOSTA = sys.stdout
sys.stdout = sys.stderr           # o que as bibliotecas imprimem não pode misturar com as respostas


def responde(d):
    RESPOSTA.write(json.dumps(d, ensure_ascii=False) + '\n')
    RESPOSTA.flush()


def main():
    import importlib
    import numpy as np
    import soundfile as sf
    from comum import F5_DATA, REF_TTS, normalizar_texto
    falar = importlib.import_module('07_falar')
    from f5_tts.api import F5TTS
    from f5_tts.infer.utils_infer import preprocess_ref_audio_text

    ck = falar.ckpt_padrao()
    enxuto = ck.parent / 'robo_ema_fp16.safetensors'
    tts = F5TTS(model='F5TTS_Base', ckpt_file=str(enxuto if enxuto.exists() else ck),
                vocab_file=str(F5_DATA / 'vocab.txt'), use_ema=True)
    regras = falar.carregar_pronuncia()
    refs = sorted(p.stem for p in REF_TTS.glob('*.wav') if p.with_suffix('.txt').exists())
    preparadas = {}

    def ref(nome):
        if nome not in preparadas:
            r = REF_TTS / f'{nome}.wav'
            rt = normalizar_texto(r.with_suffix('.txt').read_text(encoding='utf-8'))
            rp, rtp = preprocess_ref_audio_text(str(r), rt, show_info=lambda *x: None)
            seg = sf.info(rp).duration
            preparadas[nome] = (str(r), rt, seg, seg / max(len(rtp.encode('utf-8')), 1))
        return preparadas[nome]

    def gera(frase, nome_ref, nfe, speed, semente):
        r, rt, seg, spb = ref(nome_ref)
        gen = falar.aplicar_pronuncia(normalizar_texto(frase), regras)
        w, sr, _ = tts.infer(ref_file=r, ref_text=rt, gen_text=gen, nfe_step=int(nfe), cfg_strength=2.0,
                             speed=float(speed), seed=int(semente),
                             fix_duration=seg + len(gen.encode('utf-8')) * spb / float(speed) + 0.3,
                             show_info=lambda *x: None, progress=None)
        return np.asarray(w, np.float32), sr

    gera('Aquecendo a placa.', refs[0] if 'robo_curta' not in refs else 'robo_curta', 8, 1.0, 1)
    responde({'pronto': True, 'refs': refs})

    import time
    for linha in sys.stdin:
        if not linha.strip():
            continue
        try:
            p = json.loads(linha)
            t = time.perf_counter()
            frases = [f.strip() for f in re.split(r'(?<=[.!?])\s+', p['texto'].strip()) if f.strip()]
            partes, sr = [], 24000
            for i, f in enumerate(frases):
                w, sr = gera(f, p.get('ref', 'robo_curta'), p.get('nfe', 16), p.get('speed', 1.0),
                             p.get('semente', 2026) + i)
                partes += [w, np.zeros(int(sr * 0.2), np.float32)]
            a = np.concatenate(partes) if partes else np.zeros(1, np.float32)
            sf.write(p['saida'], a, sr)
            responde({'ok': True, 'taxa': sr, 's': round(time.perf_counter() - t, 2)})
        except Exception as e:
            responde({'ok': False, 'erro': f'{type(e).__name__}: {e}'})


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        responde({'pronto': False, 'erro': f'{type(e).__name__}: {e}'})
