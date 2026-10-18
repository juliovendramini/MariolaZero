#include "Arduino.h"
#include "../troca/SoftwareSerial.h"
#include "sim_ponte.h"

// tempos do readByteDirect() do brick a 16 MHz
static const int64_t LOOP_ESPERA_NS = 440;   // cada volta do while esperando o start bit (~7 ciclos)
static const int64_t CENTRO_NS = 2000;       // _rx_delay_centering
static const int64_t STOP_NS = 8000;         // _rx_delay_stopbit
static const int64_t CUSTO_AVAILABLE_NS = 500;

SoftwareSerial::SoftwareSerial(uint8_t receivePin, uint8_t transmitPin)
    : _receivePin(receivePin), _transmitPin(transmitPin) {
    pinMode(transmitPin, OUTPUT);
    digitalWrite(transmitPin, HIGH);
    pinMode(receivePin, INPUT);
    digitalWrite(receivePin, HIGH);
}

void SoftwareSerial::begin(long speed) {
    _baud = speed > 0 ? (uint32_t)speed : 9600;
    _bit_ns = 1000000000LL / _baud;
    sim_custo_ns(_bit_ns);
}

void SoftwareSerial::limpaVelhos() {
    // tira da linha os bytes que já terminaram há mais de 1 ms
    int k = 0;
    for (int i = 0; i < _n; i++) {
        if (_linha[i].t + 10 * _bit_ns + 1000000 > sim_t_ns) _linha[k++] = _linha[i];
    }
    _n = k;
}

int SoftwareSerial::nivel(int64_t t) const {
    for (int i = 0; i < _n; i++) {
        int64_t d = t - _linha[i].t;
        if (d < 0 || d >= 10 * _bit_ns) continue;
        int bit = (int)(d / _bit_ns);
        if (bit == 0) return LOW;          // start
        if (bit == 9) return HIGH;         // stop
        return (_linha[i].b >> (bit - 1)) & 1;
    }
    return HIGH;
}

int64_t SoftwareSerial::proximoLow(int64_t t) const {
    int64_t melhor = INT64_MAX;
    for (int i = 0; i < _n; i++) {
        for (int bit = 0; bit < 9; bit++) {
            bool low = bit == 0 ? true : !((_linha[i].b >> (bit - 1)) & 1);
            if (!low) continue;
            int64_t a = _linha[i].t + bit * _bit_ns;
            int64_t b = a + _bit_ns;
            if (b <= t) continue;
            int64_t c = a > t ? a : t;
            if (c < melhor) melhor = c;
            break;                          // o primeiro LOW deste byte depois de t
        }
    }
    return melhor;
}

size_t SoftwareSerial::write(uint8_t b) {
    if (_bit_ns == 0) {
        setWriteError();
        return 0;
    }
    // start + 8 bits + stop, mais o tunedDelay do fim
    int64_t inicio = sim_t_ns;
    sim_custo_ns(11 * _bit_ns);
    SimReq r;
    SimResp s;
    r.u8(_receivePin);
    r.u8(_transmitPin);
    r.u32(_baud);
    r.i64(inicio);
    r.u8(b);
    if (sim_chamar(OP_SERIAL_TX, r, s)) {
        limpaVelhos();
        uint16_t n = s.u16();
        for (uint16_t i = 0; i < n; i++) {
            int64_t t = s.i64();
            uint8_t v = s.u8();
            if (_n < MAX_LINHA) _linha[_n++] = {t, v};
        }
    }
    return 1;
}

int SoftwareSerial::available() {
    sim_custo_ns(CUSTO_AVAILABLE_NS);
    return nivel(sim_t_ns) == LOW ? 1 : 0;
}

int SoftwareSerial::readByteDirect() {
    int64_t agora = sim_t_ns;
    int64_t limite = agora + (int64_t)_timeout_loops * LOOP_ESPERA_NS;
    int64_t borda = proximoLow(agora);
    if (borda > limite) {
        sim_custo_ns(limite - agora);
        return -1;
    }
    // o while só percebe o LOW na volta seguinte
    int64_t voltas = (borda - agora + LOOP_ESPERA_NS - 1) / LOOP_ESPERA_NS;
    sim_t_ns = agora + voltas * LOOP_ESPERA_NS;
    int64_t t = sim_t_ns + CENTRO_NS;
    uint8_t d = 0;
    for (int i = 0; i < 8; i++) {
        t += _bit_ns;
        d >>= 1;
        if (nivel(t)) d |= 0x80;
    }
    t += STOP_NS;
    sim_custo_ns(t - sim_t_ns);
    return d;
}

int SoftwareSerial::read() { return readByteDirect(); }

size_t SoftwareSerial::readBytes(uint8_t *buffer, size_t length) {
    size_t count = 0;
    while (count < length) {
        int c = readByteDirect();
        if (c < 0) break;
        buffer[count++] = (uint8_t)c;
    }
    return count;
}
