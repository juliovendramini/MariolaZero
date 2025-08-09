# Botoes

A classe `Botoes` fornece uma interface para leitura de botões GPIO utilizando a biblioteca gpiod. Ideal para projetos embarcados que precisam monitorar botões físicos conectados aos pinos GPIO do sistema.

---

## Exemplo de uso

```python
from libs.botoes import Botoes

# Inicializa os botões
botoes = Botoes()

# Lê o estado do botão 1
estado = botoes.le_botao(botoes.P1)
print("Botão 1 está", "pressionado" if estado == botoes.APERTADO else "liberado")

# Verifica se o botão 2 está pressionado
if botoes.botao_pressionado(botoes.P2):
    print("Botão 2 pressionado!")

# Exemplo usando constantes
if botoes.botao_pressionado(botoes.P3):
    print("Botão 3 (ENTER) pressionado!")
```

---

## Métodos

### `__init__(self)`
Inicializa os 4 botões configurando os pinos GPIO como entrada.

### `le_botao(self, pin)`
Lê o estado de um botão específico.

- **pin**: número do pino GPIO (usar as constantes P1, P2, P3, P4)
- **Retorno**: `LIBERADO` (1) se não pressionado, `APERTADO` (0) se pressionado

### `botao_pressionado(self, pin)`
Verifica se um botão está pressionado.

- **pin**: número do pino GPIO (usar as constantes P1, P2, P3, P4)
- **Retorno**: `True` se pressionado, `False` caso contrário

---

## Constantes

- `P1`: 267 (GPIO do botão 1)
- `P2`: 266 (GPIO do botão 2)
- `P3`: 265 (GPIO do botão 3)
- `P4`: 234 (GPIO do botão 4)
- `LIBERADO`: Value.ACTIVE (botão não pressionado)
- `APERTADO`: Value.INACTIVE (botão pressionado)

---

## Detalhes

- Utiliza a biblioteca `gpiod` para acesso aos pinos GPIO.
- Configura automaticamente os pinos como entrada na inicialização.
- Cada botão possui seu próprio objeto de requisição GPIO para isolamento.
- Lança `ValueError` se um pino inválido for especificado.

---

## Requisitos

- [gpiod](https://pypi.org/project/libgpiod/)

---

## Licença

MIT License.
