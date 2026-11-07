---
name: mapa-da-foto-maze
description: Monta um mapa do simulador da Maze (simuladorMaze/mapas/*.json) a partir de foto(s) de um labirinto de verdade da RoboCupJunior Rescue Maze. Use quando o Julio mandar foto de labirinto/arena da Maze (competição, laboratório) pedindo mapa, json, "labirinto igual a esse", "monta no simulador", ou pedir para conferir/ajustar um mapa da Maze feito de foto. Para pista da Line, a skill é a mapa-da-foto.
---

# Mapa da Maze a partir de foto

O roteiro completo (fotos, coordenadas, os dois jeitos de calibrar, comandos, lições) está em
`simuladorMaze/ferramentas/MAPA_DA_FOTO.md`. **Leia antes de começar.** A ferramenta é
`simuladorMaze/ferramentas/foto_mapa.py` (rode da pasta `simuladorMaze`; `-h` lista os comandos).
Exemplos: `simuladorMaze/fotos_mapa/sintetico/` (foto sintética do `exemplo1`, resposta conhecida) e
`simuladorMaze/fotos_mapa/foto1/` (foto real de 06/11/2026, que não fechou: veja as lições).

## Como trabalhar

1. **Pasta de trabalho:** `foto_mapa.py novo <nome> <foto>`. A foto anexada no chat está no caminho
   que a mensagem de sistema informa (pasta `uploads`). Várias fotos: uma pasta por foto.
2. **Olhe** a `foto_regua.png` (Read): níveis, rampa/escada, pisos coloridos, vítimas, o que sai da
   foto. Diga ao Julio, em poucas linhas, o que viu e se a foto dá para o labirinto inteiro.
3. **Calibre** cada nível: por 4 pontos do chão (`calibra`) ou, se não souber onde fica nenhum canto,
   pelos pontos de fuga (`fugas` com bordas de pisos coloridos, depois `calibra --fugas`). Confira na
   vista de cima: pisos quadrados e a grade nas **paredes** (não nos pisos).
4. **Paredes** com `paredes` (foto com as paredes possíveis + vista na altura do alto delas), **pisos**
   com `pisos`, **vítimas** com `ponto --parede`. As listas automáticas são pistas: decida olhando.
5. **Descreva** na `descricao.json` (o `desenho` em texto é o jeito mais rápido), **monte** (`monta`) e
   **compare** (`compara`: a sobreposição das paredes do mapa na foto). Repita até bater.
6. **Entregue:** o mapa em `simuladorMaze/mapas/<nome>.json` e a `sobreposicao.png` (SendUserFile).
   Diga o que foi suposto e o que vale a pena medir ou fotografar de novo; ponha isso no `_comentario`.

## Cuidados

* Uma foto inclinada de um canto quase nunca dá o labirinto inteiro: as paredes escondem o piso e umas
  às outras. Se não fechar, diga o que deu (grade, níveis, parte do mapa) e peça as fotos do roteiro
  ("Tirando as fotos") em vez de chutar paredes.
* O simulador só tem rampa e escada de um ladrilho: escada maior vira um ladrilho com o mesmo desnível
  (decisão do Julio em 06/11/2026), anotada.
* Não mexa no código do simulador para encaixar a foto. Faltou um recurso? Proponha e espere ele pedir.
* As imagens e listas da pasta de trabalho o git ignora; `foto.jpg`, `projeto.json` e `descricao.json`
  ficam (ele decide o commit). Commits só quando ele pedir.
* Mudou o método ou aprendeu algo novo: atualize o `MAPA_DA_FOTO.md` (seção "Lições").
