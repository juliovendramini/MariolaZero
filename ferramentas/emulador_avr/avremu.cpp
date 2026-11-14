// Emulador de AVR para testar os firmwares dos motores do Mariola sem a placa.
//   tipo 0: ATmega328PB (placaBrickVendra)    tipo 1: ATtiny1616 (placaControleMotor)
// Roda o .hex compilado, instrução por instrução, contando ciclos. Periféricos: só os que os dois firmwares
// usam, seguindo o datasheet (PWM com o OCR "bufferizado", serial, interrupções, EEPROM, watchdog).
// Nos pinos fica um modelo da ponte H L9110 + motor DC com redução + encoder em quadratura.
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <vector>

#ifdef _WIN32
#define EXP extern "C" __declspec(dllexport)
#else
#define EXP extern "C" __attribute__((visibility("default")))
#endif
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef uint64_t u64;
static const u64 NUNCA = ~(u64)0;
enum { fC = 1, fZ = 2, fN = 4, fV = 8, fS = 16, fH = 32, fT = 64, fI = 128 };

// ------------------------------------------------------------------ estado do núcleo
static int tipo = 0;
static u16 flashw[0x8000];
static u8 flashb[0x10000];
static u32 pcmask = 0x3FFF;
static u8 R[32];
static u8 mem[0x10000];
static u8 sreg; static u16 sp; static u32 pc; static u64 cyc;
static u16 ram_ini = 0x100;
static bool parou; static int irq_atraso; static bool irq_sujo;
static u64 prox_evt;
static char erro[256];
static double F_CPU = 16e6;
static u32 fis_ciclos = 256;         // passo da física (16 us)
static u64 fis_prox;
static u64 n_resets;                 // resets pelo watchdog (tiny)
static bool nivel_isr;               // tiny: interrupção de nível 0 em execução

// ------------------------------------------------------------------ motor + encoder
struct Mot { double w, th; bool mao; double mao_vel; double acum; int a, b; bool inv_m, inv_e; int falha; double k_re; };
static Mot mot[4];
static int n_mot = 4;
static double W_NL = 2505.0;         // velocidade livre em contagens/s (130 rpm x 1156 contagens por volta)
static double TAU = 0.06;            // constante de tempo mecânica (s)
static double A_C = 2900.0;          // atrito seco em contagens/s2 (equivale a ~7% de PWM para sair do lugar)
static u32 amostra = 16; static u32 n_passo;
static std::vector<double> traco;    // linhas de 11: t, u0..u3 (média), th0, th1, w0, w1, pinos, extra
static const int COLS = 11;

// ------------------------------------------------------------------ serial (as duas placas)
struct RxP { u64 quando; u8 b; };
static std::vector<RxP> rx_fila; static size_t rx_pos;
static u8 rx_fifo[4]; static int rx_n; static u32 rx_perdidos;
static u64 tx_fim; static u8 tx_shift, tx_buf; static bool tx_cheio, txc;
static u32 bitc = 64;                // ciclos por bit
static u64 rx_ultimo;
struct TxB { u64 quando; u8 b; };
static std::vector<TxB> tx_saida;

// ------------------------------------------------------------------ mega: periféricos
struct Timer {
    u8 tccra, tccrb, tcnt, ocra, ocrb, ocra_buf, ocrb_buf, tifr, timsk;
    bool oca, ocb, bloqueia;
    u32 presc; u64 prox; int id;
    int modo() const {             // 0 normal, 1 CTC, 2 PWM (rápido; o de fase correta é tratado igual)
        if (id == 1) { int w = (tccra & 3) | ((tccrb >> 1) & 0xC); return w == 0 ? 0 : (w == 4 ? 1 : 2); }
        int w = (tccra & 3) | ((tccrb & 8) >> 1); return w == 0 ? 0 : (w == 2 ? 1 : 2);
    }
    void acerta_presc() {
        static const u32 p01[8] = {0, 1, 8, 64, 256, 1024, 0, 0};
        static const u32 p2[8] = {0, 1, 8, 32, 64, 128, 256, 1024};
        u32 novo = (id == 2 ? p2 : p01)[tccrb & 7];
        if (novo != presc) { presc = novo; prox = presc ? (cyc / presc + 1) * presc : NUNCA; }
    }
    void escreve_ocr(bool b, u8 v) {
        if (b) { ocrb_buf = v; if (modo() != 2) ocrb = v; }
        else { ocra_buf = v; if (modo() != 2) ocra = v; }
    }
    void modo_mudou() { if (modo() != 2) { ocra = ocra_buf; ocrb = ocrb_buf; } }
    void tick() {
        u8 ant = tcnt;
        bool cA = (ant == ocra) && !bloqueia, cB = (ant == ocrb) && !bloqueia;
        bloqueia = false;
        int m = modo();
        u8 top = (m == 1) ? ocra : 0xFF;
        tcnt = (ant == top || ant == 0xFF) ? 0 : ant + 1;
        if (cA) tifr |= 2;
        if (cB) tifr |= 4;
        if (ant == 0xFF) tifr |= 1;
        int comA = (tccra >> 6) & 3, comB = (tccra >> 4) & 3;
        if (m == 2) {
            if (cA) { if (comA == 2) oca = false; else if (comA == 3) oca = true; }
            if (cB) { if (comB == 2) ocb = false; else if (comB == 3) ocb = true; }
            if (tcnt == 0) {                        // BOTTOM: o OCR novo passa a valer e a saída é ligada
                ocra = ocra_buf; ocrb = ocrb_buf;
                if (comA == 2) oca = true; else if (comA == 3) oca = false;
                if (comB == 2) ocb = true; else if (comB == 3) ocb = false;
            }
        } else {
            if (cA) { if (comA == 1) oca = !oca; else if (comA == 2) oca = false; else if (comA == 3) oca = true; }
            if (cB) { if (comB == 1) ocb = !ocb; else if (comB == 2) ocb = false; else if (comB == 3) ocb = true; }
        }
    }
};
static Timer t0, t1, t2;
static u8 eifr, eimsk, eicra, ucsra, ucsrb;
static u8 ext_nivel[4], ext_dirige[4];   // portas B, C, D, E: nível posto de fora e quais pinos são dirigidos
static u8 eeprom[1024]; static u64 ee_fim; static bool eempe;
static u8 tmp16;

enum { PB = 0, PC = 1, PD = 2, PE = 3 };
static inline u8 &DDR(int p) { return mem[0x24 + 3 * p]; }
static inline u8 &PORT(int p) { return mem[0x25 + 3 * p]; }

static inline bool mega_saida(int p, int bit) {       // nível que o pino põe para fora (entrada = 0)
    if (!((DDR(p) >> bit) & 1)) return false;
    if (p == PD) {
        if (bit == 6 && (t0.tccra & 0xC0)) return t0.oca;
        if (bit == 5 && (t0.tccra & 0x30)) return t0.ocb;
        if (bit == 3 && (t2.tccra & 0x30)) return t2.ocb;
    } else if (p == PB) {
        if (bit == 1 && (t1.tccra & 0xC0)) return t1.oca;
        if (bit == 2 && (t1.tccra & 0x30)) return t1.ocb;
        if (bit == 3 && (t2.tccra & 0xC0)) return t2.oca;
    }
    return (PORT(p) >> bit) & 1;
}
static u8 mega_pin(int p) {
    u8 v = 0;
    for (int b = 0; b < 8; b++) {
        bool n;
        if ((DDR(p) >> b) & 1) n = mega_saida(p, b);
        else if ((ext_dirige[p] >> b) & 1) n = (ext_nivel[p] >> b) & 1;
        else n = (PORT(p) >> b) & 1;                  // pull-up
        if (n) v |= 1 << b;
    }
    return v;
}
static void mega_ext(int p, int bit, bool nivel) {    // muda um pino dirigido de fora (encoder, botão)
    bool ant = (ext_nivel[p] >> bit) & 1;
    ext_dirige[p] |= 1 << bit;
    if (nivel) ext_nivel[p] |= 1 << bit; else ext_nivel[p] &= ~(1 << bit);
    if (ant != nivel && p == PD && (bit == 2 || bit == 3)) {
        int i = bit - 2; int isc = (eicra >> (2 * i)) & 3;
        if (isc == 1 || (isc == 2 && !nivel) || (isc == 3 && nivel)) { eifr |= 1 << i; irq_sujo = true; }
    }
}

// ------------------------------------------------------------------ tiny1616: periféricos
// endereços: VPORTA 0x00, VPORTB 0x04, VPORTC 0x08, GPIOR 0x1C, RSTCTRL 0x40, CLKCTRL 0x60, WDT 0x100,
// CPUINT 0x110, PORTMUX 0x200, PORTA 0x400, PORTB 0x420, PORTC 0x440, USART0 0x800, TCA0 0xA00,
// TCB0 0xA40, TCD0 0xA80, NVMCTRL 0x1000, EEPROM 0x1400, RAM 0x3800, flash 0x8000
static u8 p_dir[3], p_out[3], p_intf[3], p_ctrl[3][8], p_ext[3], p_extd[3], p_in_ant[3];
static u8 rstfr = 0x01;              // causa do reset (PORF ao ligar)
static u8 ccp_janela;
static u64 wdt_fim; static u8 wdt_ctrla; static u32 wdt_limpezas;
static u8 us_ctrla, us_ctrlb, us_status;
// TCA0 em modo dividido: dois contadores de 8 bits que descem
static u8 tca_ctrla, tca_ctrlb, tca_ctrld, tca_intctrl, tca_intflags;
static u8 tca_lcnt, tca_hcnt, tca_lper = 0xFF, tca_hper = 0xFF, tca_lcmp[3], tca_hcmp[3];
static bool tca_wo[6];
static u32 tca_presc; static u64 tca_prox;
// TCD0: usado pelo megaTinyCore para o millis() (interrupção de estouro)
static u8 tcd_ctrla, tcd_intctrl, tcd_intflags; static u16 tcd_cmpbclr = 0xFFF; static u64 tcd_prox; static u32 tcd_per, tcd_div = 1; static u16 tcd_cap;
// TCB0
static u8 tcb_ctrla, tcb_ctrlb, tcb_intctrl, tcb_intflags; static u16 tcb_ccmp, tcb_cnt; static u64 tcb_prox; static u32 tcb_presc;
// pinos da placa de motor (definidos pelo teste): ponte H e encoder
static int tm_pwm_a = -1, tm_pwm_b = -1;   // índices de pino: porta*8+bit
static int tm_enc_a = -1, tm_enc_b = -1;

static inline bool tiny_saida(int idx) {              // nível que o pino põe para fora
    int p = idx >> 3, b = idx & 7;
    if (!((p_dir[p] >> b) & 1)) return false;
    // saídas do TCA0 em modo dividido: WO0-2 = PB0-PB2, WO3-5 = PA3-PA5 (PORTMUX padrão)
    if (tca_ctrld & 1) {
        if (p == 1 && b <= 2 && (tca_ctrlb & (1 << b))) return tca_wo[b];
        if (p == 0 && b >= 3 && b <= 5 && (tca_ctrlb & (0x10 << (b - 3)))) return tca_wo[b];
    }
    return (p_out[p] >> b) & 1;
}
static u8 tiny_in(int p) {
    u8 v = 0;
    for (int b = 0; b < 8; b++) {
        bool n;
        if ((p_dir[p] >> b) & 1) n = tiny_saida(p * 8 + b);
        else if ((p_extd[p] >> b) & 1) n = (p_ext[p] >> b) & 1;
        else n = (p_ctrl[p][b] & 0x08) != 0;          // pull-up
        if (n) v |= 1 << b;
    }
    return v;
}
static void tiny_bordas(int p) {                      // interrupções de pino
    u8 agora = tiny_in(p), mud = agora ^ p_in_ant[p];
    p_in_ant[p] = agora;
    for (int b = 0; b < 8 && mud; b++) if ((mud >> b) & 1) {
        int isc = p_ctrl[p][b] & 7; bool n = (agora >> b) & 1;
        if (isc == 1 || (isc == 2 && n) || (isc == 3 && !n)) { p_intf[p] |= 1 << b; irq_sujo = true; }
    }
}
static void tiny_ext(int idx, bool nivel) {
    int p = idx >> 3, b = idx & 7;
    p_extd[p] |= 1 << b;
    if (nivel) p_ext[p] |= 1 << b; else p_ext[p] &= ~(1 << b);
    tiny_bordas(p);
}
static void tca_acerta() {
    static const u32 pr[8] = {1, 2, 4, 8, 16, 64, 256, 1024};
    u32 novo = (tca_ctrla & 1) ? pr[(tca_ctrla >> 1) & 7] : 0;
    if (novo != tca_presc) { tca_presc = novo; tca_prox = novo ? (cyc / novo + 1) * novo : NUNCA; }
}
static void tca_tick() {
    // modo dividido: dois contadores de 8 bits que descem; a saída fica em HIGH enquanto CNT < CMP
    // (megaTinyCore: PER = 254, duty = CMP / 255). Os CMP não têm buffer: valem na hora.
    if (tca_lcnt == 0) { tca_lcnt = tca_lper; tca_intflags |= 1; } else tca_lcnt--;
    if (tca_hcnt == 0) { tca_hcnt = tca_hper; tca_intflags |= 2; } else tca_hcnt--;
    for (int i = 0; i < 3; i++) { tca_wo[i] = tca_lcnt < tca_lcmp[i]; tca_wo[3 + i] = tca_hcnt < tca_hcmp[i]; }
}

// ------------------------------------------------------------------ memória
static void porta_mudou();
static void serial_escreve(u8 v) {
    if (tx_fim == NUNCA) { tx_shift = v; tx_fim = cyc + 10 * (u64)bitc; if (tx_fim < prox_evt) prox_evt = tx_fim; }
    else { tx_buf = v; tx_cheio = true; }
    txc = false;
}
static u8 serial_le() {
    u8 v = rx_fifo[0];
    if (rx_n > 0) { rx_n--; rx_fifo[0] = rx_fifo[1]; rx_fifo[1] = rx_fifo[2]; rx_fifo[2] = rx_fifo[3]; }
    return v;
}

static u8 mega_rd(u16 a) {
    if (a < 0x20) return R[a];
    switch (a) {
        case 0x5F: return sreg; case 0x5D: return sp & 0xFF; case 0x5E: return sp >> 8;
        case 0x23: return mega_pin(PB); case 0x26: return mega_pin(PC);
        case 0x29: return mega_pin(PD); case 0x2C: return mega_pin(PE);
        case 0x35: return t0.tifr; case 0x36: return t1.tifr; case 0x37: return t2.tifr;
        case 0x3C: return eifr; case 0x3D: return eimsk; case 0x69: return eicra;
        case 0x44: return t0.tccra; case 0x45: return t0.tccrb; case 0x46: return t0.tcnt;
        case 0x47: return t0.ocra_buf; case 0x48: return t0.ocrb_buf; case 0x6E: return t0.timsk;
        case 0x80: return t1.tccra; case 0x81: return t1.tccrb; case 0x84: return t1.tcnt; case 0x85: return 0;
        case 0x88: return t1.ocra_buf; case 0x89: return 0; case 0x8A: return t1.ocrb_buf; case 0x8B: return 0;
        case 0x6F: return t1.timsk;
        case 0xB0: return t2.tccra; case 0xB1: return t2.tccrb; case 0xB2: return t2.tcnt;
        case 0xB3: return t2.ocra_buf; case 0xB4: return t2.ocrb_buf; case 0x70: return t2.timsk;
        case 0xC0: return (rx_n ? 0x80 : 0) | (txc ? 0x40 : 0) | (tx_cheio ? 0 : 0x20) | (ucsra & 3);
        case 0xC1: return ucsrb;
        case 0xC6: { irq_sujo = true; return serial_le(); }
        case 0x3F: return (mem[0x3F] & 0x38) | (ee_fim != NUNCA ? 2 : 0);
    }
    return mem[a];
}
static void mega_wr(u16 a, u8 v) {
    if (a < 0x20) { R[a] = v; return; }
    irq_sujo = true;
    switch (a) {
        case 0x5F: if (!(sreg & fI) && (v & fI)) irq_atraso = 1; sreg = v; return;
        case 0x5D: sp = (sp & 0xFF00) | v; return;
        case 0x5E: sp = (sp & 0x00FF) | (v << 8); return;
        case 0x23: PORT(PB) ^= v; return; case 0x26: PORT(PC) ^= v; return;
        case 0x29: PORT(PD) ^= v; return; case 0x2C: PORT(PE) ^= v; return;
        case 0x35: t0.tifr &= ~v; return; case 0x36: t1.tifr &= ~v; return; case 0x37: t2.tifr &= ~v; return;
        case 0x3C: eifr &= ~v; return; case 0x3D: eimsk = v; return; case 0x69: eicra = v; return;
        case 0x44: t0.tccra = v; t0.modo_mudou(); return;
        case 0x45: t0.tccrb = v; t0.modo_mudou(); t0.acerta_presc(); if (t0.prox < prox_evt) prox_evt = t0.prox; return;
        case 0x46: t0.tcnt = v; t0.bloqueia = true; return;
        case 0x47: t0.escreve_ocr(false, v); return; case 0x48: t0.escreve_ocr(true, v); return;
        case 0x6E: t0.timsk = v; return;
        case 0x80: t1.tccra = v; t1.modo_mudou(); return;
        case 0x81: t1.tccrb = v; t1.modo_mudou(); t1.acerta_presc(); if (t1.prox < prox_evt) prox_evt = t1.prox; return;
        case 0x85: case 0x89: case 0x8B: tmp16 = v; return;       // byte alto: o timer é tratado como de 8 bits
        case 0x84: t1.tcnt = v; t1.bloqueia = true; return;
        case 0x88: t1.escreve_ocr(false, v); return; case 0x8A: t1.escreve_ocr(true, v); return;
        case 0x6F: t1.timsk = v; return;
        case 0xB0: t2.tccra = v; t2.modo_mudou(); return;
        case 0xB1: t2.tccrb = v; t2.modo_mudou(); t2.acerta_presc(); if (t2.prox < prox_evt) prox_evt = t2.prox; return;
        case 0xB2: t2.tcnt = v; t2.bloqueia = true; return;
        case 0xB3: t2.escreve_ocr(false, v); return; case 0xB4: t2.escreve_ocr(true, v); return;
        case 0x70: t2.timsk = v; return;
        case 0xC0: if (v & 0x40) txc = false; ucsra = v & 3; goto baud;
        case 0xC1: ucsrb = v; return;
        case 0xC4: case 0xC5: mem[a] = v;
        baud: { u32 ubrr = mem[0xC4] | ((mem[0xC5] & 0x0F) << 8); bitc = (ubrr + 1) * ((ucsra & 2) ? 8 : 16); return; }
        case 0xC6: serial_escreve(v); return;
        case 0x3F:
            mem[0x3F] = v & 0x38;
            if (v & 1) mem[0x40] = eeprom[(mem[0x41] | (mem[0x42] << 8)) & 0x3FF];
            if (v & 4) eempe = true;
            if ((v & 2) && eempe) {
                eeprom[(mem[0x41] | (mem[0x42] << 8)) & 0x3FF] = mem[0x40];
                ee_fim = cyc + 54400; eempe = false; if (ee_fim < prox_evt) prox_evt = ee_fim;
            }
            return;
    }
    mem[a] = v;
}

static void tiny_reset(u8 causa);
static u8 tiny_rd(u16 a) {
    if (a < 0x0C) { int p = a >> 2; switch (a & 3) { case 0: return p_dir[p]; case 1: return p_out[p]; case 2: return tiny_in(p); default: return p_intf[p]; } }
    if (a >= 0x400 && a < 0x460) {
        int p = (a - 0x400) >> 5, r = a & 0x1F;
        if (r <= 3) return p_dir[p]; if (r <= 7) return p_out[p]; if (r == 8) return tiny_in(p); if (r == 9) return p_intf[p];
        if (r >= 0x10 && r <= 0x17) return p_ctrl[p][r - 0x10];
        return 0;
    }
    switch (a) {
        case 0x3F: return sreg; case 0x3D: return sp & 0xFF; case 0x3E: return sp >> 8;
        case 0x40: return rstfr;
        case 0x63: return 0x10;                       // MCLKSTATUS: oscilador de 20 MHz estável
        case 0x100: return wdt_ctrla; case 0x101: return 0;
        case 0x111: return nivel_isr ? 1 : 0;
        case 0x800: { irq_sujo = true; return serial_le(); }
        case 0x801: return rx_n ? 0x80 : 0;
        case 0x804: return (rx_n ? 0x80 : 0) | (txc ? 0x40 : 0) | (tx_cheio ? 0 : 0x20);
        case 0x805: return us_ctrla; case 0x806: return us_ctrlb;
        case 0xA00: return tca_ctrla; case 0xA01: return tca_ctrlb; case 0xA03: return tca_ctrld;
        case 0xA0A: return tca_intctrl; case 0xA0B: return tca_intflags;
        case 0xA20: return tca_lcnt; case 0xA21: return tca_hcnt; case 0xA26: return tca_lper; case 0xA27: return tca_hper;
        case 0xA28: return tca_lcmp[0]; case 0xA29: return tca_hcmp[0]; case 0xA2A: return tca_lcmp[1];
        case 0xA2B: return tca_hcmp[1]; case 0xA2C: return tca_lcmp[2]; case 0xA2D: return tca_hcmp[2];
        case 0xA40: return tcb_ctrla; case 0xA41: return tcb_ctrlb; case 0xA45: return tcb_intctrl; case 0xA46: return tcb_intflags;
        case 0xA80: return tcd_ctrla; case 0xA8C: return tcd_intctrl; case 0xA8D: return tcd_intflags;
        case 0xA8E: return 0x03;                      // TCD0.STATUS: ENRDY | CMDRDY
        case 0xAA2: return tcd_cap & 0xFF;
        case 0xAA3: return tcd_cap >> 8;
        case 0x1002: return 0;                        // NVMCTRL.STATUS: livre
    }
    return mem[a];
}
static void tiny_wr(u16 a, u8 v) {
    irq_sujo = true;
    if (a < 0x0C) {
        int p = a >> 2;
        switch (a & 3) { case 0: p_dir[p] = v; break; case 1: p_out[p] = v; break; case 2: p_out[p] ^= v; break; default: p_intf[p] &= ~v; }
        tiny_bordas(p); return;
    }
    if (a >= 0x400 && a < 0x460) {
        int p = (a - 0x400) >> 5, r = a & 0x1F;
        switch (r) {
            case 0: p_dir[p] = v; break; case 1: p_dir[p] |= v; break; case 2: p_dir[p] &= ~v; break; case 3: p_dir[p] ^= v; break;
            case 4: p_out[p] = v; break; case 5: p_out[p] |= v; break; case 6: p_out[p] &= ~v; break; case 7: p_out[p] ^= v; break;
            case 8: break; case 9: p_intf[p] &= ~v; break;
            default: if (r >= 0x10 && r <= 0x17) p_ctrl[p][r - 0x10] = v;
        }
        tiny_bordas(p); return;
    }
    switch (a) {
        case 0x3F: if (!(sreg & fI) && (v & fI)) irq_atraso = 1; sreg = v; return;
        case 0x3D: sp = (sp & 0xFF00) | v; return;
        case 0x3E: sp = (sp & 0x00FF) | (v << 8); return;
        case 0x34: ccp_janela = v; return;            // CCP: aceito sempre
        case 0x40: rstfr &= ~v; return;
        case 0x41: if (v & 1) tiny_reset(0x10); return;   // reset por software
        case 0x100:
            wdt_ctrla = v;
            if (v & 0x0F) {
                static const u32 ms[12] = {0, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192};
                wdt_fim = cyc + (u64)(ms[(v & 0x0F) > 11 ? 11 : (v & 0x0F)] * 1e-3 * F_CPU);
                if (wdt_fim < prox_evt) prox_evt = wdt_fim;
            } else wdt_fim = NUNCA;
            return;
        case 0x802: serial_escreve(v); return;
        case 0x804: if (v & 0x40) txc = false; return;
        case 0x805: us_ctrla = v; return;
        case 0x806: us_ctrlb = v; a = 0x808; v = mem[0x808];
        case 0x808: case 0x809: {
            mem[a] = v; u32 baud = mem[0x808] | (mem[0x809] << 8);
            if (baud >= 64) bitc = (u32)((baud * ((us_ctrlb & 0x06) == 0x02 ? 8.0 : 16.0)) / 64.0 + 0.5);
            return;
        }
        case 0xA00: tca_ctrla = v; tca_acerta(); if (tca_prox < prox_evt) prox_evt = tca_prox; return;
        case 0xA01: tca_ctrlb = v; return; case 0xA03: tca_ctrld = v; return;
        case 0xA0A: tca_intctrl = v; return; case 0xA0B: tca_intflags &= ~v; return;
        case 0xA20: tca_lcnt = v; return; case 0xA21: tca_hcnt = v; return;
        case 0xA26: tca_lper = v; return; case 0xA27: tca_hper = v; return;
        case 0xA28: tca_lcmp[0] = v; return; case 0xA29: tca_hcmp[0] = v; return; case 0xA2A: tca_lcmp[1] = v; return;
        case 0xA2B: tca_hcmp[1] = v; return; case 0xA2C: tca_lcmp[2] = v; return; case 0xA2D: tca_hcmp[2] = v; return;
        case 0xA40: tcb_ctrla = v; return;            // TCB0: o firmware não usa
        case 0xA41: tcb_ctrlb = v; return; case 0xA45: tcb_intctrl = v; return; case 0xA46: tcb_intflags &= ~v; return;
        case 0xA4C: tcb_ccmp = (tcb_ccmp & 0xFF00) | v; return; case 0xA4D: tcb_ccmp = (tcb_ccmp & 0xFF) | (v << 8); return;
        case 0xA80: {
            tcd_ctrla = v;
            if (v & 1) {
                static const u32 cnt[4] = {1, 4, 32, 0}; static const u32 syn[4] = {1, 2, 4, 8};
                u32 base = 1;                          // megaTinyCore: TCD0 no oscilador de 20 MHz
                u32 div = cnt[(v >> 3) & 3] * syn[(v >> 1) & 3]; if (!div) div = 1;
                tcd_div = div * base; tcd_per = ((u32)tcd_cmpbclr + 1) * tcd_div;
                tcd_prox = cyc + tcd_per; if (tcd_prox < prox_evt) prox_evt = tcd_prox;
            } else tcd_prox = NUNCA;
            return;
        }
        case 0xA8C: tcd_intctrl = v; return; case 0xA8D: tcd_intflags &= ~v; return;
        case 0xA84:                                    // CTRLE: SCAPTUREA guarda a contagem deste instante
            if (v & 0x08) tcd_cap = (tcd_prox == NUNCA) ? 0 : (u16)((cyc - (tcd_prox - tcd_per)) / tcd_div);
            return;
        case 0xAAE: tcd_cmpbclr = (tcd_cmpbclr & 0xF00) | v; return;
        case 0xAAF: tcd_cmpbclr = (tcd_cmpbclr & 0xFF) | ((v & 0x0F) << 8); return;
        case 0x1000:                                   // NVMCTRL.CTRLA: grava a página (a EEPROM é memória comum aqui)
            return;
    }
    mem[a] = v;
}

static inline u8 rd(u16 a) { if (a >= ram_ini) return mem[a]; return tipo ? tiny_rd(a) : mega_rd(a); }
static inline void wr(u16 a, u8 v) {
    if (a >= ram_ini) { if (tipo && a >= 0x8000) return; mem[a] = v; return; }
    if (tipo) tiny_wr(a, v); else mega_wr(a, v);
}
static inline void push(u8 v) { mem[sp--] = v; }
static inline u8 pop() { return mem[++sp]; }

// ------------------------------------------------------------------ física
static inline void ponte(int m, bool &pwm, bool &dir) {
    if (tipo == 0) {
        switch (m) {
            case 0: pwm = mega_saida(PB, 1); dir = mega_saida(PD, 4); break;
            case 1: pwm = mega_saida(PB, 2); dir = mega_saida(PE, 3); break;
            case 2: pwm = mega_saida(PD, 6); dir = mega_saida(PD, 7); break;
            default: pwm = mega_saida(PD, 5); dir = mega_saida(PE, 2);
        }
    } else {                                           // placa de motor: dois pinos de PWM (A = positivo)
        dir = tm_pwm_a >= 0 && tiny_saida(tm_pwm_a);
        pwm = tm_pwm_b >= 0 && tiny_saida(tm_pwm_b);
    }
}
static void fisica() {
    const double DT = fis_ciclos / F_CPU;
    for (int m = 0; m < n_mot; m++) {
        Mot &q = mot[m];
        bool pwm, dir; ponte(m, pwm, dir);
        int u = (dir && !pwm) ? 1 : ((!dir && pwm) ? -1 : 0);
        bool solto = tipo && !dir && !pwm;
        q.acum += u;
        if (q.inv_m) u = -u;                           // fios do motor trocados
        if (q.falha & 4) { u = 0; solto = true; }      // motor desligado
        double alvo = u * W_NL; if (u < 0 && q.k_re > 0) alvo *= q.k_re;   // motor mais fraco num sentido
        if (q.mao) q.w = q.mao_vel;
        else {
            double a = solto ? 0.0 : (alvo - q.w) / TAU;
            if (q.w == 0) {
                if (fabs(a) <= A_C) a = 0; else a -= copysign(A_C, a);
                q.w += a * DT;
            } else {
                double w2 = q.w + (a - copysign(A_C, q.w)) * DT;
                if (w2 * q.w < 0) w2 = 0;
                q.w = w2;
            }
        }
        q.th += q.w * DT;
        if (m < 2) {
            double f = (q.inv_e ? -q.th : q.th) * (tipo ? 0.25 : 0.5); f -= floor(f);   // inv_e: canais A e B trocados
            int A = f < 0.5, B = (f >= 0.25 && f < 0.75);
            if (q.falha & 1) A = 1;                    // canal A solto (fica no pull-up)
            if (q.falha & 2) B = 1;                    // canal B solto
            if (tipo == 0) {
                if (B != q.b) { q.b = B; mega_ext(PE, m, B); }
                if (A != q.a) { q.a = A; mega_ext(PD, 2 + m, A); }
            } else if (m == 0 && tm_enc_a >= 0) {
                if (B != q.b) { q.b = B; tiny_ext(tm_enc_b, B); }
                if (A != q.a) { q.a = A; tiny_ext(tm_enc_a, A); }
            }
        }
    }
    if (++n_passo >= amostra) {
        n_passo = 0;
        double l[COLS];
        l[0] = cyc / F_CPU;
        for (int m = 0; m < 4; m++) { l[1 + m] = mot[m].acum / amostra; mot[m].acum = 0; }
        l[5] = mot[0].th; l[6] = mot[1].th; l[7] = mot[0].w; l[8] = mot[1].w;
        if (tipo == 0) { l[9] = (DDR(PC) & PORT(PC)) & 0x3F; l[10] = (mega_saida(PB, 5) ? 1 : 0); }
        else { l[9] = (tiny_saida(6) ? 1 : 0) | (((p_dir[0] >> 4) & 3) << 1); l[10] = (double)n_resets; }
        traco.insert(traco.end(), l, l + COLS);
    }
}

// ------------------------------------------------------------------ eventos e interrupções
static void eventos() {
    if (tipo == 0) {
        while (t0.prox <= cyc) { t0.tick(); t0.prox += t0.presc; }
        while (t1.prox <= cyc) { t1.tick(); t1.prox += t1.presc; }
        while (t2.prox <= cyc) { t2.tick(); t2.prox += t2.presc; }
        if (ee_fim <= cyc) ee_fim = NUNCA;
    } else {
        while (tca_prox <= cyc) { tca_tick(); tca_prox += tca_presc; }
        while (tcd_prox <= cyc) { tcd_intflags |= 1; tcd_prox += tcd_per; }
        if (wdt_fim <= cyc) { tiny_reset(0x08); return; }
    }
    while (fis_prox <= cyc) { fisica(); fis_prox += fis_ciclos; }
    if (tx_fim <= cyc) {
        TxB t = {tx_fim, tx_shift}; tx_saida.push_back(t);
        if (tipo && (us_ctrlb & 0x80)) { if (rx_n < 3) rx_fifo[rx_n++] = tx_shift; }
        if (tx_cheio) { tx_shift = tx_buf; tx_cheio = false; tx_fim += 10 * (u64)bitc; }
        else { tx_fim = NUNCA; txc = true; }
    }
    while (rx_pos < rx_fila.size() && rx_fila[rx_pos].quando <= cyc) {
        bool recebe = tipo == 0 ? (ucsrb & 0x10) : (us_ctrlb & 0x80);
        if (recebe) { if (rx_n < 3) rx_fifo[rx_n++] = rx_fila[rx_pos].b; else rx_perdidos++; }
        rx_pos++;
    }
    u64 p = fis_prox;
    if (tipo == 0) {
        if (t0.prox < p) p = t0.prox; if (t1.prox < p) p = t1.prox; if (t2.prox < p) p = t2.prox;
        if (ee_fim < p) p = ee_fim;
    } else {
        if (tca_prox < p) p = tca_prox; if (tcd_prox < p) p = tcd_prox;
        if (wdt_fim < p) p = wdt_fim;
    }
    if (tx_fim < p) p = tx_fim;
    if (rx_pos < rx_fila.size() && rx_fila[rx_pos].quando < p) p = rx_fila[rx_pos].quando;
    prox_evt = p;
    irq_sujo = true;
}

static int mega_irq() {
    u8 f = eifr & eimsk;
    if (f & 1) { eifr &= ~1; return 1; }
    if (f & 2) { eifr &= ~2; return 2; }
    f = t2.tifr & t2.timsk;
    if (f & 2) { t2.tifr &= ~2; return 7; } if (f & 4) { t2.tifr &= ~4; return 8; } if (f & 1) { t2.tifr &= ~1; return 9; }
    f = t1.tifr & t1.timsk;
    if (f & 2) { t1.tifr &= ~2; return 11; } if (f & 4) { t1.tifr &= ~4; return 12; } if (f & 1) { t1.tifr &= ~1; return 13; }
    f = t0.tifr & t0.timsk;
    if (f & 2) { t0.tifr &= ~2; return 14; } if (f & 4) { t0.tifr &= ~4; return 15; } if (f & 1) { t0.tifr &= ~1; return 16; }
    if ((ucsrb & 0x80) && rx_n) return 18;
    if ((ucsrb & 0x20) && !tx_cheio) return 19;
    if ((ucsrb & 0x40) && txc) { txc = false; return 20; }
    return 0;
}
static int tiny_irq() {                                // as flags não são limpas sozinhas no AVRxt
    if (nivel_isr) return 0;
    if (p_intf[0]) return 3; if (p_intf[1]) return 4; if (p_intf[2]) return 5;
    u8 f = tca_intflags & tca_intctrl;
    if (f & 1) return 8; if (f & 2) return 9;
    if (tcd_intflags & tcd_intctrl & 1) return 15;
    if ((us_ctrla & 0x80) && rx_n) return 27;
    if ((us_ctrla & 0x20) && !tx_cheio) return 28;
    if ((us_ctrla & 0x40) && txc) return 29;
    return 0;
}
static void tiny_reset(u8 causa) {
    n_resets++;
    rstfr |= causa;
    memset(p_dir, 0, sizeof p_dir); memset(p_out, 0, sizeof p_out); memset(p_intf, 0, sizeof p_intf);
    memset(p_ctrl, 0, sizeof p_ctrl);
    wdt_fim = NUNCA; wdt_ctrla = 0;
    us_ctrla = us_ctrlb = 0; rx_n = 0; tx_fim = NUNCA; tx_cheio = false; txc = false;
    tca_ctrla = tca_ctrlb = tca_ctrld = tca_intctrl = tca_intflags = 0; tca_presc = 0; tca_prox = NUNCA;
    tca_lper = tca_hper = 0xFF; memset(tca_lcmp, 0, 3); memset(tca_hcmp, 0, 3); memset(tca_wo, 0, sizeof tca_wo);
    tcd_ctrla = tcd_intctrl = tcd_intflags = 0; tcd_prox = NUNCA; tcd_cmpbclr = 0xFFF;
    tcb_ctrla = tcb_intctrl = tcb_intflags = 0; tcb_prox = NUNCA;
    memset(mem, 0, 0x40);                              // GPIOR
    sreg = 0; sp = 0x3FFF; pc = 0; nivel_isr = false; irq_atraso = 0;
    for (int p = 0; p < 3; p++) p_in_ant[p] = tiny_in(p);
    prox_evt = cyc;
}

// ------------------------------------------------------------------ instruções
static inline void fadd(u8 a, u8 b, u8 r) {
    u8 c = (a & b) | (b & ~r) | (~r & a), v = (a & b & ~r) | (~a & ~b & r);
    u8 f = sreg & ~(fC | fZ | fN | fV | fS | fH);
    if (c & 0x80) f |= fC; if (c & 0x08) f |= fH; if (!r) f |= fZ; if (r & 0x80) f |= fN;
    if (v & 0x80) f |= fV; if ((r ^ v) & 0x80) f |= fS;
    sreg = f;
}
static inline void fsub(u8 a, u8 b, u8 r, bool mz) {
    u8 c = (~a & b) | (b & r) | (r & ~a), v = (a & ~b & ~r) | (~a & b & r);
    bool z = (r == 0) && (!mz || (sreg & fZ));
    u8 f = sreg & ~(fC | fZ | fN | fV | fS | fH);
    if (c & 0x80) f |= fC; if (c & 0x08) f |= fH; if (z) f |= fZ; if (r & 0x80) f |= fN;
    if (v & 0x80) f |= fV; if ((r ^ v) & 0x80) f |= fS;
    sreg = f;
}
static inline void flog(u8 r) {
    u8 f = sreg & ~(fZ | fN | fV | fS);
    if (!r) f |= fZ; if (r & 0x80) f |= fN | fS;
    sreg = f;
}
static inline void fnzvs(u8 r, bool v) {
    u8 f = sreg & ~(fZ | fN | fV | fS);
    bool n = r & 0x80;
    if (!r) f |= fZ; if (n) f |= fN; if (v) f |= fV; if (n != v) f |= fS;
    sreg = f;
}
static inline bool dois_words(u16 w) { return (w & 0xFE0F) == 0x9000 || (w & 0xFE0F) == 0x9200 || (w & 0xFE0C) == 0x940C; }
static inline int salta() { if (dois_words(flashw[pc])) { pc += 2; return 2; } pc += 1; return 1; }
static inline u16 r16(int d) { return R[d] | (R[d + 1] << 8); }
static inline void w16(int d, u16 v) { R[d] = v; R[d + 1] = v >> 8; }
static void falha(u16 w) { snprintf(erro, sizeof erro, "instrucao %04x em %#x (ciclo %llu)", w, (pc - 1) * 2, (unsigned long long)cyc); parou = true; }

static inline void passo() {
    u16 w = flashw[pc & pcmask]; pc++;
    int cy = 1;
    const bool xt = tipo != 0;
    int d5 = (w >> 4) & 0x1F, r5 = (w & 0x0F) | ((w >> 5) & 0x10);
    switch (w >> 12) {
    case 0x0: {
        if (w == 0) break;
        u8 hi = w >> 8;
        if (hi == 1) { int d = ((w >> 4) & 0xF) * 2, r = (w & 0xF) * 2; R[d] = R[r]; R[d + 1] = R[r + 1]; break; }
        if (hi == 2) {
            int d = 16 + ((w >> 4) & 0xF), r = 16 + (w & 0xF);
            u16 p = (u16)((int8_t)R[d] * (int8_t)R[r]);
            w16(0, p); sreg = (sreg & ~(fC | fZ)) | (p >> 15) | (p == 0 ? fZ : 0); cy = 2; break;
        }
        if (hi == 3) {
            int d = 16 + ((w >> 4) & 7), r = 16 + (w & 7), k = ((w >> 6) & 2) | ((w >> 3) & 1);
            int a = R[d], b = R[r];
            if (k != 1) a = (int8_t)a;
            if (k == 2) b = (int8_t)b;
            u16 p = (u16)(a * b); u8 c = p >> 15;
            if (k != 0) p <<= 1;
            w16(0, p); sreg = (sreg & ~(fC | fZ)) | c | (p == 0 ? fZ : 0); cy = 2; break;
        }
        u8 a = R[d5], b = R[r5], r;
        switch ((w >> 10) & 3) {
            case 1: r = a - b - (sreg & fC); fsub(a, b, r, true); break;
            case 2: r = a - b - (sreg & fC); fsub(a, b, r, true); R[d5] = r; break;
            case 3: r = a + b; fadd(a, b, r); R[d5] = r; break;
            default: falha(w);
        }
        break;
    }
    case 0x1: {
        u8 a = R[d5], b = R[r5], r;
        switch ((w >> 10) & 3) {
            case 0: if (a == b) cy += salta(); break;
            case 1: r = a - b; fsub(a, b, r, false); break;
            case 2: r = a - b; fsub(a, b, r, false); R[d5] = r; break;
            default: r = a + b + (sreg & fC); fadd(a, b, r); R[d5] = r;
        }
        break;
    }
    case 0x2: {
        u8 r;
        switch ((w >> 10) & 3) {
            case 0: r = R[d5] & R[r5]; flog(r); R[d5] = r; break;
            case 1: r = R[d5] ^ R[r5]; flog(r); R[d5] = r; break;
            case 2: r = R[d5] | R[r5]; flog(r); R[d5] = r; break;
            default: R[d5] = R[r5];
        }
        break;
    }
    case 0x3: case 0x4: case 0x5: case 0x6: case 0x7: {
        int d = 16 + ((w >> 4) & 0xF); u8 k = ((w >> 4) & 0xF0) | (w & 0xF), a = R[d], r;
        switch (w >> 12) {
            case 3: r = a - k; fsub(a, k, r, false); break;
            case 4: r = a - k - (sreg & fC); fsub(a, k, r, true); R[d] = r; break;
            case 5: r = a - k; fsub(a, k, r, false); R[d] = r; break;
            case 6: r = a | k; flog(r); R[d] = r; break;
            default: r = a & k; flog(r); R[d] = r;
        }
        break;
    }
    case 0x8: case 0xA: {
        int q = (w & 7) | ((w >> 7) & 0x18) | ((w >> 8) & 0x20);
        u16 base = (w & 8) ? r16(28) : r16(30);
        if (w & 0x0200) wr(base + q, R[d5]); else R[d5] = rd(base + q);
        cy = 2;
        break;
    }
    case 0x9: {
        u16 top = w & 0xFE00; int low = w & 0xF;
        if (top == 0x9000 || top == 0x9200) {
            bool load = top == 0x9000;
            if (low == 0) {
                u16 k = flashw[pc & pcmask]; pc++;
                if (load) R[d5] = rd(k); else wr(k, R[d5]);
                cy = (xt && load) ? 3 : 2; break;
            }
            if (load && (low == 4 || low == 5)) {
                u16 z = r16(30); R[d5] = flashb[z]; if (low == 5) w16(30, z + 1); cy = 3; break;
            }
            if (low == 0xF) { if (load) { R[d5] = pop(); cy = 2; } else { push(R[d5]); cy = xt ? 1 : 2; } break; }
            int reg;
            switch (low) { case 1: case 2: reg = 30; break; case 9: case 10: reg = 28; break; case 12: case 13: case 14: reg = 26; break; default: falha(w); return; }
            u16 a = r16(reg);
            bool pre = (low == 2 || low == 10 || low == 14), pos = (low == 1 || low == 9 || low == 13);
            if (pre) { a--; w16(reg, a); }
            if (load) R[d5] = rd(a); else wr(a, R[d5]);
            if (pos) w16(reg, a + 1);
            cy = (xt && !load && !pre) ? 1 : 2;
            break;
        }
        if (top == 0x9400) {
            if ((w & 0xFE0C) == 0x940C) {
                u32 k = flashw[pc & pcmask] | ((u32)(((w >> 3) & 0x3E) | (w & 1)) << 16); pc++;
                if (w & 2) { push(pc & 0xFF); push(pc >> 8); pc = k; cy = xt ? 3 : 4; } else { pc = k; cy = 3; }
                break;
            }
            u8 a = R[d5], r;
            switch (low) {
                case 0: r = ~a; fnzvs(r, false); sreg |= fC; R[d5] = r; break;
                case 1: {
                    r = -a; u8 f = sreg & ~(fC | fZ | fN | fV | fS | fH);
                    bool v = r == 0x80, n = r & 0x80;
                    if (r) f |= fC; else f |= fZ; if (n) f |= fN; if (v) f |= fV; if (n != v) f |= fS; if ((r | a) & 0x08) f |= fH;
                    sreg = f; R[d5] = r; break;
                }
                case 2: R[d5] = (a << 4) | (a >> 4); break;
                case 3: r = a + 1; fnzvs(r, a == 0x7F); R[d5] = r; break;
                case 5: case 6: case 7: {
                    u8 c = a & 1;
                    if (low == 5) r = (a >> 1) | (a & 0x80); else if (low == 6) r = a >> 1; else r = (a >> 1) | ((sreg & fC) << 7);
                    bool n = r & 0x80;
                    fnzvs(r, n != (bool)c); sreg = (sreg & ~fC) | c; R[d5] = r; break;
                }
                case 0xA: r = a - 1; fnzvs(r, a == 0x80); R[d5] = r; break;
                case 8:
                    if ((w & 0xFF8F) == 0x9408) {
                        int b = (w >> 4) & 7; if (b == 7 && !(sreg & fI)) { irq_atraso = 1; irq_sujo = true; }
                        sreg |= 1 << b;
                    } else if ((w & 0xFF8F) == 0x9488) sreg &= ~(1 << ((w >> 4) & 7));
                    else if (w == 0x9508 || w == 0x9518) {
                        u8 h = pop(), l = pop(); pc = (h << 8) | l; cy = 4;
                        if (w == 0x9518) {
                            if (xt) nivel_isr = false; else { sreg |= fI; }
                            irq_atraso = 1; irq_sujo = true;
                        }
                    } else if (w == 0x9588 || w == 0x9598) { /* SLEEP / BREAK */ }
                    else if (w == 0x95A8) {                                  // WDR
                        if (xt && (wdt_ctrla & 0x0F)) { u8 v = wdt_ctrla; tiny_wr(0x100, v); wdt_limpezas++; }
                    } else if (w == 0x95C8) { R[0] = flashb[r16(30)]; cy = 3; }
                    else falha(w);
                    break;
                case 9:
                    if (w == 0x9409) { pc = r16(30); cy = 2; }
                    else if (w == 0x9509) { push(pc & 0xFF); push(pc >> 8); pc = r16(30); cy = xt ? 2 : 3; }
                    else falha(w);
                    break;
                default: falha(w);
            }
            break;
        }
        if (top == 0x9600) {
            int d = 24 + ((w >> 4) & 3) * 2; u16 k = ((w >> 2) & 0x30) | (w & 0xF), a = r16(d), r; bool v, c;
            if (w & 0x0100) { r = a - k; v = (a & 0x8000) && !(r & 0x8000); c = (r & 0x8000) && !(a & 0x8000); }
            else { r = a + k; v = !(a & 0x8000) && (r & 0x8000); c = !(r & 0x8000) && (a & 0x8000); }
            bool n = r & 0x8000;
            u8 f = sreg & ~(fC | fZ | fN | fV | fS);
            if (c) f |= fC; if (!r) f |= fZ; if (n) f |= fN; if (v) f |= fV; if (n != v) f |= fS;
            sreg = f; w16(d, r); cy = 2;
            break;
        }
        if (top == 0x9800 || top == 0x9A00) {
            u16 A = (tipo ? 0 : 0x20) + ((w >> 3) & 0x1F); int b = w & 7, kind = (w >> 8) & 3;
            if (kind == 0 || kind == 2) {
                // registradores de flag e PINx: escrever 1 tem efeito próprio; só o bit pedido é escrito
                bool especial = tipo ? ((A & 3) >= 2 && A < 0x0C) : (A == 0x23 || A == 0x26 || A == 0x29 || A == 0x2C || (A >= 0x35 && A <= 0x37) || A == 0x3B || A == 0x3C);
                if (especial) { if (kind == 2) wr(A, 1 << b); }
                else if (!tipo && A == 0x3F) wr(A, (mem[0x3F] & 0x38) | (kind == 2 ? (1 << b) : 0));
                else { u8 v = rd(A); wr(A, kind == 2 ? (v | (1 << b)) : (v & ~(1 << b))); }
                cy = xt ? 1 : 2;
            } else {
                bool bit = (rd(A) >> b) & 1;
                if (bit == (kind == 3)) cy += salta();
            }
            break;
        }
        if ((w & 0xFC00) == 0x9C00) { u16 p = R[d5] * R[r5]; w16(0, p); sreg = (sreg & ~(fC | fZ)) | (p >> 15) | (p == 0 ? fZ : 0); cy = 2; break; }
        falha(w);
        break;
    }
    case 0xB: {
        u16 A = (tipo ? 0 : 0x20) + ((w & 0xF) | ((w >> 5) & 0x30));
        if (w & 0x0800) wr(A, R[d5]); else R[d5] = rd(A);
        break;
    }
    case 0xC: { int k = w & 0xFFF; if (k & 0x800) k -= 0x1000; pc = (pc + k) & pcmask; cy = 2; break; }
    case 0xD: { int k = w & 0xFFF; if (k & 0x800) k -= 0x1000; push(pc & 0xFF); push(pc >> 8); pc = (pc + k) & pcmask; cy = xt ? 2 : 3; break; }
    case 0xE: R[16 + ((w >> 4) & 0xF)] = ((w >> 4) & 0xF0) | (w & 0xF); break;
    default: {
        if (!(w & 0x0800)) {
            int k = (w >> 3) & 0x7F; if (k & 0x40) k -= 0x80;
            bool bit = (sreg >> (w & 7)) & 1;
            if (bit == !(w & 0x0400)) { pc += k; cy = 2; }
        } else if ((w & 0x0E08) == 0x0800) { if (sreg & fT) R[d5] |= 1 << (w & 7); else R[d5] &= ~(1 << (w & 7)); }
        else if ((w & 0x0E08) == 0x0A00) { if ((R[d5] >> (w & 7)) & 1) sreg |= fT; else sreg &= ~fT; }
        else if ((w & 0x0C08) == 0x0C00) { bool bit = (R[d5] >> (w & 7)) & 1; if (bit == (bool)(w & 0x0200)) cy += salta(); }
        else falha(w);
    }
    }
    cyc += cy;
}

// ------------------------------------------------------------------ interface
EXP void emu_inicia(int t) {
    tipo = t;
    memset(R, 0, sizeof R); memset(mem, 0, sizeof mem);
    sreg = 0; pc = 0; cyc = 0; parou = false; irq_atraso = 0; irq_sujo = true; erro[0] = 0;
    memset(mot, 0, sizeof mot); traco.clear(); n_passo = 0;
    rx_fila.clear(); rx_pos = 0; rx_n = 0; rx_perdidos = 0; tx_fim = NUNCA; tx_cheio = false; txc = false; rx_ultimo = 0; tx_saida.clear();
    n_resets = 0; nivel_isr = false;
    if (tipo == 0) {
        F_CPU = 16e6; fis_ciclos = 256; ram_ini = 0x100; sp = 0x8FF; pcmask = 0x3FFF; bitc = 64; n_mot = 4;
        memset(&t0, 0, sizeof t0); memset(&t1, 0, sizeof t1); memset(&t2, 0, sizeof t2);
        t0.id = 0; t1.id = 1; t2.id = 2; t0.prox = t1.prox = t2.prox = NUNCA;
        eifr = eimsk = eicra = ucsra = ucsrb = 0; ee_fim = NUNCA; eempe = false;
        memset(ext_nivel, 0, 4); memset(ext_dirige, 0, 4);
    } else {
        F_CPU = 20e6; fis_ciclos = 320; ram_ini = 0x3800; pcmask = 0x1FFF; bitc = 80; n_mot = 1;
        rstfr = 0; tiny_reset(0x01); n_resets = 0; wdt_limpezas = 0;
        memset(mem + 0x1400, 0xFF, 0x100); mem[0x110C] = 0x21;   // EEPROM vazia; SERNUM9 = ID da placa
        memset(p_ext, 0, 3); memset(p_extd, 0, 3);
    }
    fis_prox = fis_ciclos; prox_evt = 0;
}
EXP void emu_carrega(const u8 *d, int n) {
    memset(flashb, 0xFF, sizeof flashb);
    memcpy(flashb, d, n);
    for (int i = 0; i < 0x8000; i++) flashw[i] = flashb[2 * i] | (flashb[2 * i + 1] << 8);
    if (tipo) memcpy(mem + 0x8000, flashb, 0x4000);
}
EXP int emu_roda(u64 ate) {
    while (cyc < ate && !parou) {
        if (cyc >= prox_evt) eventos();
        if (irq_atraso) irq_atraso = 0;
        else if (irq_sujo && (sreg & fI)) {
            int v = tipo ? tiny_irq() : mega_irq();
            if (v) {
                push(pc & 0xFF); push(pc >> 8); pc = v * 2;
                if (tipo) { nivel_isr = true; cyc += 5; } else { sreg &= ~fI; cyc += 4; }
            } else irq_sujo = false;
        }
        passo();
    }
    return parou ? 1 : 0;
}
EXP u64 emu_ciclos() { return cyc; }
EXP double emu_fcpu() { return F_CPU; }
EXP const char *emu_erro() { return erro; }
EXP u32 emu_pc() { return pc * 2; }
EXP void emu_serial_envia(const u8 *d, int n) {
    u64 t = cyc > rx_ultimo ? cyc : rx_ultimo;
    for (int i = 0; i < n; i++) { t += 10 * (u64)bitc; RxP r = {t, d[i]}; rx_fila.push_back(r); }
    rx_ultimo = t;
    if (rx_pos < rx_fila.size() && rx_fila[rx_pos].quando < prox_evt) prox_evt = rx_fila[rx_pos].quando;
}
EXP int emu_serial_le(u8 *b, double *t, int max) {
    int n = (int)tx_saida.size(); if (n > max) n = max;
    for (int i = 0; i < n; i++) { b[i] = tx_saida[i].b; t[i] = tx_saida[i].quando / F_CPU; }
    tx_saida.erase(tx_saida.begin(), tx_saida.begin() + n);
    return n;
}
EXP u32 emu_rx_perdidos() { return rx_perdidos; }
EXP void emu_mem(u16 a, u8 *b, int n, int escreve) { if (escreve) memcpy(mem + a, b, n); else memcpy(b, mem + a, n); }
EXP void emu_eeprom(u8 *b, int n, int escreve) {
    u8 *e = tipo ? mem + 0x1400 : eeprom;
    if (escreve) memcpy(e, b, n); else memcpy(b, e, n);
}
EXP void emu_motor_param(double w_nl, double tau, double a_c) { W_NL = w_nl; TAU = tau; A_C = a_c; }
EXP void emu_mao(int m, int ativa, double vel) { mot[m].mao = ativa; mot[m].mao_vel = vel; if (!ativa) mot[m].w = 0; }
EXP void emu_motor(int m, double *th, double *w) { *th = mot[m].th; *w = mot[m].w; }
EXP void emu_traco_passos(u32 n) { amostra = n ? n : 1; n_passo = 0; for (int m = 0; m < 4; m++) mot[m].acum = 0; }
EXP int emu_traco_le(double *b, int max_linhas) {
    int n = (int)(traco.size() / COLS); if (n > max_linhas) n = max_linhas;
    memcpy(b, traco.data(), (size_t)n * COLS * sizeof(double));
    traco.erase(traco.begin(), traco.begin() + (size_t)n * COLS);
    return n;
}
EXP int emu_traco_linhas() { return (int)(traco.size() / COLS); }
EXP void emu_entrada(int porta, int bit, int nivel, int dirige) {
    if (tipo == 0) { if (dirige) mega_ext(porta, bit, nivel); else ext_dirige[porta] &= ~(1 << bit); }
    else { if (dirige) tiny_ext(porta * 8 + bit, nivel); else { p_extd[porta] &= ~(1 << bit); tiny_bordas(porta); } }
    irq_sujo = true;
}
EXP int emu_pino(int porta, int bit) { return tipo == 0 ? ((mega_pin(porta) >> bit) & 1) : ((tiny_in(porta) >> bit) & 1); }
EXP void emu_tiny_pinos(int pwm_a, int pwm_b, int enc_a, int enc_b) { tm_pwm_a = pwm_a; tm_pwm_b = pwm_b; tm_enc_a = enc_a; tm_enc_b = enc_b; }
EXP u64 emu_resets() { return n_resets; }
EXP u32 emu_wdt_limpezas() { return wdt_limpezas; }
EXP u32 emu_timer(int qual, int campo) {
    Timer &t = qual == 0 ? t0 : (qual == 1 ? t1 : t2);
    switch (campo) { case 0: return t.tcnt; case 1: return t.ocra; case 2: return t.ocrb; case 3: return t.ocra_buf; case 4: return t.ocrb_buf;
                     case 5: return t.oca; case 6: return t.ocb; case 7: return t.tccra; case 8: return t.tccrb; default: return t.presc; }
}
EXP void emu_polaridade(int m, int motor_inv, int enc_inv) { mot[m].inv_m = motor_inv; mot[m].inv_e = enc_inv; }
EXP void emu_falha(int m, int falha, double k_re) { mot[m].falha = falha; mot[m].k_re = k_re; }
