import serial
from lidar import LidarData
porta_serial = 'COM7'  # Altere para a porta serial correta do seu sistema

# Constantes
HEAD_BYTE = 0xFA  # Defina o valor do cabeçalho do pacote (exemplo)
PACKET_SIZE = 22  # Defina o tamanho do pacote conforme seu sensor
DATA_SIZE = 7    # Defina o tamanho dos dados conforme necessário

# Variáveis globais
wait_packet = True
packet_index = 0
packet = [0] * PACKET_SIZE
data = [0] * DATA_SIZE
current_speed = 0  # Variável para suavizar leituras de velocidade
lidar = LidarData()
def abre_porta_serial(porta, baud_rate=115200):
        try:
            ser = serial.Serial(porta, baud_rate, timeout=0.01)
            print(f'Comunicação estabelecida com sucesso na porta {porta}.')
            return ser
        except serial.SerialException as e:
            print(f'Erro ao tentar se comunicar com a porta {porta}: {e}')
            return None

def checksum(packet_data, sum_value, size):
    """Tradução da função checksum do Arduino para Python"""
    chk32 = 0
    data = [0] * (size // 2)  # array de uint16_t equivalente
    sensor_data = [0] * size  # array de uint8_t equivalente
    
    # Copiar dados do packet para sensor_data
    for i in range(size):
        sensor_data[i] = packet_data[i]
    
    # Processar dados em pares de bytes (little-endian)
    for i in range(size // 2):
        data[i] = ((sensor_data[i*2+1] << 8) + sensor_data[i*2]) & 0xFFFF
        chk32 = ((chk32 << 1) + data[i]) & 0xFFFFFFFF  # manter como 32-bit
    
    # Calcular checksum final
    checksum_result = ((chk32 & 0x7FFF) + (chk32 >> 15)) & 0xFFFFFFFF
    checksum_final = (checksum_result & 0x7FFF)
    
    # Retornar 1 se checksum válido, 0 se inválido (como boolean em Arduino)
    return 1 if checksum_final == sum_value else 0

def decode_packet(packet_data, packet_size):
    """Tradução da função decodePacket do Arduino para Python"""
    global data, current_speed
    data_idx = 0
    
    # Inicializar array de dados
    for idx in range(DATA_SIZE):
        data[idx] = 0
    
    for i in range(packet_size):
        # Descomente a linha abaixo para debug
        # print(f"0x{packet_data[i]:02X}\t", end="")
        
        if i == 0:  # header byte
            # print("data: ", end="")
            continue
            
        elif i == 1:
            angle = (packet_data[i] - 0xA0) * 4  # converter para valores entre 0 ~ 360
            if angle > 360:
                return
            # print(f"{angle}\t", end="")
            data[data_idx] = angle
            data_idx += 1
            
        elif i == 2:
            speed = 0x00
            speed |= ((packet_data[3] << 8) | packet_data[2])
            
            # Tentativa de suavizar as leituras de velocidade já que às vezes há picos devido a problema desconhecido
            if abs(speed/64 - current_speed) > 100:
                current_speed = current_speed * 0.95 + (speed/64) * 0.05
            else:
                current_speed = speed/64
                
            # print(f"{current_speed}\t", end="")
            data[data_idx] = current_speed
            data_idx += 1
            
        elif i == 4 or i == 8 or i == 12 or i == 16:
            distance = 0x00
            distance |= ((packet_data[i+1] & 0x3F) << 8) | packet_data[i]
            # print(f"{distance}\t", end="")
            data[data_idx] = distance
            data_idx += 1
            
            # Código comentado do Arduino (flags de validação)
            # print(f"\t\t{packet_data[i+3] >> 8 + packet_data[i+2]}")
            # if packet_data[i+1] & (1 << 7):
            #     print("inv: ", end="")
            #     if packet_data[i+1] & (1 << 6):
            #         print("str: ", end="")
            # else:
            #     print(f"{distance/10.0}")
    
    # Calcular e verificar checksum
    expected_checksum = packet_data[PACKET_SIZE-2] + (packet_data[PACKET_SIZE-1] << 8)
    chksum = checksum(packet_data, expected_checksum, PACKET_SIZE-2)
    data[data_idx] = chksum
    data_idx += 1

def send_data(data_array, data_size):
    """Função para enviar/processar os dados decodificados"""
    #print(f"Enviando dados: {data_array[:data_size]}")
    global lidar
    lidar.updateData(data_array)
    # Implementar o processamento dos dados conforme necessário
    pass

def process_lidar_data(lidar_sensor):
    """Tradução do código Arduino para Python"""
    global wait_packet, packet_index, packet
    
    if lidar_sensor.in_waiting > 0:  # equivalent to lidarSensor.available() > 0
        received_byte = lidar_sensor.read(1)[0]  # read one byte
        
        if wait_packet:  # wait for a new packet to arrive
            if received_byte == HEAD_BYTE:
                packet_index = 0    # initialise packet index
                wait_packet = False
                packet[packet_index] = received_byte
                packet_index += 1
        
        else:  # if currently receiving packet
            if packet[0] == HEAD_BYTE:  # ensure the head of the packet is valid
                packet[packet_index] = received_byte  # store received byte
                packet_index += 1
                
                if packet_index >= PACKET_SIZE:  # if packet buffer is full
                    wait_packet = True  # wait for a new packet
                    decode_packet(packet, PACKET_SIZE)  # process the packet
                    send_data(data, DATA_SIZE)

ser = abre_porta_serial(porta_serial, 115200)

# Loop principal para processar dados do LIDAR
if ser:
    try:
        print("Iniciando leitura dos dados do LIDAR...")
        print("Pressione Ctrl+C para parar")
        
        while True:
            process_lidar_data(ser)
            
    except KeyboardInterrupt:
        print("\nParando a leitura...")
    except Exception as e:
        print(f"Erro durante a leitura: {e}")
    finally:
        if ser.is_open:
            ser.close()
            print("Porta serial fechada.")
else:
    print("Não foi possível estabelecer comunicação serial.")

