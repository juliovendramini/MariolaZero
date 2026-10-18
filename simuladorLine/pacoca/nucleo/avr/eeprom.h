// simulador: funções da avr-libc em cima da EEPROM do simulador
#include "../EEPROM.h"
static inline uint8_t eeprom_read_byte(const uint8_t *p) { return sim_eeprom_le((int)(intptr_t)p); }
static inline void eeprom_write_byte(uint8_t *p, uint8_t v) { sim_eeprom_escreve((int)(intptr_t)p, v); }
static inline void eeprom_update_byte(uint8_t *p, uint8_t v) { sim_eeprom_escreve((int)(intptr_t)p, v); }
static inline void eeprom_read_block(void *d, const void *s, size_t n) {
    for (size_t i = 0; i < n; i++) ((uint8_t *)d)[i] = sim_eeprom_le((int)(intptr_t)s + (int)i);
}
static inline void eeprom_write_block(const void *s, void *d, size_t n) {
    for (size_t i = 0; i < n; i++) sim_eeprom_escreve((int)(intptr_t)d + (int)i, ((const uint8_t *)s)[i]);
}
static inline void eeprom_update_block(const void *s, void *d, size_t n) { eeprom_write_block(s, d, n); }
static inline uint16_t eeprom_read_word(const uint16_t *p) { uint16_t v; eeprom_read_block(&v, p, 2); return v; }
static inline void eeprom_write_word(uint16_t *p, uint16_t v) { eeprom_write_block(&v, p, 2); }
static inline void eeprom_update_word(uint16_t *p, uint16_t v) { eeprom_write_block(&v, p, 2); }
