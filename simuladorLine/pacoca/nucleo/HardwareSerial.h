#ifndef SIM_HARDWARESERIAL_H
#define SIM_HARDWARESERIAL_H
#ifdef __cplusplus
#include "Arduino.h"

#define SERIAL_8N1 0x06
#define SERIAL_8N2 0x0E
#define SERIAL_8E1 0x26
#define SERIAL_7E1 0x24

// Serial (USB): o texto vai para o terminal do simulador. Escrever gasta o tempo da
// transmissão quando o buffer de 64 bytes enche, como no robô. Nada chega do PC.
class HardwareSerial : public Stream {
    unsigned long baud = 0;
    int64_t livre_em_ns = 0;   // quando o último byte do buffer termina de sair

public:
    void begin(unsigned long b) { baud = b ? b : 9600; }
    void begin(unsigned long b, uint8_t) { begin(b); }
    void end() { baud = 0; }
    int available() override { return 0; }
    int peek() override { return -1; }
    int read() override { return -1; }
    int availableForWrite() override { return 63; }
    void flush() override;
    size_t write(uint8_t c) override;
    using Print::write;
    operator bool() { return true; }
};

extern HardwareSerial Serial;

#endif
#endif
