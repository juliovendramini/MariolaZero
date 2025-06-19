# Tela

A classe `Tela` fornece uma interface simples para exibir textos em um display OLED SSD1306 via I2C, utilizando a biblioteca [luma.oled](https://luma-oled.readthedocs.io/). Ela permite escrever, limpar e apagar linhas de texto na tela.

---

## Exemplo de uso

```python
from tela import Tela

# Inicializa a tela no barramento I2C padrão (0) e endereço 0x3C
tela = Tela()

# Escreve texto na primeira linha
tela.escreve("Olá, mundo!", linha=0)

# Escreve em outras linhas
tela.escreve("Linha 2", linha=1)
tela.escreve("Linha 3", linha=2)

# Limpa uma linha específica
tela.limpa(linha=1)

# Limpa toda a tela
tela.limpa()

# Apaga uma linha (equivalente a limpa(linha))
tela.apaga(2)
```

---

## Métodos

### `__init__(self, i2c_bus=0, i2c_address=0x3C)`
Inicializa o display OLED SSD1306 no barramento e endereço I2C especificados.

- **i2c_bus**: número do barramento I2C (padrão: 0)
- **i2c_address**: endereço do display (padrão: 0x3C)

### `escreve(self, texto, linha=0)`
Escreve o texto na linha especificada do display.

- **texto**: string a ser exibida
- **linha**: índice da linha (0 a 3)

### `limpa(self, linha=-1)`
Limpa uma linha específica ou toda a tela.

- **linha**: índice da linha a limpar (0 a 3). Se -1 (padrão), limpa todas as linhas.

### `apaga(self, linha)`
Apaga o conteúdo de uma linha específica.

- **linha**: índice da linha (0 a 3). Lança `ValueError` se o índice for inválido.

---

## Detalhes

- Usa fonte TrueType (`DejaVuSans.ttf`) para melhor legibilidade.
- O display é automaticamente limpo na inicialização.
- O método privado `_desenha` é responsável por atualizar o conteúdo do display.

---

## Requisitos

- [luma.oled](https://luma-oled.readthedocs.io/)
- [Pillow](https://python-pillow.org/)
- Fonte TrueType instalada em `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`

---