# Mapa do simulador da Maze a partir de foto do labirinto

Como transformar a foto de um labirinto de verdade (competição, laboratório) num mapa do
`simuladorMaze`. O trabalho é feito com o Claude: as ferramentas medem, retificam e desenham, e quem
decide (que parede existe, que piso é, onde está a vítima) é quem olha as imagens. No Claude Code basta
pedir "monta o mapa desta foto" e mandar a foto: a skill `mapa-da-foto-maze`
(`.claude/skills/mapa-da-foto-maze/`) segue este roteiro. É o irmão do `simuladorLine/ferramentas/
MAPA_DA_FOTO.md` (06/11/2026), com o que muda na Maze: paredes altas, pisos em mais de um nível,
vítimas nas paredes.

Ferramenta: `ferramentas/foto_mapa.py` (rode da pasta `simuladorMaze`; `-h` lista os comandos). Usa
OpenCV e NumPy (no PC do Julio já tem; o `requirements.txt` do simulador não tem o OpenCV, porque o
simulador não precisa). Teste com resposta conhecida: `ferramentas/foto_mapa_sintetica.py` desenha a
foto de um mapa (pasta de trabalho `fotos_mapa/sintetico/`, com o `exemplo1`).

## O que dá e o que não dá

* Dá: a grade, as paredes que aparecem, pisos coloridos (preto, azul, prata, vermelho), vítimas (o lado
  e a posição na parede), rampa/escada de um ladrilho (os graus são estimativa), mais de um nível.
* Na Maze a foto é **muito mais difícil** que na Line: as paredes (15 cm ou mais) escondem o piso e as
  outras paredes, e numa foto inclinada elas "tombam" na vista de cima e cobrem as bases umas das
  outras. Uma foto só, de lado, quase nunca mostra o labirinto inteiro.
* Não dá sem ajuda: o que fica atrás das paredes, a largada, a altura dos níveis (só estimativa), o tipo
  de vítima pequena ou longe. Tudo o que for suposto vai no `_comentario` do mapa.
* O simulador tem rampa e escada de **um** ladrilho. Escada maior no campo: um ladrilho de escada com os
  graus que dão o mesmo desnível (o Julio decidiu assim em 06/11/2026) e anote.

## Tirando as fotos (o que mais importa)

1. **Do alto e o mais de cima possível**, de pé numa cadeira, o celular apontado para baixo. Quanto mais
   de cima, menos as paredes escondem. Celular em pé ou deitado, tanto faz; sem zoom.
2. **Uma foto por canto** (os quatro, se der): o que uma esconde, a outra mostra.
3. Os quatro cantos de fora do labirinto aparecendo em pelo menos uma foto, e o labirinto inteiro.
4. Sem gente nem mochila em cima; luz sem reflexo forte nos pisos coloridos.
5. Uma trena esticada ao lado ajuda a conferir a escala. Anote: o tamanho do labirinto (ladrilhos), a
   altura das paredes, onde é a largada, quantos degraus/graus tem a rampa ou a escada.

## Coordenadas

* **Foto:** pixels da `foto.jpg` da pasta de trabalho (x para a direita, y para baixo); as imagens de
  trabalho têm régua com esses números.
* **Chão:** mm: X para o leste a partir da borda oeste e Y para o **sul** a partir da borda norte. O
  ladrilho da coluna c e linha l vai de X = 300c a 300c + 300 e de Y = 300l a 300l + 300. As linhas da
  grade ficam no **eixo** das paredes (a base que se vê é a face, 10 mm para o lado).
* **Ladrilho** nos comandos: `c,l` (coluna, linha); áreas `c0,l0,c1,l1`. No mapa é `{"linha", "coluna"}`.
* **Bordas:** `h<l>,<c>` = parede no norte do ladrilho (l, c) (l de 0 a linhas); `v<l>,<c>` = no oeste
  (c de 0 a colunas). São os índices de `paredes_h` e `paredes_v` do mapa.
* Escolha logo o leste e o sul do mapa (de preferência como o labirinto aparece de cima) e não mude
  mais. O sul fica 90° à direita do leste olhando de cima; ao contrário o mapa sai espelhado (o `fugas`
  avisa).

## Passo a passo

### 1. Pasta de trabalho
```
python ferramentas/foto_mapa.py novo foto1 C:\caminho\da\foto.jpg
```
Cria `fotos_mapa/foto1/` com `foto.jpg`, `projeto.json`, `descricao.json` (modelo) e `foto_regua.png`.
`recorta foto1 x0 y0 x1 y1 [--zoom Z]` amplia um pedaço com régua (cantos de piso, perfis, vítimas).

### 2. Calibração
Dois caminhos. Os dois gravam a calibração de um **plano** (o chão de um nível) e a câmera dela (foco e
posição), que dá a altura das coisas.

**a) Por pontos do chão** (quando dá para ver 4 cantos da grade no mesmo nível): base dos perfis de
alumínio nos cruzamentos de parede, cantos de fora do labirinto, emendas do piso.
```
python ferramentas/foto_mapa.py calibra foto1 chao "fx,fy,X,Y" "fx,fy,X,Y" "fx,fy,X,Y" "fx,fy,X,Y"
```
Com mais de 4 pontos ela mostra o erro de cada um (acima de ~20 mm, ponto errado). A câmera sai da
própria calibração (`camera foto1 chao` refaz; `--topo "fx,fy,X,Y" ...` com pontos do alto das paredes
acerta o foco e a altura das paredes; `--fov G` força a abertura).

**b) Pelos pontos de fuga** (quando não se sabe onde fica nenhum canto da grade, como na foto inclinada
de um canto): retas de duas direções do labirinto dão a orientação do chão e o foco.
```
python ferramentas/foto_mapa.py fugas foto1 --leste "x1,y1,x2,y2" ... --sul "x1,y1,x2,y2" ...
```
Cada reta é dada no sentido da direção (primeiro ponto -> segundo = para o leste, ou para o sul). As
melhores: **bordas de pisos coloridos** (são do chão e retas de verdade); servem também emendas, bases e
alto de paredes, bordas de degrau. Ela mostra o desvio de cada reta (acima de ~1°, reta errada) e grava a
`vista_fugas.png`: a foto vista de cima, sem perspectiva, para **todos** os planos horizontais (cada
nível e o alto das paredes, cada um na sua escala: o mais perto da câmera, maior). Os rótulos brancos da
borda são os pixels dessa vista. Depois, a calibração de cada nível com 2 pontos ou mais da vista:
```
python ferramentas/foto_mapa.py calibra foto1 baixo --fugas "ru,rv,X,Y" "ru,rv,X,Y" ...
python ferramentas/foto_mapa.py calibra foto1 alto --fugas "ru,rv,X,Y" ... --altura 120 --ladrilhos 0,4,3,5
```
Ela diz a que distância da câmera fica cada plano, e a diferença entre dois = a altura de um nível sobre
o outro (bom para a rampa/escada). `--auto` também acha as retas da foto sozinha (detector LSD do OpenCV)
e ajusta o foco com elas; na foto1 isso **entortou** o chão (o piso azul deixou de sair quadrado): confira
sempre se os pisos coloridos ficam quadrados na vista.

**A grade:** escolha a grade pelas **paredes** (bases das paredes da fileira de fora, perfis nos
cruzamentos), não pelos pisos coloridos: na foto1 o piso azul ficou meio ladrilho fora da grade das
paredes. Na vista de cima as paredes aparecem "tombadas" para longe do ponto embaixo da câmera: a base
de cada uma é o lado mais perto desse ponto.

### 3. Paredes
```
python ferramentas/foto_mapa.py paredes foto1 chao --area 0,0,7,5 [--altura 150]
```
Desenha na foto, para cada borda da área, a parede que estaria ali (base magenta, alto ciano, nome da
borda) e grava a vista de cima **na altura do alto das paredes** (`vista_chao_a150.png`): o alto de cada
parede que existe cai em cima da grade. A lista `paredes_chao.txt` traz o contraste no alto e na base de
cada borda, do maior para o menor: é **pista**, não resposta (na foto sintética acertou 2 de cada 3).
Decida olhando as duas imagens. Se o alto das paredes não cai no ciano, a altura das paredes está
errada (`--altura`) ou o foco (`camera --topo`).

### 4. Pisos
```
python ferramentas/foto_mapa.py pisos foto1 chao --area 0,0,7,5
```
Cor do meio de cada ladrilho e um palpite (branco, preto, azul, vermelho, prata?, fora). Parede na frente
engana (sai "prata?" ou cinza): confira na foto. Prata reflete o que está em volta (na foto1 um piso
refletia uma camiseta laranja).

### 5. Vítimas
```
python ferramentas/foto_mapa.py ponto foto1 chao fx,fy --parede
```
Com o ponto do meio da vítima na foto, lista as faces de parede que o raio atravessa, da mais perto da
câmera para a mais longe, já como item do campo `vitimas` (`linha`, `coluna`, `parede`, `posicao`).
Vale a primeira borda que tem parede. Só se vê a face virada para a câmera. Sem `--parede`, `ponto`
dá o ladrilho de um ponto do chão (ou de um plano a `--altura`).

### 6. Descrever e montar
`descricao.json` (modelo em `ferramentas/foto_mapa_descricao_modelo.json`): o formato do mapa, com um
`desenho` em texto no lugar de `paredes_h`/`paredes_v` (os dois servem):
```
 "desenho": [
  "+--+--+--+--+",
  "|     |C    |",
  "+  +  +  +--+",
  "|  |  |     |",
  "+  +--+  +  +",
  "|        |A |",
  "+--+--+--+--+"
 ]
```
`--` = parede no norte/sul do ladrilho, `|` = no oeste/leste. Primeiro caractere de cada ladrilho:
`P` preto, `A` azul, `C` prata (checkpoint), `V` vermelho, espaço = branco. Rampa, escada, lombada,
detritos, zona e vítimas vão em `ladrilhos` e `vitimas`, como no mapa. Campos com `_` são comentários.
```
python ferramentas/foto_mapa.py monta foto1          # grava mapas/<nome>.json, avisos e mapa.png
python ferramentas/foto_mapa.py compara foto1        # comparacao.png e sobreposicao.png
```
`compara` grava a foto de cima ao lado do mapa e a **sobreposição**: as paredes do mapa desenhadas em 3D
em cima da foto, pela câmera da calibração. É o melhor teste: parede a mais ou a menos aparece na hora.
Repita até bater. Os avisos do `monta` são os do editor (alturas que não fecham, ladrilho inalcançável,
vítima em ladrilho especial).

### 7. Validar
Abra no simulador (`python simulador.py --mapa mapas/<nome>.json`), confira no editor e rode o exemplo
uma vez sem janela só para ver se nada quebra.

## Arquivos

| arquivo | o que é |
|---|---|
| `ferramentas/foto_mapa.py` | a ferramenta (`-h` mostra os comandos) |
| `ferramentas/foto_mapa_descricao_modelo.json` | modelo da `descricao.json` |
| `ferramentas/foto_mapa_sintetica.py` | foto sintética de um mapa (teste com resposta conhecida) |
| `fotos_mapa/<nome>/foto.jpg`, `projeto.json`, `descricao.json` | o trabalho de cada foto (vão para o git) |
| `fotos_mapa/<nome>/*.png`, `*.txt` | imagens e listas de trabalho (o git ignora; saem de novo) |

## Lições

* **foto1 (06/11/2026, uma foto do Julio, de um canto, com celular):** dois níveis (o vermelho de
  baixo 90-145 mm acima do azul, pelo tamanho na vista de cima), uma escada comprida no meio, pisos
  azul, vermelhos, preto e prata. Os pontos de fuga pelas bordas dos pisos deram foco 1090 px (abertura
  58°) e câmera ~1,25 m acima do piso de baixo, olhando 63° para baixo. Os pisos coloridos não estavam
  todos na mesma grade (o azul meio ladrilho fora da grade das paredes), as paredes tombadas cobriam as
  bases e a parte de baixo/esquerda saía da foto: **não deu para fechar o mapa com uma foto só**. O
  `--auto` (retas achadas na foto, com os perfis como verticais) entortou o chão. Pasta
  `fotos_mapa/foto1/` com as calibrações `baixo` (grade pelas paredes da fileira de cima) e `alto`.
* Teste sintético (`fotos_mapa/sintetico/`, o `exemplo1`): a calibração por 5 pontos achou a câmera
  exata, o `monta` refez o mapa idêntico e a sobreposição caiu certinho. O contraste das paredes acertou
  só 2 de cada 3: a decisão é visual.
