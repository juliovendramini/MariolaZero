/*!
 * Classe Teclado para controle de PCF8574A
 * Expansor de I/O I2C com 4 botões e 4 LEDs
 * Adaptado para uso com SoftWire por Julio Cesar Goldner Vendramini
 */
#ifndef _TECLADO_H_
#define _TECLADO_H_

#include <Arduino.h>
#include "SoftWire.h"
#include "portas.h"

#define PCF8574A_ADDRESS 0x38  /**< Endereço I2C padrão do PCF8574A */

class Teclado {
public:
    // Constantes para estado dos botões
    static const uint8_t LIBERADO = 1;
    static const uint8_t APERTADO = 0;

    /**
     * Construtor da classe Teclado
     * @param porta Porta I2C configurada (do arquivo portas.h)
     */
    Teclado(PortaI2C porta);

    /**
     * Configura o bus I2C
     * @param bus Ponteiro para o objeto SoftWire
     */
    void setBus(SoftWire * bus) { this->bus = bus; }
    
    /**
     * Retorna o bus I2C
     * @return Ponteiro para o objeto SoftWire
     */
    SoftWire * getBus() { return bus; }

    /**
     * Inicializa o PCF8574A
     * Configura pinos 0-3 como entrada (botões) e 4-7 como saída (LEDs)
     */
    void init();

    /**
     * Lê o estado de um botão
     * @param botao Número do botão (1 a 4)
     * @return Estado do botão (LIBERADO = 1 ou APERTADO = 0)
     */
    uint8_t leBotao(uint8_t botao);

    /**
     * Controla o estado de um LED
     * @param led Número do LED (1 a 4)
     * @param valor Estado desejado (true = ligado, false = desligado)
     */
    void alteraLed(uint8_t led, bool valor);

private:
    SoftWire * bus;
    uint8_t sda;
    uint8_t scl;
    char descricaoPorta[6];
    uint8_t address;
    uint8_t state;  // Estado atual dos pinos

    /**
     * Atualiza o estado dos pinos no PCF8574A
     */
    void atualizaEstado();

    /**
     * Configura os pinos (0-3 entrada, 4-7 saída)
     */
    void configuraPinos();

    /**
     * Escreve um byte no PCF8574A
     * @param data Byte a ser escrito
     */
    void writeByte(uint8_t data);

    /**
     * Lê um byte do PCF8574A
     * @return Byte lido
     */
    uint8_t readByte();
};

#endif /* _TECLADO_H_ */
