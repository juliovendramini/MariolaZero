# Botoes (juntada ao PinosDigitais em 27/10/2026)

A classe `Botoes` (`libs/botoes.py`) **não existe mais**. Ela usava os mesmos 8 pinos da
[`PinosDigitais`](PinosDigitais.md) e as duas davam "Device or resource busy" quando estavam no
mesmo programa. Tudo o que ela fazia está na `PinosDigitais`, que começa com os 8 pinos como
entrada:

| antes (`Botoes`) | agora (`PinosDigitais`) |
|---|---|
| `from botoes import Botoes` | `from pinosDigitais import PinosDigitais` |
| `botoes = Botoes()` | `botoes = PinosDigitais()` (sempre o mesmo objeto no programa) |
| `Botoes.P1` … `Botoes.P8` | `PinosDigitais.P1` … `PinosDigitais.P8` |
| `Botoes.APERTADO`, `Botoes.LIBERADO` | `PinosDigitais.APERTADO`, `PinosDigitais.LIBERADO` |
| `botoes.le_botao(p)`, `botoes.botao_pressionado(p)` | iguais |

```python
from pinosDigitais import PinosDigitais

botoes = PinosDigitais()
if botoes.botao_pressionado(PinosDigitais.P3):
    print("Botão de início apertado!")
```

Os pinos têm pull-up: solto = nível alto (`LIBERADO`), ligado ao GND = nível baixo (`APERTADO`).
Detalhes (linhas GPIO, escolha do gpiochip, saídas): [`PinosDigitais.md`](PinosDigitais.md).
