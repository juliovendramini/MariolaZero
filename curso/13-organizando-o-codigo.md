# Módulo 13 — Organizando o código de um robô de competição

**Objetivo:** sair dos programas de teste e montar um projeto que cresce sem virar bagunça: uma
camada de hardware (`robo.py`), a estratégia separada, uma máquina de estados e ferramentas de
depuração.

Modelo: os programas de exemplo dos simuladores (`simuladorLine/exemplo_aluno/` e
`simuladorMaze/exemplo_aluno/`).

## 13.1 O problema

Nos tutoriais, cada programa cria os objetos, escreve um `anda()` e mistura sensores e decisões.
Num robô de competição isso dá errado rápido:

* a mesma conta (mm por contagem, sinal do giroscópio) aparece em cinco lugares, e uma delas fica
  errada;
* trocar um sensor de porta exige caçar o número pelo código;
* não dá para entender **por que** o robô fez algo.

## 13.2 Camadas

```
main.py          ← ESTRATÉGIA: o que fazer (seguir, desviar, resgatar). Não sabe de portas nem bytes.
resgate.py       ← estratégia de uma parte da prova
navegacao.py     ← lógica pura (mapa, rotas): sem hardware, dá para testar no PC
robo.py          ← HARDWARE: cria os objetos e oferece ações com nome de gente:
                    anda(ve, vd), gira(graus), anda_mm(mm), reflexao(), cores(), z(),
                    distancia('frente'), espera_botao(), garra.fecha() ...
libs (motores.py, ...)   ← as bibliotecas do Mariola
```

Regra: **só o `robo.py` importa as libs do Mariola.** O `main.py` só chama métodos do `Robo`.

Vantagens:
* trocou o motor de lado? Muda uma linha no `robo.py`;
* o robô de esteira e o 4x4 usam o mesmo `main.py` (o `robo.py` do exemplo descobre a tração);
* dá para ler o `main.py` como uma descrição da estratégia.

### Constantes no topo do `robo.py`
Tudo o que se **mede** ou se **ajusta** fica em constantes com nome e comentário de unidade:

```python
DIAMETRO_RODA = 70.0          # mm
CONTAGENS_POR_VOLTA = 17 * 34 * 2
GIRO_HORARIO_POSITIVO = True
BRACO_BAIXO, BRACO_ALTO = 820, 270            # potenciômetro do servo 70 (A CALIBRAR)
VL53_CANAIS = {'frente': Portas.I2C5, 'esquerda': Portas.I2C1, 'direita': Portas.I2C3}
```

E as de estratégia no topo do `main.py` (`VEL`, `KP`, `KD`, `PRETO`, `DIST_OBSTACULO`).

## 13.3 Máquina de estados

Um robô de competição está sempre "fazendo alguma coisa": seguindo linha, conferindo um verde,
atravessando um gap, desviando, na área de resgate. Escreva isso **explicitamente**:

```python
estado = 'SEGUINDO'
while True:
    if estado == 'SEGUINDO':
        if viu_verde():
            estado = 'VERDE'
        elif sem_linha():
            estado = 'GAP'
        elif obstaculo_na_frente():
            estado = 'OBSTACULO'
        else:
            segue_linha()
    elif estado == 'VERDE':
        trata_intersecao()
        estado = 'SEGUINDO'
    elif estado == 'GAP':
        estado = 'SEGUINDO' if atravessa_gap() else 'PROCURANDO'
    ...
    mostra(estado)                  # LEDs / simdebug.texto
    time.sleep(0.01)
```

* Cada estado tem **uma** responsabilidade e uma condição de saída clara.
* Mostre o estado (LED de uma cor por estado no robô; `simdebug.texto` no simulador). Quando o robô
  fizer besteira, você vai saber **em que estado** estava.
* Toda manobra tem **tempo máximo**. Nenhum estado pode prender o robô para sempre.

O `main.py` do exemplo da Line faz algo parecido, com um método por situação (`intersecao`, `gap`,
`obstaculo`) chamados pelo `passo()`.

## 13.4 Percepção x decisão x ação

Ao depurar, separe as três perguntas:

1. **Percepção:** o robô **viu** certo? (o sensor disse verde quando era verde?)
2. **Decisão:** com o que viu, ele **decidiu** certo?
3. **Ação:** a manobra **executou** o que foi decidido?

`print` do que foi visto e decidido (com o tempo), `simdebug.pose()` do que ele acha e o painel do
simulador com o que realmente é: na maioria das vezes o erro aparece na hora.

```python
def log(*a):
    print(f'{time.time() - T0:7.2f}', *a, flush=True)
```

## 13.5 Arquivos que o robô grava

Checkpoint (Maze), cores calibradas, relógio da rodada:

* caminho **absoluto a partir da pasta do programa** (o menu roda com a pasta atual em
  `/home/banana`):
  ```python
  PASTA = os.path.dirname(os.path.abspath(__file__))
  ARQUIVO = os.path.join(PASTA, 'checkpoint.json')
  ```
* **escrita atômica** (o robô pode ser desligado no meio): grave num `.tmp` e troque com
  `os.replace` (o `navegacao.py` da Maze faz assim);
* no simulador, liste esses arquivos em `arquivos_rodada` do `robo.json`, para o **Nova rodada**
  apagá-los.

## 13.6 Teste por partes

* Cada capacidade nova nasce num **programa de teste pequeno** (como os de `codigos/`) e num **mapa
  pequeno** com só aquele desafio.
* A lógica sem hardware (mapa, BFS, classificação) se testa no PC com `python` puro.
* Antes de cada mudança grande, rode as sementes de referência no simulador (módulo 11) e compare
  os totais.

## 13.7 Controle de versão

Use **git** (ou, no mínimo, uma cópia datada da pasta) a cada versão que funcionou. Na competição,
"a versão de ontem que funcionava" vale ouro. Anote no commit o que mudou e o resultado no
simulador.

## Exercícios

1. Pegue o seu seguidor do módulo 6 e separe em `robo.py` (hardware) e `main.py` (estratégia).
2. Transforme o laço principal numa máquina de estados com pelo menos `SEGUINDO`, `PERDEU_LINHA` e
   `CHEGADA`. Acenda uma cor de LED diferente em cada estado.
3. Faça o `log()` com tempo e grave também num arquivo na pasta do programa.
