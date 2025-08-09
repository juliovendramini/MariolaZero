import subprocess

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
    I2C3 = 2
    I2C4 = 3
    I2C5 = 4
    I2C6 = 5
    I2C7 = 6
    I2C8 = 7

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
                    if 'usb-0:1.2' in line:
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
                    if 'usb-0:1.4' in line:
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

    def abre_porta_serial(self, porta, baud_rate=115200):
        porta_real = self.porta_serial_real(porta)
        try:
            ser = serial.Serial(porta_real, baud_rate, timeout=0.01)
            print(f'Comunicação estabelecida com sucesso na porta {porta_real}.')
            return ser
        except serial.SerialException as e:
            print(f'Erro ao tentar se comunicar com a porta {porta_real}: {e}')
            return None
