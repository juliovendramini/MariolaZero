# Módulo 14 — Projeto: o seguidor completo da Rescue Line

**Objetivo:** juntar tudo num programa que faz a prova inteira da linha: marcadores verdes, curvas
de 90°, gaps, obstáculo, rampas, lombadas e a chegada. Estudamos o programa de exemplo do simulador
e o que cada parte resolve.

Programa: `simuladorLine/exemplo_aluno/` (`robo.py`, `main.py`, `resgate.py`, `calibra_cores.py`).
Mapas: `treino.json` (interseções, gap), `completo.json` (tudo), `resgate.json`.

```bash
python simulador.py --mapa mapas/completo.json
```

## 14.1 Estrutura

* `robo.py` — o hardware (módulo 13): `anda`, `gira`, `anda_mm(mm, para_se=...)`, `reflexao()`,
  `cores()` (com a confirmação RGB do módulo 6), `z()`, `inclinacao()`, `distancia(nome)` (VL53 sem
  bloquear), `para_choque()`, `espera_botao()`, e a classe `Garra`.
* `main.py` — a classe `Seguidor`, com um método por situação e o `passo()`, chamado em laço a cada
  10 ms.

## 14.2 O `passo()`: a ordem das perguntas importa

A cada volta, o seguidor pergunta, **nesta ordem**:

1. **É a entrada da área de resgate?** (fita prata) → `AreaResgate(r).executa()`
2. **Vermelho em 2 ou mais TCS?** → chegada: para (e fica parado).
3. **Para-choque ou VL53 da frente < 70 mm?** → `obstaculo()`
4. **Sensor sem contraste** (tudo escuro por igual)? → segue reto pelo giroscópio (lombada, pé ou
   topo de rampa).
5. **Faixa preta larga** (um canal da ponta + os dois do meio)? → `intersecao(lado)`
6. **Não vê linha?** → se a linha estava escapando para um lado, é curva: gira para lá. Senão,
   `gap()`.
7. **Caso normal:** PD na posição da linha (módulo 6), mais devagar quando o erro é grande, mais
   rápido subindo rampa, mais lento descendo.

A ordem é uma decisão de estratégia: o prata e o vermelho vêm antes de tudo porque são raros e
importantes; o PD vem por último porque é o "senão".

## 14.3 Marcadores verdes e interseções

**A regra:** antes de uma interseção pode haver marcadores verdes. Verde à esquerda → vire à
esquerda; à direita → direita; dos dois lados → meia-volta; nenhum → siga reto.

**O problema de tempo:** os TCS passam pelo verde **antes** de a fileira de IR chegar à faixa preta
da interseção. Quando o robô percebe a interseção, o verde já ficou para trás.

**A solução do exemplo:** guardar **quando** viu verde de cada lado e, ao chegar na interseção,
olhar se foi há pouco tempo:

```python
def olha_verde(self):                 # chamado em TODO passo
    c = self.r.cores()
    if c[0] == 'verde':
        self.verde_esq = time.time()
    if c[2] == 'verde':
        self.verde_dir = time.time()
    return c

def verde_recente(self, janela=0.6):
    agora = time.time()
    return agora - self.verde_esq < janela, agora - self.verde_dir < janela
```

Na interseção: anda até o centro do robô ficar sobre o cruzamento (`anda_mm(70)`), gira 45° (ou
150° na meia-volta) e termina **procurando a linha** girando devagar até os canais do meio a verem
— em vez de confiar num ângulo fixo.

**Sem verde:** avança um pouco; se ainda há linha no meio, é cruzamento (segue reto); senão é uma
**curva de 90°** e gira para o lado da faixa preta.

> **Atenção à rampa:** inclinado, o sensor muda de altura e a leitura engana. O exemplo não trata
> faixa larga como interseção quando a inclinação está entre 3° e 18° (transição de rampa).

## 14.4 Gap

**A regra:** a linha pode ter falhas de até 20 cm, sempre em trecho reto.

```python
def gap(self):
    def achou():
        return posicao_linha(r.reflexao())[0] is not None
    if not r.anda_mm(GAP_MAX_MM, vel=30, para_se=achou):   # anda reto pelo giroscópio
        return True                                        # achou a linha: era gap
    r.anda_mm(-GAP_MAX_MM, vel=35)                         # não era: volta e procura
    self.procura_linha_girando(+1, max_graus=60)
    ...
```

O `anda_mm(..., para_se=função)` do `robo.py` é um padrão muito útil: **andar até uma condição ou
até a distância**, o que vier primeiro, mantendo a direção pelo giroscópio.

**Curva x gap:** se a linha sumiu enquanto escapava para um lado (`erro_ant` grande), o mais
provável é uma curva fechada, não um gap. O exemplo gira para aquele lado antes de supor gap.

## 14.5 Obstáculo

**A regra:** um obstáculo em cima da linha; o robô deve contorná-lo e voltar à linha depois dele
(pode empurrar se ele for solto, mas não pode tirar da pista de propósito).

O exemplo contorna pela direita "às cegas": ré, gira −90°, anda 170 mm, gira 90°, anda 420 mm,
gira 90°, anda até achar preto, procura a linha. Funciona para o obstáculo padrão, mas:

* não sabe o **tamanho** do obstáculo;
* não sabe se há **parede ou outra linha** do lado escolhido.

**Melhoria clássica (exercício):** usar o VL53 lateral para **contornar seguindo o obstáculo**
(módulo 7, seguir parede) até a linha aparecer.

## 14.6 Rampas, lombadas e detritos

* **Rampa:** `inclinacao()` (giroscópio X) > 8° → mais velocidade; < −8° → menos. No pé e na
  crista, o sensor muda de altura e tudo escurece: o passo 4 do `passo()` segue reto pelo
  giroscópio enquanto a leitura não tem contraste.
* **Lombada:** o sensor sobe e desce; com o sensor perto do chão o branco satura (> 200) e o preto
  fica cinza; os TCS também clareiam. Não confunda com prata (módulo 6).
* **Detritos:** palitos que fazem o robô "pular". Velocidade menor ajuda.

## 14.7 Chegada

Vermelho em 2 ou mais TCS (com a confirmação RGB) → parar e **ficar parado mais de 5 s**. O
exemplo para e nunca mais anda (`self.parado`).

## 14.8 Checkpoints e LoP

No LoP o juiz põe o robô no último checkpoint. O simulador pode **reiniciar o programa** (como
desligar e ligar o robô). Para a linha, quase não há estado a guardar — o seguidor recomeça
seguindo. Mas, se o seu programa já fez a área de resgate, ele precisa **saber disso** depois de
reiniciar (um arquivo, módulo 13).

## 14.9 Como evoluir o programa

1. Rode as sementes 1–6 no `completo.json` e anote LoPs e totais (módulo 11).
2. Para a pior rodada, assista na janela com `simdebug.texto()` mostrando o estado.
3. Classifique o erro: percepção, decisão ou ação (módulo 13).
4. Crie um mapa pequeno que reproduza o problema, corrija, rode as 6 sementes de novo.
5. Confirme no robô real.

## Exercícios

1. Monte um mapa com 4 interseções (verde esquerda, direita, os dois, nenhum) e faça o exemplo
   acertar todas em 6 sementes.
2. Troque o contorno "às cegas" do obstáculo por um contorno seguindo o obstáculo com o VL53
   direito.
3. A janela de 0,6 s do verde depende da velocidade. Troque por **distância** (encoder): "vi verde
   nos últimos 40 mm".
4. Aumente a velocidade base para 50 e ajuste o que for preciso para continuar completando o
   `completo.json`.
5. Faça a fita vermelha encerrar o programa só depois de 6 s parado (e confira o placar).
