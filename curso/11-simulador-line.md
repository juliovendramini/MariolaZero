# Módulo 11 — O simulador da Rescue Line

**Objetivo:** usar o simulador como ferramenta de desenvolvimento: rodar o seu programa, entender o
painel, criar mapas no editor, ler o placar do juiz, repetir testes com a mesma semente e testar
dezenas de rodadas sem janela.

Documentação completa: `simuladorLine/README.md`.

## 11.1 O que ele é (e o que não é)

O simulador roda **o seu `main.py` sem mudar nada**, com as **bibliotecas reais** do Mariola. Ele
troca só a camada de baixo (serial, I2C, pinos, relógio) por placas virtuais que respondem os
mesmos bytes que o firmware de verdade. Por isso:

* o que funciona nele usa as mesmas chamadas que vão funcionar no robô;
* os comportamentos "chatos" do hardware estão lá: timeout de 5 s, encoder ×2 e ×4, leitura velha
  do VL53, TCS atrás do IR, trava dos servos, câmera que erra.

Ele **não** substitui o robô: atrito, luz, bateria e mecânica reais sempre diferem um pouco. Use
para desenvolver a **lógica** e chegar ao robô com algo que já funciona.

## 11.2 Rodando

Na pasta `simuladorLine`:

```bash
python simulador.py                                        # robô 4x4, mapa de treino, programa de exemplo
python simulador.py --programa ../meuSeguidor/main.py      # o SEU programa
python simulador.py --robo robo_esteira.json               # robô de esteira
python simulador.py --mapa mapas/completo.json             # rampas, ponte, gangorra, obstáculo
python simulador.py --mapa mapas/resgate.json              # linha + área de resgate
python simulador.py --editor                               # abre no editor de mapas
```

| Opção | Para quê |
|---|---|
| `--programa CAMINHO/main.py` | o programa que vai rodar no robô virtual |
| `--robo arquivo.json` | qual robô (medidas, sensores, motores) |
| `--mapa arquivo.json` | qual pista |
| `--sem-janela` | roda uma rodada sem interface e imprime o placar |
| `--velocidade 4` | até 4x mais rápido (o resultado é o mesmo, veja 11.6) |
| `--semente N` | o "sorteio" do ruído e das vítimas; mesma semente = mesma rodada |
| `--tempo 480` | duração máxima da rodada (s) |
| `--lop reiniciar` / `botao` | no LoP, reinicia o programa ou só aperta o botão |

## 11.3 A janela

| Botão / tecla | Faz |
|---|---|
| **▶ Iniciar rodada** (F5) | zera tudo, põe o robô no início, inicia o programa e o relógio de 8 min |
| **■ Parar** | manda `Ctrl+C` (`KeyboardInterrupt`) para o programa |
| **↺ Nova rodada** | volta tudo ao início |
| **LoP** (L) | falta de progresso: volta ao último checkpoint |
| **Botão do robô** (B) / **Auto-botão** | aperta o botão de início (P3) / aperta sozinho 1,5 s após o programa subir |
| **Robô** | troca entre os `robo_*.json` |
| **Caminho** (P) | mostra o número de cada passo do caminho |
| **Pausar** (espaço), **Vel.** (1–5) | pausa / velocidade de 0,25x a 4x |
| arrastar, Q/E, roda do mouse | reposiciona o robô (programa parado) |
| R, T | raios dos VL53, trilha |
| F1–F4, clique nos botões do painel | botões do teclado do brick (Voltar, Baixo, Cima, Enter) |
| O | mostra/esconde a **tela e o teclado do brick** (canto de baixo à direita do mapa) |

O **painel** mostra: tempo, placar, eventos do juiz, os 4 canais IR, os 12 ITR8307 um a um, a cor
de cada TCS, giroscópio, encoders, VL53, para-choque, e (no 4x4) servos, garra, caçamba e o que a
câmera viu. Embaixo, o **console** com os `print` do programa.

No canto de baixo à direita do mapa fica a **frente do brick**: a tela OLED (o que a `tela.py`
desenha), os 4 LEDs do teclado com as cores de verdade e os 4 botões, que você aperta com o mouse.
Assim dá para testar no simulador o menu e a calibração que o robô vai usar no campo.

## 11.4 Ver o que o programa "pensa": `simdebug`

```python
try:
    import simdebug          # no robô, copie robo_real/simdebug.py (não faz nada)
except ImportError:
    simdebug = None

if simdebug:
    simdebug.texto('estado: GAP')                 # aparece no painel
    simdebug.pose(x_mm, y_mm, theta)              # contorno roxo onde você acha que está
    simdebug.marca(x_mm, y_mm, 'verde')           # um ponto no mapa
```

Mostrar o **estado** do programa (`seguindo`, `verde à esquerda`, `gap`, `obstáculo`...) é a forma
mais rápida de achar o porquê de um erro.

## 11.5 O juiz (regra 2026)

O simulador pontua como o árbitro:

* **Perigos** (uma vez por sentido em que o caminho passa): interseção/beco 10, gap 10, obstáculo
  20, lombada 10, rampa 10, gangorra 20.
* **Checkpoint:** ladrilhos desde o anterior × 5 / 3 / 1 / 0 (1ª a 4ª tentativa).
* **Chegada:** parado mais de 5 s na fita vermelha; bônus de saída 60 − 5 × LoP.
* **LoP automático:** robô sai do campo/cai, pega uma linha que não é a próxima do caminho, fica
  10 s fora do caminho. Depois de 3 tentativas, vai para o próximo checkpoint.
* **Área de resgate:** vivas no verde e a morta no vermelho (só depois das duas vivas), ×1,4 cada,
  perdendo 0,05 por LoP no trecho, nunca abaixo de 1,25.

No fim, o placar item por item:
```
0:46.48   +35  checkpoint: 7 ladrilhos x 5 (1ª tentativa)
0:54.90    +5  chegada: 1 ladrilhos x 5 (1ª tentativa)
0:54.90   +60  bônus de saída (60 - 5 x 0 LoP)
          TOTAL: 130   {'LoP': 0, 'passo': '14/14'}
```

O modo **LoP: reinicia prog.** desliga e liga o programa num LoP, como desligar o robô. Isso testa
se o seu programa **retoma** certo (checkpoint em arquivo, relógio da rodada).

## 11.6 Repetir e comparar: semente e relógio sincronizado

* **Semente:** com `--semente N` (padrão 1), o ruído dos sensores e o sorteio das vítimas são
  sempre os mesmos. A rodada sai **igual, bit a bit**. Mudou o programa e piorou? Foi o programa,
  não a sorte.
* **Relógio sincronizado:** o tempo do programa só anda quando ele **espera** (`sleep`, serial). O
  tempo que o PC gasta calculando não conta, então o resultado não depende da velocidade nem do
  computador. **Consequência:** um laço sem nenhum `sleep` "congela" o tempo. Ponha
  `time.sleep(0.01)` no laço principal (no robô ele também ajuda).

### Testando várias rodadas de uma vez: `avalia.py`

Um programa bom completa a pista com **várias** sementes, não com uma. O `avalia.py`, na mesma
pasta, roda o programa nas sementes que você pedir (sem janela, em paralelo) e resume:

```bash
python avalia.py --programa ../meuSeguidor/main.py --mapa mapas/completo.json --sementes 1-3
```
```
  sem.  total  LoP  passo   chegou  vítim.   tempo  mapa                      fim
     1    295    0   25/25     sim     -      73.1  completo.json             robô parou na chegada
     2    295    0   25/25     sim     -      73.3  completo.json             robô parou na chegada
     3    278    1   25/25     sim     -      81.3  completo.json             robô parou na chegada

  média 289.3   pior 278   melhor 295   desvio 8.0   LoPs 1   (110 s)
```

Ele também confere as metas da **trilha de desafios** (`--desafio L04`) e sorteia **pistas
surpresa** (`--surpresa medio`). Tudo isso está no [módulo 18](18-desafios.md).

## 11.7 O editor de mapas

`python simulador.py --editor` (ou o botão **Editar mapa**). Usa os **82 ladrilhos oficiais**
(os do sistema do rcj.cloud), com caminhos, gaps e interseções.

| Ferramenta | Uso |
|---|---|
| **Ladrilho** | escolha na paleta e clique; clicar de novo gira; R/roda giram o da paleta; botão direito apaga |
| **Girar** | clique gira 90° |
| **Início** | marca o ladrilho de início (clique de novo troca a direção) |
| **Checkpoint** | marca/desmarca |
| **Rampa** | sem → N → L → S → O; botão direito muda a inclinação (10°–25°) |
| **Lombada**, **Obstáculo**, **Detritos** | colocam os perigos |
| **Camada ±** | ladrilho de ponte (camada 1 sobre a 0) |
| **Área resgate**, **Entrada/saída**, **Triângulos** | montam a área de resgate |

O editor calcula o **caminho esperado** (o mesmo algoritmo do sistema oficial), numera os passos e
avisa os problemas (caminho que não chega na chegada, checkpoint em ladrilho com item...). O
**Abrir** também lê mapas exportados do rcj.cloud.

**Dica de treino:** monte mapas pequenos com **um desafio só** (só interseções verdes, só gaps,
só obstáculo) e use-os como "testes unitários" do seu programa. O `curso_pista.json` deste curso
é um exemplo: só curvas.

## 11.8 Os robôs: `robo_4x4.json` e `robo_esteira.json`

O arquivo do robô diz **onde está cada coisa**: medidas, motores e em que porta/ID, sensor de linha
(posição dos ITR e TCS, altura), giroscópio (sentido, deriva), VL53 (canal, posição, ângulo,
altura), para-choque, TCS horizontais, câmera, mecanismo de resgate. **Os valores que vieram são
estimativas**: o módulo 17 mostra como medir o seu robô e ajustar o arquivo.

## 11.9 Limitações

* Mundo 2,5D: o robô não capota; lombadas levantam, mas não fazem quicar.
* A câmera não gera imagem (stub).
* O BNO085 não existe no simulador (a tela OLED e o teclado existem: veja 11.3).
* O barramento serial é "perfeito" (no real pode haver erro de comunicação).
* O VL53 mede na hora em que o resultado é **lido**; no robô a medida é da hora em que foi
  **pedida** (a leitura "velha" do módulo 7 não aparece no simulador).
* O motor é "ideal": com `potencia_motores` ele não perde rotação com a carga (rampa, empurrar
  obstáculo), e com `velocidade_motores` o PID nunca satura. No robô, potência fixa fica mais lenta
  na subida.
* `threading.Event.wait(timeout)` e afins usam o relógio real.

## Exercícios

1. Rode o exemplo com as sementes 1 a 6 no `completo.json`. Anote os totais. Qual semente é a pior?
   Assista essa rodada na janela (`--semente N`) e descubra o que deu errado.
2. Monte no editor um mapa só com 4 interseções de verde e teste o seu seguidor nele.
3. Coloque `simdebug.texto()` mostrando o estado do seu seguidor e acompanhe uma rodada.
4. Rode o mesmo programa a 1x e a 4x com a mesma semente. O placar é igual?
