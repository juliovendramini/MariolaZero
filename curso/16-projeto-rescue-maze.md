# Módulo 16 — Projeto: Rescue Maze

**Objetivo:** fazer o robô andar ladrilho a ladrilho num labirinto, ver paredes, tratar os pisos
especiais, achar vítimas, e evoluir da "regra da mão direita" para um explorador com mapa,
rotas e checkpoint em arquivo.

Códigos: [`codigos/09_maze/mao_direita.py`](codigos/09_maze/mao_direita.py) e o exemplo completo
`simuladorMaze/exemplo_aluno/` (`robo.py`, `navegacao.py`, `main.py`, `calibra_cores.py`).

## 16.1 A Maze em resumo

* Labirinto de ladrilhos de 30 × 30 cm com paredes. O robô explora e volta ao início.
* **Pisos:** preto (proibido: entrar = LoP), azul (parar 5 s; 30 pontos), prata (checkpoint),
  vermelho (entrada da zona de perigo, opcional).
* **Terreno:** lombadas, escadas, detritos.
* **Vítimas** nas paredes: letras (H, S, U) e alvos cognitivos. Identificar = **piscar o LED 5 s
  parado**; depois **deixar kits** (2 ferida, 1 estável, 0 ilesa).
* **Saída:** voltar ao início e piscar 10 s (1 s / 1 s).

## 16.2 As ações básicas (tudo que você já sabe)

| Ação | Como | Módulo |
|---|---|---|
| andar 1 ladrilho reto | encoder + giroscópio, parando se a parede da frente chegar perto | 4, 5 |
| girar 90° | giroscópio com **alvo acumulado** | 5 |
| ver paredes | VL53: lado < 150 mm, frente < 200 mm | 7 |
| cor do piso | `cor_piso()` (3 TCS votando) | 6 |
| alinhar | para-choque (os dois apertados) ou dois VL53 do mesmo lado | 7, 8 |
| esperar sem soltar o motor | laço mandando `anda(0, 0)` | 3 |

## 16.3 Tutorial: regra da mão direita

```python
while time.time() - inicio < 120:
    d = distancias()
    if d['direita'] > PAREDE_LADO and not acabou_de_ver_preto:
        gira(-90)                         # direita livre: vira para a direita
    elif d['frente'] > PAREDE_FRENTE:
        pass                              # senão, frente livre: segue
    elif d['esquerda'] > PAREDE_LADO:
        gira(90)                          # senão, esquerda
    else:
        gira(180)                         # beco: meia-volta
    acabou_de_ver_preto = False
    if avanca() == 'preto':               # anda 1 ladrilho; se vir preto, volta
        gira(180)
        acabou_de_ver_preto = True
        continue
    piso = cor.cor_piso()
    if piso == 'azul':
        espera(5.5)                       # parado 5 s, mandando comando
```

```bash
python simulador.py --programa ../curso/codigos/09_maze/mao_direita.py --semente 1
```

**O bug que apareceu no desenvolvimento:** a primeira versão, depois de ver o preto, voltava e
virava à esquerda. Na volta seguinte, a direita estava "livre" de novo (o preto não é parede para o
VL53) e o robô entrava no preto para sempre. A solução foi **lembrar** que acabou de ver o preto e
não virar para a direita uma vez. Generalizando: **o robô precisa de memória** — é o próximo passo.

Limites da mão direita:
* não visita "ilhas" (paredes soltas no meio);
* não sabe onde está, então não sabe **voltar ao início**;
* revisita muita coisa.

## 16.4 O explorador do exemplo: mapa + busca

O `exemplo_aluno` da Maze guarda um **mapa interno** e decide para onde ir:

**Referencial:** o robô começa no ladrilho `(0, 0)` olhando para a direção 0. Direções: 0 =
frente, 1 = esquerda, 2 = trás, 3 = direita (girar à esquerda soma 1). Cada ladrilho visitado
registra suas paredes e o piso.

**`navegacao.py`** (sem hardware nenhum, dá para testar no PC):

| Função | Faz |
|---|---|
| `Mapa.set_parede(p, d, tem)` | grava a parede do ladrilho `p` na direção `d` (e a do vizinho) |
| `Mapa.bloqueado(p, d)` | parede, ou vizinho preto/vermelho |
| `Mapa.fronteira(p)` | direções abertas que levam a ladrilhos **não visitados** |
| `Mapa.caminho(origem, criterio)` | **busca em largura (BFS)**: menor rota até um ladrilho que satisfaz o critério |
| `salva_checkpoint(...)` / `carrega_checkpoint()` | mapa + posição em arquivo, com **escrita atômica** |

**A estratégia (`main.py`):**
1. Chegou num ladrilho: lê o piso, as paredes, centraliza, procura vítimas.
2. Tem vizinho não visitado aberto? Vai (preferindo frente, depois esquerda, direita).
3. Não tem? Usa a BFS para achar o ladrilho visitado mais perto que ainda tem fronteira, e vai até
   ele.
4. Mapa todo explorado, ou passou de 6,5 min? BFS até `(0, 0)` e pisca o sinal de saída.

Isso é uma **busca em profundidade** guiada por BFS: visita tudo e sempre sabe voltar.

## 16.5 Detalhes que fazem a diferença

* **Corrigir o giroscópio com as paredes:** a cada ladrilho com parede na frente, encosta no
  para-choque (os dois botões = reto contra a parede) e redefine a direção; com parede do lado,
  mede o ângulo com dois VL53 e corrige. Sem isso, a deriva acumula em 8 minutos.
* **A parede da frente é melhor que o encoder:** se há parede à frente ao alcance, o robô para a
  uma distância certa dela (o encoder patina).
* **Preto:** o sensor de cor está na frente; ao ver preto, volta a distância andada e marca o
  ladrilho como proibido.
* **Checkpoint (prata):** salva o mapa e a posição **no arquivo** assim que chega. No LoP o
  programa é reiniciado e recomeça daquele ponto com o mapa que já tinha.
* **Vítimas:** procura depois de cada giro e de cada chegada; marca `(ladrilho, parede)` para não
  sinalizar a mesma duas vezes; pisca os LEDs 8–9 por 5,6 s parado; deixa os kits.
* **Iluminação:** acende os LEDs das câmeras **depois** do botão de início (antes, o timeout de 5 s
  do Mariola apaga tudo).
* **Zona de perigo:** o exemplo **evita** (vermelho = volta). Entrar vale mais, mas arrisca.

## 16.6 Como evoluir

1. Rode com várias sementes e anote: ladrilhos visitados, vítimas, LoPs, se voltou ao início.
2. Use `simdebug.pose()` (o exemplo já usa): se o contorno roxo se afasta do robô real, o problema
   é de **posição** (giro, encoder), não de estratégia.
3. Otimize a ordem de exploração (ex.: preferir ladrilhos perto do início no fim da rodada).

## Exercícios

1. Na `mao_direita.py`, troque para "mão esquerda". O robô visita os mesmos ladrilhos?
2. Teste `navegacao.py` no PC: monte um mapa à mão com `set_parede` e peça `caminho()` até um
   ladrilho.
3. No exemplo, mude `TEMPO_VOLTAR` para 3 min e confira que o robô volta ao início a tempo.
4. Faça o exemplo entrar na zona de perigo e compare a pontuação em 6 sementes.
