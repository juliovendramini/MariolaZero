# curso/ — Curso Mariola (público, vai para o GitHub)

Curso para os alunos: brick Mariola + simuladores da Rescue Line e da Rescue Maze. Leitor: aluno do
ensino médio/técnico. Português simples, frases curtas, um conceito por seção, sempre com código que
roda. Regras gerais do repositório no `../CLAUDE.md`.

## Estrutura

| caminho | o que é |
|---|---|
| `README.md` | apresentação e índice do curso |
| `01-...md` a `18-desafios.md` | módulos. Cada um termina em `## Exercícios` (numerados; o gabarito fica em `../professor/gabarito/NN-*.md`) |
| `referencia/` | uma página por lib (todos os métodos, quando usar, cuidados). `modulos-simulador.md` = simdebug, visao, vítimas e kits |
| `codigos/` | programas dos tutoriais (`01_ola_mariola/` ... `09_maze/`), todos testados nos simuladores |
| `mapas/` | `curso_pista.json` e `curso_area.json` (cópias dos que estão em `../simuladorLine/mapas/`) |
| `imagens/` | fotos do brick, da placa, do sensor de linha, da tela+teclado |
| `site/monta.py`, `site/modelo.html` | gerador do site |
| `curso-mariola.html` | o site (gerado; não editar à mão) |

Grupos de módulos no site: Começando (1-3), Atuadores e sensores (4-10), Simuladores e organização
(11-13), Projetos (14-18).

## Gerar o site

```bash
python curso/site/monta.py        # da raiz do repositório; grava curso/curso-mariola.html
```

* Rode **sempre** que mudar um `.md`, um código de `codigos/` ou uma imagem.
* `monta.py` embute todos os `.md`, `.py` e `.json` de `curso/` (menos `site/` e este `CLAUDE.md`) e as
  imagens em base64. Uma referência nova em `referencia/` precisa entrar em `ref_ordem` e `curtos`
  (o script para com `assert` se faltar).
* `modelo.html` tem o CSS e o JavaScript: trilha lateral, busca, links internos (`#pasta~arquivo`),
  página de pasta quando o link aponta para uma pasta sem README, tema escuro conforme o sistema. Carrega
  `marked@12.0.2` e `highlight.js@11.9.0` do cdnjs: o site precisa de internet para abrir.
* O mesmo `modelo.html` é usado pelo `../professor/monta_professor.py`: teste os dois se mudar o modelo.
* No app do Claude o site está publicado como artifact "Curso Mariola"
  (`https://claude.ai/artifact/T86jjJubDKDdahemc7T1Pa`, privado). Dá para republicar daqui com a
  ferramenta Artifact (`url` = esse link, `file_path` = `curso/curso-mariola.html`); leia a versão
  publicada antes. Pergunte ao Julio antes de republicar, ou republique se ele pedir.

## Testar os códigos do curso

Todo programa de `codigos/` foi rodado sem janela. Exemplo:

```bash
cd simuladorLine
python simulador.py --robo robo_esteira.json --mapa ../curso/mapas/curso_pista.json \
       --programa ../curso/codigos/04_linha/seguidor_p.py --sem-janela --velocidade 4 --semente 1
```

Números citados no texto vieram desses testes (ex.: `curso_pista.json` com o PD da esteira = 130
pontos sem LoP; `curso_area.json` com o exemplo = 220). Se a física de um simulador mudar, rode de
novo e corrija os números.

## O módulo 18 e os desafios

* Descreve `avalia.py`, `desafios/desafios.json` (Line L01–L13, Maze M01–M06), pista/labirinto
  surpresa e `--semente-mapas`. Se um desafio mudar no JSON, atualize a tabela do 18.
* A tabela de referência (18.6) diz quanto o **programa de exemplo** de cada simulador cumpre. Valores
  de 18/10/2026, depois da correção do cruzamento com verde no exemplo da Line:
  L04, L05, L06, L08, L09, L11 = 6/6; L07 média ~287; L10 5/6; L12 4/6; L13 3/6 (em aberto, de
  propósito); Maze M01–M06 = 3/3. Se o exemplo mudar, rode `python avalia.py --desafio LXX` e atualize.

## Coisas que o curso afirma e precisam continuar verdadeiras

* Limitações do simulador (11.9, 17.1 e READMEs): motor ideal (em potência a rotação não cai com
  carga), VL53 sem leitura "velha" (mede na hora em que o resultado é lido), barramento dos servos e
  placas de motor ideal. Por isso os exercícios 4.4 e 7.4 são **no robô**.
* Para-choque (8.2): se só um botão aperta, o robô gira **para o lado do botão apertado**.
* Teclado: LED acende com bit 1; usar `Teclado(i2c_bus=0)` na placa atual.
* Relógio sincronizado nos dois simuladores: mesma semente = mesma rodada (módulo 11.6, 12).
* Tempo de detecção da câmera na Maze: `robo.json` → `deteccao.tempo_processamento_s` (0,1 s).

Ao mudar um exercício, mude também o gabarito em `../professor/gabarito/` (e nunca o contrário:
nada de gabarito aqui).

## Pendências

* Aproximar o simulador do robô real (motor com carga, atraso do VL53...): o Julio deixou para depois.
* Brick Paçoca (programa `.ino` no simuladorLine, desde 18/10) ainda não aparece no curso.
