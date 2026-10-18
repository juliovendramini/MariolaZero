#include "Arduino.h"
#include "../troca/SoftWire.h"
#include "sim_ponte.h"

// I2C por software do brick: ~2 us de meio período + o código em volta
static const int64_t BYTE_NS = 50000;      // 8 bits + ACK
static const int64_t START_STOP_NS = 12000;

static uint8_t transacao_escreve(uint8_t sda, uint8_t scl, uint8_t addr, const uint8_t *b, uint8_t n) {
    sim_custo_ns(START_STOP_NS + (int64_t)(n + 1) * BYTE_NS);
    SimReq r;
    SimResp s;
    r.u8(sda);
    r.u8(scl);
    r.u8(addr);
    r.u8(n);
    r.bytes(b, n);
    if (!sim_chamar(OP_I2C_ESCREVE, r, s)) return 2;
    return s.u8();
}

static uint8_t transacao_le(uint8_t sda, uint8_t scl, uint8_t addr, uint8_t *b, uint8_t n, uint8_t *status) {
    SimReq r;
    SimResp s;
    r.u8(sda);
    r.u8(scl);
    r.u8(addr);
    r.u8(n);
    if (!sim_chamar(OP_I2C_LE, r, s)) {
        sim_custo_ns(START_STOP_NS + BYTE_NS);
        *status = 2;
        return 0;
    }
    *status = s.u8();
    uint8_t k = s.u8();
    for (uint8_t i = 0; i < k; i++) b[i] = s.u8();
    sim_custo_ns(START_STOP_NS + (int64_t)(*status == 0 ? n + 1 : 1) * BYTE_NS);
    return *status == 0 ? k : 0;
}

void SoftWire::beginTransmission(uint8_t address) {
    _txAddress = address;
    _txN = 0;
    _transmitindo = true;
}

size_t SoftWire::write(uint8_t data) {
    if (!_transmitindo || _txN >= sizeof _txBuffer) {
        setWriteError();
        return 0;
    }
    _txBuffer[_txN++] = data;
    return 1;
}

size_t SoftWire::write(const uint8_t *data, size_t quantity) {
    size_t n = 0;
    for (size_t i = 0; i < quantity; i++) n += write(data[i]);
    return n;
}

uint8_t SoftWire::endTransmission(uint8_t) {
    _transmitindo = false;
    // 0 = ok, 2 = NACK no endereço (como o Wire)
    return transacao_escreve(_sda, _scl, _txAddress, _txBuffer, _txN);
}

uint8_t SoftWire::requestFrom(uint8_t address, uint8_t quantity, uint8_t) {
    if (quantity > sizeof _rxBuffer) quantity = sizeof _rxBuffer;
    uint8_t st = 0;
    _rxN = transacao_le(_sda, _scl, address, _rxBuffer, quantity, &st);
    _rxI = 0;
    return _rxN;
}

int SoftWire::available(void) { return _rxN - _rxI; }

int SoftWire::read(void) {
    if (_rxI < _rxN) return _rxBuffer[_rxI++];
    return -1;
}

int SoftWire::peek(void) {
    if (_rxI < _rxN) return _rxBuffer[_rxI];
    return -1;
}

SoftWire::result_t SoftWire::llStart(uint8_t rawAddr) {
    if (_llAberto && !_llLeitura && _llN) {
        transacao_escreve(_sda, _scl, _llAddr, _llBuf, _llN);     // repeated start
    }
    _llAberto = true;
    _llAddr = rawAddr >> 1;
    _llLeitura = rawAddr & 1;
    _llN = 0;
    _llLidos = 0;
    if (!_llLeitura) return ack;
    return ack;
}

SoftWire::result_t SoftWire::llWrite(uint8_t data) {
    if (!_llAberto || _llLeitura || _llN >= sizeof _llBuf) return nack;
    _llBuf[_llN++] = data;
    return ack;
}

SoftWire::result_t SoftWire::llRead(uint8_t &data, bool) {
    if (!_llAberto || !_llLeitura || _llLidos >= sizeof _llBuf) return nack;
    // lê de novo do começo até este byte (o sensor simulado não guarda posição entre leituras)
    uint8_t st = 0;
    uint8_t buf[32];
    uint8_t k = transacao_le(_sda, _scl, _llAddr, buf, (uint8_t)(_llLidos + 1), &st);
    if (st != 0 || k <= _llLidos) return nack;
    data = buf[_llLidos++];
    return ack;
}

SoftWire::result_t SoftWire::stop(bool) {
    if (_llAberto && !_llLeitura) {
        uint8_t st = transacao_escreve(_sda, _scl, _llAddr, _llBuf, _llN);
        _llAberto = false;
        return st == 0 ? ack : nack;
    }
    _llAberto = false;
    return ack;
}
