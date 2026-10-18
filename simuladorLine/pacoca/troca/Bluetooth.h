// simulador: o módulo bluetooth não recebe nada; o que for enviado aparece no terminal
#ifndef BLUETOOTH_SIM_H
#define BLUETOOTH_SIM_H
#include <Arduino.h>
#include "portas.h"

class Bluetooth : public Stream {
public:
    static Bluetooth *bluetooth_active_object;
    Bluetooth(PortaSerial) {}
    void begin() { Serial.println(F("Bluetooth inicializado (no simulador ele não recebe nada)")); }
    bool listen() { return true; }
    bool stopListening() { return true; }
    void end() {}
    bool isListening() { return true; }
    bool overflow() { return false; }
    int read() override { return -1; }
    int available() override { return 0; }
    size_t write(uint8_t b) override { return Serial.write(b); }
    using Print::write;
    void flush() override {}
    int peek() override { return -1; }
    operator bool() { return true; }
    void handle_interrupt() {}
};
inline Bluetooth *Bluetooth::bluetooth_active_object = nullptr;
#endif
