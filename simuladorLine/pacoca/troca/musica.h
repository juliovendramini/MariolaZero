// simulador: a música não toca; cada música aparece no terminal e "dura" o tempo das notas
#ifndef MUSICA_H
#define MUSICA_H
#include "motorAudio.h"
#include "portas.h"

class Musica {
    uint32_t fim = 0;
public:
    enum Timbre { QUADRADA = MUS_QUADRADA, TRIANGULAR = MUS_TRIANGULAR, SENOIDAL = MUS_SENOIDAL,
                  DENTE_DE_SERRA = MUS_DENTE_DE_SERRA };
    Musica(PortaBuzzer, bool = true) {}
    void inicializa() { Serial.println(F("Musica inicializada (o simulador não toca som)")); }
    void tocar(const char *rtttl) {
        Serial.print(F("[musica] "));
        Serial.println(rtttl);
        fim = millis() + 2000;
    }
    void tocar(const __FlashStringHelper *r) { tocar((const char *)r); }
    void tocarAteOFim(const char *r) { tocar(r); aguarda(); }
    void tocarAteOFim(const __FlashStringHelper *r) { tocar((const char *)r); aguarda(); }
    void nota(uint16_t, uint16_t duracaoMs) { fim = millis() + duracaoMs; }
    void notaAteOFim(uint16_t f, uint16_t d) { nota(f, d); aguarda(); }
    bool tocando() { return (int32_t)(millis() - fim) < 0; }
    void aguarda() { while (tocando()) delay(1); }
    void parar() { fim = millis(); }
    void repetir(bool) {}
    void volume(uint8_t) {}
    void timbre(Timbre) {}
    void decaimento(bool) {}
};
#endif
