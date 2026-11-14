import struct
import threading
import time
import math

from cronometro import Cronometro
from portas import Portas


class Giroscopio:
    GYRO = 0
    GYRO2 = 1
    GYRO_CAL = 2
    ROS_IMU = 3
    modo = 0
    quantidade_bytes_modo = 8

    def __init__(self, porta_serial):
        # 8 valores (modo GYRO/GYRO2)
        self.lista = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        
        # Dados ROS IMU (modo ROS_IMU)
        self.qw = 1.0  # Quaternion w
        self.qx = 0.0  # Quaternion x
        self.qy = 0.0  # Quaternion y
        self.qz = 0.0  # Quaternion z
        
        self.angular_vel_x = 0.0  # rad/s
        self.angular_vel_y = 0.0  # rad/s
        self.angular_vel_z = 0.0  # rad/s
        
        self.linear_accel_x = 0.0  # m/s²
        self.linear_accel_y = 0.0  # m/s²
        self.linear_accel_z = 0.0  # m/s²
        
        # Covariâncias (conforme definido no Arduino)
        self.orientation_covariance = [
            0.001, 0.0,   0.0,
            0.0,   0.001, 0.0,
            0.0,   0.0,   0.1
        ]
        
        self.angular_velocity_covariance = [
            0.0001, 0.0,    0.0,
            0.0,    0.0001, 0.0,
            0.0,    0.0,    0.0001
        ]
        
        self.linear_acceleration_covariance = [
            0.001, 0.0,   0.0,
            0.0,   0.001, 0.0,
            0.0,   0.0,   0.001
        ]
        
        portas = Portas()
        self.ser = portas.abre_porta_serial(porta_serial, 115200)
        if self.ser is None:
            raise Exception('Erro ao abrir a porta serial do giroscopio')
        self.set_modo(self.GYRO)
        self._thread_ativa = False
        self._thread = None
        self._iniciar_thread()

    def __del__(self):
        """Destrutor da classe. Para a thread e fecha a porta serial."""
        self._parar_thread()
        if self.ser is not None:
            self.ser.close()

    def _atualiza_periodicamente(self):
        """Função que chama `atualiza` a cada 25ms."""
        while self._thread_ativa:
            self.atualiza()
            time.sleep(0.005)  # 25ms

    def _iniciar_thread(self):
        """Inicia a thread para chamar `atualiza` periodicamente."""
        if not self._thread_ativa:
            self._thread_ativa = True
            self._thread = threading.Thread(target=self._atualiza_periodicamente)
            self._thread.daemon = True  # Permite que o programa principal encerre mesmo com a thread ativa
            self._thread.start()

    def _parar_thread(self):
        """Para a thread que chama `atualiza`."""
        self._thread_ativa = False
        if self._thread is not None:
            self._thread.join()

    def set_modo(self, modo):
        if modo < 0 or modo > 3:
            raise ValueError('Modo inválido. Deve ser 0, 1, 2 ou 3.')
        self.modo = modo
        if modo in {self.GYRO, self.GYRO2}:
            self.quantidade_bytes_modo = 8
        elif modo == self.GYRO_CAL:
            self.quantidade_bytes_modo = 1
        elif modo == self.ROS_IMU:
            self.quantidade_bytes_modo = 40  # 10 floats = 40 bytes

    def atualiza(self):
        # limpo o buffer de entrada
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        # Envia o comando para solicitar o bytes necessarios
        self.ser.write(bytes([self.modo]))

        # Aguarda receber os self.quantidade_bytes_modo bytes via serial
        dados = self.ser.read(self.quantidade_bytes_modo)

        # Verifica se recebeu exatamente self.quantidade_bytes_modo bytes
        if len(dados) == self.quantidade_bytes_modo:
            if self.modo == self.ROS_IMU:
                # Modo ROS_IMU: 10 floats (40 bytes)
                # Formato: qw, qx, qy, qz, ang_vel_x, ang_vel_y, ang_vel_z, lin_acc_x, lin_acc_y, lin_acc_z
                values = struct.unpack('<10f', dados)  # Little-endian, 10 floats
                
                self.qw = values[0]
                self.qx = values[1]
                self.qy = values[2]
                self.qz = values[3]
                
                self.angular_vel_x = values[4]
                self.angular_vel_y = values[5]
                self.angular_vel_z = values[6]
                
                self.linear_accel_x = values[7]
                self.linear_accel_y = values[8]
                self.linear_accel_z = values[9]
            else:
                # Modos GYRO, GYRO2, GYRO_CAL: atualiza lista de bytes
                self.lista = list(dados)
            return True
        else:
            return False

    def le_angulo_x(self):
        # tenho q usar struct pra pegar dois bytes da lista e transformar em inteiro com sinal
        angulo_x = struct.unpack('>h', bytes(self.lista[0:2]))[0]
        return angulo_x

    def le_angulo_y(self):
        # tenho q usar struct pra pegar dois bytes da lista e transformar em inteiro com sinal
        angulo_y = struct.unpack('>h', bytes(self.lista[2:4]))[0]
        return angulo_y

    def le_angulo_z(self):
        # tenho q usar struct pra pegar dois bytes da lista e transformar em inteiro com sinal
        angulo_z = struct.unpack('>h', bytes(self.lista[4:6]))[0]
        return angulo_z

    def reseta_z(self):
        # apenas troco o modo de GYRO para GYRO2 ou o contrário
        if self.modo == self.GYRO:
            self.modo = self.GYRO2
        else:
            self.modo = self.GYRO
        time.sleep(0.025)
    
    # ========== Métodos para ROS IMU ==========
    
    def get_quaternion(self):
        """
        Retorna a orientação como quaternion (w, x, y, z).
        Modo ROS_IMU deve estar ativo.
        
        Returns:
            tuple: (w, x, y, z)
        """
        return (self.qw, self.qx, self.qy, self.qz)
    
    def get_angular_velocity(self):
        """
        Retorna a velocidade angular em rad/s.
        Modo ROS_IMU deve estar ativo.
        
        Returns:
            tuple: (x, y, z) em rad/s
        """
        return (self.angular_vel_x, self.angular_vel_y, self.angular_vel_z)
    
    def get_linear_acceleration(self):
        """
        Retorna a aceleração linear em m/s².
        Modo ROS_IMU deve estar ativo.
        
        Returns:
            tuple: (x, y, z) em m/s²
        """
        return (self.linear_accel_x, self.linear_accel_y, self.linear_accel_z)
    
    def get_orientation_euler(self):
        """
        Converte o quaternion atual para ângulos de Euler (roll, pitch, yaw) em graus.
        Modo ROS_IMU deve estar ativo.
        
        Returns:
            tuple: (roll, pitch, yaw) em graus
        """
        # Conversão de quaternion para Euler
        # Roll (x-axis rotation)
        sinr_cosp = 2 * (self.qw * self.qx + self.qy * self.qz)
        cosr_cosp = 1 - 2 * (self.qx * self.qx + self.qy * self.qy)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        
        # Pitch (y-axis rotation)
        sinp = 2 * (self.qw * self.qy - self.qz * self.qx)
        if abs(sinp) >= 1:
            pitch = math.copysign(math.pi / 2, sinp)  # Use 90 degrees if out of range
        else:
            pitch = math.asin(sinp)
        
        # Yaw (z-axis rotation)
        siny_cosp = 2 * (self.qw * self.qz + self.qx * self.qy)
        cosy_cosp = 1 - 2 * (self.qy * self.qy + self.qz * self.qz)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        
        # Converter de radianos para graus
        roll_deg = math.degrees(roll)
        pitch_deg = math.degrees(pitch)
        yaw_deg = math.degrees(yaw)
        
        return (roll_deg, pitch_deg, yaw_deg)
    
    def get_orientation_covariance(self):
        """
        Retorna a matriz de covariância da orientação (3x3 = 9 valores).
        Formato: [xx, xy, xz, yx, yy, yz, zx, zy, zz]
        
        Returns:
            list: 9 valores da matriz de covariância
        """
        return self.orientation_covariance.copy()
    
    def get_angular_velocity_covariance(self):
        """
        Retorna a matriz de covariância da velocidade angular (3x3 = 9 valores).
        Formato: [xx, xy, xz, yx, yy, yz, zx, zy, zz]
        
        Returns:
            list: 9 valores da matriz de covariância
        """
        return self.angular_velocity_covariance.copy()
    
    def get_linear_acceleration_covariance(self):
        """
        Retorna a matriz de covariância da aceleração linear (3x3 = 9 valores).
        Formato: [xx, xy, xz, yx, yy, yz, zx, zy, zz]
        
        Returns:
            list: 9 valores da matriz de covariância
        """
        return self.linear_acceleration_covariance.copy()
    
    def get_all_imu_data(self):
        """
        Retorna todos os dados do IMU em um dicionário (formato compatível com ROS).
        Modo ROS_IMU deve estar ativo.
        
        Returns:
            dict: Dicionário com todos os dados do IMU
        """
        return {
            'orientation': {
                'w': self.qw,
                'x': self.qx,
                'y': self.qy,
                'z': self.qz
            },
            'orientation_covariance': self.orientation_covariance.copy(),
            'angular_velocity': {
                'x': self.angular_vel_x,
                'y': self.angular_vel_y,
                'z': self.angular_vel_z
            },
            'angular_velocity_covariance': self.angular_velocity_covariance.copy(),
            'linear_acceleration': {
                'x': self.linear_accel_x,
                'y': self.linear_accel_y,
                'z': self.linear_accel_z
            },
            'linear_acceleration_covariance': self.linear_acceleration_covariance.copy()
        }
    
    def print_imu_data(self):
        """
        Imprime todos os dados do IMU de forma formatada.
        Útil para debug.
        """
        print("===== ROS IMU Data =====")
        print(f"Orientation (Quaternion):")
        print(f"  w: {self.qw:.6f}")
        print(f"  x: {self.qx:.6f}")
        print(f"  y: {self.qy:.6f}")
        print(f"  z: {self.qz:.6f}")
        
        roll, pitch, yaw = self.get_orientation_euler()
        print(f"\nOrientation (Euler - graus):")
        print(f"  Roll:  {roll:.2f}°")
        print(f"  Pitch: {pitch:.2f}°")
        print(f"  Yaw:   {yaw:.2f}°")
        
        print(f"\nAngular Velocity (rad/s):")
        print(f"  x: {self.angular_vel_x:.6f}")
        print(f"  y: {self.angular_vel_y:.6f}")
        print(f"  z: {self.angular_vel_z:.6f}")
        
        print(f"\nLinear Acceleration (m/s²):")
        print(f"  x: {self.linear_accel_x:.6f}")
        print(f"  y: {self.linear_accel_y:.6f}")
        print(f"  z: {self.linear_accel_z:.6f}")
        print("========================\n")

    def calibra(self):
        self._parar_thread()
        self.set_modo(self.GYRO_CAL)
        tempo = Cronometro()
        tempo.inicia()
        # Aguarda 5 segundos para a calibração
        self.ser.write(bytes([self.modo]))  # envio o modo novo de calibração
        while tempo.tempo() < 5000:
            dados = self.ser.read(1)  # o modo de calibracao do giroscopio só retorna 1 byte
            # Verifica se recebeu exatamente self.quantidade_bytes_modo bytes
            if len(dados) == 1:
                # Atualiza a lista com os valores recebidos
                break
        self.set_modo(self.GYRO)
        self._iniciar_thread()
        if tempo.tempo() >= 5000:
            print('Tempo de calibração excedido')
            return False
        # Aguarda 5 segundos para a calibração
        print('Calibração concluída')
        return True
