# Ladrilho próprio (pista de treino fora dos ladrilhos oficiais)

Desde 13/11/2026 o simulador aceita **ladrilhos próprios**: um desenho de linha que não está entre os 82
oficiais, feito de uma **foto** (pista de treino no laboratório, num quadro branco, num campo de outra
competição) ou de um **desenho** (Paint, Inkscape). Ele pode ocupar 1 ladrilho ou um **bloco** de vários
(2x2, 3x1...): a imagem é uma só e o simulador corta em peças de 30 x 30 cm.

Ferramenta: `ferramentas/ladrilho_proprio.py` (rode da pasta `simuladorLine`).
Exemplo pronto: o bloco `exemplo_foto` (2x2, da foto `fotos_mapa/ladrilho_exemplo_foto/foto.jpg`) e o mapa
`mapas/exemplo_ladrilho_proprio.json`.

## Onde fica

```
simuladorLine/ladrilhos_proprios/
    proprios.json          a lista dos blocos (tamanho, descrição, peças)
    NOME.png               o desenho visto de cima, 1 mm por pixel: (L x 300) x (A x 300) px
    _conferir/             imagens para conferir (o git ignora)
```

O `NOME.png` só pode ter as cores do simulador: branco, preto (linha), verde (25 x 25 mm), vermelho
(chegada) e, se quiser, prata (a cor exata `(180, 186, 196)`). A ferramenta já grava assim.

No `proprios.json`, cada peça é `"coluna,linha"` (0,0 = canto de cima à esquerda = noroeste):

```json
"exemplo_foto": {
  "imagem": "exemplo_foto.png", "largura": 2, "altura": 2,
  "descricao": "pista de treino da foto do laboratório",
  "pecas": {
    "1,1": {"caminhos": {"L": "O"}, "intersecoes": 1, "gaps": 1, "ponto": [120, 135], "rumo": "O"},
    "0,1": {"caminhos": {"L": "O"}, "intersecoes": 2}
  }
}
```

* **caminhos**: por onde o robô entra e por onde sai daquela peça, no caminho que o juiz espera
  (N = cima, L = direita, S = baixo, O = esquerda; também aceita top/right/bottom/left). É o mesmo
  que os ladrilhos oficiais têm. Peça sem caminho não está no percurso (pode ter linha de enfeite).
  O que acontece **dentro** da peça (curvas, verdes, quadrados) não importa para o juiz: ele só
  quer saber a ordem das peças.
* **intersecoes** e **gaps**: os pontos que a peça dá quando o robô passa por ela (10 cada).
* **ponto** e **rumo** (opcionais): onde o robô é posto quando começa ou volta de um LoP nessa peça
  (mm a partir do canto noroeste da peça) e para onde ele fica virado. Sem eles, o robô fica no meio da
  peça, virado para a saída, como nos oficiais. Use quando a linha não passa no meio.

No simulador cada peça vira um ladrilho chamado `NOME@coluna,linha` (num bloco 1x1, só `NOME`). Esse é
o nome que vai no arquivo do mapa.

## No editor

O bloco aparece **no fim da paleta**, inteiro. Escolha, gire com R (ou a roda do mouse) e clique numa
célula: o bloco entra todo, com o canto de cima à esquerda (depois de girar) na célula clicada. O que
ficar fora do campo não entra (aparece um aviso). Cada peça depois se comporta como um ladrilho comum:
dá para tirar, pôr checkpoint, rampa...

Abriu o simulador antes de criar o ladrilho? Feche e abra de novo (o catálogo é lido ao abrir).

## Passo a passo com uma foto

1. **A foto.** De cima, o mais de frente possível, com o desenho inteiro e um pouco de branco em volta.
   Tem que aparecer algo de tamanho conhecido: um quadrado de fita, as emendas dos ladrilhos ou os verdes
   (25 mm).
2. **Os pontos.** Escolha 4 pontos (ou mais) que você sabe onde ficam no bloco. No exemplo foram os 4
   cantos do quadrado grande de fita (meio da fita), que viraram um quadrado de 245 mm com o canto de
   cima à esquerda em u = 125, v = 330 do bloco. O 245 foi escolhido para os verdes saírem com ~25 mm, e a
   posição para as saídas da esquerda e da direita ficarem perto do meio da borda (150 mm) da linha de
   baixo dos ladrilhos.
   Coordenadas do bloco: mm a partir do canto noroeste, u para a direita e v para baixo.
3. **Criar:**
   ```
   python ferramentas/ladrilho_proprio.py foto exemplo_foto fotos_mapa/ladrilho_exemplo_foto/foto.jpg 2x2 415,751,125,330 1014,774.5,370,330 1064.5,1372,370,575 383.5,1431,125,575 --prolonga 12 --descricao "pista de treino da foto do laboratório"
   ```
   Ela endireita a foto (vista de cima), separa preto/verde/vermelho do fundo (a luz pode variar no
   quadro), tira sujeira pequena (pontos de caneta) e os verdes cortados pela borda da foto, e diz:
   a largura da linha (tem que dar 1 a 2 cm) e o tamanho dos verdes (25 mm): se não bater, a escala dos
   pontos está errada. `--prolonga 12`: linha que para a menos de 12 mm da borda do bloco (a foto acabou
   antes) segue até a borda, para emendar no ladrilho vizinho.
   Confira `ladrilhos_proprios/NOME.png` e `_conferir/NOME_vista.jpg`.
4. **As bordas.** A ferramenta lista onde as linhas cruzam a borda de cada peça (`bordas NOME` mostra de
   novo). Para emendar com os oficiais, a linha tem que sair perto do meio da borda (150 mm); no exemplo,
   135 e 166 (o robô segue os 15 mm de degrau sem problema).
5. **Os caminhos.** Ande pelo desenho como o robô andaria (com a regra do verde) e anote, peça por peça,
   por onde ele entra e sai. No exemplo, entrando pela direita: a peça 1,1 de L para O (passa uma
   interseção e o gap) e a 0,1 de L para O (duas interseções com verde). Entrando por outro lado o robô
   fica dando voltas nos quadrados: por isso só esse caminho.
   ```
   python ferramentas/ladrilho_proprio.py pecas exemplo_foto --caminhos "1,1:L>O 0,1:L>O" --intersecoes "1,1:1 0,1:2" --gaps "1,1:1" --ponto "1,1:120,135:O"
   ```
   Peça com mais de um caminho: `"0,0:N>S/S>N"`. `--limpa` apaga as peças antes.
   O `pecas` também faz `_conferir/NOME_conferir.png` (peças, setas dos caminhos, ponto de retorno).
6. **Um mapa.** No editor (ou por programa: `Mapa.coloca_bloco(x, y, z, 'NOME', rot)`), com ladrilhos
   oficiais antes e depois. No exemplo: início numa reta (`tile-0`), checkpoint, o bloco e a chegada.

## Passo a passo com um desenho

Desenhe no Paint (ou outro) já visto de cima, na proporção do bloco (2x2 = quadrado), com fundo branco,
linha preta grossa (1 a 2 cm na escala do bloco) e verdes de 25 mm:

```
python ferramentas/ladrilho_proprio.py desenho meu_teste meu_teste.png 2x1 --descricao "zigue-zague"
```

Depois, passos 4 a 6.

## O exemplo (13/11/2026)

A foto do Julio (pista de treino do laboratório, 3000 x 4000 px, guardada com 1500 x 2000) mostra dois
quadrados de fita com três verdes, uma linha que sobe, uma que vai para a esquerda, uma para a direita com
gap e duas para baixo. Endireitada, ela tem ~60 cm entre as saídas da esquerda e da direita (2 ladrilhos);
a parte de cima do bloco só tem a linha que sobe. Linha de ~20 mm, verdes de 25 a 29 mm.

No mapa `exemplo_ladrilho_proprio.json` o robô entra pela direita: com o `exemplo_aluno/main.py` (robô
4x4), sementes 1 a 3, ele passou o gap e as três interseções nas três e chegou ao fim (125 pontos sem LoP na
semente 3; nas sementes 1 e 2 errou uma vez a decisão do verde e tomou LoP). Rotação do bloco (0, 90, 180 e
270°) e ponto de retorno conferidos por programa.

O que não é feito sozinho: os caminhos (a ferramenta mostra as bordas, mas quem decide o percurso é você,
com a regra do verde) e a posição do bloco na foto (os 4 pontos).
