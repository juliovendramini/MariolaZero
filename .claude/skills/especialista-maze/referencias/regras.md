# Regra da Rescue Maze 2026 em resumo

Fonte: rascunho das regras RCJ Rescue Maze 2026 (28/01/2026,
`junior.robocup.org/wp-content/uploads/2026/01/RCJRescueMaze2026-draft.pdf`) e o juiz do simulador
(`simuladorMaze/README.md` "Juiz (regra 2026)", `simuladorMaze/sim/juiz.py`). A regra oficial e o juiz da
competição mandam: se a pergunta depender de um detalhe que não está aqui, diga que é preciso conferir no
livro de regras (a versão final pode ter mudado) e, na competição, perguntar ao juiz antes da rodada.

## Campo

* Ladrilhos de 30 × 30 cm com paredes (paredes de pelo menos 15 cm acima de qualquer piso, regra 3.1.3).
  No simulador a espessura da parede é configurável (`espessura_parede`, padrão 20 mm): o corredor tem
  300 − espessura.
* **Pisos:** preto (buraco: entrar = LoP), azul (parar 5 s; não parar = LoP), prata (checkpoint),
  vermelho (entrada da zona de perigo, opcional).
* **Terreno:** lombadas (1 cm; 2 cm na zona de perigo), detritos soltos, escadas.
* **Rampa** (3.1.5): reta, no máximo 25°.
* **Escada** (3.4.6-9): da largura do caminho, degraus de no máximo 2 cm, inclinação menor que 25° (menor
  que 30° na zona de perigo, 3.5.6), pode mudar o nível, fica entre paredes.
* Vítima nunca fica em parede de frente para rampa ou escada.

## Vítimas e kits

* Vítimas nas paredes: letras (H = ferida, S = estável, U = ilesa) e alvos cognitivos (anéis: soma 2, 1 ou
  0). Letra ou soma que não é nenhuma dessas = vítima falsa (não sinalizar).
* **Identificação:** parado a até 15 cm da vítima, piscar o indicador 500 ms aceso / 500 ms apagado por
  5 s. No simulador só os LEDs 8-9 contam. Identificação errada: −5.
* Pontos da identificação: letra 5 ou 15, cognitiva 10 ou 30 (o valor maior quando a parede não é
  "linear", isto é, não é alcançada seguindo a parede a partir do início).
* **Kits** (seção 3.7): ferida 2, estável 1, ilesa 0. Valem 10 (1 kit) e 30 (2 kits), só depois da
  identificação. O kit não precisa ser cubo: no mínimo 1 cm em cada dimensão e 1 cm³ depois de liberado,
  no máximo 8, não pode rolar nem quicar para longe, liberação clara para o juiz. Vale a posição do kit
  quando o robô sai inteiro do raio de 15 cm da vítima.

## Pontuação e rodada

* Checkpoint (prata) 10, azul 30 (−10 por revisita), lombada 5, escada 10 (5.6.10), rampa 10 subindo ou
  descendo (5.6.9, no máximo 10 por rampa).
* **Bônus de confiabilidade:** no simulador, 10 × (vítimas identificadas + kits entregues + azuis com
  parada) − 15 por LoP, nunca negativo. Cada LoP custa caro.
* **Bônus de saída**: voltar ao ladrilho do início e piscar 1 s / 1 s por 10 s. No bônus de saída entram
  também 5 por escada e 5 por rampa passadas.
* Rodada de 8 min, ou até a saída.
* **LoP** (falta de progresso): o robô volta ao último checkpoint visitado (ou ao início). Entrar no preto
  é LoP. No LoP o robô pode ser reiniciado (o programa começa de novo): o checkpoint salvo em arquivo é o
  que faz ele lembrar do mapa.

## O que o simulador simplifica

* O kit vale pela posição em que caiu (não rola até a parede).
* "Parado" = velocidade menor que 6 mm/s.
* Escada e rampa valem quando o meio do robô entra no ladrilho por uma ponta e sai pela outra (a regra
  pede o robô inteiro no ladrilho plano do outro lado).
* Sem obstáculos; sem ponte (cada ladrilho tem uma altura só).
