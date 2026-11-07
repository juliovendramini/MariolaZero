# Mapa do simulador a partir de foto da pista

Como transformar a foto de uma pista de verdade (de competição, do laboratório) num mapa do simulador
da Line, o mais parecido possível. O trabalho é feito com o Claude: as ferramentas medem e comparam, e o
reconhecimento final (que ladrilho é, onde está o verde, o que está escondido) é feito olhando as
imagens. No Claude Code basta pedir "monta o mapa desta foto" e mandar a foto: a skill `mapa-da-foto`
(`.claude/skills/mapa-da-foto/`) segue este roteiro.

Ferramenta: `ferramentas/foto_mapa.py` (rode da pasta `simuladorLine`). Precisa só do que o simulador
já usa (OpenCV, NumPy, pygame). Primeiro uso: 04/11/2026, a pista do mundial
(`mapas/pista_foto.json`, pasta de trabalho `fotos_mapa/mundial2026/`).

## O que dá e o que não dá

* Dá: ladrilhos oficiais e rotação, verdes, gaps, chegada, área de resgate (posição, entrada, saída,
  cantos verde/vermelho), obstáculos, checkpoints, lombadas em qualquer posição e ângulo, tabuleiros
  inclinados (o ângulo é uma estimativa).
* Não dá sem ajuda: o que a foto não mostra (ladrilho escondido atrás de um objeto ou parede, a
  largada, alturas). O ladrilho escondido sai das ligações dos vizinhos; a largada é escolhida e
  anotada. Tudo o que for suposto vai no `_comentario` do mapa.
* Ladrilho fora do catálogo oficial (desenho feito à mão) não existe no simulador: usa-se o oficial
  mais parecido e anota-se.

## Tirando as fotos (vale ouro na competição)

1. **Do alto e de frente**, de pé numa cadeira se der, pegando a pista inteira. Quanto mais de cima,
   melhor a vista de cima depois. Uma foto geral e, se der, uma por tabuleiro.
2. **A área de resgate inteira** (os 4 cantos do chão dela) e os cantos dos tabuleiros aparecendo.
3. Sem gente nem mochila em cima da pista. Luz sem reflexo forte (reflexo apaga a fita preta).
4. Uma **trena** esticada ao lado de um tabuleiro ajuda a conferir a escala.
5. Tabuleiro inclinado: uma foto **de lado** dele (o ângulo sai bem melhor que pela foto de frente).
6. Anote o que a foto não mostra: onde é a largada, quantos graus tem a rampa/tabuleiro inclinado.

## Coordenadas (o mais importante para não se perder)

* **Foto:** pixels da `foto.jpg` da pasta de trabalho (x para a direita, y para baixo). Todas as
  imagens de trabalho têm uma régua com esses números.
* **Chão:** mm no referencial do **mapa**: X para o leste a partir da borda oeste do mapa, Y para o
  **sul** a partir da borda norte (o norte é o alto da tela do simulador). O ladrilho (x, y) vai de
  X = 300x a 300x + 300 e de Y = 300y a 300y + 300. Canto noroeste do ladrilho (x, y) = (300x, 300y).
* **Dentro do ladrilho** (lombadas, obstáculos): u, v em mm a partir do canto **sudoeste**, v para o
  norte (como no arquivo do mapa). Lombada solta: `{u, v, ang, comp}`, centro, ângulo em graus
  anti-horário a partir do leste, comprimento. Na área de resgate, u, v a partir do canto sudoeste dela.
* Escolha logo a grade do mapa: quais colunas e fileiras cada tabuleiro ocupa. Deixe uma fileira ou
  coluna de folga se não souber o tamanho ainda (dá para refazer as calibrações depois).

## Passo a passo

Os exemplos são os comandos de verdade da pista do mundial.

### 1. Pasta de trabalho
```
python ferramentas/foto_mapa.py novo mundial2026 C:\caminho\da\foto.jpg
```
Cria `fotos_mapa/mundial2026/` com a `foto.jpg` (já de pé), `projeto.json`, `descricao.json` (modelo)
e `foto_regua.png` (a foto inteira com régua). Olhe a `foto_regua.png` e decida:
* quantos tabuleiros, quantos ladrilhos cada um (conte as emendas, as linhas finas a cada 30 cm);
* onde fica a área de resgate (4 x 3 ladrilhos = 120 x 90 cm);
* a grade do mapa (largura x altura) e em que colunas/fileiras vai cada coisa.

Para ver detalhes: `recorta` (pedaço ampliado, com régua; `--emendas` realça as emendas):
```
python ferramentas/foto_mapa.py recorta mundial2026 0 1140 1980 2690 --emendas
```

### 2. Calibração: ligar pontos da foto a pontos do chão
Precisa de **4 pontos ou mais no mesmo plano** (o chão de um tabuleiro), espalhados (perto dos
cantos do tabuleiro), cuja posição em mm no mapa se conhece. Bons pontos, do melhor para o pior:
1. **Cruzamento de duas emendas** (canto comum de 4 ladrilhos): posição exata, múltiplo de 300.
2. **Cruzamento de linhas** ou ponta de T no meio da borda: a linha da regra passa no meio da borda
   (150 mm) — confira no desenho do ladrilho.
3. Canto do chão da área de resgate (120 x 90 cm por fora; a parede tem espessura) — foi a primeira
   tentativa no mundial e ficou torta: a base da parede não é bem o canto.

```
python ferramentas/foto_mapa.py calibra mundial2026 chao "930,1224,150,450" "1824,1230,1050,450" "764,2060,450,1650" "380,2044,150,1650" --obs "cruzamentos de linha do tabuleiro da esquerda"
```
Cada ponto é `"fx,fy,X,Y"`: (fx, fy) na foto, (X, Y) em mm no mapa. Com mais de 4 pontos ela usa
todos (mínimos quadrados) e mostra o erro de cada um: acima de ~20 mm, o ponto está errado.

Ela grava a vista de cima (`vista_chao.png`) com a **grade do mapa** em magenta e os pontos usados em
verde. **Confira:** as emendas dos ladrilhos têm de cair na grade em todo o tabuleiro, inclusive longe
dos pontos. Se escorregar, troque/acrescente pontos e rode de novo (mesmo nome = substitui).
`vista ... --emendas` realça as emendas; `--preto` mostra o que vai contar como fita preta.

**Um plano, uma calibração.** Tabuleiro inclinado, tabuleiro em outra altura ou desalinhado é outro
plano: faça outra calibração só com pontos dele e diga a região em que ela vale:
```
python ferramentas/foto_mapa.py calibra mundial2026 fundo "1974,956,1200,0" "3216,950,2400,0" "3280,1228,2400,600" "1960,1224,1200,600" --ladrilhos 4,0,7,3
```
(Num tabuleiro inclinado as distâncias ao longo dele, na foto, são as do plano dele: a vista de cima
fica certa para reconhecer os ladrilhos, mas a posição dele no chão é aproximada.)

### 3. Reconhecer os ladrilhos
```
python ferramentas/foto_mapa.py casa mundial2026 chao 0,1,3,6
```
Compara cada quadrado com os 82 ladrilhos oficiais nas 4 rotações (deixa a grade escorregar até
40 mm). Grava `casa_0_1.txt` (os 6 melhores de cada quadrado: nota em mm, menor = melhor; acima de
~15 é duvidoso) e `casa_0_1.png` (foto | escolhido). **A escolha automática é um ponto de partida:**
* ela não vê o verde (conta como preto): T com e sem verde, cruzamento com verde em cantos diferentes
  dão a mesma nota. Decida o verde olhando a foto;
* objetos em cima (cilindros, prancheta, fita, trena) atrapalham: o quadrado sai errado;
* `branco` com nota baixa pode ser ladrilho escondido.

Para decidir entre candidatos, desenhe-os grandes, com rotação e ligações (entrada>saída):
```
python ferramentas/foto_mapa.py catalogo                       # folha com todos (uma vez)
python ferramentas/foto_mapa.py candidatos tile-16_2/180 tile-41/180 tile-15/180
```
Regra de ouro: **as ligações têm de fechar.** A linha que sai de um ladrilho pela borda leste entra
no vizinho pela oeste, na mesma altura. Ladrilho escondido: escolha o que liga os vizinhos.

### 4. Itens
* **Ponto da foto → mm/ladrilho/u,v:**
  ```
  python ferramentas/foto_mapa.py ponto mundial2026 chao 1504,1760 --zona 4,4,3
  ```
  Use a **base** do objeto (o ponto que toca o chão), nunca o topo: o topo está acima do chão e a
  calibração é do chão. Cilindro: o meio da base.
* **Lombadas** (varetas): o ladrilho de perto, 2 px/mm, com régua u/v a cada 50 mm:
  ```
  python ferramentas/foto_mapa.py ladrilho mundial2026 chao 2 5
  ```
  Meça as duas pontas de cada vareta (u1,v1 e u2,v2) e escreva `{u: meio, v: meio, ang: atan2(v2-v1,
  u2-u1) em graus, comp: distância}`. Depois de pôr na `descricao.json`, rode de novo: as lombadas
  descritas aparecem em ciano em cima da foto, para conferir.
* **Obstáculos:** posição (u, v) da base e tamanho (`larg`, `comp`, `altura` em mm). Padrão do
  simulador: 60 x 60 x 150, 1,5 kg, solto.
* **Checkpoints:** os discos (amarelos no mundial) → `"checkpoint": true`.
* **Área de resgate:** canto (x, y) da grade, `larg` 4 e `alt` 3 (ou 3 e 4), `entrada` e `saida`
  como `{lado: N/L/S/O, i}` (i = qual célula daquele lado, contando do oeste ou do norte, a partir de
  0), cantos dos triângulos `verde` e `vermelho` (NO/NE/SE/SO), palitos (`detritos`: número ou lista),
  `cor_parede`, obstáculos dentro dela. A entrada tem fita prata, a saída fita preta.
* **Tabuleiro inclinado:** graus por estimativa (melhor: medir no campo ou foto de lado):
  ```
  python ferramentas/foto_mapa.py inclinacao mundial2026 chao --sobe N --dobra 1200 --em 1200 --topo 1974,956 --comprimento 1200
  ```
  `--dobra`: mm (Y se sobe N/S, X se sobe L/O) da linha em que ele sai do chão; `--em`: a outra
  coordenada, perto do ponto medido; `--topo`: um ponto da borda de cima dele na foto;
  `--comprimento`: da dobra até essa borda, ao longo dele. Ele testa aberturas de câmera de 55 a 85°;
  vale a linha com "ortogonalidade" mais perto de 0. No mundial deu 3,4-3,9° (o mapa ficou com 5°,
  chute de antes da ferramenta). Rampa de um ladrilho só: `"rampa": {"sobe", "graus"}` no ladrilho.
* **Largada:** a foto quase nunca mostra. Escolha um ladrilho reto no começo provável e anote.

### 5. Montar e conferir
Escreva a `descricao.json` (modelo em `ferramentas/foto_mapa_descricao_modelo.json`; exemplo
completo em `fotos_mapa/mundial2026/descricao.json`):
```json
{
 "nome": "pista_foto",
 "_comentario": "o que foi suposto",
 "largura": 8, "altura": 7,
 "inicio": [3, 2], "inicio_dir": "S",
 "ladrilhos": {
  "0,1": "tile-16_2 180",
  "3,2": {"tipo": "tile-18", "rot": 90, "lombadas": [{"u": 152, "v": 195, "ang": 45, "comp": 185}]},
  "1,4": {"tipo": "tile-59", "rot": 90, "checkpoint": true, "_obs": "disco amarelo"}
 },
 "inclinacao": [{"de": [4, 0], "ate": [7, 3], "sobe": "N", "graus": 5}],
 "zona_resgate": {"x": 4, "y": 4, "larg": 4, "alt": 3, "entrada": {"lado": "O", "i": 2},
                  "saida": {"lado": "O", "i": 0}, "verde": "NE", "vermelho": "SE", "detritos": 40}
}
```
Campos que começam com `_` são comentários (não vão para o mapa).
```
python ferramentas/foto_mapa.py monta mundial2026
python ferramentas/foto_mapa.py compara mundial2026
```
`monta` grava `mapas/<nome>.json`, mostra o **caminho que o juiz calcula** (cada passo; `*` = área de
resgate) e os avisos da validação. O caminho tem de ir da largada até a chegada passando pela área;
se parar no meio, a ligação entre dois ladrilhos não fecha (ou o verde está do lado errado).
"Ladrilho com linha fora do caminho" é normal em pista de competição (becos, desvios).
`compara` grava `comparacao.png`: foto vista de cima | mapa, na mesma grade. Repita 3 a 5 até as
duas metades baterem.

### 6. Validar no simulador
* Abra o mapa na janela (`python simulador.py --mapa mapas/pista_foto.json`) e olhe; o editor ajusta
  detalhes (Shift+clique põe lombada solta, a roda gira).
  `confere mapas/x.json --janela saida.png` grava o desenho da própria janela, sem abrir.
* Rode um programa de exemplo nele (`--sem-janela`) só para ver se nada quebra; a nota não importa.
* Escreva no `_comentario`: de onde veio a foto, o que foi suposto, o que falta medir.

## Arquivos

| arquivo | o que é |
|---|---|
| `ferramentas/foto_mapa.py` | a ferramenta (`-h` mostra os comandos) |
| `ferramentas/foto_mapa_descricao_modelo.json` | modelo da `descricao.json` |
| `fotos_mapa/<nome>/foto.jpg`, `projeto.json`, `descricao.json` | o trabalho de cada foto (vão para o git) |
| `fotos_mapa/<nome>/*.png` | imagens de trabalho (o git ignora; saem de novo) |
| `fotos_mapa/mundial2026/` | o exemplo completo: a pista do mundial (`mapas/pista_foto.json`) |

## Lições do mundial (04/11/2026)

* A primeira calibração (cantos do chão da área de resgate) ficou boa no geral, mas torta no
  tabuleiro da esquerda. Recalibrar com pontos **do próprio tabuleiro** (cruzamentos de linha) resolveu.
* O tabuleiro do fundo era inclinado: por isso as fileiras dele pareciam mais altas na foto e ele
  ficava "meio ladrilho deslocado". Calibração separada dele e inclinação no mapa.
* A comparação automática acertou a maior parte; a fileira de cima, com a grade escorregando um pouco,
  e os ladrilhos com verde foram decididos à mão com os `candidatos`.
* Ladrilhos atrás dos cilindros e da parede da área saíram das ligações dos vizinhos.
* As 9 varetas brancas presas com fita preta são lombadas em posições quaisquer (cruzadas, em
  diagonal): foi por causa delas que o simulador ganhou a lombada solta `{u, v, ang, comp}`.
* Validação: o caminho do juiz fechou com 43 passos; o exemplo da Line roda nele (70 pontos, 18 LoPs:
  não foi feito para essa pista).
