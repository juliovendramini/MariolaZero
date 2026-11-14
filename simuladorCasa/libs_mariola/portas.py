import subprocess
import time

import serial


class Portas:
    _SERIAL0 = 0
    SERIAL1 = 1
    SERIAL2 = 2
    SERIAL3 = 3
    SERIAL4 = 4
    SERIAL5 = 5
    SERIAL6 = 6
    I2C1 = 0
    I2C2 = 1
    I2C3 = 7
    I2C4 = 2
    I2C5 = 3
    I2C6 = 6
    I2C7 = 5
    I2C8 = 4

    def porta_serial_real(self, porta):
        if porta == self._SERIAL0:
            try:
                result = subprocess.check_output(['ls', '-l', '/dev/serial/by-path/'], text=True)
                for line in result.splitlines():
                    if 'usb-0:1.1' in line:
                        caminho = line.split('->')[-1].strip()
                        caminho = '/dev/' + caminho.split('/')[-1]
                        return caminho
            except Exception as e:
                raise RuntimeError(f'Erro ao descobrir a porta serial: {e}')
        if porta == self.SERIAL1:
            try:
                result = subprocess.check_output(['ls', '-l', '/dev/serial/by-path/'], text=True)
                for line in result.splitlines():
                    if 'usb-0:1.4' in line:
                        caminho = line.split('->')[-1].strip()
                        caminho = '/dev/' + caminho.split('/')[-1]
                        return caminho
            except Exception as e:
                raise RuntimeError(f'Erro ao descobrir a porta serial: {e}')
        if porta == self.SERIAL2:
            try:
                result = subprocess.check_output(['ls', '-l', '/dev/serial/by-path/'], text=True)
                for line in result.splitlines():
                    if 'usb-0:1.3' in line:
                        caminho = line.split('->')[-1].strip()
                        caminho = '/dev/' + caminho.split('/')[-1]
                        return caminho
            except Exception as e:
                raise RuntimeError(f'Erro ao descobrir a porta serial: {e}')
        if porta == self.SERIAL3:
            try:
                result = subprocess.check_output(['ls', '-l', '/dev/serial/by-path/'], text=True)
                for line in result.splitlines():
                    if 'usb-0:1.2' in line:
                        caminho = line.split('->')[-1].strip()
                        caminho = '/dev/' + caminho.split('/')[-1]
                        return caminho
            except Exception as e:
                raise RuntimeError(f'Erro ao descobrir a porta serial: {e}')
            except Exception as e:
                raise RuntimeError(f'Erro ao descobrir a porta serial: {e}')
        if porta == self.SERIAL4:
            return '/dev/ttyS4'
        if porta == self.SERIAL5:
            return '/dev/ttyS2'
        if porta == self.SERIAL6:
            return '/dev/ttyS5'
        else:
            raise ValueError('Porta serial inválida.')

    def abre_porta_serial(self, porta, baud_rate=250000, timeout=0.010):
        porta_real = self.porta_serial_real(porta)
        try:
            ser = serial.Serial(porta_real, baud_rate, timeout=timeout)
            ser.porta_mariola = porta  # para o reabre_porta_serial achar a porta de novo
            print(f'Comunicação estabelecida com sucesso na porta {porta_real}.')
            return ser
        except serial.SerialException as e:
            print(f'Erro ao tentar se comunicar com a porta {porta_real}: {e}')
            return None

    def reabre_porta_serial(self, ser, tempo_maximo=3.0):
        """Reabre uma porta que caiu e devolve True se conseguiu (tenta por até tempo_maximo segundos).

        As portas USB do brick (_SERIAL0 a SERIAL3) ficam atrás de um hub. Se o hub reinicia (queda dos
        5 V ou ruído dos motores; no dmesg: "usb 1-1: reset high-speed USB device"), os conversores somem
        e voltam, e o Linux pode dar outro ttyUSB a cada um. Por isso a porta é achada de novo pelo lugar
        no hub e o MESMO objeto é reaberto: quem divide a porta (as placas de motor do barramento)
        continua com ele."""
        porta = getattr(ser, 'porta_mariola', None)
        fim = time.monotonic() + tempo_maximo
        try:
            ser.close()  # solta o ttyUSB antigo
        except Exception:
            pass
        while True:
            try:
                if porta is not None:
                    ser.port = self.porta_serial_real(porta)
                ser.open()
                return True
            except Exception:
                if time.monotonic() >= fim:
                    return False
                time.sleep(0.1)
