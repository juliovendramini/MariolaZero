"""Gráfico de antes e depois (firmware antigo x novo) com quatro cenários do emulador."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import testa_brick as tb
import testa_placa as tp
from emu import *
from placa import ATUALIZA_P, SET_FREIO

CORES = {'antigo': '#c0392b', 'novo': '#1e8449'}
NOMES = {'antigo': 'firmware antigo', 'novo': 'firmware novo'}
fig, eixos = plt.subplots(2, 2, figsize=(13, 8.5))

# 1) brick: programa novo com HOLD depois de reposicionar o robô
ax = eixos[0][0]
for q in ('antigo', 'novo'):
    e = tb.brick(q)
    e.anda(0.3, 0, 0, freio=HOLD)
    e.anda(0.8, 40, 40, freio=HOLD)
    e.anda(0.5, 0, 0, freio=HOLD)
    e.roda(6.0)
    e.mao(0, 578)
    e.roda(0.5)
    e.mao(0, None)
    e.roda(1.0)
    t0 = e.t
    e.anda(1.0, 0, 0, freio=HOLD)
    tr = e.traco()
    tr = tr[tr[:, 0] > t0 - 2.0]
    ax.plot(tr[:, 0] - t0, (tr[:, 5] - tr[-1, 5] if q == 'antigo' else tr[:, 5] - tr[0, 5] - 289) * tb.GRAUS + (0 if q == 'antigo' else 90),
            color=CORES[q], label=NOMES[q], lw=2)
ax.axvline(0, color='gray', ls='--', lw=1)
ax.text(0.02, 45, 'programa novo começa\n(parar, freio HOLD)', fontsize=9, color='gray')
ax.text(-1.95, 60, 'aluno gira\na roda 90°', fontsize=9, color='gray')
ax.set_title('Brick: programa novo em HOLD, robô reposicionado antes', fontsize=11)
ax.set_xlabel('tempo (s)')
ax.set_ylabel('posição da roda (graus)')
ax.legend(loc='lower left')
ax.grid(alpha=0.3)

# 2) brick: parar em BREAK (tensão na ponte H)
ax = eixos[0][1]
for q in ('antigo', 'novo'):
    pior = None
    for i in range(10):
        e = tb.brick(q)
        e.anda(0.3, 0, 0)
        e.anda(0.8 + i * 0.00041, 50, 50, periodo=0.02 + i * 0.00041)
        e.passos_traco(1)
        e.roda(0.006)
        t0 = e.t
        e.envia(msg_motores(0, 0))
        e.roda(0.010)
        e.passos_traco(16)
        tr = e.traco()
        tr = tr[tr[:, 0] > t0 - 0.006]
        p = tb.pulso(tr[tr[:, 0] > t0], 1, -1)
        if pior is None or p > pior[0]:
            pior = (p, (tr[:, 0] - t0) * 1000, tr[:, 1])
    desloca = 0 if q == 'antigo' else -2.6
    ax.step(pior[1], pior[2] + desloca, color=CORES[q], label=NOMES[q] + (' (pior de 10)' if q == 'antigo' else ''), lw=1.5, where='post')
    ax.axhline(desloca, color=CORES[q], lw=0.5, alpha=0.5)
ax.axvline(0, color='gray', ls='--', lw=1)
ax.text(0.1, 1.15, 'comando de parar', fontsize=9, color='gray')
ax.set_yticks([1, 0, -1, -1.6, -2.6, -3.6])
ax.set_yticklabels(['frente', 'freio', 'ré', 'frente', 'freio', 'ré'])
ax.set_ylim(-3.9, 1.5)
ax.set_title('Brick: parar em BREAK a 50 (ponte H do motor 1)', fontsize=11)
ax.set_xlabel('tempo (ms)')
ax.legend(loc='lower right', fontsize=9)
ax.grid(alpha=0.3)

# 3) brick: primeira partida (PID, velocidade 30)
ax = eixos[1][0]
for q in ('antigo', 'novo'):
    e = tb.brick(q)
    e.anda(0.3, 0, 0)
    e.passos_traco(1)
    t0 = e.t
    e.envia(msg_motores(30, 30))
    e.roda(0.045)
    e.passos_traco(16)
    tr = e.traco()
    tr = tr[tr[:, 0] > t0]
    liga = np.flatnonzero(tr[:, 1] > 0.5)
    t1 = tr[liga[0], 0]
    sel = (tr[:, 0] > t1 - 0.002) & (tr[:, 0] < t1 + 0.014)
    desloca = 0 if q == 'antigo' else -1.6
    ax.step((tr[sel, 0] - t1) * 1000, tr[sel, 1] + desloca, color=CORES[q], label=NOMES[q], lw=1.5, where='post')
ax.set_yticks([1, 0, -0.6, -1.6])
ax.set_yticklabels(['frente', 'freio', 'frente', 'freio'])
ax.set_ylim(-2.3, 1.3)
ax.set_title('Brick: primeira partida do programa (velocidade 30, PID)', fontsize=11)
ax.set_xlabel('tempo desde o primeiro pulso (ms)')
ax.legend(loc='lower right', fontsize=9)
ax.grid(alpha=0.3)

# 4) placa externa: reinícios pelo watchdog com a placa parada e depois de um programa
ax = eixos[1][1]
y = 0
rotulos = []
for nome, usa in (('sem programa', False), ('depois de um programa', True)):
    for q in ('antigo', 'novo'):
        e = tp.placa(q)
        if usa:
            e.anda(1.0, 40)
            e.anda(0.2, 0)
        t0 = e.t
        e.roda(60.0)
        r = [x - t0 for x in tp.instantes_reset(e)]
        ax.hlines(y, 0, 60, color=CORES[q], lw=1, alpha=0.4)
        ax.plot(r, [y] * len(r), 'v', color=CORES[q], ms=11)
        rotulos.append('%s\n%s' % (nome, NOMES[q]))
        y -= 1
ax.set_yticks(range(0, y, -1))
ax.set_yticklabels(rotulos, fontsize=9)
ax.set_ylim(y + 0.4, 0.6)
ax.set_title('Placa externa: reinícios pelo watchdog em 60 s (▼)', fontsize=11)
ax.set_xlabel('tempo (s)')
ax.grid(alpha=0.3, axis='x')

fig.suptitle('Firmwares dos motores no emulador (o .hex de cada placa rodando): antigo x novo', fontsize=13)
fig.tight_layout()
saida = os.path.join(BUILDS, 'motores_antes_depois.png')
fig.savefig(saida, dpi=110)
print(saida)
