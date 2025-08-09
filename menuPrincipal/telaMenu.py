import subprocess
import signal
import psutil
import sys
import os
import netifaces
import subprocess
from time import sleep
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import ImageFont

class MenuPrincipal:
    width = 128
    height = 64
    i2c_bus = None
    i2c_address = None
    tamanho_menu = 3
    tamanho_fonte = 12
    serial = None
    display = None
    menu_opcoes = []
    opcao_selecionada = 0
    deslocamento_inicial = 20
    inicio_menu = 0
    fim_menu = tamanho_menu-1
    MENU_PRINCIPAL = 0
    MENU_DESLIGAR = 1
    modo_menu = MENU_PRINCIPAL
    def __init__(self, i2c_bus=0, i2c_address=0x3C):
        self.i2c_bus = i2c_bus
        self.i2c_address = i2c_address
        self._ajustes_iniciais()
        with canvas(self.display) as draw:
            draw.rectangle(self.display.bounding_box, outline="black", fill="black")
        self.definir_menu()

    def _ajustes_iniciais(self):
        self.serial = i2c(port=self.i2c_bus, address=self.i2c_address)
        self.display = ssd1306(self.serial, width=self.width, height=self.height, rotate=0)
        self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", self.tamanho_fonte)


    def definir_menu(self):
        self.opcao_selecionada = 0
        self.monta_itens_menu()
        self.atualizar_menu()

    def atualizar_menu(self):
        if self.modo_menu == self.MENU_PRINCIPAL:
            self.menu_principal()
        elif self.modo_menu == self.MENU_DESLIGAR:
            self.menu_desligar()

    def menu_principal(self):
        self.monta_itens_menu()
        with canvas(self.display) as draw:
            draw.rectangle(self.display.bounding_box, outline="black", fill="black")
            ip = self.ip_equipamento()
            temperatura = self.obter_temperatura_cpu()
            texto = f"{ip} {temperatura}°C"
            draw.text((0, 0), texto, font=self.font, fill="white")
            if self.opcao_selecionada > self.fim_menu:
                self.inicio_menu = self.opcao_selecionada
                self.fim_menu = min(len(self.menu_opcoes), self.inicio_menu + self.tamanho_menu - 1)
            if self.opcao_selecionada < self.inicio_menu:
                self.inicio_menu = max(0, self.opcao_selecionada - self.tamanho_menu - 1)
                self.fim_menu = min(len(self.menu_opcoes), self.inicio_menu + self.tamanho_menu - 1)
            print(self.opcao_selecionada, self.inicio_menu, self.fim_menu)
            for i, opcao in enumerate(self.menu_opcoes[self.inicio_menu:self.fim_menu+1], start=self.inicio_menu):
                y_pos = self.deslocamento_inicial + (i - self.inicio_menu) * self.tamanho_fonte
                if i == self.opcao_selecionada:
                    draw.text((0, y_pos), f"> {opcao} <", font=self.font, fill="white")
                else:
                    draw.text((0, y_pos), f"  {opcao}", font=self.font, fill="white")

    def menu_desligar(self):
        self.menu_opcoes = ["Desligar Brick", "Wifi Off", "Wifi On"]
        with canvas(self.display) as draw:
            texto = f"Opções:"
            draw.text((0, 0), texto, font=self.font, fill="white")
            if self.opcao_selecionada > self.fim_menu:
                self.inicio_menu = self.opcao_selecionada
                self.fim_menu = min(len(self.menu_opcoes), self.inicio_menu + self.tamanho_menu - 1)
            if self.opcao_selecionada < self.inicio_menu:
                self.inicio_menu = max(0, self.opcao_selecionada - self.tamanho_menu - 1)
                self.fim_menu = min(len(self.menu_opcoes), self.inicio_menu + self.tamanho_menu - 1)
            print(self.opcao_selecionada, self.inicio_menu, self.fim_menu)
            for i, opcao in enumerate(self.menu_opcoes[self.inicio_menu:self.fim_menu+1], start=self.inicio_menu):
                y_pos = self.deslocamento_inicial + (i - self.inicio_menu) * self.tamanho_fonte
                if i == self.opcao_selecionada:
                    draw.text((0, y_pos), f"> {opcao} <", font=self.font, fill="white")
                else:
                    draw.text((0, y_pos), f"  {opcao}", font=self.font, fill="white")

    def mover_para_cima(self):
        if self.opcao_selecionada > 0:
            self.opcao_selecionada -= 1
            self.atualizar_menu()

    def mover_para_baixo(self):
        if self.opcao_selecionada < len(self.menu_opcoes) - 1:
            self.opcao_selecionada += 1
            self.atualizar_menu()

    def obter_opcao_selecionada(self):
        return self.menu_opcoes[self.opcao_selecionada]
    
    def ip_equipamento(self):
        try:
            interfaces = netifaces.ifaddresses('wlan0')
            ip = interfaces[netifaces.AF_INET][0]['addr']
            return ip
        except KeyError:
            return "Sem IP"
        except Exception as e:
            return "Sem IP"
        
    def obter_temperatura_cpu(self):
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as file:
                temp_millicelsius = int(file.read().strip())
                temp_celsius = temp_millicelsius / 1000.0
                return int(temp_celsius)
        except FileNotFoundError:
            return "--°C"
        except Exception as e:
            return "--°C"
        
    def executar_opcao_selecionada(self):
        opcao = self.obter_opcao_selecionada()
        if self.modo_menu == self.MENU_PRINCIPAL:
            print(f"Executando comando para: {opcao}")
            self.desenha_inicio_execucao()
            sleep(1)
            script_path = os.path.join("/home/banana", opcao, "main.py")
            resultado = subprocess.run(["python3", script_path], check=True)
            self._ajustes_iniciais()
            self.modo_menu = self.MENU_PRINCIPAL
            self.atualizar_menu()
        elif self.modo_menu == self.MENU_DESLIGAR:
            if self.opcao_selecionada == 0:
                print("Desligando o equipamento...")
                with canvas(self.display) as draw:
                    draw.rectangle(self.display.bounding_box, outline="black", fill="black")
                    texto = f"DESLIGANDO..."
                    draw.text((0, 0), texto, font=self.font, fill="white")
                sleep(1)
                self.limpa_tela()
                subprocess.run(["sudo", "shutdown", "-h", "now"])
                sleep(10)
            elif self.opcao_selecionada == 1:
                print("Desligando o Wi-Fi...")
                with canvas(self.display) as draw:
                    draw.rectangle(self.display.bounding_box, outline="black", fill="black")
                    texto = f"DESLIGANDO WIFI..."
                    draw.text((0, 0), texto, font=self.font, fill="white")
                sleep(2)
                self.limpa_tela()
                subprocess.run(["sudo", "ifconfig", "wlan0", "down"])
            elif self.opcao_selecionada == 2:
                print("Ligando o Wi-Fi...")
                with canvas(self.display) as draw:
                    texto = f"LIGANDO WIFI..."
                    draw.rectangle(self.display.bounding_box, outline="black", fill="black")
                    draw.text((0, 0), texto, font=self.font, fill="white")
                sleep(2)
                self.limpa_tela()
                subprocess.run(["sudo", "ifconfig", "wlan0", "up"])
            self.modo_menu = self.MENU_PRINCIPAL
            self.opcao_selecionada = 0
            self.atualizar_menu()

    def monta_itens_menu(self):
        self.menu_opcoes = []
        base_path = "/home/banana"
        lista_pastas = os.listdir(base_path)
        lista_pastas.sort()
        for item in lista_pastas:
            item_path = os.path.join(base_path, item)
            if item.startswith("."):
                continue
            if os.path.isdir(item_path):
                arquivos = os.listdir(item_path)
                if "main.py" in arquivos:
                    self.menu_opcoes.append(item)

    def limpa_tela(self):
        with canvas(self.display) as draw:
            draw.rectangle(self.display.bounding_box, outline="black", fill="black")

    def desenha_inicio_execucao(self):
        with canvas(self.display) as draw:
            self.limpa_tela()
            draw.text((0, 0), "Iniciando...", font=self.font, fill="white")

    def _processo_rodando(self):
        for proc in psutil.process_iter(['cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and len(cmdline) > 1 and cmdline[0] == 'python3' and 'main.py' in cmdline[1]:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False
    
    
    def aguarda_se_tela_em_uso_por_outro_processo(self):
        if self._processo_rodando():
            print("Aguardando outro processo usar a tela...")
            while self._processo_rodando():
                sleep(1)
            sleep(1)
            self._ajustes_iniciais()

