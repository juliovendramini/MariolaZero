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
    i2cBus = None
    i2cAddress = None
    TAMANHO_MENU = 3
    TAMANHO_FONTE = 12
    serial = None
    display = None
    menuOpcoes = []
    opcaoSelecionada = 0
    descolamentoInicial = 20
    inicioMenu = 0
    fimMenu = TAMANHO_MENU-1
    MENU_PRINCIPAL = 0
    MENU_DESLIGAR = 1
    modoMenu = MENU_PRINCIPAL
    def __init__(self, i2c_bus=0, i2c_address=0x3C):
        self.i2cBus = i2c_bus
        self.i2cAddress = i2c_address
        self._ajustesIniciais()
        with canvas(self.display) as draw:
            draw.rectangle(self.display.bounding_box, outline="black", fill="black")
        self.definirMenu()

    def _ajustesIniciais(self):
        self.serial = i2c(port=self.i2cBus, address=self.i2cAddress)
        self.display = ssd1306(self.serial, width=self.width, height=self.height, rotate=0)
        self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", self.TAMANHO_FONTE)


    def definirMenu(self):
        self.opcaoSelecionada = 0
        self.montaItensMenu()
        self.atualizarMenu()

    def atualizarMenu(self):
        if self.modoMenu == self.MENU_PRINCIPAL:
            self.menuPrincipal()
        elif self.modoMenu == self.MENU_DESLIGAR:
            self.menuDesligar()

    def menuPrincipal(self):
        self.montaItensMenu()
        with canvas(self.display) as draw:
            draw.rectangle(self.display.bounding_box, outline="black", fill="black")
            ip = self.ipEquipamento()
            temperatura = self.obterTemperaturaCpu()
            texto = f"{ip} {temperatura}°C"
            draw.text((0, 0), texto, font=self.font, fill="white")
            if self.opcaoSelecionada > self.fimMenu:
                self.inicioMenu = self.opcaoSelecionada
                self.fimMenu = min(len(self.menuOpcoes), self.inicioMenu + self.TAMANHO_MENU - 1)
            if self.opcaoSelecionada < self.inicioMenu:
                self.inicioMenu = max(0, self.opcaoSelecionada - self.TAMANHO_MENU - 1)
                self.fimMenu = min(len(self.menuOpcoes), self.inicioMenu + self.TAMANHO_MENU - 1)
            print(self.opcaoSelecionada, self.inicioMenu, self.fimMenu)
            for i, opcao in enumerate(self.menuOpcoes[self.inicioMenu:self.fimMenu+1], start=self.inicioMenu):
                y_pos = self.descolamentoInicial + (i - self.inicioMenu) * self.TAMANHO_FONTE
                if i == self.opcaoSelecionada:
                    draw.text((0, y_pos), f"> {opcao} <", font=self.font, fill="white")
                else:
                    draw.text((0, y_pos), f"  {opcao}", font=self.font, fill="white")

    def menuDesligar(self):
        self.menuOpcoes = ["Desligar Brick", "Wifi Off", "Wifi On"]
        with canvas(self.display) as draw:
            texto = f"Opções:"
            draw.text((0, 0), texto, font=self.font, fill="white")
            if self.opcaoSelecionada > self.fimMenu:
                self.inicioMenu = self.opcaoSelecionada
                self.fimMenu = min(len(self.menuOpcoes), self.inicioMenu + self.TAMANHO_MENU - 1)
            if self.opcaoSelecionada < self.inicioMenu:
                self.inicioMenu = max(0, self.opcaoSelecionada - self.TAMANHO_MENU - 1)
                self.fimMenu = min(len(self.menuOpcoes), self.inicioMenu + self.TAMANHO_MENU - 1)
            print(self.opcaoSelecionada, self.inicioMenu, self.fimMenu)
            for i, opcao in enumerate(self.menuOpcoes[self.inicioMenu:self.fimMenu+1], start=self.inicioMenu):
                y_pos = self.descolamentoInicial + (i - self.inicioMenu) * self.TAMANHO_FONTE
                if i == self.opcaoSelecionada:
                    draw.text((0, y_pos), f"> {opcao} <", font=self.font, fill="white")
                else:
                    draw.text((0, y_pos), f"  {opcao}", font=self.font, fill="white")

    def moverParaCima(self):
        if self.opcaoSelecionada > 0:
            self.opcaoSelecionada -= 1
            self.atualizarMenu()

    def moverParaBaixo(self):
        if self.opcaoSelecionada < len(self.menuOpcoes) - 1:
            self.opcaoSelecionada += 1
            self.atualizarMenu()

    def obterOpcaoSelecionada(self):
        return self.menuOpcoes[self.opcaoSelecionada]
    
    def ipEquipamento(self):
        try:
            interfaces = netifaces.ifaddresses('wlan0')
            ip = interfaces[netifaces.AF_INET][0]['addr']
            return ip
        except KeyError:
            return "Sem IP"
        except Exception as e:
            return "Sem IP"
        
    def obterTemperaturaCpu(self):
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as file:
                temp_millicelsius = int(file.read().strip())
                temp_celsius = temp_millicelsius / 1000.0
                return int(temp_celsius)
        except FileNotFoundError:
            return "--°C"
        except Exception as e:
            return "--°C"
        
    def executarOpcaoSelecionada(self):
        opcao = self.obterOpcaoSelecionada()
        if self.modoMenu == self.MENU_PRINCIPAL:
            print(f"Executando comando para: {opcao}")
            self.desenhaInicioExecucao()
            sleep(1)
            script_path = os.path.join("/home/banana", opcao, "main.py")
            resultado = subprocess.run(["python3", script_path], check=True)
            self._ajustesIniciais()
            self.modoMenu = self.MENU_PRINCIPAL
            self.atualizarMenu()
        elif self.modoMenu == self.MENU_DESLIGAR:
            if self.opcaoSelecionada == 0:
                print("Desligando o equipamento...")
                with canvas(self.display) as draw:
                    draw.rectangle(self.display.bounding_box, outline="black", fill="black")
                    texto = f"DESLIGANDO..."
                    draw.text((0, 0), texto, font=self.font, fill="white")
                sleep(1)
                self.limpaTela()
                subprocess.run(["sudo", "shutdown", "-h", "now"])
                sleep(10)
            elif self.opcaoSelecionada == 1:
                print("Desligando o Wi-Fi...")
                with canvas(self.display) as draw:
                    draw.rectangle(self.display.bounding_box, outline="black", fill="black")
                    texto = f"DESLIGANDO WIFI..."
                    draw.text((0, 0), texto, font=self.font, fill="white")
                sleep(2)
                self.limpaTela()
                subprocess.run(["sudo", "ifconfig", "wlan0", "down"])
            elif self.opcaoSelecionada == 2:
                print("Ligando o Wi-Fi...")
                with canvas(self.display) as draw:
                    texto = f"LIGANDO WIFI..."
                    draw.rectangle(self.display.bounding_box, outline="black", fill="black")
                    draw.text((0, 0), texto, font=self.font, fill="white")
                sleep(2)
                self.limpaTela()
                subprocess.run(["sudo", "ifconfig", "wlan0", "up"])
            self.modoMenu = self.MENU_PRINCIPAL
            self.opcaoSelecionada = 0
            self.atualizarMenu()

    def montaItensMenu(self):
        self.menuOpcoes = []
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
                    self.menuOpcoes.append(item)

    def limpaTela(self):
        with canvas(self.display) as draw:
            draw.rectangle(self.display.bounding_box, outline="black", fill="black")

    def desenhaInicioExecucao(self):
        with canvas(self.display) as draw:
            self.limpaTela()
            draw.text((0, 0), "Iniciando...", font=self.font, fill="white")

    def _processoRodando(self):
        for proc in psutil.process_iter(['cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and len(cmdline) > 1 and cmdline[0] == 'python3' and 'main.py' in cmdline[1]:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False
    
    
    def aguardaSeTelaEmUsoPorOutroProcesso(self):
        if self._processoRodando():
            print("Aguardando outro processo usar a tela...")
            while self._processoRodando():
                sleep(1)
            sleep(1)
            self._ajustesIniciais()

