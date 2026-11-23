# Robô tutor: plano (18/11/2026)

Ideia do Julio: usar o robô para ensinar programação. O aluno recebe um desafio (seguir linha, os
desafios da OBR), programa em blocos ou em Python, roda, e o próprio robô conversa com ele sobre o
código: o que deu errado, onde, e uma pista do caminho, sem entregar a resposta.

Feito até agora (18/11/2026): a **fase 0**, o registro da volta no simulador da Line e o
`tutor/resumo.py`, com 21 casos de teste (21 de 21 certos); e a **fase 1**, o `tutor/tutor.py` pelo
terminal com o Claude Haiku: 19 de 21 casos no teste automático (meta: 17), US$ 0,0017 por resposta.
O Julio leu as conversas e aprovou o tom em 19/11 ("qualquer coisa a gente ajusta" depois).
Em 19/11, a primeira versão da **fase 2**: `tutor/servidor.py` + `tutor/pagina/` (Monaco e Jedi em
`tutor/terceiros/`), roda no PC do aluno, com a chave embaralhada numa DLL (decisões dele: local para
o aluno poder usar em casa; a chave atual por enquanto). Falta ele fazer de aluno do L01 ao L03 e o
pacote para o PC do aluno. Os **blocos ficaram para depois** (decisão dele, 19/11). Como usar e o que se
aprendeu: [LEIAME.md](LEIAME.md). O resto é plano; a próxima é a fase 2 (a página).

## Decisões já tomadas

* **Cérebro: Claude pela API, por enquanto** (decisão do Julio em 18/11: "vamos usar o claude pra
  testes, se no futuro precisar a gente troca"). Modelo padrão `claude-haiku-5-5`, a mesma chave do
  robô de casa (`CEREBRO_CHAVE_API`). O cérebro fica atrás de uma interface só, como no
  `simuladorCasa/exemplo_casa/cerebro.py`, para dar para trocar por um modelo local (Ollama) depois.
  Não usar o Opus sem o Julio pedir.
* **A IA não roda no brick.** O Banana Pi não aguenta um modelo que entenda código. "Embarcada", na
  prática, quer dizer que o robô fala e o pensamento vem da API (ou, no futuro, de um servidor da escola).
* **A voz é local**, como no robô de casa: o robô fala pelo Piper (no brick ou no PC) e ouve pelo
  Whisper no PC. Nenhum serviço de voz na internet.
* **Começa pelo simulador da Line**, não pelo robô de verdade. Lá tudo se repete igual (semente), o
  juiz já sabe onde o robô saiu da linha e os 13 desafios já existem com meta automática.

## A ideia central: o tutor não julga, ele explica

Ler só o código não basta em robótica: o código pode estar "certo" e o robô sair da linha por causa
do ganho, da velocidade ou do sensor. E uma IA que decide se o aluno passou erra com confiança. Então:

1. **Quem diz se deu certo é o juiz**, por regra fixa (a `meta` de `simuladorLine/desafios/desafios.json`,
   que o `avalia.py` já confere em 6 sementes).
2. **Quem diz o que aconteceu é o registro da volta**: o que o programa leu e mandou, de 50 em 50 ms.
3. **Um resumo automático** (Python, sem IA) acha os momentos importantes no registro: onde perdeu a
   linha, se o robô ziguezagueia, se o motor ficou no máximo, se viu o verde e não virou, se o
   programa travou ou deu erro.
4. **A IA só junta tudo e conversa**: recebe o desafio, o código, o placar e o resumo, e faz uma
   pergunta ou dá uma pista ao aluno.

Exemplo do que se quer ouvir: "Na curva fechada os quatro sensores ficaram brancos por 0,8 s e você
continuou mandando 60 nos dois motores. O que o seu programa faz quando perde a linha?"

## O fluxo

```
aluno escreve (blocos → Python, ou Python direto)
   ↓ botão Rodar
simulador (avalia.py: 1 a 6 sementes, sem janela)  →  placar + eventos do juiz + registro da volta
   ↓
resumo.py (sem IA): problemas encontrados + trechos de 2 s em volta de cada um
   ↓
tutor (Claude): desafio + notas do professor + código + resumo + conversa até agora + nível de dica
   ↓
resposta curta (texto na página; o robô fala, se a voz estiver ligada)
   ↓
aluno muda o código e roda de novo  (ou pergunta: "por que ele vira para o lado errado?")
```

## As peças

### 1. Registro da volta (novo, no simulador)

O `simulador.py --resultado` já grava o placar e os eventos do juiz (LoP, verde, gap, com tempo).
Falta o registro fino. Proposta: `--registro arquivo.jsonl`, uma linha a cada 50 ms:

* `t`, posição e ângulo do robô na pista e o ladrilho em que está (o tutor usa isso para dizer "na
  curva fechada"; o aluno não tem isso no robô de verdade);
* o que o programa **leu**: sensor de linha (os 4 IR), cores, giroscópio, distâncias;
* o que o programa **mandou**: potência/velocidade de cada motor, servos, LEDs;
* o que o programa imprimiu (`print`) e o erro, se houver (com a linha do código).

O simulador já passa por todas essas leituras e comandos (é ele que responde às libs pelo socket),
então dá para gravar sem mexer no programa do aluno nem nas libs.

### 2. Resumo do registro (novo, `tutor/resumo.py`)

Sem IA, testável. Procura e mede:

* **perda de linha**: os 4 IR no branco; quanto tempo; o que os motores faziam;
* **ziguezague**: quantas vezes por segundo o erro troca de sinal nas retas (KP alto, KD baixo);
* **lerdo ou travado**: velocidade média, tempo parado sem estar na chegada;
* **saturação**: motor em ±100 por muito tempo;
* **verde**: o sensor viu verde perto da interseção e o robô virou certo/errado/não virou;
* **gap e obstáculo**: o que aconteceu no gap; distância lida antes de bater;
* **programa**: erro (exceção) com a linha; laço sem pausa; tempo entre leituras.

Saída curta (umas 30 linhas) para caber barato no pedido à API.

### 3. Desafio para o tutor

Os desafios L01-L13 já têm título, descrição, módulo do curso e meta. Para o tutor, cada um ganha:

* `objetivo_aluno`: o que o aluno deve aprender (ex.: "controle proporcional", "tratar a perda de linha");
* `dicas`: 3 níveis (pergunta → pista → apontar o trecho do código), nunca o código pronto;
* `erros_comuns`: o que o resumo deve procurar com mais atenção nesse desafio.

O que for gabarito ou nota do professor fica em `professor/` (privado). **Cuidado:** se as notas
forem junto para o PC do laboratório, um aluno pode abrir o arquivo. Ou elas ficam num PC que o
aluno não mexe (o tutor roda ali e os PCs dos alunos só abrem a página), ou as notas não podem ter
a resposta.

### 4. O tutor (novo, `tutor/tutor.py`)

* Instrução fixa: professor paciente, fala curta (vai virar voz), em português simples, pergunta
  antes de explicar, nunca escreve o programa pelo aluno, sobe o nível de dica só depois de o aluno
  tentar. Fala sobre o código **do aluno** (nomes das variáveis dele, número da linha).
* A parte fixa (instrução + referência das libs do curso + desafio) com cache de prompt, para ficar
  barato a cada nova tentativa.
* Ferramentas que ele pode pedir (como as 7 do robô de casa): `ver_trecho_registro(t1, t2)`,
  `ver_linhas_codigo(a, b)`, `rodar_de_novo(semente)`, `sobe_nivel_dica()`.
* Mede o custo de cada resposta (como o `PRECO_USD_MTOK` do `cerebro.py`) e grava.

### 5. A página do aluno (nova)

Servidor Python local + uma página, como o estúdio de voz (`simuladorCasa/ferramentas/estudio_voz.py`):

* editor de Python e, depois, de blocos. Os blocos usam a API real das libs (`Motores`,
  `SensorCorReflexao`...), e o Python gerado aparece ao lado: o aluno vê o que os blocos viram, e
  o tutor sempre lê o Python;
* botão Rodar (chama o `avalia.py`), o placar, e a conversa com o tutor;
* tem de rodar nos PCs do laboratório sem instalar nada: o Python portátil do `simuladorLine`
  (`ferramentas/monta_portatil.py`) mais o pacote `anthropic`;
* os blocos: o Blockly (biblioteca JavaScript do Google, gratuita) já traz o gerador de Python.
  **Precisa baixar uma vez** (pedir ao Julio) e fica dentro da pasta: a página não usa a internet
  para isso.

### 6. Painel do professor

Pasta `resultados/tutor/<aluno>/` com cada tentativa (código, placar, resumo, conversa, custo). Uma
página que lista a turma: quem passou em qual desafio, quantas tentativas, onde travou, e as
conversas para o Julio conferir se o tutor está ensinando certo.

## Privacidade (alunos menores de idade)

* Para a API vão só o código, o resumo da volta e o texto da conversa. Sem nome (um apelido ou
  número), sem foto, sem áudio: a voz é transcrita no PC e só o texto vai.
* Guardar as conversas no PC da escola, não na nuvem.
* Avisar os alunos (e a escola, se precisar) de que o tutor usa um serviço na internet. É por isso
  que o cérebro fica trocável por um modelo local.

## Fases

Cada fase termina testada antes da seguinte.

| fase | o que | pronto quando |
|---|---|---|
| 0 | `--registro` no simulador da Line e o `resumo.py` | o resumo acha o defeito certo num conjunto de ~20 programas estragados de propósito (KP alto, sem tratar a perda de linha, sinal trocado, rápido demais, verde ao contrário, laço sem pausa, erro de digitação...) e não acha problema nos `curso/codigos/` que passam |
| 1 | tutor pelo terminal: `python tutor/tutor.py --desafio L01 --programa x/main.py` | nos mesmos ~20 programas, aponta o defeito sem entregar a resposta em pelo menos 17; o Julio lê as conversas e aprova o tom; custo por resposta medido |
| 2 | página com o editor de Python, Rodar e a conversa | um aluno (ou o Julio fazendo de aluno) vai do L01 ao L03 só com o tutor |
| 3 | blocos | os desafios do nível 1 dá para fazer só com blocos |
| 4 | voz | o robô do simulador fala as respostas (Piper); ouvir pelo Whisper do PC, se fizer sentido na sala |
| 5 | robô de verdade | registro no brick (um módulo que o programa importa e que anota leituras e comandos, sem mudar `libs/`), o arquivo volta para o PC pelo envio, juiz pelos sensores (perder a linha = 4 IR no branco) e um botão para "cheguei"/"saí"; o robô fala a resposta |
| 6 | a trilha toda | L01-L13 (níveis 1 a 4 da OBR) e depois a Maze (`simuladorMaze` já tem o `avalia.py` e desafios) |

## O que já existe e vai ser reaproveitado

* `simuladorLine/avalia.py` e `desafios/desafios.json`: os 13 desafios, as metas e as várias sementes.
* `simuladorLine/sim/juiz.py`: o placar e os eventos com tempo.
* `simuladorCasa/exemplo_casa/cerebro.py`: o Claude pela API com ferramentas, a chave, a troca por
  modelo local e a conta do custo.
* `simuladorCasa/exemplo_casa/voz.py` e o `servidor_voz.py`: falar (Piper) e ouvir (Whisper no PC).
* `curso/` (18 módulos, `referencia/`, `codigos/`): o que o tutor sabe sobre as libs e o que pede
  em cada desafio.
* `.claude/skills/especialista-mariola/`: os problemas conhecidos que os alunos já tiveram.
* `professor/gabarito/`: aonde o aluno tem de chegar (privado; ver o cuidado acima).

## Em aberto (perguntar ao Julio quando chegar a hora)

* O laboratório tem internet estável nos PCs? Sem ela, o tutor pela API para.
* O tutor roda em cada PC de aluno ou num PC só (do professor) que todos abrem pela rede? O segundo
  protege as notas do professor e a chave da API, mas esbarra no firewall do Windows.
* Quanto gastar por aula: medir na fase 1 e decidir.
* O tutor tem nome e voz próprios, ou é o "robô" de cada equipe?
* Começar pelo robô de esteira (`robo_esteira.json`, o do módulo 6) ou pelo 4x4?
