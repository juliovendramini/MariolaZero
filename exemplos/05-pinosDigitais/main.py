#!/usr/bin/env python3
"""
Exemplo de uso da classe PinosDigitais
Demonstra como usar os 8 pinos digitais como entrada e saída
"""
from libs.pinosDigitais import PinosDigitais
from gpiod.line import Direction


def exemplo_basico():
    """Exemplo básico de leitura e escrita"""
    print("=== Exemplo Básico ===\n")
    
    pinos = PinosDigitais()
    
    # Configurar P1-P4 como entrada (botões)
    print("P1-P4 configurados como ENTRADA (botões)")
    # Já estão como entrada por padrão
    
    # Configurar P5-P8 como saída (LEDs)
    print("P5-P8 configurados como SAÍDA (LEDs)")
    pinos.configura_pino(pinos.P5, Direction.OUTPUT)
    pinos.configura_pino(pinos.P6, Direction.OUTPUT)
    pinos.configura_pino(pinos.P7, Direction.OUTPUT)
    pinos.configura_pino(pinos.P8, Direction.OUTPUT)
    
    print("\nPressione os botões P1-P4 para acender LEDs P5-P8")
    print("Ctrl+C para sair\n")
    
    try:
        while True:
            # Ler botões e controlar LEDs correspondentes
            if pinos.botao_pressionado(pinos.P1):
                pinos.liga_pino(pinos.P5)
                print("P1 pressionado -> P5 ligado")
            else:
                pinos.desliga_pino(pinos.P5)
            
            if pinos.botao_pressionado(pinos.P2):
                pinos.liga_pino(pinos.P6)
                print("P2 pressionado -> P6 ligado")
            else:
                pinos.desliga_pino(pinos.P6)
            
            if pinos.botao_pressionado(pinos.P3):
                pinos.liga_pino(pinos.P7)
                print("P3 pressionado -> P7 ligado")
            else:
                pinos.desliga_pino(pinos.P7)
            
            if pinos.botao_pressionado(pinos.P4):
                pinos.liga_pino(pinos.P8)
                print("P4 pressionado -> P8 ligado")
            else:
                pinos.desliga_pino(pinos.P8)
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n\nDesligando todos os LEDs...")
        pinos.desliga_pino(pinos.P5)
        pinos.desliga_pino(pinos.P6)
        pinos.desliga_pino(pinos.P7)
        pinos.desliga_pino(pinos.P8)
        print("Finalizado!")


def exemplo_pisca_led():
    """Exemplo de LED piscante em todos os pinos de saída"""
    print("=== Exemplo Pisca LED ===\n")
    
    pinos = PinosDigitais()
    
    # Configurar todos como saída
    print("Configurando P1-P8 como SAÍDA...")
    for pin in [pinos.P1, pinos.P2, pinos.P3, pinos.P4, 
                pinos.P5, pinos.P6, pinos.P7, pinos.P8]:
        pinos.configura_pino(pin, Direction.OUTPUT)
    
    print("Piscando todos os LEDs...")
    print("Ctrl+C para sair\n")
    
    try:
        contador = 0
        while True:
            print(f"Ciclo {contador}: LIGANDO todos os pinos")
            for pin in [pinos.P1, pinos.P2, pinos.P3, pinos.P4,
                       pinos.P5, pinos.P6, pinos.P7, pinos.P8]:
                pinos.liga_pino(pin)
            
            time.sleep(0.5)
            
            print(f"Ciclo {contador}: DESLIGANDO todos os pinos")
            for pin in [pinos.P1, pinos.P2, pinos.P3, pinos.P4,
                       pinos.P5, pinos.P6, pinos.P7, pinos.P8]:
                pinos.desliga_pino(pin)
            
            time.sleep(0.5)
            contador += 1
            
    except KeyboardInterrupt:
        print("\n\nDesligando todos os pinos...")
        for pin in [pinos.P1, pinos.P2, pinos.P3, pinos.P4,
                   pinos.P5, pinos.P6, pinos.P7, pinos.P8]:
            pinos.desliga_pino(pin)
        print("Finalizado!")


def exemplo_sequencial():
    """Exemplo de sequência tipo 'corrida de LEDs'"""
    print("=== Exemplo Sequencial (Corrida de LEDs) ===\n")
    
    pinos = PinosDigitais()
    
    # Configurar todos como saída
    for pin in [pinos.P1, pinos.P2, pinos.P3, pinos.P4,
                pinos.P5, pinos.P6, pinos.P7, pinos.P8]:
        pinos.configura_pino(pin, Direction.OUTPUT)
        pinos.desliga_pino(pin)
    
    lista_pinos = [pinos.P1, pinos.P2, pinos.P3, pinos.P4,
                   pinos.P5, pinos.P6, pinos.P7, pinos.P8]
    
    print("Corrida de LEDs...")
    print("Ctrl+C para sair\n")
    
    try:
        while True:
            # Ida
            for i, pin in enumerate(lista_pinos):
                print(f"LED {i+1} (P{i+1})")
                pinos.liga_pino(pin)
                time.sleep(0.1)
                pinos.desliga_pino(pin)
            
            # Volta
            for i, pin in enumerate(reversed(lista_pinos)):
                print(f"LED {8-i} (P{8-i})")
                pinos.liga_pino(pin)
                time.sleep(0.1)
                pinos.desliga_pino(pin)
                
    except KeyboardInterrupt:
        print("\n\nDesligando todos os LEDs...")
        for pin in lista_pinos:
            pinos.desliga_pino(pin)
        print("Finalizado!")


def exemplo_inverte():
    """Exemplo usando o método inverte_pino()"""
    print("=== Exemplo Inversão de Estado ===\n")
    
    pinos = PinosDigitais()
    
    # Configurar P5-P8 como saída
    for pin in [pinos.P5, pinos.P6, pinos.P7, pinos.P8]:
        pinos.configura_pino(pin, Direction.OUTPUT)
        pinos.desliga_pino(pin)
    
    print("Invertendo estado dos pinos P5-P8 a cada 0.5s")
    print("Ctrl+C para sair\n")
    
    try:
        contador = 0
        while True:
            print(f"Ciclo {contador}: Invertendo P5-P8")
            pinos.inverte_pino(pinos.P5)
            pinos.inverte_pino(pinos.P6)
            pinos.inverte_pino(pinos.P7)
            pinos.inverte_pino(pinos.P8)
            
            time.sleep(0.5)
            contador += 1
            
    except KeyboardInterrupt:
        print("\n\nDesligando todos os LEDs...")
        for pin in [pinos.P5, pinos.P6, pinos.P7, pinos.P8]:
            pinos.desliga_pino(pin)
        print("Finalizado!")


def menu():
    """Menu principal"""
    print("\n" + "="*50)
    print("   EXEMPLOS - Classe PinosDigitais")
    print("   8 Pinos Digitais (Entrada/Saída)")
    print("="*50)
    print("\nEscolha um exemplo:")
    print("1 - Básico (Botões controlam LEDs)")
    print("2 - Pisca LED (todos os pinos)")
    print("3 - Sequencial (corrida de LEDs)")
    print("4 - Inversão de estado")
    print("0 - Sair")
    print()
    
    opcao = input("Digite a opção: ")
    
    if opcao == "1":
        exemplo_basico()
    elif opcao == "2":
        exemplo_pisca_led()
    elif opcao == "3":
        exemplo_sequencial()
    elif opcao == "4":
        exemplo_inverte()
    elif opcao == "0":
        print("Saindo...")
    else:
        print("Opção inválida!")
        menu()


if __name__ == "__main__":
    try:
        menu()
    except Exception as e:
        print(f"\nErro: {e}")
        import traceback
        traceback.print_exc()
