// Conversa com a ponte (pacoca/ponte.py) e relógio virtual. Uso interno do núcleo.
#ifndef SIM_PONTE_H
#define SIM_PONTE_H
#include <stdint.h>

enum {
    OP_OLA = 1,          // -> pinos ligados a sensores, tensão da bateria
    OP_SYNC = 2,         // só avança o tempo
    OP_SERIAL_TX = 3,    // rx, tx, baud, byte -> bytes que voltam [(t_ns, byte)]
    OP_I2C_ESCREVE = 4,  // sda, scl, endereço, bytes -> status (0 ok, 2 NACK no endereço)
    OP_I2C_LE = 5,       // sda, scl, endereço, n -> status, bytes
    OP_PINO_SAIDA = 6,   // pino, valor 0..255 (PWM) -> -
    OP_PINO_ENTRADA = 7, // pino -> nível
    OP_ANALOGICO = 8,    // pino -> 0..1023
    OP_ULTRASSOM = 9,    // trig, echo -> distância em mm (-1 = sem eco)
    OP_LEDS = 10,        // pino, n, rgb... -> -
    OP_SERVO = 11,       // pino, pulso em us (0 = solto) -> -
    OP_FIM = 12          // programa terminou
};

// resposta: flags (bit 0 = o simulador mandou parar) + dados
struct SimResp {
    uint8_t flags;
    int n;
    uint8_t d[1024];
    int pos;
    uint8_t u8() { return pos < n ? d[pos++] : 0; }
    uint16_t u16() { uint16_t v = u8(); v |= (uint16_t)u8() << 8; return v; }
    uint32_t u32() { uint32_t v = u16(); v |= (uint32_t)u16() << 16; return v; }
    int32_t i32() { return (int32_t)u32(); }
    int64_t i64() { uint64_t v = u32(); v |= (uint64_t)u32() << 32; return (int64_t)v; }
};

struct SimReq {
    uint8_t d[1024];
    int n = 0;
    void u8(uint8_t v) { if (n < (int)sizeof d) d[n++] = v; }
    void u16(uint16_t v) { u8(v & 0xFF); u8(v >> 8); }
    void u32(uint32_t v) { u16(v & 0xFFFF); u16(v >> 16); }
    void i64(int64_t v) { u32((uint32_t)((uint64_t)v & 0xFFFFFFFFu)); u32((uint32_t)((uint64_t)v >> 32)); }
    void bytes(const uint8_t *b, int k) { for (int i = 0; i < k; i++) u8(b[i]); }
};

// relógio (ns desde que o programa começou)
extern int64_t sim_t_ns;
void sim_custo_ns(int64_t ns);          // o robô gastou ns neste trecho
void sim_sincroniza(void);              // manda o tempo atual para a ponte (força a física a andar)

// rede (sim_rede.cpp). Sem a variável PACOCA_PONTE o programa roda sozinho (sem simulador).
bool sim_rede_conecta(void);
bool sim_rede_ativa(void);
bool sim_rede_chamar(uint8_t op, int64_t t_ns, const SimReq &req, SimResp &resp);
void sim_saida(const char *s, int n);   // texto do Serial para o terminal do simulador
void sim_saida_flush(void);

// chamada completa: manda o tempo atual e encerra o programa se o simulador mandou parar
bool sim_chamar(uint8_t op, const SimReq &req, SimResp &resp);

// núcleo
void sim_leds(uint8_t pino, const uint8_t *rgb, uint8_t n);
#endif
