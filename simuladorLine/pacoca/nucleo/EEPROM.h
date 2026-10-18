// EEPROM do simulador: 1 KB guardado num arquivo na pasta do programa (eeprom_pacoca.bin),
// então a calibração gravada continua lá na próxima rodada, como no robô.
#ifndef SIM_EEPROM_H
#define SIM_EEPROM_H
#include "Arduino.h"

uint8_t sim_eeprom_le(int idx);
void sim_eeprom_escreve(int idx, uint8_t v);

struct EERef {
    int index;
    EERef(int i) : index(i) {}
    operator uint8_t() const { return sim_eeprom_le(index); }
    EERef &operator=(uint8_t v) { sim_eeprom_escreve(index, v); return *this; }
    EERef &operator=(const EERef &r) { return *this = (uint8_t)r; }
    EERef &operator+=(uint8_t v) { return *this = (uint8_t)(*this + v); }
    EERef &operator-=(uint8_t v) { return *this = (uint8_t)(*this - v); }
    EERef &operator|=(uint8_t v) { return *this = (uint8_t)(*this | v); }
    EERef &operator&=(uint8_t v) { return *this = (uint8_t)(*this & v); }
    EERef &operator++() { return *this += 1; }
    EERef &operator--() { return *this -= 1; }
    uint8_t operator++(int) { uint8_t v = *this; ++(*this); return v; }
    uint8_t operator--(int) { uint8_t v = *this; --(*this); return v; }
    EERef &update(uint8_t v) { return v != (uint8_t)*this ? *this = v : *this; }
};

class EEPROMClass {
public:
    uint8_t read(int idx) { return sim_eeprom_le(idx); }
    void write(int idx, uint8_t v) { sim_eeprom_escreve(idx, v); }
    void update(int idx, uint8_t v) { sim_eeprom_escreve(idx, v); }
    EERef operator[](int idx) { return EERef(idx); }
    uint16_t length() { return 1024; }
    template <typename T> T &get(int idx, T &t) {
        uint8_t *p = (uint8_t *)&t;
        for (size_t i = 0; i < sizeof(T); i++) p[i] = sim_eeprom_le(idx + (int)i);
        return t;
    }
    template <typename T> const T &put(int idx, const T &t) {
        const uint8_t *p = (const uint8_t *)&t;
        for (size_t i = 0; i < sizeof(T); i++) sim_eeprom_escreve(idx + (int)i, p[i]);
        return t;
    }
};

extern EEPROMClass EEPROM;
#endif
