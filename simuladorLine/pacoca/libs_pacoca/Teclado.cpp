/*!
 * Implementação da classe Teclado para controle de PCF8574A
 * Expansor de I/O I2C com 4 botões e 4 LEDs
 * Adaptado para uso com SoftWire por Julio Cesar Goldner Vendramini
 */

#include "Teclado.h"

Teclado::Teclado(PortaI2C porta)
{
    this->sda = porta.sda;
    this->scl = porta.scl;
    strcpy(this->descricaoPorta, porta.descricao);
    this->bus = NULL;
    this->address = PCF8574A_ADDRESS;
    this->state = 0xFF;  // Estado inicial: todos os pinos como entrada
}

void Teclado::init()
{
    this->bus = new SoftWire(this->sda, this->scl);
    this->bus->setTimeout_ms(10);
    this->bus->begin();
    this->bus->setTimeout_ms(10);
    
    // Verifica se o PCF8574A está presente
    // Tenta ler o estado dos pinos
    this->state = 0xFF;
    writeByte(this->state);
    uint8_t leitura = readByte();
    
    // Se a leitura retornar 0xFF constantemente, pode ser que não haja dispositivo
    // Vamos tentar uma segunda vez com um padrão diferente
    if (leitura == 0xFF) {
        delay(3);
        this->state = 0x00;
        writeByte(this->state);
        leitura = readByte();
        
        // Se ainda retornar o mesmo valor ou se não conseguiu comunicar
        if (leitura == 0xFF) {
            Serial.print(F("Erro ao detectar o Teclado na porta "));
            Serial.println(this->descricaoPorta);
            while(1);
        }
    }
    
    Serial.print(F("Teclado detectado com sucesso na porta "));
    Serial.println(this->descricaoPorta);
    
    // Configura os pinos: 0-3 entrada (botões), 4-7 saída (LEDs)
    configuraPinos();
}

void Teclado::configuraPinos()
{
    // Pinos 0-3 como entrada (1), pinos 4-7 como saída (0)
    // 0x0F = 0b00001111
    this->state = 0x0F;
    atualizaEstado();
}

void Teclado::atualizaEstado()
{
    writeByte(this->state);
}

void Teclado::writeByte(uint8_t data)
{
    if (bus == NULL) return;
    
    bus->beginTransmission(this->address);
    bus->write(data);
    bus->endTransmission();
}

uint8_t Teclado::readByte()
{
    if (bus == NULL) return 0xFF;
    
    bus->requestFrom(this->address, (uint8_t)1);
    
    if (bus->available()) {
        return bus->read();
    }
    
    return 0xFF;
}

uint8_t Teclado::leBotao(uint8_t botao)
{
    // Valida o número do botão (1 a 4)
    if (botao < 1 || botao > 4) {
        Serial.print(F("Erro: Botao invalido ("));
        Serial.print(botao);
        Serial.println(F("). Use valores de 1 a 4."));
        return LIBERADO;
    }
    
    // Converter índice 1-4 para 0-3
    uint8_t pino = botao - 1;
    
    // Lê o estado atual dos pinos
    uint8_t leitura = readByte();
    
    // Extrai o bit correspondente ao botão
    return (leitura >> pino) & 0x01;
}

void Teclado::alteraLed(uint8_t led, bool valor)
{
    // Valida o número do LED (1 a 4)
    if (led < 1 || led > 4) {
        Serial.print(F("Erro: LED invalido ("));
        Serial.print(led);
        Serial.println(F("). Use valores de 1 a 4."));
        return;
    }
    
    // Converter índice 1-4 para 4-7
    uint8_t pino = led + 3;
    
    if (valor) {
        // Define o pino como alto (1) - LED ligado
        this->state |= (1 << pino);
    } else {
        // Define o pino como baixo (0) - LED desligado
        this->state &= ~(1 << pino);
    }
    
    atualizaEstado();
}
