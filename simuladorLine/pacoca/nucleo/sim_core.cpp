// Núcleo do Arduino simulado: relógio virtual, pinos, Serial, EEPROM e o main().
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <string>

#include "Arduino.h"
#include "EEPROM.h"
#include "sim_ponte.h"

extern "C" {
volatile uint8_t __sim_regs[256];
}

// ============================================================== relógio
// sim_t_ns é o tempo "de verdade" do robô (o mesmo da física). O millis()/micros() do AVR
// atrasa um pouco quando as interrupções ficam desligadas mais de 1 ms (o Timer0 perde
// estouros), e isso também é imitado.
int64_t sim_t_ns = 0;
static int64_t t_sincronizado = 0;
static const int64_t SYNC_NS = 10000000;     // conversa com a ponte pelo menos a cada 10 ms
static const int64_t T0_NS = 1024000;        // estouro do Timer0 (prescaler 64): 1,024 ms
static int64_t perdido_ns = 0;               // estouros perdidos com as interrupções desligadas
static int64_t t_cli = 0;
static bool interrupcoes = true;

// custos aproximados no ATmega a 16 MHz (ns)
static const int64_t C_DIGITALWRITE = 3600, C_DIGITALREAD = 3200, C_PINMODE = 3600, C_ANALOGWRITE = 6000,
                     C_ANALOGREAD = 112000, C_MILLIS = 1200, C_MICROS = 3500, C_LOOP = 1000;

void sim_custo_ns(int64_t ns) {
    if (ns > 0) sim_t_ns += ns;
    if (sim_t_ns - t_sincronizado >= SYNC_NS) sim_sincroniza();
}

bool sim_chamar(uint8_t op, const SimReq &req, SimResp &resp) {
    t_sincronizado = sim_t_ns;
    return sim_rede_chamar(op, sim_t_ns, req, resp);
}

void sim_sincroniza(void) {
    SimReq r;
    SimResp s;
    sim_chamar(OP_SYNC, r, s);
}

extern "C" void sim_gasta_us(double us) { sim_custo_ns((int64_t)(us * 1000.0)); }
extern "C" void sim_gasta_ciclos(uint32_t ciclos) { sim_custo_ns((int64_t)ciclos * 1000 / 16); }

extern "C" void sim_cli(void) {
    if (interrupcoes) {
        interrupcoes = false;
        t_cli = sim_t_ns;
    }
}

extern "C" void sim_sei(void) {
    if (!interrupcoes) {
        interrupcoes = true;
        int64_t n = sim_t_ns / T0_NS - t_cli / T0_NS;
        if (n > 1) perdido_ns += (n - 1) * T0_NS;      // só um estouro fica pendente
    }
}

SimSREG SREG;
SimSREG::operator uint8_t() const { return interrupcoes ? 0x80 : 0x00; }
SimSREG &SimSREG::operator=(uint8_t v) {
    if (v & 0x80) sim_sei();
    else sim_cli();
    return *this;
}
SimSREG &SimSREG::operator|=(uint8_t v) { return *this = (uint8_t)(*this | v); }
SimSREG &SimSREG::operator&=(uint8_t v) { return *this = (uint8_t)(*this & v); }

// micros do AVR: com as interrupções desligadas o contador de estouros não anda (só um
// estouro pendente é contado) e o valor "dá a volta" a cada 1,024 ms
static int64_t avr_ns(void) {
    int64_t t = sim_t_ns;
    if (!interrupcoes) {
        int64_t c0 = t_cli / T0_NS;
        int64_t k = t / T0_NS - c0;
        if (k > 1) t = (c0 + 1) * T0_NS + (t % T0_NS);
    }
    return t - perdido_ns;
}

extern "C" unsigned long millis(void) {
    sim_custo_ns(C_MILLIS);
    int64_t t = interrupcoes ? sim_t_ns : t_cli;     // o millis só anda na interrupção
    return (unsigned long)(uint32_t)((t - perdido_ns) / 1000000);
}

extern "C" unsigned long micros(void) {
    sim_custo_ns(C_MICROS);
    return (unsigned long)(uint32_t)((avr_ns() / 4000) * 4);   // resolução de 4 us
}

extern "C" void delay(unsigned long ms) {
    // o delay() do AVR conta com o micros(); aqui o tempo passa em pedaços para a física acompanhar
    int64_t fim = sim_t_ns + (int64_t)ms * 1000000 + 2000;
    while (sim_t_ns < fim) {
        int64_t passo = fim - sim_t_ns;
        if (passo > SYNC_NS) passo = SYNC_NS;
        sim_custo_ns(passo);
    }
}

extern "C" void delayMicroseconds(unsigned int us) {
    sim_custo_ns((int64_t)us * 1000 + 500);
}

extern "C" void yield(void) {}

// ============================================================== pinos
static uint8_t modo[32];
static uint8_t nivel[32];
static uint8_t pwm[32];
static bool eh_entrada_ponte[32];      // botões, para-choque... (a ponte responde)
static bool eh_analogico_ponte[32];
static bool eh_saida_ponte[32];        // pinos dos motores
static bool eh_echo_ponte[32];
static uint16_t bateria_mv = 3900;

static void ponte_saida(uint8_t pin, uint8_t valor) {
    if (pin >= 32 || !eh_saida_ponte[pin]) return;
    SimReq r;
    SimResp s;
    r.u8(pin);
    r.u8(valor);
    sim_chamar(OP_PINO_SAIDA, r, s);
}

extern "C" void pinMode(uint8_t pin, uint8_t m) {
    sim_custo_ns(C_PINMODE);
    if (pin >= 32) return;
    modo[pin] = m;
    if (m == INPUT_PULLUP) nivel[pin] = 1;
}

extern "C" void digitalWrite(uint8_t pin, uint8_t val) {
    sim_custo_ns(C_DIGITALWRITE);
    if (pin >= 32) return;
    val = val ? 1 : 0;
    uint8_t novo = val ? 255 : 0;
    bool mudou = (pwm[pin] != novo) || (nivel[pin] != val);
    nivel[pin] = val;
    pwm[pin] = novo;
    if (mudou) ponte_saida(pin, novo);
}

extern "C" void analogWrite(uint8_t pin, int val) {
    sim_custo_ns(C_ANALOGWRITE);
    if (pin >= 32) return;
    if (val < 0) val = 0;
    if (val > 255) val = 255;
    uint8_t v = (uint8_t)val;
    bool mudou = pwm[pin] != v;
    pwm[pin] = v;
    nivel[pin] = v >= 128;
    if (mudou) ponte_saida(pin, v);
}

extern "C" int digitalRead(uint8_t pin) {
    sim_custo_ns(C_DIGITALREAD);
    if (pin >= 32) return LOW;
    if (eh_entrada_ponte[pin]) {
        SimReq r;
        SimResp s;
        r.u8(pin);
        sim_chamar(OP_PINO_ENTRADA, r, s);
        return s.u8() ? HIGH : LOW;
    }
    if (modo[pin] == OUTPUT) return nivel[pin];
    return modo[pin] == INPUT_PULLUP ? HIGH : LOW;
}

extern "C" int analogRead(uint8_t pin) {
    sim_custo_ns(C_ANALOGREAD);
    if (pin < 14) pin += 14;            // analogRead(6) == analogRead(A6)
    if (pin == 21) return (int)((uint32_t)bateria_mv * 1023 / 5000);
    if (pin < 32 && (eh_analogico_ponte[pin] || eh_entrada_ponte[pin])) {
        SimReq r;
        SimResp s;
        r.u8(pin);
        sim_chamar(OP_ANALOGICO, r, s);
        return s.u16();
    }
    if (pin < 32 && modo[pin] == INPUT_PULLUP) return 1023;
    return 0;
}

extern "C" void analogReference(uint8_t) {}

unsigned long pulseInLong(uint8_t pin, uint8_t state, unsigned long timeout) { return pulseIn(pin, state, timeout); }

extern "C" unsigned long pulseIn(uint8_t pin, uint8_t state, unsigned long timeout) {
    // só faz sentido no pino ECHO de um ultrassom do robo_pacoca.json
    if (pin < 32 && eh_echo_ponte[pin] && state == HIGH) {
        SimReq r;
        SimResp s;
        r.u8(0);
        r.u8(pin);
        sim_chamar(OP_ULTRASSOM, r, s);
        int32_t mm = s.i32();
        if (mm >= 0) {
            unsigned long dur = (unsigned long)(mm * 5.83);
            if (dur + 460 <= timeout) {
                sim_custo_ns((int64_t)(460 + dur) * 1000);
                return dur;
            }
        }
    }
    sim_custo_ns((int64_t)timeout * 1000);
    return 0;
}

unsigned long pulseIn(uint8_t pin, uint8_t state) { return pulseIn(pin, state, 1000000UL); }

extern "C" void shiftOut(uint8_t dataPin, uint8_t clockPin, uint8_t bitOrder, uint8_t val) {
    for (uint8_t i = 0; i < 8; i++) {
        digitalWrite(dataPin, bitOrder == LSBFIRST ? (val >> i) & 1 : (val >> (7 - i)) & 1);
        digitalWrite(clockPin, HIGH);
        digitalWrite(clockPin, LOW);
    }
}

extern "C" uint8_t shiftIn(uint8_t dataPin, uint8_t clockPin, uint8_t bitOrder) {
    uint8_t v = 0;
    for (uint8_t i = 0; i < 8; i++) {
        digitalWrite(clockPin, HIGH);
        if (bitOrder == LSBFIRST) v |= digitalRead(dataPin) << i;
        else v |= digitalRead(dataPin) << (7 - i);
        digitalWrite(clockPin, LOW);
    }
    return v;
}

extern "C" void attachInterrupt(uint8_t, void (*)(void), int) {
    static bool avisou = false;
    if (!avisou) {
        avisou = true;
        const char *m = "[simulador] attachInterrupt: interrupções externas não são simuladas\n";
        sim_saida(m, (int)strlen(m));
    }
}
extern "C" void detachInterrupt(uint8_t) {}

void tone(uint8_t, unsigned int, unsigned long) {}
void noTone(uint8_t) {}

void sim_leds(uint8_t pino, const uint8_t *rgb, uint8_t n) {
    SimReq r;
    SimResp s;
    r.u8(pino);
    r.u8(n);
    r.bytes(rgb, 3 * n);
    sim_chamar(OP_LEDS, r, s);
}

// ============================================================== matemática
// random() igual ao da avr-libc (mesma sequência do robô)
static unsigned long semente_random = 1;
static long avr_random(void) {
    long hi, lo, x = (long)semente_random;
    if (x == 0) x = 123459876L;
    hi = x / 127773L;
    lo = x % 127773L;
    x = 16807L * lo - 2836L * hi;
    if (x < 0) x += 0x7fffffffL;
    semente_random = (unsigned long)x;
    return x % (0x7fffffffL + 1L);
}
long random(long howbig) { return howbig == 0 ? 0 : avr_random() % howbig; }
long random(long howsmall, long howbig) {
    if (howsmall >= howbig) return howsmall;
    return random(howbig - howsmall) + howsmall;
}
void randomSeed(unsigned long seed) { if (seed != 0) semente_random = seed; }
long map(long x, long in_min, long in_max, long out_min, long out_max) {
    if (in_max == in_min) return out_min;
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}
uint16_t makeWord(uint16_t w) { return w; }
uint16_t makeWord(uint8_t h, uint8_t l) { return (uint16_t)((h << 8) | l); }

// ============================================================== Serial
HardwareSerial Serial;

size_t HardwareSerial::write(uint8_t c) {
    sim_custo_ns(1500);
    if (baud) {
        int64_t bit = (int64_t)10000000000LL / (int64_t)baud;     // 10 bits por byte
        if (livre_em_ns < sim_t_ns) livre_em_ns = sim_t_ns;
        livre_em_ns += bit;
        int64_t espera = livre_em_ns - 64 * bit - sim_t_ns;       // buffer de 64 bytes cheio
        if (espera > 0) sim_custo_ns(espera);
    }
    char ch = (char)c;
    sim_saida(&ch, 1);
    return 1;
}

void HardwareSerial::flush() {
    if (livre_em_ns > sim_t_ns) sim_custo_ns(livre_em_ns - sim_t_ns);
}

size_t Print::printf(const char *fmt, ...) {
    char buf[256];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    if (n < 0) return 0;
    if (n >= (int)sizeof buf) n = (int)sizeof buf - 1;
    return write((const uint8_t *)buf, (size_t)n);
}

// ============================================================== EEPROM (arquivo na pasta do programa)
static uint8_t eeprom[1024];
static bool eeprom_carregada = false;
static std::string eeprom_arquivo;

static void eeprom_carrega(void) {
    if (eeprom_carregada) return;
    eeprom_carregada = true;
    memset(eeprom, 0xFF, sizeof eeprom);
    const char *a = getenv("PACOCA_EEPROM");
    eeprom_arquivo = a && *a ? a : "eeprom_pacoca.bin";
    FILE *f = fopen(eeprom_arquivo.c_str(), "rb");
    if (f) {
        size_t lidos = fread(eeprom, 1, sizeof eeprom, f);
        (void)lidos;
        fclose(f);
    }
}

uint8_t sim_eeprom_le(int idx) {
    eeprom_carrega();
    sim_custo_ns(1000);
    return (idx >= 0 && idx < (int)sizeof eeprom) ? eeprom[idx] : 0xFF;
}

void sim_eeprom_escreve(int idx, uint8_t v) {
    eeprom_carrega();
    if (idx < 0 || idx >= (int)sizeof eeprom) return;
    if (eeprom[idx] == v) {
        sim_custo_ns(1000);
        return;
    }
    eeprom[idx] = v;
    sim_custo_ns(3400000);       // ~3,4 ms por byte, como no ATmega
    FILE *f = fopen(eeprom_arquivo.c_str(), "wb");
    if (f) {
        fwrite(eeprom, 1, sizeof eeprom, f);
        fclose(f);
    }
}

EEPROMClass EEPROM;

// ============================================================== tabelas de pinos (ATmega328P)
extern "C" {
const uint8_t digital_pin_to_port_PGM[] = {PD, PD, PD, PD, PD, PD, PD, PD, PB, PB, PB, PB, PB, PB,
                                           PC, PC, PC, PC, PC, PC, NOT_A_PORT, NOT_A_PORT};
const uint8_t digital_pin_to_bit_mask_PGM[] = {1, 2, 4, 8, 16, 32, 64, 128, 1, 2, 4, 8, 16, 32,
                                               1, 2, 4, 8, 16, 32, 0, 0};
const uint8_t digital_pin_to_timer_PGM[22] = {0};
const uint16_t port_to_mode_PGM[] = {0, 0, 0x24, 0x27, 0x2A, 0x2D};
const uint16_t port_to_output_PGM[] = {0, 0, 0x25, 0x28, 0x2B, 0x2E};
const uint16_t port_to_input_PGM[] = {0, 0, 0x23, 0x26, 0x29, 0x2C};
}

// ============================================================== reset e main
extern "C" void sim_reset(void) {
    const char *m = "[simulador] reset do brick (jmp 0): o programa vai reiniciar\n";
    sim_saida(m, (int)strlen(m));
    sim_saida_flush();
    exit(42);
}

static void ola(void) {
    SimReq r;
    SimResp s;
    if (!sim_chamar(OP_OLA, r, s)) return;
    uint8_t n = s.u8();
    for (uint8_t i = 0; i < n; i++) { uint8_t p = s.u8(); if (p < 32) eh_entrada_ponte[p] = true; }
    n = s.u8();
    for (uint8_t i = 0; i < n; i++) { uint8_t p = s.u8(); if (p < 32) eh_analogico_ponte[p] = true; }
    n = s.u8();
    for (uint8_t i = 0; i < n; i++) { uint8_t p = s.u8(); if (p < 32) eh_saida_ponte[p] = true; }
    n = s.u8();
    for (uint8_t i = 0; i < n; i++) { uint8_t p = s.u8(); if (p < 32) eh_echo_ponte[p] = true; }
    bateria_mv = s.u16();
}

int main(void) {
    __sim_regs[0x5F] = 0x80;
    if (sim_rede_conecta()) ola();
    setup();
    for (;;) {
        loop();
        sim_custo_ns(C_LOOP);
    }
}
