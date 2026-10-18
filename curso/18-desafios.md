# Módulo 18 — Desafios e projetos

Cada módulo tem exercícios curtos. Aqui estão **desafios maiores**, em ordem de dificuldade, que
juntam vários módulos. Todos podem ser feitos no simulador e conferidos pelo placar (com várias
sementes!) e depois no robô.

## Nível 1 — Fundamentos

| # | Desafio | Módulos | Pronto quando |
|---|---|---|---|
| 1.1 | **Quadrado perfeito:** andar um quadrado de 50 cm e voltar ao ponto de partida | 4, 5 | erro final < 3 cm e < 3° |
| 1.2 | **Estacionar:** parar a 10 cm da parede, girar 180°, voltar e parar a 10 cm da parede oposta | 4, 5, 7 | ±1 cm |
| 1.3 | **Painel de sensores:** um programa que mostra (tela ou print) todos os sensores e muda de página com o teclado | 6, 7, 8 | usado de verdade para conferir o robô no campo |
| 1.4 | **Garra de teste:** pegar uma bolinha parada à frente e jogar no lado certo da caçamba | 9 | 5 de 5 tentativas |

## Nível 2 — Rescue Line

| # | Desafio | Pronto quando |
|---|---|---|
| 2.1 | **PD afinado:** `curso_pista.json` com velocidade 50, sem LoP | 6 sementes sem LoP |
| 2.2 | **Interseções:** mapa só com verdes (esquerda, direita, os dois, nenhum, curva de 90° sem verde) | todas certas em 6 sementes |
| 2.3 | **Gap e obstáculo:** mapa com 2 gaps e 1 obstáculo, contornando com o VL53 lateral | 6 sementes sem LoP |
| 2.4 | **Rampa e lombada:** `completo.json` sem LoP nos trechos de rampa e lombada | 6 sementes |
| 2.5 | **Prova completa:** `completo.json` ponta a ponta | média ≥ 250 em 6 sementes |

## Nível 3 — Área de resgate

| # | Desafio | Pronto quando |
|---|---|---|
| 3.1 | **Só sair:** robô de esteira acha a saída em `resgate.json` | 6 de 6 |
| 3.2 | **Uma viva:** resgatar uma vítima viva no verde | 5 de 6 |
| 3.3 | **As três:** duas vivas e a morta, na ordem certa | média ≥ 2,5 vítimas em 6 sementes |
| 3.4 | **Vítimas difíceis:** vítimas encostadas nas paredes e perto dos triângulos (edite o mapa) | 2 de 3 resgatadas |

## Nível 4 — Rescue Maze

| # | Desafio | Pronto quando |
|---|---|---|
| 4.1 | **Mão direita robusta:** sem entrar no preto, parando no azul | 2 min sem LoP |
| 4.2 | **Mapa interno:** desenhar com `simdebug.marca` cada parede detectada | o desenho bate com o labirinto |
| 4.3 | **Volta ao início:** explorar 3 min e voltar pela rota mais curta | volta em 6 sementes |
| 4.4 | **Vítimas e kits:** identificar e deixar os kits certos | sem identificação errada |
| 4.5 | **Checkpoint:** com LoP "reinicia prog.", retomar do último prata | retoma certo em 3 LoPs |

## Projeto final

Escolham **Line** ou **Maze** e, em equipe:

1. Montem o robô e meçam tudo (módulo 17); ajustem o `robo*.json`.
2. Organizem o código em camadas com máquina de estados (módulo 13).
3. Criem **mapas de teste** para cada desafio e uma bateria de sementes de referência.
4. Mantenham um **diário**: versão, o que mudou, placar nas sementes de referência.
5. Façam uma rodada oficial no robô real (cronometrada e pontuada como na competição).

### Sugestão de avaliação (professor)

| Critério | Peso |
|---|---|
| Resultado nas sementes de referência no simulador | 25% |
| Resultado no robô real (rodada oficial) | 25% |
| Organização do código (camadas, constantes, estados, nomes) | 20% |
| Diário de testes (o que tentaram, o que mediram, o que aprenderam) | 20% |
| Apresentação: explicar uma decisão de projeto e um erro que corrigiram | 10% |

## Sugestão de cronograma

| Semana | Conteúdo |
|---|---|
| 1 | Módulos 1–3: brick, ambiente, primeiro programa |
| 2 | Módulo 4: motores e encoders |
| 3 | Módulo 5: giroscópio; desafio 1.1 |
| 4–5 | Módulo 6: sensor de linha, PD; desafio 2.1 |
| 6 | Módulos 7–8: distância, botões, tempo; desafios 1.2–1.3 |
| 7 | Módulos 11–13: simulador a fundo, organização do código |
| 8–9 | Módulo 14: seguidor completo; desafios 2.2–2.5 |
| 10 | Módulos 9–10: servos e câmera; desafio 1.4 |
| 11–12 | Módulo 15: área de resgate; desafios 3.x |
| (paralelo) | Módulos 12 e 16 para a equipe da Maze; desafios 4.x |
| 13+ | Módulo 17 e projeto final |
