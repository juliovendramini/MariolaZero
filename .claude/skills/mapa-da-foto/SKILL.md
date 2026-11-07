---
name: mapa-da-foto
description: Monta um mapa do simulador da Line (simuladorLine/mapas/*.json) a partir de foto(s) de uma pista de verdade da RoboCupJunior Rescue Line. Use quando o Julio mandar foto de pista/campo (competição, laboratório) pedindo mapa, json, "pista igual a essa", "monta no simulador", ou pedir para conferir/ajustar um mapa feito de foto.
---

# Mapa da Line a partir de foto

O roteiro completo, com as coordenadas, os comandos e as lições do primeiro uso, está em
`simuladorLine/ferramentas/MAPA_DA_FOTO.md`. **Leia antes de começar.** A ferramenta é
`simuladorLine/ferramentas/foto_mapa.py` (rode da pasta `simuladorLine`; `-h` lista os comandos). O
exemplo completo é `simuladorLine/fotos_mapa/mundial2026/` (`projeto.json` e `descricao.json`).

## Como trabalhar

1. **Pasta de trabalho:** `foto_mapa.py novo <nome> <foto>`. A foto anexada no chat está no caminho
   que a mensagem de sistema informa (pasta `uploads`). Várias fotos da mesma pista: uma pasta por foto
   (ou use a melhor para calibrar e as outras só para olhar detalhes com `recorta`).
2. **Olhe** a `foto_regua.png` (Read) e conte tabuleiros, emendas, área de resgate. Diga ao Julio, em
   poucas linhas, o que achou e a grade que vai usar.
3. **Calibre** cada plano (chão de cada tabuleiro; inclinado = calibração própria com `--ladrilhos`),
   com pontos de emendas/cruzamentos do próprio tabuleiro. Abra a vista e só siga quando as emendas
   caírem na grade.
4. **Reconheça** com `casa` e decida à mão com `candidatos` (verde, objetos em cima, escondidos). As
   ligações têm de fechar.
5. **Itens** com `ponto` (base do objeto, nunca o topo) e `ladrilho` (lombadas com régua u/v).
6. **Monte** (`monta`) e **compare** (`compara`); repita até a comparação bater e o caminho do juiz ir
   da largada à chegada passando pela área.
7. **Entregue:** o mapa em `simuladorLine/mapas/<nome>.json` e a `comparacao.png` (mande pelo
   SendUserFile). Diga o que foi suposto (largada, escondidos, graus da inclinação) e o que vale a pena
   medir no campo. Ponha isso também no `_comentario` da `descricao.json` e use `_obs` nos ladrilhos.

## Cuidados

* Mostre progresso curto ao Julio a cada etapa (na competição ele está com pressa): primeiro a grade,
  depois o mapa, depois os detalhes. Um mapa que roda vale mais que um perfeito atrasado.
* Não mexa no código do simulador para encaixar a foto. Se faltar um recurso (como faltou a lombada
  solta e a inclinação em 04/11), proponha e espere ele pedir.
* Não use os ladrilhos de competição fora do catálogo oficial: escolha o oficial mais parecido e anote.
* As imagens `*.png` da pasta de trabalho o git ignora; `foto.jpg`, `projeto.json` e `descricao.json`
  ficam (ele decide o commit). Commits só quando ele pedir.
* Mudou algo no método ou aprendeu uma lição nova: atualize o `MAPA_DA_FOTO.md` (seção "Lições").
