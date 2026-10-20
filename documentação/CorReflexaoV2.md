# CorReflexao (sensor Pro1616, V2)

Lib `exemplos/11-sensorCorReflexaoV2/sensorCorReflexao.py` para o sensor de linha/cor Pro1616
(ATtiny1616, firmware `sensorLinhaPro1616.ino`), ligado numa porta serial do Mariola a 115200 bps.

## Valores (escala do firmware)

| Índices | Conteúdo | Escala |
|---|---|---|
| 0–3 | reflexão IR dos 4 sensores | 0 = preto, ~100 = branco calibrado; a fita prata lê **menos** que o branco (~80) |
| 4–7 | TCS1 (R, G, B, C) | calibrado no branco e enviado pela **metade**: branco ~127, prata passa de 127 (~200) |
| 8–11 | TCS do meio (R, G, B, C) | idem |
| 12–15 | TCS2 (R, G, B, C) | idem |

## Detecção de cor

Cada cor é uma **referência** (média e desvio) de até cinco características:

* cromaticidade `r/(r+g+b)`, `g/(r+g+b)`, `b/(r+g+b)`: a cor em si, independe do brilho;
* brilho `C/127`: branco = 1, prata > 1, preto ~ 0;
* IR `/100`, do IR que fica ao lado daquele TCS (só com `usar_ir=True`): branco = 1, prata ~0,8, preto ~ 0.

O IR vem **desligado** por padrão (`usar_ir=False`): a fileira de IR fica 9 mm à frente dos TCS e, na borda
da linha, o IR já está no branco enquanto o TCS ainda está no preto (dava falso vermelho/verde). Quem vê
o prata é o TCS.

A leitura vai para a referência mais próxima (distância em desvios). Se nenhuma está a menos de
`limiar` (padrão 6), o resultado é `'desconhecida'`. No preto a cromaticidade não pesa (é ruído).

As referências padrão são estimativas. **Aprenda as cores no campo**, no tempo de calibração:

```python
from sensorCorReflexao import CorReflexao
from portas import Portas

sensor = CorReflexao(Portas.SERIAL6, arquivo_cores='cores.json')   # carrega se existir
sensor.usa_cores(['branco', 'preto', 'prata', 'azul', 'vermelho'])  # Maze (Line: ponha 'verde')

sensor.aprende_cor('azul')       # robô parado com os 3 TCS sobre o azul (~1 s)
sensor.salva_cores('cores.json')

sensor.cor(2)          # 'azul'  -> TCS do meio (1 = TCS1, 3 = TCS2)
sensor.cores()         # ['branco', 'azul', 'azul']
sensor.cor_piso()      # votação dos três; sem maioria vale o do meio
sensor.detecta_cor(2)  # o mesmo como constante: CorReflexao.COR_AZUL
sensor.distancias(2)   # [(0.8, 'azul'), (9.3, 'branco'), ...] para depurar
```

Constantes: `COR_PRETO`, `COR_BRANCO`, `COR_VERMELHO`, `COR_VERDE`, `COR_AZUL`, `COR_AMARELO`,
`COR_DESCONHECIDA`, `COR_PRATA` (nova), `COR_NADA`.

Mudança de interface: `detectar_cor(r, g, b, c, ir=None)` agora é método da instância (usa as
referências do sensor) e espera valores na escala do firmware (branco ~127).

## Calibração do firmware

* `calibra_branco()`: com o sensor no branco (o firmware leva ~7 s e ajusta o tempo dos LEDs IR e o branco do TCS).
* `calibra_preto()`: com o sensor no preto (~2 s).

Depois de calibrar o firmware, refaça `aprende_cor()` das cores.
