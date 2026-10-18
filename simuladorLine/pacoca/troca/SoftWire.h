// SoftWire do simulador: mesma interface da lib do brick, mas cada transação I2C vai inteira
// para a ponte, que responde como o sensor ligado naquela porta (robo_pacoca.json).
// O tempo gasto é o do I2C por software do brick (~50 us por byte).
#ifndef SOFTWIRE_H
#define SOFTWIRE_H

#include <Arduino.h>
#include <stdint.h>
#include "AsyncDelay.h"

#define DELAY_TIME_US 1

class SoftWire : public Stream {
public:
    enum result_t {
        ack = 0,
        nack = 1,
        timedOut = 2,
    };
    enum mode_t {
        writeMode = 0,
        readMode = 1,
    };

    static const uint8_t defaultDelay_us = 2;
    static const uint16_t defaultTimeout_ms = 100;

    static uint8_t crc8_update(uint8_t crc, uint8_t data) {
        const uint16_t polynomial = 0x107;
        crc ^= data;
        for (uint8_t i = 8; i; --i) {
            if (crc & 0x80) crc = (uint16_t(crc) << 1) ^ polynomial;
            else crc <<= 1;
        }
        return crc;
    }

    SoftWire(uint8_t sda, uint8_t scl) : _sda(sda), _scl(scl) {}
    uint8_t getSda(void) const { return _sda; }
    uint8_t getScl(void) const { return _scl; }
    uint8_t getDelay_us(void) const { return _delay_us; }
    uint16_t getTimeout_ms(void) const { return _timeout_ms; }
    uint8_t getInputMode(void) const { return INPUT_PULLUP; }
    void setSda(uint8_t sda) { _sda = sda; }
    void setScl(uint8_t scl) { _scl = scl; }
    void enablePullups(bool = true) {}
    void setDelay_us(uint8_t d) { _delay_us = d; }
    void setTimeout_ms(uint16_t t) { _timeout_ms = t; }
    void setClock(uint32_t) {}
    void begin(void) const {}
    void end(void) {}

    // interface do Wire
    void beginTransmission(uint8_t address);
    void beginTransmission(int address) { beginTransmission((uint8_t)address); }
    uint8_t endTransmission(uint8_t sendStop);
    uint8_t endTransmission(void) { return endTransmission(true); }
    uint8_t requestFrom(uint8_t address, uint8_t quantity, uint8_t sendStop = true);
    uint8_t requestFrom(int address, int quantity, int sendStop = 1) {
        return requestFrom((uint8_t)address, (uint8_t)quantity, (uint8_t)sendStop);
    }
    int available(void) override;
    size_t write(uint8_t data) override;
    size_t write(const uint8_t *data, size_t quantity) override;
    int read(void) override;
    int peek(void) override;
    void flush(void) override {}

    // nível baixo (transações montadas à mão): start/escreve/lê/stop
    result_t llStart(uint8_t rawAddr);
    result_t llRepeatedStart(uint8_t rawAddr) { return llStart(rawAddr); }
    result_t llStartWait(uint8_t rawAddr) { return llStart(rawAddr); }
    result_t stop(bool = true);
    result_t startRead(uint8_t addr) { return llStart((addr << 1) | 1); }
    result_t startWrite(uint8_t addr) { return llStart(addr << 1); }
    result_t repeatedStartRead(uint8_t addr) { return llStart((addr << 1) | 1); }
    result_t repeatedStartWrite(uint8_t addr) { return llStart(addr << 1); }
    result_t startReadWait(uint8_t addr) { return llStart((addr << 1) | 1); }
    result_t startWriteWait(uint8_t addr) { return llStart(addr << 1); }
    result_t start(uint8_t addr, mode_t rw) { return llStart((addr << 1) | rw); }
    result_t repeatedStart(uint8_t addr, mode_t rw) { return llStart((addr << 1) | rw); }
    result_t startWait(uint8_t addr, mode_t rw) { return llStart((addr << 1) | rw); }
    result_t llWrite(uint8_t data);
    result_t llRead(uint8_t &data, bool sendAck = true);
    result_t readThenAck(uint8_t &data) { return llRead(data, true); }
    result_t readThenNack(uint8_t &data) { return llRead(data, false); }

private:
    uint8_t _sda, _scl;
    uint8_t _delay_us = defaultDelay_us;
    uint16_t _timeout_ms = defaultTimeout_ms;

    uint8_t _txAddress = 0;
    uint8_t _txBuffer[32];
    uint8_t _txN = 0;
    bool _transmitindo = false;
    uint8_t _rxBuffer[32];
    uint8_t _rxN = 0;
    uint8_t _rxI = 0;

    // nível baixo
    bool _llAberto = false;
    bool _llLeitura = false;
    uint8_t _llAddr = 0;
    uint8_t _llBuf[32];
    uint8_t _llN = 0;
    uint8_t _llLidos = 0;
};

#endif
