import os
import netifaces
import subprocess
from time import sleep
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import ImageFont

class TelaSSD1306:
    width = 128
    height = 64
    TAMANHO_MENU = 3
    TAMANHO_FONTE = 12
    serial = None
    display = None
    menu_opcoes = []
    opcao_selecionada = 0
    descolamento_inicial = 20
    inicioMenu = 0
    fimMenu = TAMANHO_MENU-1
    MENU_PRINCIPAL = 0
    MENU_DESLIGAR = 1
    modoMenu = MENU_PRINCIPAL
    def __init__(self, i2c_bus=0, i2c_address=0x3C):
        # Inicializar a interface I2C e o display SSD1306
        self.serial = i2c(port=i2c_bus, address=i2c_address)
        self.display = ssd1306(self.serial, width=self.width, height=self.height, rotate=0)
        self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", self.TAMANHO_FONTE)
        # Limpar a tela no início
        with canvas(self.display) as draw:
            draw.rectangle(self.display.bounding_box, outline="black", fill="black")
        self.definir_menu()
        # Fonte padrão
        #self.font = ImageFont.load_default()

    def definir_menu(self):
        """Define as opções do menu."""
        self.opcao_selecionada = 0  # Começa na primeira opção
        self.monta_itens_menu()
        self.atualizar_menu()

    def atualizar_menu(self):
        """Atualiza a tela do menu."""
        if self.modoMenu == self.MENU_PRINCIPAL:
            self.menu_principal()
        elif self.modoMenu == self.MENU_DESLIGAR:
            self.menu_desligar()

    def menu_principal(self):
        """Atualiza a tela para exibir o menu com rolagem."""
        self.monta_itens_menu()
        with canvas(self.display) as draw:
            # Limpar a tela
            draw.rectangle(self.display.bounding_box, outline="black", fill="black")
            ip = self.ip_equipamento()
            temperatura = self.obter_temperatura_cpu()

            # Exibir informações na parte superior da tela
            texto = f"{ip} {temperatura}°C"
            draw.text((0, 0), texto, font=self.font, fill="white")
            # Determinar o intervalo de opções a serem exibidas
            if(self.opcao_selecionada > self.fimMenu):
                self.inicioMenu = self.opcao_selecionada #max(0, self.opcao_selecionada - self.TAMANHO_MENU + 1)  # Linha inicial
                self.fimMenu = min(len(self.menu_opcoes), self.inicioMenu + self.TAMANHO_MENU - 1)  # Linha final
            if(self.opcao_selecionada < self.inicioMenu):
                self.inicioMenu = max(0,self.opcao_selecionada - self.TAMANHO_MENU-1) #max(0, self.opcao_selecionada - self.TAMANHO_MENU + 1)  # Linha inicial
                self.fimMenu = min(len(self.menu_opcoes), self.inicioMenu + self.TAMANHO_MENU - 1)  # Linha final
            print(self.opcao_selecionada, self.inicioMenu, self.fimMenu)

            # Exibir as opções do menu dentro do intervalo
            for i, opcao in enumerate(self.menu_opcoes[self.inicioMenu:self.fimMenu+1], start=self.inicioMenu):
                y_pos = self.descolamento_inicial + (i - self.inicioMenu) * self.TAMANHO_FONTE  # Calcular posição vertical
                if i == self.opcao_selecionada:
                    # Destacar a opção selecionada
                    draw.text((0, y_pos), f"> {opcao} <", font=self.font, fill="white")
                else:
                    draw.text((0, y_pos), f"  {opcao}", font=self.font, fill="white")

    def menu_desligar(self):
        """Atualiza a tela para exibir a opção de desligar"""
        self.menu_opcoes = ["Sim", "Não", "Wifi Off", "Wifi On"]
        with canvas(self.display) as draw:
            # Limpar a tela
            # Exibir informações na parte superior da tela
            texto = f"DESLIGAR?"
            draw.text((0, 0), texto, font=self.font, fill="white")
            # Determinar o intervalo de opções a serem exibidas
            if(self.opcao_selecionada > self.fimMenu):
                self.inicioMenu = self.opcao_selecionada #max(0, self.opcao_selecionada - self.TAMANHO_MENU + 1)  # Linha inicial
                self.fimMenu = min(len(self.menu_opcoes), self.inicioMenu + self.TAMANHO_MENU - 1)  # Linha final
            if(self.opcao_selecionada < self.inicioMenu):
                self.inicioMenu = max(0,self.opcao_selecionada - self.TAMANHO_MENU-1) #max(0, self.opcao_selecionada - self.TAMANHO_MENU + 1)  # Linha inicial
                self.fimMenu = min(len(self.menu_opcoes), self.inicioMenu + self.TAMANHO_MENU - 1)  # Linha final
            print(self.opcao_selecionada, self.inicioMenu, self.fimMenu)

            # Exibir as opções do menu dentro do intervalo
            for i, opcao in enumerate(self.menu_opcoes[self.inicioMenu:self.fimMenu+1], start=self.inicioMenu):
                y_pos = self.descolamento_inicial + (i - self.inicioMenu) * self.TAMANHO_FONTE  # Calcular posição vertical
                if i == self.opcao_selecionada:
                    # Destacar a opção selecionada
                    draw.text((0, y_pos), f"> {opcao} <", font=self.font, fill="white")
                else:
                    draw.text((0, y_pos), f"  {opcao}", font=self.font, fill="white")


    def mover_para_cima(self):
        """Move a seleção para cima no menu."""
        if self.opcao_selecionada > 0:
            self.opcao_selecionada -= 1
            self.atualizar_menu()

    def mover_para_baixo(self):
        """Move a seleção para baixo no menu."""
        if self.opcao_selecionada < len(self.menu_opcoes) - 1:
            self.opcao_selecionada += 1
            self.atualizar_menu()

    def obter_opcao_selecionada(self):
        """Retorna a opção atualmente selecionada."""
        return self.menu_opcoes[self.opcao_selecionada]
    
    def ip_equipamento(self):
        try:
            # Obter informações da interface wlan0
            interfaces = netifaces.ifaddresses('wlan0')
            # Pegar o endereço IP da interface
            ip = interfaces[netifaces.AF_INET][0]['addr']
            return ip
        except KeyError:
            return "Sem IP"
        except Exception as e:
            return "Sem IP"
        
    def obter_temperatura_cpu(self):
        try:
            # Caminho para o arquivo que contém a temperatura da CPU
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as file:
                temp_millicelsius = int(file.read().strip())
                # Converter de milicelsius para celsius
                temp_celsius = temp_millicelsius / 1000.0
                return int(temp_celsius)
        except FileNotFoundError:
            return "--°C"
        except Exception as e:
            return "--°C"
        
    def executar_opcao_selecionada(self):
        """Executa o comando associado à opção selecionada."""
        opcao = self.obter_opcao_selecionada()
        if(self.modoMenu == self.MENU_PRINCIPAL):
            # Aqui você pode adicionar lógica para executar comandos específicos com base na opção selecionada
            print(f"Executando comando para: {opcao}")
            self.desenha_inicio_execucao()
            sleep(1)
            script_path = os.path.join("/home/banana", opcao, "main.py")
            resultado = subprocess.run(["python", script_path], check=True)
        elif(self.modoMenu == self.MENU_DESLIGAR):
            if self.opcao_selecionada == 0:  # "Sim"
                # Executar o comando de desligamento
                print("Desligando o equipamento...")
                with canvas(self.display) as draw:
                    # Limpar a tela
                    # Exibir informações na parte superior da tela
                    draw.rectangle(self.display.bounding_box, outline="black", fill="black")
                    texto = f"DESLIGANDO..."
                    draw.text((0, 0), texto, font=self.font, fill="white")
                sleep(1)
                self.limpa_tela()
                subprocess.run(["sudo", "shutdown", "-h", "now"])
                sleep(10)
            # elif self.opcao_selecionada == 1:  # "Nao"
            #     # Retornar ao menu principal
            #     self.modoMenu = self.MENU_PRINCIPAL
            #     self.opcao_selecionada = 0
            #     self.atualizar_menu()
            elif self.opcao_selecionada == 2:  # "Wifi Off"
                # Executar o comando para desligar o Wi-Fi
                print("Desligando o Wi-Fi...")
                with canvas(self.display) as draw:
                    # Limpar a tela
                    # Exibir informações na parte superior da tela
                    draw.rectangle(self.display.bounding_box, outline="black", fill="black")
                    texto = f"DESLIGANDO WIFI..."
                    draw.text((0, 0), texto, font=self.font, fill="white")
                sleep(2)
                self.limpa_tela()
                subprocess.run(["sudo", "ifconfig", "wlan0", "down"])
            elif self.opcao_selecionada == 3:  # "Wifi On"
                # Executar o comando para ligar o Wi-Fi
                print("Ligando o Wi-Fi...")
                with canvas(self.display) as draw:
                    # Limpar a tela
                    # Exibir informações na parte superior da tela
                    texto = f"LIGANDO WIFI..."
                    draw.rectangle(self.display.bounding_box, outline="black", fill="black")
                    draw.text((0, 0), texto, font=self.font, fill="white")
                sleep(2)
                self.limpa_tela()
                subprocess.run(["sudo", "ifconfig", "wlan0", "up"])
                # Atualizar o menu após ligar o Wi-Fi
            self.modoMenu = self.MENU_PRINCIPAL
            self.opcao_selecionada = 0
            self.atualizar_menu()

    def monta_itens_menu(self):
    
        self.menu_opcoes = []
        base_path = "/home/banana"  # Caminho base para procurar as pastas

        # Listar apenas o primeiro nível de pastas
        lista_pastas = os.listdir(base_path)
        #ordeno a lista
        lista_pastas.sort()

        for item in lista_pastas:
            item_path = os.path.join(base_path, item)
            #ordenor os itens
            # Ignorar arquivos ocultos
            if item.startswith("."):
                continue

            # Verificar se é um diretório
            if os.path.isdir(item_path):
                # Verificar se contém apenas o arquivo main.py
                arquivos = os.listdir(item_path)
                if "main.py" in arquivos:
                    # Adicionar o nome da pasta ao menu de opções
                    self.menu_opcoes.append(item)


    def limpa_tela(self):
        """Limpa a tela do display."""
        with canvas(self.display) as draw:
            draw.rectangle(self.display.bounding_box, outline="black", fill="black")

    def desenha_inicio_execucao(self):
        """Desenha uma tela de início de execução."""
        with canvas(self.display) as draw:
            # Limpar a tela
            self.limpa_tela()
            # Desenhar o texto "Iniciando..."
            draw.text((0, 0), "Iniciando...", font=self.font, fill="white")
            
            
