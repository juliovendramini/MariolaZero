# Exemplo do sensor de cor TCS34725 avulso no Mariola (ligado direto num conector I2C)
#
# Os arquivos .py das bibliotecas usadas (tcs34725.py, portas.py) precisam estar dentro da pasta
# do projeto.
#
# ---------------------------------------------------------------------------------------------
# Como o sensor funciona
# ---------------------------------------------------------------------------------------------
# * É o mesmo chip dos três sensores de cor do Pro1616, mas solto: você põe onde quiser (na frente
#   do robô para ver a cor do triângulo da área de resgate, na garra para ver a vítima...).
# * Todo TCS34725 tem o endereço 0x29, então cada um vai num conector I2C diferente (o mux do
#   Mariola separa). Os VL53L0X ficam no mesmo barramento.
# * A lib liga o sensor com ganho 4x e uma medida nova a cada ~154 ms. Ler mais rápido que isso
#   devolve o mesmo valor (não dá erro).
# * le_valores() devolve (r, g, b, c): valores crus de 0 a 65535, sem calibração. O c ("clear") é a
#   luz total. O LED branco do módulo ilumina o alvo, então os números caem muito quando o objeto
#   se afasta: para saber a cor, o que vale é a PROPORÇÃO entre r, g e b, não o valor de cada um.
# * Se o c der 0 com algo claro bem perto, o LED do módulo está apagado (confira o pino LED do
#   módulo) ou o sensor está com defeito.
# ---------------------------------------------------------------------------------------------

from time import sleep

from portas import Portas
from tcs34725 import TCS34725

PORTA = Portas.I2C1  # conector onde o sensor está ligado (I2C1 a I2C8)

# Abaixo deste "c" o objeto está longe demais (ou não tem nada na frente) e a cor não vale.
# Olhe o c que aparece com o objeto na distância que o robô vai usar e ajuste.
C_MINIMO = 50


def nome_porta(canal):
    """Portas.I2C1 (que vale 6) -> 'I2C1'. O número do canal no mux nem sempre é o do conector."""
    for n in range(1, 9):
        if getattr(Portas, f'I2C{n}') == canal:
            return f'I2C{n}'
    return f'canal {canal}'


def procura_tcs():
    """Procura em qual conector I2C tem um TCS34725 (para quando ele não responde na PORTA)."""
    from smbus2 import SMBus
    achados = []
    with SMBus(1) as bus:
        for canal in range(8):
            try:
                bus.write_byte(0x70, 1 << canal)  # escolhe o canal no mux
                # registrador de identificação (0x12, com o bit de comando 0x80)
                if bus.read_byte_data(0x29, 0x80 | 0x12) in (0x44, 0x4D, 0x10):
                    achados.append(nome_porta(canal))
            except OSError:
                pass  # nada (ou outro sensor) neste canal
        try:
            bus.write_byte(0x70, 0)  # desliga todos os canais do mux
        except OSError:
            pass
    return sorted(achados)


def nao_achou(motivo):
    print(f'O TCS34725 não respondeu no {nome_porta(PORTA)} ({motivo}).')
    achados = procura_tcs()
    if achados:
        print('Achei TCS34725 em:', ', '.join(achados), '-> troque a PORTA no começo do main.py.')
    else:
        print('Não achei nenhum TCS34725: confira o cabo e a alimentação do sensor.')
    raise SystemExit(1)


def nome_da_cor(r, g, b, c):
    """Classifica pela proporção entre r, g e b. Os números são um ponto de partida: imprima as
    proporções com as cores de verdade da pista e ajuste."""
    if c < C_MINIMO:
        return 'longe (sem cor)'
    soma = r + g + b
    if soma == 0:
        return 'longe (sem cor)'
    pr, pg, pb = r / soma, g / soma, b / soma
    if pr > 0.50:
        return 'vermelho'
    if pg > 0.42 and g > 1.3 * r:
        return 'verde'
    if pb > 0.40:
        return 'azul'
    return 'branco/cinza/preto'  # sem cor dominante: aqui quem diferencia é o c


try:
    sensor = TCS34725(PORTA)
    # Confere se quem respondeu é mesmo um TCS: o VL53L0X também usa o endereço 0x29 (até a lib
    # dele trocar para 0x30) e, no lugar do TCS, daria leituras sem sentido (zeros).
    ident = sensor.bus.read_byte_data(0x29, 0x80 | 0x12)
except OSError as e:
    nao_achou(e)
if ident not in (0x44, 0x4D, 0x10):
    nao_achou(f'quem respondeu no 0x29 não é um TCS34725: identificação 0x{ident:02X}')

sleep(0.16)  # espera a primeira medida ficar pronta

erros = 0
try:
    while True:
        try:
            r, g, b, c = sensor.le_valores()
            soma = max(r + g + b, 1)
            print(f'R {r:5d}  G {g:5d}  B {b:5d}  C {c:5d}   '
                  f'r {r / soma:.2f} g {g / soma:.2f} b {b / soma:.2f}   -> {nome_da_cor(r, g, b, c)}')
        except OSError as e:
            # O sensor não respondeu (mau contato, tranco): liga ele de novo e segue o programa
            erros += 1
            print(f'Erro no TCS34725 ({e}). Ligando de novo... (erro número {erros})')
            try:
                sensor = TCS34725(PORTA)
            except OSError as e2:
                print('Não respondeu:', e2)  # tenta de novo na próxima volta
        sleep(0.16)  # uma medida nova a cada ~154 ms

# Ctrl+C no terminal (ou parar pelo teclado do brick) cai aqui
except KeyboardInterrupt:
    print('\nPrograma encerrado.')
