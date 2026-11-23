# Robô tutor

O plano está em [PLANO.md](PLANO.md). Aqui está o que já existe: a **fase 0** (registro da volta e
resumo automático, sem IA) e a **fase 1** (o tutor pelo terminal, com o Claude), de 18/11/2026, e a
primeira versão da **fase 2** (a página do aluno), de 19/11.

## A página do aluno (fase 2)

```bash
tutor\Tutor.bat                 # ou: python tutor/servidor.py   → abre http://127.0.0.1:8780
```

Uma página no navegador com o desafio (escolhe L01-L13 em cima), o editor de Python, os botões
**Rodar** (Ctrl+Enter) e **Ver a volta**, o placar do juiz e a conversa com o tutor. Roda no PC do aluno
(dá para levar para casa): o servidor só escuta em 127.0.0.1 e o que vai para a internet é só o pedido
ao tutor, como no `tutor.py`.

* **Editor:** o Monaco (o do VS Code), com cores, número de linha, desfazer, achar e trocar. Ctrl+S salva
  (e salva sozinho 1,2 s depois de parar de digitar).
* **Complemento:** o Jedi, no servidor, com as `libs_mariola` do simulador no caminho: `motores.` mostra
  `velocidade_motores(velocidade1, velocidade2)` etc., e os parâmetros aparecem ao abrir o parêntese;
  passar o mouse por cima de um nome mostra a explicação da lib. Também completa as variáveis do aluno.
* **Erro de sintaxe:** conferido enquanto ele digita (sublinhado vermelho e a mensagem em cima do
  editor). As mensagens mais comuns do Python estão traduzidas (`SINTAXE_PT` no `tutor.py`: dois-pontos,
  recuo, parêntese que não fecha, `=` no lugar de `==`...). Com erro de sintaxe o Rodar não chama o
  simulador nem o tutor: mostra a linha. O aluno pode perguntar ao tutor pela conversa.
* **Rodar:** salva, roda 2 sementes no simulador (~15 s no L01), mostra o placar e o tutor fala. A
  linha "cumpriram a meta" é a do juiz sem a regra em código.
* **Conversa:** o que o aluno escreve vai para o tutor com o mesmo nível de dica do terminal. Se ele mudou
  o código depois de rodar, o tutor recebe o código novo e o aviso de que ainda não rodou; se ele
  pergunta antes de rodar a primeira vez, o tutor só tem o desafio e o código (`Tutor.sem_volta`). Os
  números de linha que o tutor fala viram links: clicar mostra a linha no editor, marcada em amarelo.
* **Ver a volta:** abre a janela do simulador com a pior rodada da última tentativa (a mesma semente,
  então é a mesma volta). Nos desafios de pista surpresa (L11-L13) ainda não abre.
* O programa de cada desafio fica em `tutor/trabalhos/LXX/main.py` (começa com um modelo: os imports, os
  motores, o sensor e o desafio num comentário) e a conversa em `tutor/conversas/`, como no terminal.
  Os dois ficam fora do git. Fechou o servidor, a conversa da página recomeça (a gravada continua lá).
* **Limite:** 150 respostas do tutor por dia em cada PC (`TUTOR_LIMITE_DIA`, contadas em
  `trabalhos/uso.json`). Não protege a chave; evita um laço gastando o crédito.

Testado em 19/11 pelo navegador do app do Claude: o modelo com um erro (o tutor apontou a linha 19), o
caso 06 dos testes (perdeu a linha e girou para o lado errado: o tutor contou o giro de 173° para a
direita e perguntou o que o programa manda cada roda fazer; na pergunta seguinte, nível 2, apontou a
linha 63), o erro de sintaxe e o `Tutor.bat`. Três respostas, US$ 0,008. O "Ver a volta" foi
conferido só pelo comando (sem abrir a janela). **Falta o Julio fazer de aluno do L01 ao L03**, que é o
critério da fase 2.

### A chave da API na página

No PC do Julio vale a `CEREBRO_CHAVE_API`. No PC do aluno, a `tutor/chave_tutor.dll` (fora do git):

```bash
python tutor/ferramentas/faz_chave.py      # lê a CEREBRO_CHAVE_API e gera a DLL (gcc do Dev-C++, 64 bits)
```

A chave fica embaralhada dentro da DLL (não aparece procurando o texto) e o `chave.py` a passa direto
para o cliente do `anthropic`, nunca para `os.environ`: o programa do aluno roda num processo filho (o
simulador) e leria a variável; por isso o `roda_simulador` e o "Ver a volta" também tiram as variáveis de
chave do ambiente. **Embaralhar não é proteger:** quem souber usar um depurador (ou carregar a DLL pelo
`ctypes`, que é o que o `chave.py` faz) tira a chave. Em 19/11 a DLL tem a chave atual do Julio, por
decisão dele ("põe a chave atual por enquanto, depois a gente troca"). Antes de ir para os alunos: uma
chave só do tutor, com limite de gasto no Console, e rodar o `faz_chave.py` de novo. Se vazar, trocar a
chave e a DLL. Mais seguro, para depois: um servidor intermediário (a VM do bot do Telegram) que guarda a
chave.

### O que está em `terceiros/` (baixado uma vez, em 19/11/2026)

**Fora do git** (decisão do Julio, 19/11): a pasta fica só no PC dele e vai no zip dos alunos. Num
clone novo do repositório ela não existe; para refazer, baixe as mesmas versões:

* `monaco/vs/`: o `min/vs` do pacote npm `monaco-editor` 0.52.2
  (`https://registry.npmjs.org/monaco-editor/-/monaco-editor-0.52.2.tgz`), 13 MB, licença MIT
  (`monaco/LICENSE.txt` e `ThirdPartyNotices.txt`, do mesmo pacote).
* `python/`: `jedi` 0.19.2 e `parso` 0.8.4 (as rodas `py2.py3-none-any` do PyPI, descompactadas com
  as `.dist-info`), 5 MB, licença MIT. O `servidor.py` põe a pasta no `sys.path`; não precisa instalar.

### Para levar ao PC do aluno (ainda não feito)

O `Tutor.bat` usa o Python portátil do simulador (`simuladorLine/portatil/python`) quando ele tem o
pacote `anthropic`, e hoje ele não tem (só pygame, pymunk, numpy, pillow e opencv). Faltam: pôr o
`anthropic` e as dependências dele no portátil (rodas `win_amd64` para o Python 3.12), e um zip com
`tutor/` (com `terceiros/` e `chave_tutor.dll`, que estão fora do git; sem `conversas/` e
`trabalhos/`), `simuladorLine/`, `curso/referencia/` e
`simuladorCasa/exemplo_casa/cerebro.py`, que o tutor usa.

## O tutor (fase 1)

```bash
python tutor/tutor.py --desafio L01 --programa meuRobo/main.py
```

Roda o programa no simulador (2 sementes, uns 1,5 min), mostra o placar e o tutor fala. Depois é só
escrever: uma pergunta, `rodar` (depois de mudar o código) ou `sair`. A dica sobe de nível (1 = uma
pergunta que faz olhar para o lugar certo, 2 = em que parte do código está, 3 = a linha e o que ela faz
de errado) quando o aluno pergunta de novo, ou roda de novo com o mesmo problema; problema novo volta ao 1.
O tutor nunca escreve o código nem o valor certo. Opções: `--sementes 1-6`, `--mostra` (mostra também o
resumo automático), `--seco` (não chama a IA, mostra o que seria mandado), `--registros PASTA --sem-rodar`
(usa registros já gravados), `--uma-vez`, `--cerebro local` (Ollama, sem internet; não testado aqui).

* O cérebro é o do robô de casa (`simuladorCasa/exemplo_casa/cerebro.py`): Claude pela API, chave em
  `CEREBRO_CHAVE_API`, `claude-haiku-5-5`, esforço `medium`.
* As instruções (com a referência de `motores`, `sensorCorReflexao`, `giroscopio` e `vl53` do curso) são
  iguais para todos os desafios e ficam em cache: a 1ª resposta custa ~US$ 0,004; as seguintes, ~US$ 0,001.
* Para a API vão o desafio, o placar, o resumo, o código (sem as duas linhas do começo dos casos de teste,
  que dizem o defeito) e o texto da conversa. Nada de nome.
* Duas ferramentas: `ver_trecho` (amostras do registro entre dois tempos) e `ler_arquivo` (outro `.py` da
  pasta, como o `robo.py` do exemplo). Quase nunca usa.
* A conversa fica em `tutor/conversas/AAAAMMDD-HHMMSS_LXX/` (fora do git): `conversa.json` (cada fala, nível,
  placar, problemas, tokens, custo, tempo) e os registros de cada tentativa.

### Teste do tutor

```bash
python tutor/testes/testa_tutor.py          # os 21 casos, com os registros do roda_casos.py (~US$ 0,10)
```

Em cada caso o aluno fala três vezes sem mudar o código ("o que aconteceu?", "não entendi", "me passa o
código certo") e um juiz (o Haiku, que sabe o defeito e a correção) diz se o tutor levou ao defeito, se
entregou a resposta, se inventou algo, e dá uma nota para o tom. Grava `testes/resultados/tutor_*.md`
(as conversas inteiras, para ler) e `.json`.

Resultado em 18/11/2026 (terceira rodada, depois dos ajustes abaixo): **19 de 21**; US$ 0,104 pelas 63
respostas (US$ 0,0017 cada); 4,1 s por resposta em média (máximo 8,7 s; o Haiku pensa antes de responder).
O que ainda falha:

* **02 (KP baixo):** o resumo só diz "perde a linha" e o tutor vai para a recuperação (o que fazer quando
  perde), não para o ganho. O resumo não separa "corrige pouco" de "recupera mal".
* **16 (KD negativo):** no nível 3 disse "ajuste o sinal dessa parcela", que é quase a resposta.
* O nível 2 às vezes já entrega quase tudo (no 18 compara o 30 com o GAP_MAX_MM). O Julio leu as conversas e
  aprovou o tom e os níveis em 19/11/2026; esses três ficam para ajustar quando aparecerem com alunos.

O que foi ajustado olhando as conversas (as duas primeiras rodadas deram 17 de 21):

* o tutor errava para que lado o robô vira: as instruções dizem que o motor 1 é o da esquerda e que o lado
  mais rápido fica por fora da curva, e que o sinal trocado pode estar em três lugares (posição, correção,
  qual roda recebe o quê);
* o resumo afirmava "o sinal da correção está trocado" também quando o erro era o cálculo da posição
  (caso 15): agora diz que algum sinal está trocado entre o sensor e os motores;
* caso 17: o verde ficou 13 s antes do LoP (o robô vira errado e vaga) e o resumo procurava só 8 s para
  trás ("nenhum TCS passou por cima do verde", falso). Agora procura desde a tentativa, no ladrilho da
  interseção, e diz o lado do verde e para onde o robô girou depois;
* caso 04: problema novo `rapido_demais` (perde a linha nas curvas andando a mais de 1,8 vez os ~113 mm/s
  do seguidor do curso); antes o tutor culpava o KD;
* "zero LoP" não é "nunca perdeu a linha"; sem crase nem asterisco na fala (vai para a voz).

## Registro da volta (no simulador da Line)

```bash
cd simuladorLine
python simulador.py --sem-janela --robo robo_esteira.json --mapa desafios/mapas/L01_pista.json \
       --programa ../curso/codigos/04_linha/seguidor_p.py --registro volta.jsonl
python avalia.py --desafio L01 --programa ../meuRobo/main.py --registros ../tutor/regs   # um por rodada
```

A cada 50 ms: posição, velocidade e giro do robô, o ladrilho, o chão **de verdade** debaixo de cada
canal de IR e de cada TCS, o que o programa leu do sensor de linha, giroscópio e VL53, o que ele mandou
para os motores e o que ele imprimiu. No fim, os eventos do juiz e o placar. O formato está no começo de
`simuladorLine/sim/registro.py`. O registro só lê o simulador: a rodada sai igual com e sem ele.

## Resumo

```bash
python tutor/resumo.py tutor/regs                 # junta as rodadas da pasta
python tutor/resumo.py tutor/regs --json          # o mesmo, em JSON (é o que o tutor vai receber)
python tutor/resumo.py tutor/regs/L01_s1.jsonl --trecho 12 15   # as amostras de 12 a 15 s
```

Diz o que deu errado, onde e com os números, do mais importante para o menos. Cada problema tem um
código (lista em `CODIGOS`, no começo do `resumo.py`): erro no programa, motores girando ao contrário,
correção com o sinal trocado, comandos que não mudam com a linha, laço lento, programa que termina
cedo, perder a linha (seguindo reto, girando para o lado errado ou só perdendo), verde, gap, obstáculo,
rápido demais para as curvas, ziguezague, passar da chegada, devagar demais, parado.

## Testes

`testes/gera_estragados.py` faz 21 programas, cada um com um defeito conhecido (KP alto, sinal da
correção trocado, motor sem inverter, erro de digitação, verde trocado, gap...) e dois sem defeito, e
grava o que o resumo deve achar em `testes/casos.json`. Os casos 00-16 partem do seguidor PD do curso
(esteira, L01); os 17-20, do programa de exemplo do simulador (4x4, L04 e L05).

```bash
python tutor/testes/gera_estragados.py     # só se o seguidor do curso ou o exemplo mudar
python tutor/testes/roda_casos.py          # roda os 21 casos no simulador (2 sementes; uns 10 min)
python tutor/testes/testa_resumo.py -v     # confere o resumo caso por caso
```

Os registros dos testes ficam em `testes/registros/` (fora do git).

Resultado em 18/11/2026: **21 de 21** (o defeito certo em primeiro lugar, e nada de grau 2 ou 3 nos dois
programas sem defeito). Os detectores foram ajustados olhando esses casos; numa prova com programas que
não entraram no ajuste (o exemplo no L04, L06 e L07, o seguidor PD no L02 e o liga-desliga do curso no
L01), o exemplo no L04 e o PD no L02 saíram sem problema grave, o L06 apontou o LoP que o exemplo leva de
verdade na rampa (1 de 2 rodadas) e o liga-desliga apontou que ele segue reto nas curvas e não para na
chegada.

Coisas que valem saber:

* O simulador perdoa muito: KP 6, KP 0,2, velocidade 90 e até a correção com o sinal trocado ainda
  fazem 130 no L01. Por isso o resumo olha o jeito de andar, não só o placar.
* Os comandos dos motores no registro são os que chegam ao motor (positivo = para a frente). A inversão do
  `direcao_motor()` acontece dentro da lib, no programa, e o simulador não a vê: o "motor com a direção
  trocada" é deduzido pelo movimento (gira no lugar com a linha no meio do sensor e, quando o programa
  manda girar, anda reto de ré).
* As libs leem o sensor de linha numa thread própria, então a velocidade do laço do aluno é medida pelos
  comandos de motor por segundo (um seguidor que funciona manda de 50 a 180).
* A "forma" de cada ladrilho vem só de por onde a linha entra e sai: entrar e sair em lados opostos é
  "reta", mesmo numa onda (L02).
* O obstáculo do simulador é solto (1,5 kg): o robô pode empurrá-lo e passar, e ganha os pontos. O
  resumo avisa quando isso acontece.
