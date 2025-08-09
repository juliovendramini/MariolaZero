# Cronometro

A classe `Cronometro` é uma ferramenta simples para medir o tempo em milissegundos. Ela pode ser usada para criar cronômetros temporários ou persistentes, com a opção de salvar e carregar o estado do cronômetro em arquivos.

---

## Funcionalidades

- Medir o tempo decorrido em milissegundos.
- Salvar o estado do cronômetro em um arquivo para persistência.
- Carregar o estado salvo de um cronômetro.
- Resetar ou apagar o cronômetro.

---

## Atributos da Classe

- **`nome_arquivo`**: Nome do arquivo onde o estado do cronômetro será salvo (opcional).
- **`tempo_inicial`**: Tempo inicial do cronômetro (em segundos desde a época Unix).

---

## Métodos da Classe

### `__init__(self, nome_arquivo=None)`
Construtor da classe. Inicializa o cronômetro.

- **Parâmetros**:
  - `nome_arquivo` (str, opcional): Nome do arquivo para salvar o estado do cronômetro. Se não for fornecido, o cronômetro será temporário e não salvará seu estado.

---

### `inicia(self)`
Inicia o cronômetro a partir do momento atual.

- **Comportamento**:
  - Se um `nome_arquivo` foi fornecido, o estado do cronômetro será salvo no arquivo.

---

### `apaga(self)`
Apaga o estado salvo do cronômetro.

- **Comportamento**:
  - Remove o arquivo especificado em `nome_arquivo`.
  - Reseta o atributo `tempo_inicial` para `None`.

---

### `reseta(self)`
Reseta o cronômetro para o momento atual.

- **Comportamento**:
  - Atualiza o tempo inicial para o momento atual.
  - Salva o estado no arquivo, se um `nome_arquivo` foi fornecido.

---

### `tempo(self)`
Retorna o tempo decorrido em milissegundos desde que o cronômetro foi iniciado.

- **Retorno**:
  - (int): Tempo decorrido em milissegundos.
  - `None` se o cronômetro não foi iniciado.

---

### `salva(self)`
Salva o estado atual do cronômetro no arquivo especificado em `nome_arquivo`.

- **Comportamento**:
  - Escreve o valor de `tempo_inicial` no arquivo.

---

### `carrega(self)`
Carrega o estado do cronômetro a partir do arquivo especificado em `nome_arquivo`.

- **Comportamento**:
  - Lê o valor de `tempo_inicial` do arquivo.
  - Se o arquivo não existir ou não puder ser lido, inicia o cronômetro a partir do momento atual e salva o estado.

---

## Exemplo de Uso

```python
from libs.cronometro import Cronometro

# Cronômetro temporário (não salva estado em arquivo)
cronometro_temp = Cronometro()
cronometro_temp.inicia()
print("Tempo decorrido:", cronometro_temp.tempo(), "ms")

# Cronômetro persistente (salva estado em arquivo)
cronometro_persistente = Cronometro("cronometro.txt")
cronometro_persistente.inicia()
print("Tempo decorrido:", cronometro_persistente.tempo(), "ms")

# Reseta o cronômetro
cronometro_persistente.reseta()
print("Tempo após reset:", cronometro_persistente.tempo(), "ms")

# Apaga o estado salvo
cronometro_persistente.apaga()