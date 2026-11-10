# Exemplo do sensor de distância VL53L0X no Mariola
#
# Os arquivos .py das bibliotecas usadas (vl53.py, portas.py...) precisam estar dentro da pasta
# do projeto. Use o vl53.py desta pasta (ou o de libs/): a versão de 09/11/2026 em diante é a que
# não trava depois de um Ctrl+C (veja abaixo). Para conferir, procure "_reset_software" no vl53.py.
#
# ---------------------------------------------------------------------------------------------
# Por que o VL53 "parava de responder" (e por que não precisa mais do fio no XSHUT)
# ---------------------------------------------------------------------------------------------
# O VL53 tem registradores separados em "bancos". Várias funções da lib trocam de banco
# (registrador 0xFF = 1), escrevem algumas coisas e voltam no fim (0xFF = 0). Se o programa leva
# Ctrl+C bem no meio disso, o sensor fica no banco errado. Ele continua ligado e lembra disso.
# O programa seguinte escrevia a inicialização nos registradores errados e o sensor travava:
# passava a dar "OSError: No such device or address" ou "Sensor não encontrado" e só voltava
# desligando o robô.
#
# Medido num Mariola com 3 sensores (09/11/2026): com a lib antiga, 8 travamentos em 300 Ctrl+C;
# com a lib nova, nenhum em 400. A lib nova reinicia o sensor por software (registrador 0xBF, o
# mesmo efeito do pino XSHUT) toda vez que o objeto é criado. Então:
#   * Ctrl+C à vontade: o próximo programa destrava o sensor sozinho.
#   * Se um sensor der erro com o programa rodando (mau contato, tranco), chame recover():
#     ele faz o mesmo reset e inicializa de novo. É o que este exemplo faz.
#   * Se travar SEM ter tido Ctrl+C antes, a causa é outra (cabo, ruído dos motores,
#     alimentação). Avise o professor antes de desligar o robô.
# ---------------------------------------------------------------------------------------------

from time import sleep

from portas import Portas
from vl53 import VL53L0X

# Crie os sensores uma vez só, no começo. Aqui já acontece o reset por software.
sensor1 = VL53L0X(Portas.I2C1)

erros = 0
try:
    while True:
        try:
            sensor1.solicita_leitura()     # dispara a medida e volta logo
            sleep(0.03)                    # a medida leva ~33 ms (dá para fazer outra coisa aqui)
            distancia = sensor1.leitura_mm()
            print(distancia, 'mm')
        except (OSError, TimeoutError) as e:
            # O sensor não respondeu: reinicia ele e segue o programa
            erros += 1
            print(f'Erro no VL53 ({e}). Recuperando... (erro número {erros})')
            try:
                sensor1.recover()
            except OSError as e2:
                print('Não recuperou:', e2)  # tenta de novo na próxima volta
                sleep(0.2)

# Ctrl+C no terminal (ou parar pelo teclado do brick) cai aqui
except KeyboardInterrupt:
    print('\nPrograma encerrado.')
