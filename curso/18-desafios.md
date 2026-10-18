# Módulo 18 — Desafios e projetos

**Objetivo:** praticar com metas claras e conferidas pelo computador, do seguidor de linha à
pista surpresa, e saber quando o programa está pronto de verdade.

Cada módulo tem exercícios curtos. Aqui estão os **desafios**, em ordem de dificuldade. A maioria
é conferida pelo `avalia.py`, que roda o seu programa em várias rodadas e diz se a meta foi
cumprida. Os outros, no fim da página, são conferidos por você ou pelo professor.

## 18.1 Por que várias rodadas

Uma rodada só engana. O ruído dos sensores muda a cada **semente**: com uma semente o robô passa
raspando na curva, com outra ele sai da linha. Um programa bom funciona em **todas**. Por isso as
metas falam em "6 de 6 rodadas" ou "média de 250 pontos", nunca em "uma rodada de 295".

O `avalia.py` faz isso por você. Ele fica na pasta de cada simulador:

```bash
cd simuladorLine
python avalia.py --lista                                      # os desafios da Line
python avalia.py --desafio L01 --programa ../meuRobo/main.py  # roda o L01 e confere a meta
```

```
=== L01: Primeira volta ===
Pista só com retas e curvas de 90°. Robô de esteira, como no módulo 6.
programa: /home/aluno/meuRobo/main.py
robô: robo_esteira.json   rodadas: 6   tempo máx.: 240 s   em paralelo: 2

  sem.  total  LoP  passo   chegou  vítim.   tempo  mapa                      fim
     2    130    0   14/14     sim     -      40.0  L01_pista.json            robô parou na chegada
     1    130    0   14/14     sim     -      39.9  L01_pista.json            robô parou na chegada
   ...
  média 130.0   pior 130   melhor 130   desvio 0.0   LoPs 0   (49 s)

  meta: 6 de 6 rodadas sem LoP e parando na chegada
    - 6 de 6 rodadas cumpriram "chegou and lop == 0" (precisa 6)

  >>> DESAFIO CUMPRIDO <<<
```

Como ler a tabela:

| Coluna | O que é |
|---|---|
| `sem.` | a semente do ruído daquela rodada |
| `total` | a pontuação do juiz |
| `LoP` | quantas faltas de progresso |
| `passo` | até que ladrilho do caminho o robô chegou (`14/14` = até a chegada) |
| `chegou` | parou mais de 5 s na chegada (bônus de saída) |
| `vítim.` | (com área de resgate) vítimas vivas e mortas que valeram |
| `fim` | por que a rodada acabou: parou na chegada, o programa terminou, acabou o tempo... |

* Se o seu programa dá erro, a linha avisa `<< erro no programa (veja o log)`. O log de cada
  rodada fica em `resultados/logs/` (é a mesma saída que aparece no terminal com a janela).
* Para ver uma rodada ruim acontecendo, abra o simulador com janela no **mesmo mapa e com a
  mesma semente**: `python simulador.py --mapa ... --semente 4 --programa ...`. A rodada sai igual.
* Sem `--desafio`, o `avalia.py` só roda e resume, com o mapa que você escolher:
  `python avalia.py --programa ../meuRobo/main.py --mapa mapas/completo.json --sementes 1-6`.

## 18.2 A trilha da Rescue Line (`simuladorLine`)

| ID | Desafio | Robô | Meta | Módulos |
|---|---|---|---|---|
| **Nível 1** | **seguir a linha** | | | |
| L01 | Primeira volta: retas e curvas de 90° | esteira | 6 de 6 sem LoP, parando na chegada | 6 |
| L02 | Curvas desenhadas: ondas, arcos, cobrinha | esteira | 6 de 6 chegando, no máximo 1 LoP | 6 |
| L03 | Contra o relógio: o L01 em até 30 s | esteira | 6 de 6 sem LoP, em até 30 s | 6 |
| **Nível 2** | **a prova da linha** | | | |
| L04 | Marcadores verdes (esquerda, direita, verde que não vale, cruzamentos) | 4x4 | 6 de 6 sem LoP, parando na chegada | 6, 14 |
| L05 | Gaps e obstáculo | 4x4 | 6 de 6 sem LoP, parando na chegada | 7, 14 |
| L06 | Terreno: lombadas, detritos, rampas, gangorra | 4x4 | 6 de 6 sem LoP, parando na chegada | 5, 14 |
| L07 | Prova completa (`completo.json`) | 4x4 | média ≥ 250, chegando em todas | 14 |
| **Nível 3** | **área de resgate** | | | |
| L08 | Só sair: entrar na área, achar a saída e terminar | esteira | 6 de 6 parando na chegada | 7, 15 |
| L09 | Uma vítima viva no triângulo verde | 4x4 | 5 de 6 com pelo menos 1 viva | 9, 10, 15 |
| L10 | As três vítimas, na ordem certa, e sair | 4x4 | 5 de 6 com 2 vivas + 1 morta, parando na chegada | 15 |
| **Nível 4** | **pista surpresa** | | | |
| L11 | Pista surpresa fácil (6 pistas sorteadas) | 4x4 | 6 de 6 sem LoP, parando na chegada | 14 |
| L12 | Pista surpresa média | 4x4 | 4 de 6 chegando, no máximo 1 LoP | 14 |
| L13 | Pista surpresa difícil | 4x4 | 5 de 6 chegando, no máximo 2 LoP | 14 |

Os mapas estão em `simuladorLine/desafios/mapas/`. Abra cada um no simulador com janela antes de
começar, para ver o que ele tem.

## 18.3 A trilha da Rescue Maze (`simuladorMaze`)

| ID | Desafio | Meta | Módulos |
|---|---|---|---|
| **Nível 1** | **andar no labirinto** | | |
| M01 | Explorar sem cair no preto, passando pelo azul | 3 de 3 sem LoP, com a parada no azul | 12, 16 |
| M02 | Vítimas e kits | 3 de 3 com pelo menos 5 vítimas e nenhuma identificação errada | 10, 16 |
| M03 | Voltar para casa | 3 de 3 voltando ao início | 16 |
| **Nível 2** | **labirinto surpresa** | | |
| M04 | Labirinto surpresa fácil (4x5, só corredores) | 3 de 3 com ≥ 3 vítimas, sem LoP, voltando ao início | 16 |
| M05 | Labirinto surpresa médio (5x7, ciclos, vítima falsa) | 3 de 3 com ≥ 4 vítimas, sem erro, voltando ao início | 16 |
| M06 | Labirinto surpresa difícil (6x8, ilhas e salas) | 3 de 3 com ≥ 6 das 7 vítimas verdadeiras, sem erro | 16 |

Os dois simuladores usam o **relógio sincronizado** (módulo 11.6): a mesma semente repete a
rodada igual, e o `avalia.py` roda várias rodadas ao mesmo tempo. Cada rodada da Maze leva de 1 a
2 minutos de PC; por isso as metas usam 3 rodadas.

## 18.4 Pista e labirinto surpresa

Na competição a pista só é conhecida no dia. Quem treina sempre no mesmo mapa acaba ajustando o
programa para **aquele** mapa: a constante que faz aquela curva, o tempo que acerta aquele gap. Os
geradores sorteiam pistas e labirintos novos, sempre dentro da regra:

```bash
# Line: caminho, ladrilhos, interseções com verde, gaps, obstáculo, lombada, detritos
python ferramentas/pista_surpresa.py --nivel medio --semente 7      # grava mapas/surpresa_medio_7.json

# Maze: paredes, buracos pretos, pratas, azuis, lombadas, detritos e vítimas
python ferramentas/labirinto_surpresa.py --nivel dificil --semente 3
```

| Nível | Line | Maze |
|---|---|---|
| fácil | retas e curvas simples, 1 interseção | 4x5, só corredores (seguir a parede visita tudo), 1 preto, 4 vítimas |
| médio | + ladrilhos desenhados, gap, lombada, 2–3 interseções | 5x7, alguns ciclos, 2 pretos, azul, lombada, 6 vítimas (1 falsa) |
| difícil | + ziguezague, cruzamentos, 2 gaps, obstáculo, detritos, 3–4 interseções | 6x8, ilhas e salas abertas, 3 pretos, 8 vítimas |

A mesma semente gera sempre o mesmo mapa. No `avalia.py`, `--surpresa medio --mapas 6` usa uma
pista diferente em cada rodada; as pistas ficam em `resultados/mapas/`, e o `avalia.py` mostra o
comando para abrir a pior rodada com janela.

**Treino recomendado:** quando o programa passar num desafio de mapa fixo, rode-o na pista
surpresa do mesmo nível. Se cair muito, ele estava "decorando" o mapa.

## 18.5 Desafios sem correção automática

| # | Desafio | Módulos | Pronto quando |
|---|---|---|---|
| A1 | **Quadrado perfeito:** andar um quadrado de 50 cm e voltar ao ponto de partida | 4, 5 | erro final < 3 cm e < 3° |
| A2 | **Estacionar:** parar a 10 cm da parede, girar 180°, voltar e parar a 10 cm da parede oposta | 4, 5, 7 | ±1 cm |
| A3 | **Painel de sensores:** um programa que mostra na tela todos os sensores e muda de página com o teclado | 6, 7, 8 | usado de verdade para conferir o robô no campo |
| A4 | **Garra de teste:** pegar uma bolinha parada à frente e jogar no lado certo da caçamba | 9 | 5 de 5 tentativas |
| A5 | **Obstáculo seguindo a parede:** contornar com o VL53 lateral em vez de "às cegas" (passe no L05 assim) | 7, 14 | L05 cumprido com o contorno novo |
| A6 | **Vítimas difíceis:** vítimas encostadas nas paredes e perto dos triângulos (edite o mapa) | 15 | 2 de 3 resgatadas |
| A7 | **Mapa interno (Maze):** desenhar com `simdebug.marca` cada parede detectada | 16 | o desenho bate com o labirinto |
| A8 | **Checkpoint (Maze):** com LoP "reinicia prog.", retomar do último prata | 16 | retoma certo em 3 LoPs |

## 18.6 Para o professor

**Avaliar a turma.** Cada `avalia.py` grava um relatório em `resultados/` com o desafio, a meta,
se foi cumprida, o placar de cada rodada, a data e uma **impressão digital** dos arquivos `.py` da
pasta do programa (muda se qualquer arquivo mudar). Peça o relatório junto com o código: rodando o
mesmo código, a impressão digital e o resultado se repetem.

```bash
python avalia.py --desafio L07 --programa ../equipe3/main.py --aluno "Equipe 3"
```

**Pista surpresa no dia da avaliação.** Os desafios de pista surpresa usam, por padrão, as
sementes de mapa 1 a 6, que os alunos conhecem e podem treinar. No dia, use outra:

```bash
python avalia.py --desafio L12 --programa ../equipe3/main.py --semente-mapas 4721
```

Um programa que só funcionava nas pistas de treino aparece aqui.

**Criar um desafio.** Os desafios ficam em `desafios/desafios.json`, um por chave:

```json
"L20": {
  "nivel": "Desafios da turma",
  "titulo": "Minha pista",
  "descricao": "O que tem na pista.",
  "robo": "robo_4x4.json",
  "mapa": "desafios/mapas/minha_pista.json",
  "sementes": "1-6",
  "tempo": 300,
  "meta": {"rodada": "chegou and lop == 0", "minimo": 5},
  "meta_texto": "5 de 6 rodadas sem LoP e parando na chegada"
}
```

* Mapa fixo (`"mapa"`) ou sorteado (`"surpresa": "facil|medio|dificil"`, `"mapas": 6`,
  `"semente_mapas": 1`).
* `"meta"` aceita `"rodada"` (uma condição que cada rodada precisa cumprir) com `"minimo"` (quantas
  rodadas), e/ou `"media"` (uma condição sobre a média das rodadas). Pode ter as duas.
* Nomes que valem nas condições — **Line:** `total`, `lop`, `passo`, `passos`, `progresso` (0 a 1),
  `chegou`, `vivas`, `mortas`, `vitimas`, `tempo`, `linha` (pontos da linha, sem o multiplicador).
  **Maze:** `total`, `lop`, `svi` (vítimas identificadas), `srd` (kits certos), `sbv` (azuis),
  `ssn` (escadas), `vitimas`, `saida`, `erros`, `tempo`. Nas duas: `erro_programa`.
* Na média, `chegou` e `saida` viram a fração das rodadas (`chegou >= 0.99` = todas).
* Faça o mapa no editor do simulador e salve em `desafios/mapas/`.

**Os programas de exemplo** (`exemplo_aluno/` de cada simulador e o `seguidor_p.py` do módulo 6)
mostram que as metas são possíveis. Onde o exemplo **não** cumpre, o desafio está em aberto: o
aluno precisa fazer melhor que o exemplo. As metas valem para o programa **do aluno** (rodar o
exemplo não vale).

| Desafio | Programa de referência | Resultado (sementes padrão) |
|---|---|---|
| L01 | `seguidor_p.py` | cumpre: 6 de 6 sem LoP, 40 s |
| L02 | `seguidor_p.py` | cumpre: 6 de 6 sem LoP (o `exemplo_aluno` no robô de esteira: 4 de 6, não cumpre) |
| L03 | `seguidor_p.py` com velocidade e ganhos maiores | cumpre: 29 s (o original leva 40 s) |
| L04 | `exemplo_aluno` | cumpre: 6 de 6 sem LoP |
| L05, L06 | `exemplo_aluno` | cumpre: 6 de 6 sem LoP |
| L07 | `exemplo_aluno` | cumpre: média 286,5 |
| L08 | `exemplo_aluno` (esteira) | cumpre: 6 de 6 |
| L09 | `exemplo_aluno` | cumpre: 6 de 6 com pelo menos 1 viva |
| L10 | `exemplo_aluno` | cumpre no limite: 5 de 6 (na semente 4 só resgata 1 viva) |
| L11 | `exemplo_aluno` | cumpre: 6 de 6 sem LoP |
| L12 | `exemplo_aluno` | cumpre no limite: 4 de 6 |
| L13 | `exemplo_aluno` | **não cumpre**: 3 de 6 (duas pistas sem terminar: o exemplo se perde nas curvas fechadas desenhadas) |
| M01 | `exemplo_aluno` (Maze) | cumpre: 3 de 3 (6 vítimas; o tempo de 300 s acaba antes de ele voltar) |
| M02, M03 | `exemplo_aluno` (Maze) | cumpre: 3 de 3 (415 pontos, 6 vítimas, volta ao início) |
| M04 | `exemplo_aluno` (Maze) | cumpre: 3 de 3 (4 vítimas) |
| M05 | `exemplo_aluno` (Maze) | cumpre: 3 de 3 (5 vítimas) |
| M06 | `exemplo_aluno` (Maze) | cumpre: 3 de 3 (média 6,3 vítimas) |

## Projeto final

Escolham **Line** ou **Maze** e, em equipe:

1. Montem o robô e meçam tudo (módulo 17); ajustem o `robo*.json`.
2. Organizem o código em camadas com máquina de estados (módulo 13).
3. Passem pela trilha de desafios do simulador escolhido, guardando os relatórios do `avalia.py`.
4. Mantenham um **diário**: versão, o que mudou, resultado do `avalia.py` nas sementes de referência.
5. Façam uma rodada oficial no robô real (cronometrada e pontuada como na competição).

### Sugestão de avaliação (professor)

| Critério | Peso |
|---|---|
| Trilha de desafios no simulador (relatórios do `avalia.py`), com uma pista surpresa nova no dia | 25% |
| Resultado no robô real (rodada oficial) | 25% |
| Organização do código (camadas, constantes, estados, nomes) | 20% |
| Diário de testes (o que tentaram, o que mediram, o que aprenderam) | 20% |
| Apresentação: explicar uma decisão de projeto e um erro que corrigiram | 10% |

## Sugestão de cronograma

| Semana | Conteúdo |
|---|---|
| 1 | Módulos 1–3: brick, ambiente, primeiro programa |
| 2 | Módulo 4: motores e encoders |
| 3 | Módulo 5: giroscópio; desafio A1 |
| 4–5 | Módulo 6: sensor de linha, PD; desafios L01–L03 |
| 6 | Módulos 7–8: distância, botões, tempo; desafios A2–A3 |
| 7 | Módulos 11–13: simulador a fundo, organização do código, `avalia.py` |
| 8–9 | Módulo 14: seguidor completo; desafios L04–L07 |
| 10 | Módulos 9–10: servos e câmera; desafio A4 |
| 11–12 | Módulo 15: área de resgate; desafios L08–L10 |
| 13 | Pista surpresa: L11–L13 |
| (paralelo) | Módulos 12 e 16 para a equipe da Maze; desafios M01–M06 |
| 14+ | Módulo 17 e projeto final |
