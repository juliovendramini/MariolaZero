# simuladorCasa — guia para o Claude Code

Simulador 2D de uma **casa** para o robô de casa do Julio: o Bombertinho (RCB Challenge) com **uma
pinça na frente e uma câmera na cabeça da garra**, que procura objetos no chão, pega e guarda numa
caixa. Começado em 12/11/2026, antes de o robô ser montado. O objetivo é testar a **localização** e,
depois, o "cérebro" (voz, comandos, Claude com ferramentas ou modelo local) antes de montar.

Leia o `README.md` (como abrir, teclas, formato da casa, robô, câmera, exemplo, o que falta). As regras
gerais do repositório estão no `CLAUDE.md` da pasta de cima.

O projeto mecânico (garra, torre da tela e da caixa de som, berço da bateria) fica fora do repositório,
em `Documents\modelos3D\robotica\roboCasa\` (`garra\garra.py`, `corpo\torre.py`, cada um com `LEIAME.md`).
As medidas da pinça no `robo_casa.json` saíram do `garra.py`: mudou lá, mude aqui e no
`exemplo_casa/robo.py`.

## Origem do código

Cópia do `simuladorChallenge` de 12/11/2026, sem a arena, o juiz da competição, as pilhas, o lote e os
exemplos. **Iguais aos da Challenge** (corrigiu lá, traga para cá, e o contrário): `sim/app.py`,
`sim/firmware.py`, `sim/buzzer_mariola.py`, `sim/painel_brick.py`, `sim/protocolo.py`, `rodar.py`,
`libs_mariola/` e `fake_hw/` (menos `__init__.py`, que aqui instala a câmera, e `camera.py`, que só
existe aqui). Mudou alguma lib em `libs/`? Esta é a quarta cópia de `libs_mariola`.

O que é daqui:

| arquivo | o que faz |
|---|---|
| `sim/casa.py` | a casa (JSON em `casas/`): pisos, faixas, paredes, móveis, objetos, caixa, rótulos. `solidos()` dá as caixas 3D (física, sensores, janela e câmera usam a mesma lista) |
| `sim/fisica.py` | o da Challenge com `Objeto` (prisma com `tam`, altura, `rgb`; estados livre/preso/guardado) no lugar dos cubos e plataformas; paredes e móveis = formas estáticas (`CAT_PAREDE`; móvel com `base` > 0 = `CAT_ALTO`; paredes da caixa = `CAT_PLATAFORMA`, a garra passa por cima quando está alta: `mascara_altura(z0)`); `cena_camera(robo)` monta o que a câmera precisa |
| `sim/garra.py` | `GarraPinca`: braço de paralelogramo, pinça de dois dedos, câmera inclinável; prende quando a abertura do servo chega na largura do objeto e ele está no meio dos dedos, na altura deles; solta quando o servo abre 6 mm além da largura |
| `sim/juiz.py` | conta pegos, guardados e largados no chão; termina com "tudo guardado" |
| `sim/camera_casa.py` | desenha a imagem da câmera: rasterizador com z-buffer em numpy (caixas alinhadas ou giradas no plano), ruído com semente |
| `fake_hw/camera.py` | troca o `cv2.VideoCapture` (dispositivos de `garra.camera.dispositivos`); a imagem é desenhada no processo do programa, o servidor manda só a pose da lente e as caixas que se mexem (ops `casa` e `camera` do `sim/servidor.py`) |
| `sim/gui.py` | janela: casa, móveis, nomes, zoom que segue o robô (Z), imagem da câmera (C), arrastar robô e objetos |
| `exemplo_casa/mapa.py` | mapa **do robô** (roda nele também: só numpy e OpenCV, sem nada de `sim/`): lê o JSON da casa, monta duas grades de 25 mm (`vista` = o que os VL53 veem, sólidos que cruzam 45 mm de altura; folga até o obstáculo mais perto, sólidos abaixo de 255 mm), `raios()` vetorizado, A* numa grade de 50 mm com folga mínima de 200 mm e preferência por 450 mm, `lugar()`/`comodo()`. Repete a lista de sólidos do `sim/casa.py`: mudou o formato da casa lá, mude aqui. O arquivo vem de `CASA_MAPA` (o `simulador.py` e o "Abrir" da janela põem a casa aberta; `--mapa` troca) |
| `exemplo_casa/localiza.py` | `Localizador`: filtro de partículas (300), estado = x, y e a diferença rumo − giroscópio. Pendura-se em `Robo.loc`: todo `Robo.move()` chama `passo()` (odometria; a cada 0,15 s pede os VL53) e todo `Robo.distancias()` chama `mede()`. Informa a pose pelo `simdebug.pose` (no referencial do início) |
| `exemplo_casa/navega.py` | `Navegador`: segue a rota mirando 230 mm à frente, gira parado acima de 50° de erro, detecta "preso" (3 s sem sair do lugar), recua e refaz a rota |
| `exemplo_casa/passeio.py` | teste de localização: visita todos os cômodos e volta |
| `exemplo_casa/arruma.py` | a tarefa inteira com mapa: patrulha os cômodos (`olha_em_volta`: uma volta com a câmera), põe cada mancha de cor no mapa (`Robo.no_chao(u, v)` projeta o pixel no chão pela pose da lente; mancha maior que 110 × 130 mm e até 900 mm é "coisa grande": `Arrumador.anota_grandes` põe no mapa com `Mapa.poe_obstaculos` (as rotas desviam; `folga(..., so_planta=True)` = só a planta) e avisa; o `vigia` da viagem também acha as grandes no caminho e devolve `('grande', x, y)` para refazer a rota; `viaja(pega=False)` só desvia, usado no `ir_para`), `busca` (rota até 45 cm + câmera + `pega` do `main.py`), `leva_para_a_caixa` (rota até 43 cm da parede da caixa + `guarda` do `main.py`), e pega o que aparece no caminho (`Navegador.ao_andar`) |
| `exemplo_casa/cerebro.py` | o cérebro, sem depender do robô nem do simulador: `ferramentas(comodos)` (formato neutro), `texto_sistema()`, `Cerebro.comando(texto)` (laço de ferramentas, até 12 idas ao modelo, registro de tempos e tokens) e os modelos `ModeloClaude` (SDK `anthropic`, `messages.create` com `output_config.effort`, padrão `low`; devolve `response.content` inteiro para a conversa) e `ModeloLocal` (Ollama `/api/chat` por `urllib`, resultado de ferramenta = `{"role": "tool", "tool_name", "content"}`). `CEREBRO`, `CEREBRO_MODELO`, `CEREBRO_URL`, `CEREBRO_ESFORCO`, `CEREBRO_PENSA` |
| `exemplo_casa/habilidades.py` | `Habilidades.executa(nome, args)`: as 7 ferramentas feitas com `Navegador`, `olha_em_volta`, `busca`, `leva_para_a_caixa`, `Arrumador`. Erro = exceção com frase para o modelo |
| `exemplo_casa/conversa.py` | programa do robô: `input('Comando:')` (ou `CASA_COMANDOS="a; b"`), cérebro, resposta. `pensa()` chama o modelo numa thread e manda `r.para()` a cada 0,25 s: sem isso o Mariola solta os motores em 5 s e as placas reiniciam em 12 s (zeram o encoder, a localização pula) |
| `exemplo_casa/testa_cerebro.py` | bateria de 20 comandos numa casa de mentira (`Mundo`), conferidos pelo estado final; `local`, `claude`, `tipo:modelo`, `--so 3,7`, `--mostra`; grava `resultados/cerebro_<modelo>.json` |
| `ferramentas/espalha_objetos.py` | põe a caixa (`--caixa x,y`) e N prismas em cômodos, visíveis do ponto do cômodo e alcançáveis (`--semente`, `--comodos`) |
| `ferramentas/bagunca_casa.py` | cópia de uma casa com móveis tirados, deslocados e coisas fora do mapa (longe das rotas do passeio), para testar com `--mapa` |
| `ferramentas/planta_dxf.py` | planta DXF → casa JSON (camadas `PAREDE`, `ESQUADRIA`, `LAY OUT`; `--nomes "bloco=Cômodo"`, `--moveis-dos-blocos`, `--ver img`). Precisa de `ezdxf` (e `matplotlib` para o `--ver`) |

## Teste de referência

```bash
python simulador.py --sem-janela --velocidade 8 --tempo 600
#   casas/casa_exemplo.json, exemplo_casa/main.py, semente 1 (12/11/2026):
#   vermelho pego 0:12.95 e guardado 0:38.78; azul 1:08.15 / 1:38.41; laranja 2:17.90 / 2:53.50;
#   verde 4:13.75 / 5:14.92; amarelo 6:42.58 / 7:33.66; "fim: tudo guardado", 5/5, 0 largados,
#   tempo 453,7 s, pose final x=689 y=2605 ângulo=3399.1°
#   (depois de o robo.py ler os quatro VL53 juntos e parar de zerar os encoders; antes 445,6 s,
#   x=684 y=2610 3039.6°)
python simulador.py --sem-janela --velocidade 4 --tempo 60 --programa exemplo_casa/teste_basico.py
#   liga tudo e imprime motores, servos, giroscópio, VL53 e câmera; com a variável de ambiente
#   CASA_FOTOS=pasta grava as fotos da câmera nela
```

Localização (12/11/2026; `casas/casa_julio.json`, semente 1):

```bash
python simulador.py --casa casas/casa_julio.json --programa exemplo_casa/passeio.py --sem-janela --velocidade 8 --tempo 1800
#   15 de 15 cômodos, 97,1 m, 578,5 s, 2339 medidas dos VL53; pose final x=8641 y=6545 ângulo=357.6°;
#   "localização: erro médio 20 mm (máx 95, no fim 34); rumo médio 0.5° (máx 2.2°); 9320 amostras"
python ferramentas/bagunca_casa.py casas/casa_julio.json casas/casa_julio_baguncada.json
python simulador.py --casa casas/casa_julio_baguncada.json --mapa casas/casa_julio.json --programa exemplo_casa/passeio.py --sem-janela --velocidade 8 --tempo 1800
#   casa diferente do mapa: 15 de 15, erro médio 49 mm (máx 290, no fim 87), rumo 0.7° (máx 2.8°)
# trajeto curto (PowerShell: $env:CASA_ROTA='Quarto 1,Cozinha'), 26 m, ~172 s:
#   normal: 19 mm (máx 56);  com $env:CASA_SEM_VL53='1': 33 mm (máx 115)
#   --ajuste "rodas.diametro=56,rodas.eficiencia_lateral=0.8,giroscopio.deriva_graus_min=3":
#   28 mm (máx 79) com os VL53; 210 mm (máx 620, e crescendo) sem eles
```

A tarefa com mapa (12/11/2026, semente 1; `casa_julio.json` com a caixa em (6400, 6000) e 6 prismas do
`espalha_objetos.py --caixa 6400,6000 --comodos "Sala de estar,Quarto 1,Sala de jantar,Cozinha,Quarto 2,Quarto casal"`):

```bash
python simulador.py --programa exemplo_casa/arruma.py --sem-janela --velocidade 8 --tempo 900
#   casa de exemplo: 5/5, "fim: tudo guardado" em 298,5 s (vermelho 0:11.42/0:34.13 ... amarelo
#   4:26.89/4:58.52), pose final x=418 y=2444 ângulo=91.5°, localização 17 mm (máx 42)
python simulador.py --casa casas/casa_julio.json --programa exemplo_casa/arruma.py --sem-janela --velocidade 8 --tempo 3600
#   casa do Julio: 6/6, "fim: tudo guardado" em 1266,9 s (~15 min de relógio): vermelho 0:27.37/0:50.53,
#   verde (no caminho) 2:05.92/2:52.73, amarelo 4:08.47/5:10.31, azul 13:43.78/14:31.54, laranja (no
#   caminho) 16:29.90/17:26.52, ciano 19:43.50/21:06.94; pose final x=6426 y=6258 ângulo=5667.9°;
#   localização 19 mm (máx 86), rumo 0.5° (máx 2.7°), 16451 amostras
#   (primeira versão, sem olhar o chão ao andar: 5/6, o verde empurrado para perto do robô)
#   13/11, com a camiseta e o caminhão (coisas grandes): 6/6 em 1263,6 s (ciano 19:43.59/21:03.56), as
#   duas grandes achadas e "não foi tocado"; localização 19 mm (máx 103). Tamanho estimado: caminhão
#   23 cm (é 28 × 16), camiseta 66 cm (é 32 × 24; vista de longe e de lado o comprimento sai grande).
#   A casa de exemplo continuou idêntica (5/5, 298,5 s).
```

Os passeios acima foram medidos antes de a casa do Julio ter caixa e prismas (os prismas não estão no
mapa e o robô os empurra): os números mudam um pouco.

O cérebro (12/11/2026; PC do Julio: RTX 5060 Ti 16 GB, Ollama 0.40.6 em `AppData\Local\Programs\Ollama`,
modelos em `C:\IaLocal`; o servidor não sobe sozinho: `ollama serve`):

```bash
python exemplo_casa/testa_cerebro.py local            # qwen3.5:9b: 20/20, 4,3 s até agir, 10,2 s de modelo por comando
#   CEREBRO_PENSA=0: 14/20 (3,0 s);  local:qwen3-coder:30b: 15/20 (3,8 s; não cabe na placa, 24% na CPU)
#   falhas típicas: fazer mais que o pedido (ir + pegar + guardar), não perguntar "qual banheiro?",
#   dizer que foi sem chamar a ferramenta (sem pensar)
# no simulador (PowerShell): $env:CEREBRO='local'; $env:CASA_COMANDOS='oi, onde você está?; vai para o banheiro; o social; tem alguma coisa no chão do quarto 2?; então guarda e volta pra base'
python simulador.py --casa casas/casa_julio.json --programa exemplo_casa/conversa.py --sem-janela --velocidade 4 --tempo 1500
#   pergunta qual banheiro, vai ao social, acha o laranja no quarto 2, guarda (4:46) e volta à base
```

**O Claude não foi rodado**: o PC não tinha `ANTHROPIC_API_KEY` nem o pacote `anthropic` (o Julio
perguntou do custo; a API é cobrada à parte da mensalidade). O `ModeloClaude` foi escrito pela
documentação da skill `claude-api` e conferido só com um cliente de mentira. Quando houver chave:
`python exemplo_casa/testa_cerebro.py claude claude:claude-haiku-5-5`.

Depois ele lembrou do crédito de API do plano Max (US$ 100/mês, a resgatar em claude.ai > Configurações >
Cobrança > API credits; ver o README) e decidiu usar a API. Preparado em 12/11: `anthropic` 2.8.0
instalado (o `messages.create` dele aceita `output_config`); a chave vem de **`CEREBRO_CHAVE_API`**
(`chave_da_api()`: variável de ambiente ou, no Windows, o registro do usuário, para valer logo depois do
`setx`), e não de `ANTHROPIC_API_KEY`, para o Claude Code do PC não trocar o login da mensalidade pela
chave; `PRECO_USD_MTOK` estima o gasto por comando. Ele resgatou o crédito e gravou a chave no mesmo dia.
Nunca peça nem escreva a chave na conversa: é ele quem roda o `setx`.

```bash
python exemplo_casa/testa_cerebro.py claude claude:claude-opus-5-5     # (o padrão agora é o Haiku)
#   sem cache de prompt: Opus 19/20, 1,7 s até agir, ~US$ 0,569;  Haiku 20/20, 1,1 s, ~US$ 0,015
#   com `cache_control={'type': 'ephemeral'}` no create (ficou): Opus 19/20, 1,8 s, ~US$ 0,317
#   (81 mil tokens lidos do cache); Haiku 19/20, 1,1 s, ~US$ 0,009
#   as "falhas" variam de rodada para rodada e são defensáveis: Opus no caso 16 diz que não sabe onde
#   estava antes e pergunta; Haiku no caso 15 pergunta se guarda o verde antes de pegar o vermelho
```

No simulador pela API com o Haiku (os 5 comandos de sempre + "arruma a sala de estar", `--velocidade 4`):
laranja guardado em 2:59.71, vermelho em 4:05.18, 1,0 s em média para decidir, 36 mil tokens de entrada.
Detalhe: depois de arrumar a sala ele disse "estou de volta na base" só porque a base fica na sala (estava
a 30 cm dela): o modelo confunde "estar no cômodo da base" com "estar na base".

**O padrão do `CEREBRO=claude` virou `claude-haiku-5-5`** (12/11): o Julio achou o Opus caro ("nesse
teste já foi quase um dólar": ~US$ 0,89 de Opus contra ~US$ 0,03 de Haiku) e o Haiku acerta o mesmo na
bateria, mais rápido. Não rode baterias no Opus sem ele pedir. Gasto total da API no dia: ~US$ 0,95.

Terceiro caminho, pedido por ele para comparar sem pagar a API: `ModeloAssinatura` (`CEREBRO=assinatura`),
o Claude Code pelo `claude-agent-sdk` 0.2.181 (instalado no Python 3.10 do PC; traz `_bundled\claude.exe`
2.1.323). Um laço asyncio numa thread mantém um `ClaudeSDKClient` aberto; as ferramentas do robô são um
servidor MCP no próprio processo (`sdk.tool` + `create_sdk_mcp_server`), e cada chamada vira um evento
numa fila que o `roda()` devolve ao `Cerebro` (o resultado volta pelo `Future`). Opções: `tools=[]`,
`system_prompt` próprio, `setting_sources=[]`, `strict_mcp_config=True`, `permission_mode='dontAsk'`,
`cwd` = pasta temporária (para não carregar este CLAUDE.md), `effort` baixo; `ANTHROPIC_API_KEY` sai do
ambiente durante a conexão para não cobrar da API. `limpa()` reabre a sessão. O `total_cost_usd` do
resultado dá a estimativa do que o comando custaria pela API. O login do Claude Code no PC estava vencido
("OAuth session expired"; o app do desktop usa outro login); o Julio rodou `ferramentas\login_claude.bat`
(`claude auth login --claudeai`) em 12/11 e passou a funcionar (plano Max). No simulador a thread do
asyncio sai do relógio sincronizado pelo `simdebug.fora_do_relogio()` (novo, em `fake_hw/sim_modulos.py` e
`robo_real/simdebug.py`).

```bash
python exemplo_casa/testa_cerebro.py assinatura assinatura:haiku
#   modelo padrão da conta = claude-opus-5-5: 20/20, 3,0 s até agir, 6,7 s de modelo por comando,
#   164300/2892 tokens, ~US$ 0,194 pela API (estimativa do Claude Code)
#   haiku = claude-haiku-5-5: 19/20, 1,1 s até agir, 2,4 s por comando, ~US$ 0,007; o caso 15 (pinça
#   ocupada) "falha" porque ele pergunta se guarda o verde antes de pegar o vermelho (defensável)
# no simulador (PowerShell): $env:CEREBRO='assinatura'; $env:CEREBRO_MODELO='haiku'; os mesmos 5 comandos:
#   laranja guardado em 3:02.98, robô na base, 1,2 s em média para decidir
```

Relógio do simulador e o modelo: a chamada ao modelo demora tempo real. Com a thread do modelo presa na
rede e a principal dormindo, o relógio sincronizado fica parado 1 s (`LIVRE_APOS`) e depois anda como
tempo real × velocidade; por isso "o pedido inteiro levou N s do robô" incha em 4x ou 8x. A latência de
verdade é a do `Cerebro.registro` (medida com `datetime`, que o simulador não troca). Não pus a thread em
`espera_externa()`: com outra thread dormindo o coordenador pula direto para o despertar dela e o tempo
dispara (vale também para programa de equipe com thread de sensor parado no `input()`; não mexi no
`cliente.py`, que é o mesmo nos quatro simuladores).

Personalidade (12/11/2026, pedido dele: "mais engraçada, zoeiro, fazer brincadeiras"): `JEITOS['zoeiro']`
no `cerebro.py` (padrão; `CEREBRO_JEITO=serio` tira) e a oitava ferramenta, `gesto` (`GESTOS`;
`Habilidades.f_gesto`, com `r.gira` e `r.garra`; com objeto na pinça ela não abre). O que aprendi afinando:
* exemplos entre aspas nas instruções viram bordão ("sem hora extra", "sindicato" em quase toda resposta):
  ficou a descrição dos tipos de graça e "a graça nasce do momento", sem frases prontas;
* com a graça o modelo inventou fatos (um cômodo "Varanda", "pinça de um dedo só"): as instruções agora
  dizem como o robô é de verdade e que da casa ele só sabe a lista de cômodos e o que as ferramentas
  responderam;
* o Haiku em `effort` baixo fica sem graça; em `medium` (o padrão agora, `CEREBRO_ESFORCO`) usa os gestos
  e acerta mais o tom, com o mesmo tempo (1,2 s até agir) e custo (~US$ 0,0007 por comando). O Sonnet 5.5
  é mais engraçado (~US$ 0,013 por comando, 19x). O Julio ainda não disse se o tom está bom: é gosto dele.
Bateria com o jeito zoeiro: Haiku 19/20 e 20/20 nas duas primeiras versões das instruções; na versão final
só rodei 6 casos (6/6, Haiku e Sonnet, `effort` medium). O caso 18 passou a ser conferido pelo que
aconteceu (não tentou pegar nada), não pelas palavras da resposta. Gasto do dia com isso: ~US$ 0,15.

Voz (12/11/2026): `exemplo_casa/voz.py` (`Boca` = Piper 1.8.0, vozes em `vozes/`, fora do git; `Ouvido` =
faster-whisper 1.2.1, que já estava no PC com `large-v3-turbo`, `large-v3`, `small` e `tiny` em cache;
`chamou()` = a frase começa pelo nome do robô, com tolerância), `testa_voz.py` e o modo `CASA_VOZ` do
`conversa.py` (`fala`, `ouve`, `simulada`; `VOZ_MUDO=1`). Coisas que deram trabalho:
* no Windows o faster-whisper na placa precisa das DLLs do CUDA: `_acha_cuda()` põe `torch/lib` no PATH
  (senão "cublas64_12.dll is not found"), e o erro só aparece na primeira transcrição, por isso o
  `Ouvido.__init__` transcreve meio segundo de silêncio antes de aceitar a placa;
* o tqdm cria threads `TMonitor` que nunca dormem pelo `time.sleep`: no simulador o relógio sincronizado
  passava a andar pelo relógio real o tempo todo, o laço do robô ficava com 20x menos voltas (139 amostras
  de pose em vez de 2700) e ele empurrava o prisma sem ver. `tqdm.tqdm.monitor_interval = 0` no `voz.py`
  e, por garantia, o `conversa.py` tira do relógio as threads que sobrarem (`simdebug.fora_do_relogio(ident)`);
* efeitos de voz "de robô" (modulação em anel, filtro pente, degrau): o Julio ouviu e disse que ficou pior.
  Ficaram no `EFEITOS`, mas o padrão é `nenhum`; `agudo` e `desenho` só sobem o tom (o Piper fala mais
  devagar e o áudio é encolhido). Pesquisa que ele pediu: kits de robô usam Piper como padrão e eSpeak
  como a voz "robótica" clássica; robôs de personagem (Cozmo) usam voz humana com o tom mexido; o Kokoro
  tem vozes pt-BR mais naturais (`pf_dora`, `pm_alex`, `pm_santa`).
  A pedido dele instalei no PC, para comparar de ouvido, `espeakng-loader` 0.2.4 (traz a `espeak-ng.dll` e
  os dados; a síntese é por ctypes: `espeak_Initialize(2, ...)`, `espeak_SetVoiceByName(b'pt-br')`,
  `espeak_SetParameter` 1 = velocidade, 3 = tom, 4 = variação, `espeak_Synth` com callback) e
  `kokoro-onnx` 0.6.1 com `vozes/kokoro/kokoro-v1.0.onnx` (310 MB) e `voices-v1.0.bin`
  (`Kokoro(...).create(texto, voice='pf_dora', lang='pt-br')` → áudio a 24 kHz). Medido no PC, frase de
  ~7 s: eSpeak 0,01 s para gerar (mas o whisper troca "laranja" por "da tanja": pronúncia pior), Piper
  0,1 s, Kokoro 1,6 a 1,8 s na CPU (lento demais para o Banana Pi; teria de rodar no PC). As amostras
  estão em `imagens/vozes/`. Nenhum dos dois entrou no `voz.py`.
  **Escolha dele (12/11): "deixa o cadu_desenho por enquanto"** = `VOZ_PADRAO = 'pt_BR-cadu-medium'` e
  `EFEITO_PADRAO = 'desenho'`. Para mudar a voz, mande amostra antes.
  **A voz tem de ser gerada no PC ou no brick, sem internet** (14/11/2026: "Não rola usar. Tem que ser
  gerada localmente"). A `thalita_robo` foi a padrão só por algumas horas; `VOZ_ROBO_PADRAO` voltou para a
  `cadu_desenho`. Amostras locais com a mesma receita (Kokoro `pf_dora` e Piper cadu/faber, tom mais fino +
  `rouco` + metal) em `resultados/vozes_locais/`, esperando a escolha dele. Kokoro na CPU: ~2 s para 7 s de
  fala; Piper: ~0,5 s.
  Amostra 30 (escolha dele antes de saber da internet): ele viu o robô Titã (@tit.bott no Instagram, feito com o
  Xiaozhi) e quis uma voz parecida. É a `thalita_robo` de `VOZES_ROBO` no `voz.py`:
  `pt-BR-ThalitaMultilingualNeural` do **edge-tts** (`pip install edge-tts`, 7.3.1; precisa de internet), tom
  `+26Hz` (meio tom abaixo da "fina" de +40 Hz), velocidade `+8%`, `rouco(2.0, 0.12, 0.15)` (rouquidão
  leve: tanh, chiado de ar, tremor de 30-80 Hz) e o metal `(60, 0.25, 5, 0.45, 0)` do `aplica_efeito`
  (zumbido leve + eco curto). Ele pediu cada passo: Thalita fina → com metal → meio tom abaixo → rouca.
  `boca_do_robo()` (usada pelo `conversa.py`, `servidor_voz.py` e `testa_voz.py`) escolhe por `VOZ_ROBO`;
  `BocaEdge` guarda as últimas 200 falas e, sem internet, fala com a `cadu_desenho` (tenta a internet de
  novo a cada 60 s). Preço: a internet leva 1,1 a 3 s por fala (o Piper levava 0,1 s); repetida sai na hora.
  O brick continua com o Piper de reserva (`voz_brick.py`). Amostras em `resultados/vozes_edge/` (fora do git).
  Nos testes, a voz que faz o papel da pessoa usa `efeito='nenhum'` (`testa_voz.py`, `CASA_VOZ=simulada`).
Teste: `python exemplo_casa/testa_voz.py` = 16/16 nas duas vozes, 0,1 s para falar e 0,21 s para ouvir por
frase; com `--ruido 10` ou `3` a faber erra uma. No simulador com `CASA_VOZ=simulada`, `VOZ_MUDO=1` e o
Haiku: laranja guardado em 3:12.38, 2705 amostras de pose. **O microfone de verdade não foi testado**
(`grava_frase` nunca rodou com som real); eu não ouço os áudios, quem julga a voz é o Julio.
O corte da frase foi conferido com um microfone de mentira (fala do Piper com silêncio e ruído em volta):
com ruído forte o começo era cortado e o nome do robô se perdia; ficou limite = 2,2x o ruído ambiente e
0,75 s guardados antes do primeiro som. O PC tem entrada "Microfone (High Definition Audio)" e saída
"Alto-falantes".
**Primeiro teste com o microfone de verdade (12/11, o Julio falando no PC,
`testa_voz.py --microfone 5`): 5 de 5 frases entendidas, todas reconhecidas como sendo com o robô,
0,27 a 0,39 s para entender cada uma (3 a 5 s de áudio), ruído ambiente 0,0009 a 0,0017 (o limite ficou no
piso de 0,012).** Ele falou frases de conversa ("Bombertinho, cadê você? Eu não te acho de jeito nenhum.").
Não sei a que distância do microfone, e foi num ambiente silencioso. O modo `CASA_VOZ=ouve` dentro do
simulador (microfone + relógio do simulador) ainda não rodou.

Ouvir durante a tarefa (12/11/2026, pedido dele: mandou o robô à sala, desistiu no meio e ele não ouviu):
* `voz.Escuta`: thread com o microfone sempre aberto (`Ouvido._captura`, ruído ambiente acompanhado
  devagar), cada frase transcrita vai para `escuta.fila`; `escuta.surdo` enquanto o robô fala; sai do
  relógio do simulador pelo `simdebug.fora_do_relogio()`.
* `robo.Interrompido` e `Robo.interrompe`: cada `move()` consulta a função; se ela devolve uma fala, zera
  os motores e levanta a exceção, que desmonta o que estiver rodando (navegação, procura, pegar, guardar).
* `Habilidades.executa` liga o `interrompe` só durante a ferramenta (o `r.para()` de quando o modelo pensa
  não interrompe nada) e, na exceção, `_interrompido()` deixa tudo num estado conhecido: se estava levando
  um objeto (`Arrumador.carregando`), continua com ele; se estava pegando, abre, levanta e fecha. O
  resultado da ferramenta é "INTERROMPIDO: no meio disso a pessoa falou: ...", e as instruções do cérebro
  dizem o que fazer com isso.
* `conversa.py`: `para_mim()` decide se a frase é com o robô (nome; ou resposta a uma pergunta dele; ou,
  no meio de uma tarefa, até 4 palavras começando por para/pare/espera/chega/calma/stop).
* Teste sem microfone: `CASA_VOZ=simulada` e `CASA_COMANDOS='Bombertinho, vai para a garagem >>10>>
  Bombertinho, esquece, vai pra cozinha; ...'` (a fala depois do `>>10>>` é dita 10 s de robô depois de a
  tarefa começar). Resultado (Haiku, `--velocidade 4`): trocou a garagem pela cozinha; parou com "para,
  para!"; interrompido com um prisma verde na pinça respondeu onde estava e perguntou se continuava, e no
  "sim, pode continuar" guardou o verde e arrumou a sala (vermelho guardado em 3:53.57).
* Bateria: 3 casos novos de interrupção (20 a 22), 22/23 no Haiku (a de sempre, caso 15).
* **Não testado com microfone de verdade** (a thread `Escuta` nunca rodou com som real) nem com o barulho
  dos motores, que o simulador não imita. Nesse teste o processo do programa saiu com o código
  3221226505 (0xC0000409) depois de imprimir "fim": algo das bibliotecas nativas na hora de fechar; não
  investigado.

Falar pouco (12/11/2026, depois de ele conversar com o robô por voz: "ele está falando demais. Distância
de onde está, e coisas assim. Não precisa falar também que pegou 'na pinça', ele só tem a pinça pra
pegar"): parágrafo "Fale pouco" nas instruções (uma frase, duas no máximo; sem distância, margem de erro,
onde fica a caixa, "na pinça"; sem oferecer ajuda no fim) **e** os resultados das ferramentas enxugados
(`Habilidades._segurando`, `f_onde_estou` sem incerteza nem caixa, `f_procurar_objetos` sem distância): o
modelo repete na fala o que lê no resultado. A `Mundo` do `testa_cerebro.py` usa as mesmas frases.

Caderno (12/11/2026, pedido dele: "ir aprendendo igual o bot da smartirriga"; não vi o código desse bot,
fiz como expliquei a ele): `memoria.py` (`Memoria`: notas numeradas e lugares marcados, JSON em
`memoria/caderno.json`, fora do git, ou `CEREBRO_MEMORIA`), ferramentas `aprender`, `esquecer` e
`marcar_lugar`, e o trecho "Seu caderno" do `texto_sistema(..., caderno=Memoria.texto())`.
* **As instruções e as ferramentas não podem mudar no meio da conversa com a API do Claude**: o raciocínio
  guardado no histórico fica amarrado a elas (400 "Invalid signature in thinking block ... bound to a
  different conversation"). Por isso o caderno entra nas instruções só no começo da conversa (o que ele
  aprende no meio já está no histórico), e o destino do `ir_para` deixou de ser `enum` (lugar marcado no
  meio da conversa tem de valer; quem confere o nome é o `Habilidades._lugar`). `Cerebro.atualiza()`
  troca tudo, mas começa conversa nova.
* Bateria: 30 casos (7 de caderno: aprender, usar, não anotar pedido comum, obedecer regra, esquecer,
  marcar lugar e voltar, jeito de falar). Haiku: 29/30 (caso 15), ~US$ 0,024, 1,2 s até agir.
* Simulador, duas conversas seguidas com `CEREBRO_MEMORIA` num arquivo de teste: aprendeu "o quarto do
  Miguel é o Quarto 1", foi lá, marcou "cantinho da bagunça", anotou "me chama de chefe" (e passou a
  chamar); no programa seguinte contou o que sabia, foi ao lugar marcado e apagou a nota do chefe.
* Não feito: quem pode ensinar (hoje qualquer um), faxina do caderno, notas por pessoa. Ele perguntou em
  seguida se dá para reconhecer quem fala (voz) e depois por foto: respondi que sim (ver a conversa);
  no PC há o modelo `speechbrain/spkrec-ecapa-voxceleb` em cache mas não o pacote `speechbrain`, e o
  OpenCV 5.0 tem `FaceDetectorYN`/`FaceRecognizerSF` (faltam os dois arquivos de modelo). Nada disso feito.

Quem está falando (12/11/2026, pedido dele; `speechbrain` 1.1.2 instalado, o modelo
`spkrec-ecapa-voxceleb` já estava no cache do HuggingFace e é copiado para `vozes/ecapa/`):
* `voz.Quem`: assinatura de 192 números por frase (15 a 28 ms na placa), pessoas em `memoria/vozes.json`
  (`VOZ_PESSOAS`), `apresenta`/`esquece`/`quem`/`notas`; decide pela semelhança com a média das amostras:
  `LIMITE` 0,45 e `FOLGA` 0,07 sobre a segunda colocada; menos de 1 s de fala = não diz nada.
  `LocalStrategy.COPY` (no Windows o atalho precisa de permissão) e dispositivo `cuda:0` (com `cuda` ele
  reclama). `voz.Fala` = uma `str` com `.quem`, `.certeza`, `.audio`, `.palpite`, `.curta`; a `Escuta` põe
  `Fala` na fila.
* Cérebro: etiqueta `[quem falou: ...]` na frente do pedido (`conversa.etiqueta`; "provavelmente X" só se
  X falou há menos de 25 s **e** a fala é curta demais ou a mais parecida é X), parágrafo "Quem está
  falando" nas instruções, ferramentas `aprender_voz` (grava a fala atual e as duas seguintes:
  `Habilidades.ouviu` + `reforco`) e `esquecer_voz`. `aprender_voz` recusa gravar com outro nome uma voz
  que já reconhece (sem isso a mesma voz virava duas pessoas e ninguém mais era reconhecido).
* Testes: `testa_voz.py --quem` com 6 vozes de máquina (faber, cadu, faber grave e 3 do Kokoro): 53/60
  certas, 7 "não sei", 0 trocas; visita confundida em 9/60 (8 delas dora x alex, do mesmo sintetizador).
  Bateria: 4 casos de voz (34 no total). Simulador (`CASA_VOZ=simulada`, falas `@faber:`, `@cadu:`,
  `@grave:`): apresentou "Júlio" e "Ana", tratou cada um pelo recado do caderno, recusou "eu sou a Ana" na
  voz do Júlio, atendeu a voz desconhecida sem nome.
* O Kokoro não carrega dentro do simulador (`'_TravaVigiadaR' object has no attribute
  '_recursion_count'`: as travas vigiadas do `fake_hw/cliente.py`); `vozes_de_teste()` deixa ele de fora
  quando `SIM_PORTA` existe.
* O Julio testou com a voz dele em 12/11 ("deu certo, ele reconheceu e aprendeu com meus pedidos"):
  `memoria/vozes.json` ficou com "Júlio", 3 amostras. Não vi as notas de semelhança (o terminal estava
  vazio), então o limite 0,45 continua o das vozes de máquina; ninguém mais da casa falou.
* Ele ensinou ao robô "não precisa dizer Bombertinho em toda frase", e o robô anotou sem poder cumprir
  (quem filtra as falas é o `conversa.py`, antes do cérebro). Feito de verdade em seguida:
  `JANELA_CONVERSA_S` = 40 s depois de responder a uma pessoa reconhecida (`conversa_com`), as falas da
  mesma voz entram sem o nome, com a etiqueta "[sem chamar pelo nome]"; o cérebro responde `SILENCIO`
  quando não é com ele, e o programa não fala nada. Só fora de tarefa: no meio de uma tarefa a regra de
  interrupção não mudou. Quem acabou de se apresentar (`hab.reforco`) já conta como reconhecido. As
  instruções do caderno agora dizem o que uma nota não muda (quando ele escuta, velocidade, volume, voz).
  Bateria: 38 casos, 37 certos no Haiku (~US$ 0,034). Simulador com vozes de máquina: continuou sem o
  nome, calou em "mãe, o almoço já está pronto", ignorou outra voz sem o nome.
* O limite 0,45 saiu de vozes de máquina. Ele perguntou
  também de reconhecer pela foto do rosto: não feito (o OpenCV 5.0 do PC tem `FaceDetectorYN` e
  `FaceRecognizerSF`, faltam os dois arquivos de modelo; o simulador não desenha gente).

Carinhas (12/11/2026, pedido dele: "vamos desenhar as carinhas!!", para a tela SSD1309 de 128 x 64 do
rosto): `exemplo_casa/rosto.py`, primeira versão. 28 expressões desenhadas por código com o Pillow
(`CARINHAS`, `quadro(nome, t)` devolve imagem 128 x 64 modo '1'; olhos de cantos redondos no estilo dos
robôs de brinquedo, pálpebras, boca e enfeites; algumas mudam com `t`: piscar, lágrima, Zzz, boca
falando, olhos procurando). `python exemplo_casa/rosto.py folha.png` grava a folha de todas
(`imagens/carinhas_v1.png`, enviada a ele). Ele aprovou o estilo ("Ficou bom. Era isso mesmo").
Ligado no mesmo dia:
* `rosto.Rosto`: três camadas (`momento` por alguns segundos > `estado` enquanto a tarefa dura > `humor`,
  que volta a neutro em 25 s; sonolento/dormindo com 60/180 s parado), `fala(True)` põe a boca que mexe
  por cima de qualquer carinha, `passo()` no máximo 8 quadros por segundo e só manda a imagem se mudou.
  Sem thread: `Robo.move()` chama `rosto.passo()` (como a localização), e o `pensa()` do `conversa.py`
  bate a cada 0,12 s.
* Tela: **a do próprio brick** (13/11, decisão dele: "a ideia é usar a tela do próprio brick, vou trocar
  a pequena por essa aí" = sai a SSD1306 de 0,96", entra a SSD1309 de 2,42" no mesmo conector TELA).
  `rosto.abre_tela()` = `luma.oled.device.ssd1309(i2c(port=0, address=0x3C))`, igual no robô e no
  simulador, onde o `fake_luma.py` (cópia sem mudança; `ssd1309` já era apelido do `ssd1306`) mostra no
  painel "brick: tela + teclado" (tecla O). A caixa separada "rosto do robô" da primeira versão
  (`simdebug.rosto`, `gui._desenha_rosto`, `debug['rosto']`) foi tirada. **Nunca testado numa tela de
  verdade.** Para quando ele trocar a tela: `libs/tela.py` e o menu do brick abrem a tela como `ssd1306`;
  os dois controladores são quase iguais, mas se a imagem sair errada na de 2,42" (contraste, linhas
  deslocadas) é ali que se troca para `ssd1309`, e só com ele pedindo (`libs/`). O rosto e a `Tela` da
  `tela.py` não podem ser usados juntos (a mesma tela).
* Quem escolhe: `Habilidades.executa` (`CARA_DA_TAREFA`, `CARA_DO_SUCESSO`, triste no erro, surpreso na
  interrupção), os gestos (`CARA_DO_GESTO`) e o cérebro. **A carinha do cérebro vem no começo da resposta,
  entre parênteses** ("(feliz) Cheguei na Cozinha."): `Cerebro.comando` tira da fala e põe em
  `registro[-1]['carinha']`. Tentei antes como ferramenta (`carinha`), mas o Haiku quase não chamava e
  cada chamada é mais uma ida ao modelo; no começo da resposta ele usa sempre e não custa nada. A lista
  `HUMORES` está repetida no `cerebro.py` (para ele não depender do Pillow) e no `rosto.py`.
* Bateria: 39 casos, 38 certos no Haiku (~US$ 0,037), todas as respostas com carinha coerente.

Esperando: a tela de 2,42" no brick para testar de verdade; carinhas a mais que ele queira.

Visão (13/11/2026, conversa, nada feito ainda): o Julio quer que o robô junte tudo do chão e, "talvez",
separe roupa de brinquedo. Plano que propus: uma rede pequena só (roupa / brinquedo / "deixa" = o que não
se pega: fio, chinelo, pé de móvel), treinada no PC com fotos da câmera do próprio robô na casa, marcadas
com ajuda de um modelo grande, e rodando no Banana Pi se der uns quadros por segundo (não medido). As
**duas caixas** (cesto de roupa e caixa de brinquedo) ficaram **para depois**, decisão dele. A garra pega
até 8 cm / 50 g: roupa grande (camiseta, toalha) não.

Primeiro teste no brick (13/11/2026, pedido dele: "vamos partir pros modelos de IA na câmera"; num
Mariola sem o robô, com uma webcam UC60 com microfone, sem caixa de som): `teste_brick/` (`LEIAME.md`
com tudo). Brick `192.168.2.110`, tudo em `~/robo_casa/` (pacotes da voz por `pip --target`, porque o
`/meu_venv` fica na raiz somente leitura). YOLO11n ncnn 320 px = ~5 quadros/s com a captura; Piper 0,8 s
por segundo de fala; Whisper tiny/base no brick 2,5-4 vezes mais lento que a fala (ouvir fica no PC).
Exportar o YOLO no brick dá "instrução ilegal": exportar no PC.
O microfone da webcam é de 8 bits (U8 estéreo, estalo de ~1 s ao ligar, nível de fundo que muda):
`voz.le_wav()` prepara (tira a média de cada 50 ms; a de 10 ms soava pior e perdia palavras). O
Whisper escrevia "Humberto" no lugar do nome: a dica do `Ouvido` virou "Bombertinho, vai para a
cozinha. Bombertinho, me ajuda." + cômodos, com `hotwords`. Divisão decidida com o Julio: o PC ouve
e fala (`servidor_voz.py`, só em 127.0.0.1, o brick chega por `ssh -R`, porque a rede do PC é
"Pública" no Windows e o firewall barra o brick; mexer no firewall é com ele), o brick roda o robô
(`voz_brick.py`: `Microfone` com arecord, `VozRemota`, `AltoFalante` com Piper local de reserva).
Primeiro teste: 1,5 s do fim da fala até a resposta pronta. Detalhes: `teste_brick/LEIAME.md`.
Contra as invenções do Whisper num barulho ("Obrigado.", "Bombertinho."): `Ouvido.MIN_FALA_S` = 0,8 s
(fala medida pelo filtro de voz). Rosto na tela de verdade (13/11, SSD1309 2,42" no brick): funciona
como `ssd1309`, 101 ms por quadro (I2C a 100 kHz), desfile das 28 carinhas ok (`teste_brick/testa_rosto.py`;
o teste pausa o menu do brick com `kill -STOP`/`-CONT`, o `sudo` pede senha). `ROSTO_GIRA` gira a tela.

Coisas grandes (13/11/2026, ele: "a ideia de avisar que tem coisas grandes é legal"): o robô deixa no
chão, marca no mapa, desvia e avisa. `arruma.objetos_na_imagem(..., grandes=True)` (meio e tamanho pela
borda de baixo e a de cima da mancha; `inteira` = não encosta na borda da imagem), `olha_em_volta(...,
grandes=lista)`, `Arrumador.grandes`/`grandes_novos`/`anota_grandes(vistas, olhou_de)` (a que não é vista de
novo de perto sai do mapa), `Mapa.poe_obstaculos([(x, y, raio)])` + `folga(so_planta=)`. Habilidades:
`_grandes()` acrescenta "Também tem no chão uma coisa azul grande demais para eu pegar" ao resultado de
`procurar_objetos` (as desta olhada), `arrumar` (as dos cômodos olhados) e `ir_para` (as novas do
caminho; o `ir_para` agora viaja pelo `Arrumador.viaja(pega=False)`); `pegar_objeto(cor)` de uma grande
dá erro "grande demais". `cerebro.py`: parágrafo para contar a cor e o cômodo e não dizer que é roupa ou
brinquedo (ele só sabe a cor). Simulador: `Objeto.grande` (lado > `GRANDE_MM` = 110 ou `"grande"` no
JSON) não conta no placar nem no "tudo guardado"; o resultado sem janela lista as grandes e se foram
empurradas. `casa_julio.json` ganhou a camiseta azul e o caminhão laranja (9500, 7300). Passagem
fechada: na primeira rodada a camiseta estava em (6650, 16150), na passagem para o quarto do casal, e o
robô não chegou nele, no closet nem no banheiro do casal (5/6). Isso é o certo (ele não pode passar por
cima), mas ele só dizia "não cheguei": agora `Mapa.fechado_por_obstaculo(de, ate)` (rota com e sem os
obstáculos) separa esse caso, o `Arrumador._sem_caminho` avisa "uma coisa grande no chão fecha a
passagem" e guarda em `Arrumador.fechados`, e o `arrumar`/`ir_para` dizem isso ao cérebro. A camiseta foi
para (6100, 18800), um canto do quarto que não fecha nada. Bateria: casos 40-43, 4/4 no Haiku (~US$ 0,004).

A janela aceita texto no `input()` do programa (`sim/gui.py`: `TEXTINPUT`, faixa amarela, Enter envia);
com o `input()` esperando, as teclas de atalho (menos F1-F12) viram texto.

O erro é medido pelo simulador: `sim/servidor.py` (`_debug`) compara cada `simdebug.pose` com a pose
real e acumula em `robo.debug['erro']` (painel da janela, resultado sem janela e o JSON do `--resultado`).

O simulador é bondoso com a odometria (sem os VL53 o erro é de só 33 mm em 26 m): para testar a
localização de verdade use o `--ajuste` e a casa bagunçada.

No Git Bash, comando com acento num heredoc falha: escreva o script num arquivo e rode pelo PowerShell
(ou use a ferramenta de edição). Já errei isso três vezes nesta pasta.

## Coisas que já deram errado

* O exemplo procurava objetos com um ainda na garra quando não conseguia chegar à caixa: via o próprio
  prisma (ele aparece embaixo na imagem), abria a pinça para "pegar" e o largava. Agora
  `leva_para_a_caixa()` só devolve com o objeto guardado ou desiste e o põe no chão.
* `arruma.py`, primeira versão: o robô empurrou um prisma ao chegar no cômodo e ele ficou a 11 cm do
  meio do robô, onde a câmera não vê (o chão só aparece a partir de ~34 cm do centro, com as barras na
  horizontal e a câmera 15° para baixo). Agora ele olha o chão à frente enquanto anda e recua 25 cm
  antes de girar. O resultado sem janela lista o que ficou no chão e onde ("ficou: ...").
* A madeira da mesa de centro (saturação 136) era vista como objeto: `SAT_MIN` = 145. Móvel de cor viva
  vira objeto para esse filtro; é limitação do exemplo, não do simulador.
* `planta_dxf.py`: o agrupamento das paredes tem de usar a distância entre segmentos (não entre pontos
  médios), e o maior grupo serve só para achar o recorte da planta; entra tudo o que está dentro dele
  (senão sobram só os muros do terreno, ou entra o desenho de detalhe ao lado).
* Normal das faces laterais no `camera_casa.py` com o sinal trocado (faces de trás desenhadas).

## Pendências

* A planta do Julio (`casas/casa_julio.json`) está como saiu do DXF: esquadrias como parede, nomes
  "z" = Cozinha e "al" = Área de lazer por palpite, móveis do projeto (ele avisou que alguns mudaram),
  um piso só. A caixa e os prismas são de teste, postos por mim (o `planta_dxf.py` os mantém ao refazer). A cópia do DXF está em `modelos3D\robotica\roboCasa\planta\`.
* Localização: feita a primeira versão (acima). Faltam: achar-se sem saber de onde saiu (hoje só
  acompanha a partir do `inicio`), desviar do que não está no mapa, usar a câmera (marcas nas paredes)
  nos cômodos grandes, onde os VL53 de 1,2 m não veem nada. Não testado no robô (ele não existe ainda):
  `EFICIENCIA_LATERAL`, `VL53_POSE` e `OFFSET_VL53` no `exemplo_casa/robo.py` são do `robo_casa.json`.
* `arruma.py`: acha objeto só por cor viva + tamanho; carregando um objeto, empurra o que estiver no
  caminho; a caixa tem de estar onde o mapa diz; áreas grandes ficam com cantos sem olhar (vê um prisma
  de 4 cm até ~2,5 m). Não testado na casa bagunçada.
* Cérebro: a conversa cresce sem limite (sem resumo); uma
  ordem nova não interrompe a ação em curso ("para!"); a bateria não tem ferramentas que falham por
  acaso; `ir_para` não pega o que está no caminho (desvia das coisas grandes, empurra as pequenas). Voz (ouvir e falar): nada ainda.
* `Simulador.bat` procura `portatil\python`, mas o pacote portátil ainda não existe para este simulador.
