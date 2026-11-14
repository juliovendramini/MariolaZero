---
name: ladrilho-proprio
description: Cria um ladrilho próprio no simulador da Line (simuladorLine/ladrilhos_proprios/) a partir de uma foto ou de um desenho de pista de treino que não é ladrilho oficial, de 1 ladrilho ou de um bloco de vários (2x2, 3x1...), e um mapa que o usa. Use quando o Julio mandar foto ou desenho de um trecho de pista pedindo "ladrilho", "ladrilho novo", "põe no simulador esse trecho", "pista de treino", ou para mudar um ladrilho próprio.
---

# Ladrilho próprio a partir de foto ou desenho

O roteiro está em `simuladorLine/ferramentas/LADRILHO_PROPRIO.md`. **Leia antes de começar.** A
ferramenta é `simuladorLine/ferramentas/ladrilho_proprio.py` (rode da pasta `simuladorLine`; `-h` lista
os comandos). Exemplo pronto: o bloco `exemplo_foto` (foto em `fotos_mapa/ladrilho_exemplo_foto/`) no
mapa `mapas/exemplo_ladrilho_proprio.json`.

## Como trabalhar

1. **Guarde a foto** em `simuladorLine/fotos_mapa/<nome>/foto.jpg` (reduza para ~1500 px de largura; a
   anexada no chat está no caminho da pasta `uploads` que a mensagem de sistema informa).
2. **Meça** com OpenCV: largura da fita (1 a 2 cm) e verdes (25 mm) dão a escala; ajuste as linhas
   retas e ache cantos (o exemplo usou os cantos do quadrado grande de fita). Diga ao Julio quantos
   ladrilhos o desenho ocupa e por quê.
3. **Escolha os pontos** (foto → mm do bloco, u para a direita e v para baixo a partir do canto noroeste),
   de modo que os verdes fiquem com ~25 mm e as linhas que saem do bloco caiam perto do meio da borda
   (150 mm) para emendar nos oficiais. `foto ... --prolonga 12` se a foto acaba antes da borda.
4. **Confira** a imagem `ladrilhos_proprios/<nome>.png` (Read) e o relatório das bordas.
5. **Caminhos:** percorra como o robô, com a regra do verde, e escreva com `pecas` (caminhos,
   interseções, gaps, `ponto`/`rumo` onde a linha não passa no meio). Se um sentido dá laço, diga.
6. **Mapa:** oficiais antes e depois (reta leste-oeste = `tile-0`, **não** o `tile-7`), início numa reta
   com `inicio_dir`, checkpoint antes do bloco, `Mapa.coloca_bloco()`. Rode o `exemplo_aluno/main.py` em
   umas 3 sementes sem janela e conte o que aconteceu.
7. **Entregue** a imagem do bloco e a do mapa (`foto_mapa.py confere mapas/<mapa>.json`) pelo
   SendUserFile, com o que foi suposto (tamanho, pontos, caminho).

## Cuidados

* O catálogo é lido ao abrir o simulador: quem estava com ele aberto tem de abrir de novo.
* Não mude o tamanho de um bloco usado em mapas sem avisar: as peças mudam de nome/posição.
* Nome do bloco sem `@` e diferente dos oficiais. Commits só quando o Julio pedir.
