// SoftwareSerial do simulador, com o mesmo comportamento da versão do brick:
// sem buffer e sem interrupção. O que o sensor manda de volta vira a forma de onda da linha RX
// (start bit, 8 bits, stop bit); available() olha se a linha está em LOW agora e read()
// espera a próxima borda de descida e amostra os bits com o mesmo tempo do código do AVR.
// Quem não estiver lendo quando os bytes chegam perde os bytes, como no robô.
#ifndef SoftwareSerial_h
#define SoftwareSerial_h

#include <Arduino.h>

#ifndef _SS_MAX_RX_BUFF
#define _SS_MAX_RX_BUFF 64
#endif

class SoftwareSerial : public Stream {
public:
    struct ByteLinha {
        int64_t t;      // início do start bit (ns)
        uint8_t b;
    };

private:
    uint8_t _receivePin;
    uint8_t _transmitPin;
    uint32_t _baud = 0;
    int64_t _bit_ns = 0;
    uint16_t _timeout_loops = 30000;
    static const int MAX_LINHA = 256;
    ByteLinha _linha[MAX_LINHA];
    int _n = 0;

    int nivel(int64_t t) const;               // nível da linha RX no instante t
    int64_t proximoLow(int64_t t) const;       // primeiro instante >= t com a linha em LOW
    void limpaVelhos();
    int readByteDirect();

public:
    SoftwareSerial(uint8_t receivePin, uint8_t transmitPin);
    ~SoftwareSerial() {}
    void begin(long speed);
    void end() {}
    void setTimeout(unsigned long timeout_ms) {
        _timeout_loops = (uint16_t)((timeout_ms * (F_CPU / 1000)) / 3);   // como no brick (uint16_t)
    }
    bool listen() { return true; }
    bool isListening() { return true; }
    bool overflow() { return false; }
    int peek() override { return -1; }

    size_t write(uint8_t byte) override;
    int read() override;
    int available() override;
    void flush() override {}
    size_t readBytes(uint8_t *buffer, size_t length) override;
    size_t readBytes(char *buffer, size_t length) override { return readBytes((uint8_t *)buffer, length); }
    operator bool() { return true; }

    using Print::write;
};

#endif
