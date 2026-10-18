// simulador: a fala não toca; cada fala aparece no terminal e "dura" 1 s
#ifndef VOZ_H
#define VOZ_H
#include "motorAudio.h"
#include "portas.h"

class Voz {
    uint32_t fim = 0;
public:
    Voz(PortaBuzzer, bool = true) {}
    void inicializa() { Serial.println(F("Voz inicializada (o simulador não toca som)")); }
    void falar(const uint8_t *fala) { iniciaFala(fala); aguarda(); }
    void iniciaFala(const uint8_t *) { Serial.println(F("[voz] fala")); fim = millis() + 1000; }
    void falarRam(const uint8_t *d, uint16_t) { falar(d); }
    void iniciaFalaRam(const uint8_t *d, uint16_t) { iniciaFala(d); }
    bool falando() { return (int32_t)(millis() - fim) < 0; }
    void aguarda() { while (falando()) delay(1); }
    void parar() { fim = millis(); }
    void volume(uint16_t) {}
    uint16_t atrasos() { return 0; }
    void atualizaSerial(Stream &) {}
    bool falarDaSerial(Stream &, uint16_t = 3000) { return false; }
    void comecaStream() {}
    void iniciaStream() {}
};
#endif
