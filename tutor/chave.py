"""A chave da API do tutor: CEREBRO_CHAVE_API (no PC do Julio) ou a chave_tutor.dll (no PC do aluno,
gerada pelo ferramentas/faz_chave.py).

A chave nunca vai para os.environ: o programa do aluno roda num processo filho (o simulador) e leria a
variável. Ela vai direto para o cliente do anthropic (cria_cliente)."""
import ctypes
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
DLL = os.path.join(AQUI, 'chave_tutor.dll')
VARIAVEIS = ('CEREBRO_CHAVE_API', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN')


def da_dll():
    if not os.path.exists(DLL):
        return None
    f = ctypes.CDLL(DLL).tutor_chave
    f.argtypes, f.restype = [ctypes.c_char_p, ctypes.c_int], ctypes.c_int
    buf = ctypes.create_string_buffer(512)
    n = f(buf, len(buf))
    return buf.value.decode('ascii') if n > 0 else None


def da_api():
    """A variável do PC (a mesma do robô de casa) e, sem ela, a DLL."""
    sys.path.append(os.path.join(os.path.dirname(AQUI), 'simuladorCasa', 'exemplo_casa'))
    import cerebro
    return cerebro.chave_da_api() or da_dll()


def ambiente_sem_chave(env=None):
    """Cópia do ambiente sem as variáveis de chave, para os processos que rodam o programa do aluno."""
    env = dict(os.environ if env is None else env)
    for v in VARIAVEIS:
        env.pop(v, None)
    return env
