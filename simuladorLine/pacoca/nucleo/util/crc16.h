#include "../Arduino.h"
static inline uint16_t _crc16_update(uint16_t crc, uint8_t a) {
    crc ^= a;
    for (int i = 0; i < 8; ++i) crc = (crc & 1) ? (crc >> 1) ^ 0xA001 : (crc >> 1);
    return crc;
}
static inline uint8_t _crc_ibutton_update(uint8_t crc, uint8_t data) {
    crc = crc ^ data;
    for (uint8_t i = 0; i < 8; i++) crc = (crc & 0x01) ? (crc >> 1) ^ 0x8C : (crc >> 1);
    return crc;
}
static inline uint8_t _crc8_ccitt_update(uint8_t crc, uint8_t data) {
    crc = crc ^ data;
    for (uint8_t i = 0; i < 8; i++) crc = (crc & 0x80) ? (crc << 1) ^ 0x07 : (crc << 1);
    return crc;
}
