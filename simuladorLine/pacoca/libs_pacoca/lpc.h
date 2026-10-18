/*
 * lpc.h - Decodificador de fala LPC (formato de quadros do TMS5220 / Talkie)
 *
 * C puro, ponto fixo, sem nenhuma dependência de hardware. O MESMO arquivo é
 * compilado no AVR (pela classe Voz) e no PC (pelo teste de bit-exatidão).
 * A versão em Python (ferramentas/lpc_codec.py) é uma tradução linha a linha
 * deste arquivo; se mudar algo aqui, mude lá também e rode o teste.
 *
 * Modelo fonte-filtro:
 *   excitação (chirp periódico ou ruído) x energia -> treliça de 10 estágios -> amostra
 *
 * Quadro = 200 amostras (8 passos de interpolação de 25 amostras).
 * Taxa de amostragem no Paçoca = 16 MHz / 510 / 4 = 7843,14 Hz  (~25,5 ms por quadro)
 *
 * Formato dos quadros (bits, lidos do LSB para o MSB de cada byte, como no Talkie):
 *   energia(4)=0            -> silêncio
 *   energia(4)=15           -> fim da fala
 *   energia(4) rep(1)=1 per(6)                         -> repete os K do quadro anterior
 *   energia(4) rep(1)=0 per(6)=0 K1..K4                -> surdo  (K5..K10 = 0)
 *   energia(4) rep(1)=0 per(6)>0 K1..K10               -> sonoro
 *   bits de K: 5,5,4,4,4,4,4,3,3,3
 */
#ifndef LPC_H
#define LPC_H

#include <stdint.h>

#ifdef __AVR__
  #include <avr/pgmspace.h>
  #define LPC_FLASH PROGMEM
  #define LPC_U8(p)   pgm_read_byte(p)
  #define LPC_I8(p)   ((int8_t)pgm_read_byte(p))
  #define LPC_I16(p)  ((int16_t)pgm_read_word(p))
#else
  #define LPC_FLASH
  #define LPC_U8(p)   (*(const uint8_t *)(p))
  #define LPC_I8(p)   (*(const int8_t *)(p))
  #define LPC_I16(p)  (*(const int16_t *)(p))
#endif

#define LPC_AMOSTRAS_POR_PASSO  25
#define LPC_PASSOS_POR_QUADRO   8
#define LPC_SAIDA_MAX           2047
#define LPC_TAMANHO_CHIRP       41
#define LPC_TAMANHO_FIFO        128          /* potência de 2, no máximo 128 */

/* ---------------------------------------------------------------- tabelas */
/* Energia (amplitude da excitação). Índice 0 = silêncio, 15 = fim. */
static const uint8_t lpc_tabEnergia[16] LPC_FLASH = {
    0, 2, 3, 4, 5, 7, 10, 15, 20, 32, 41, 57, 81, 114, 161, 0 };

/* Período do pitch em amostras. Índice 0 = quadro surdo (ruído). */
static const uint8_t lpc_tabPeriodo[64] LPC_FLASH = {
      0, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30,
     31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 45, 47, 49,
     51, 53, 54, 57, 59, 61, 63, 66, 69, 71, 73, 77, 79, 81, 85, 87,
     92, 95, 99,102,106,110,115,119,123,128,133,138,143,149,154,160 };

/* Coeficientes de reflexão do TMS5220. K1 e K2 em Q15, K3..K10 em Q7. */
static const int16_t lpc_tabK1[32] LPC_FLASH = {
    -32064,-31872,-31808,-31680,-31552,-31424,-31232,-30848,
    -30592,-30336,-30016,-29696,-29376,-28928,-28480,-27968,
    -26368,-24320,-21696,-18432,-14528,-10112, -5184,   -64,
      5120, 10048, 14464, 18368, 21568, 24256, 26304, 27904 };
static const int16_t lpc_tabK2[32] LPC_FLASH = {
    -20992,-19392,-17536,-15616,-13504,-11200, -8832, -6336,
     -3776, -1152,  1536,  4096,  6720,  9152, 11520, 13760,
     15872, 17792, 19584, 21184, 22656, 23936, 25088, 26112,
     27008, 27840, 28480, 29120, 29632, 30080, 30464, 32384 };
static const int8_t lpc_tabK3[16] LPC_FLASH = {
    -110, -97, -83, -70, -56, -43, -29, -16, -2, 11, 25, 38, 52, 65, 79, 92 };
static const int8_t lpc_tabK4[16] LPC_FLASH = {
     -82, -68, -54, -40, -26, -12,   1,  15, 29, 43, 57, 71, 85, 99,113,126 };
static const int8_t lpc_tabK5[16] LPC_FLASH = {
     -82, -70, -59, -47, -35, -24, -12,  -1, 11, 22, 34, 46, 57, 69, 81, 92 };
static const int8_t lpc_tabK6[16] LPC_FLASH = {
     -64, -53, -42, -31, -20,  -9,   3,  14, 25, 36, 47, 58, 69, 80, 91,102 };
static const int8_t lpc_tabK7[16] LPC_FLASH = {
     -77, -65, -53, -41, -29, -17,  -5,   7, 19, 31, 43, 55, 67, 79, 90,102 };
static const int8_t lpc_tabK8[8] LPC_FLASH = { -64, -40, -16,  7, 31, 55, 79,102 };
static const int8_t lpc_tabK9[8] LPC_FLASH = { -64, -44, -24, -4, 16, 37, 57, 77 };
static const int8_t lpc_tabK10[8] LPC_FLASH = { -51, -33, -15,  4, 22, 40, 59, 77 };

/* Forma de onda "chirp" do TMS5220 (pulso glotal), Q7 com sinal. */
static const int8_t lpc_chirp[LPC_TAMANHO_CHIRP] LPC_FLASH = {
       0,  42, -44,  50, -78,  18,  37,  20,   2, -31, -59,   2,  95,  90,
       5,  15,  38,  -4, -91, -91, -42, -35, -36,  -4,  37,  43,  34,  33,
      15,  -1,  -8, -18, -19, -17,  -9, -10,  -6,   0,   3,   2,   1 };

/* Deslocamento da interpolação em cada um dos 8 passos do quadro. */
static const uint8_t lpc_deslocInterp[8] LPC_FLASH = { 3, 3, 3, 2, 2, 1, 1, 0 };

/* ------------------------------------------------------------- estruturas */
enum { LPC_FONTE_FLASH = 0, LPC_FONTE_RAM = 1, LPC_FONTE_FIFO = 2 };

/* FIFO circular para fala que chega aos poucos (serial). */
typedef struct {
    uint8_t buf[LPC_TAMANHO_FIFO];
    volatile uint8_t le;        /* índice de leitura  (só o decodificador mexe) */
    volatile uint8_t escreve;   /* índice de escrita  (só quem recebe mexe)     */
    volatile uint8_t terminou;  /* 1 = não vai chegar mais nada                 */
} LpcFifo;

typedef struct {
    /* leitura de bits */
    const uint8_t *ptr;
    const uint8_t *fim;          /* só para fonte RAM/FLASH (NULL = sem limite) */
    LpcFifo *fifo;
    uint8_t fonte;
    uint8_t bit;                 /* bits já consumidos do byte atual (0..7)   */

    /* parâmetros atuais (interpolados) e alvo (do quadro) */
    int16_t energia, alvoEnergia;
    int16_t periodo, alvoPeriodo;
    int16_t k[10], alvoK[10];

    /* estado da síntese */
    int16_t x[10];               /* estados de trás da treliça (b0..b9)       */
    uint16_t ruido;              /* LFSR                                      */
    uint8_t contPeriodo;
    uint8_t contAmostra;         /* amostras restantes no passo atual          */
    uint8_t passo;               /* 0..7                                       */
    uint8_t ultimoQuadro;        /* quadro de fim foi lido                      */
    uint8_t ativo;
    uint8_t faltouDados;         /* contador de quadros sem dados na FIFO       */
} LpcDecodificador;

/* ------------------------------------------------------------------- FIFO */
static inline void lpc_fifoLimpa(LpcFifo *f) { f->le = 0; f->escreve = 0; f->terminou = 0; }
static inline uint8_t lpc_fifoQuantidade(const LpcFifo *f) {
    return (uint8_t)((f->escreve - f->le) & (LPC_TAMANHO_FIFO - 1));
}
static inline uint8_t lpc_fifoLivre(const LpcFifo *f) {
    return (uint8_t)(LPC_TAMANHO_FIFO - 1 - lpc_fifoQuantidade(f));
}
static inline uint8_t lpc_fifoEscreve(LpcFifo *f, uint8_t b) {
    uint8_t prox = (uint8_t)((f->escreve + 1) & (LPC_TAMANHO_FIFO - 1));
    if (prox == f->le) return 0;          /* cheia */
    f->buf[f->escreve] = b;
    f->escreve = prox;
    return 1;
}

/* ----------------------------------------------------------- leitura bits */
static inline uint8_t lpc_byteAtual(LpcDecodificador *d) {
    if (d->fonte == LPC_FONTE_FIFO) return d->fifo->buf[d->fifo->le];
    if (d->fonte == LPC_FONTE_FLASH) return LPC_U8(d->ptr);
    return *d->ptr;
}

static inline void lpc_avancaByte(LpcDecodificador *d) {
    d->bit = 0;
    if (d->fonte == LPC_FONTE_FIFO)
        d->fifo->le = (uint8_t)((d->fifo->le + 1) & (LPC_TAMANHO_FIFO - 1));
    else
        d->ptr++;
}

/* Quantos bits ainda podem ser lidos (satura em 255). */
static inline uint8_t lpc_bitsDisponiveis(LpcDecodificador *d) {
    uint16_t bytes;
    if (d->fonte == LPC_FONTE_FIFO) bytes = lpc_fifoQuantidade(d->fifo);
    else if (d->fim == 0) return 255;
    else bytes = (uint16_t)(d->fim - d->ptr);
    if (bytes > 31) return 255;
    return (uint8_t)(bytes * 8 - d->bit);
}

static inline uint8_t lpc_lerBits(LpcDecodificador *d, uint8_t n) {
    uint8_t v = 0;
    while (n--) {
        uint8_t b = (lpc_byteAtual(d) >> d->bit) & 1;
        v = (uint8_t)((v << 1) | b);
        if (++d->bit == 8) lpc_avancaByte(d);
    }
    return v;
}

/* --------------------------------------------------------- quadro e passo */
static inline void lpc_carregaQuadro(LpcDecodificador *d) {
    uint8_t i, e, rep, ip;
    uint8_t disp = lpc_bitsDisponiveis(d);

    if (d->fonte == LPC_FONTE_FIFO && disp < 50 && !d->fifo->terminou) {
        /* ainda não chegou um quadro inteiro: toca silêncio e espera */
        d->alvoEnergia = 0;
        if (d->faltouDados < 255) d->faltouDados++;
        return;
    }
    if (disp < 4) { e = 15; }
    else e = lpc_lerBits(d, 4);

    if (e == 0) { d->alvoEnergia = 0; return; }
    if (e == 15) { d->alvoEnergia = 0; d->ultimoQuadro = 1; return; }
    if (disp < 11) { d->alvoEnergia = 0; d->ultimoQuadro = 1; return; }

    d->alvoEnergia = LPC_U8(&lpc_tabEnergia[e]);
    rep = lpc_lerBits(d, 1);
    ip  = lpc_lerBits(d, 6);
    d->alvoPeriodo = LPC_U8(&lpc_tabPeriodo[ip]);
    if (!rep) {
        if (disp < 29 || (ip && disp < 50)) { d->alvoEnergia = 0; d->ultimoQuadro = 1; return; }
        d->alvoK[0] = LPC_I16(&lpc_tabK1[lpc_lerBits(d, 5)]);
        d->alvoK[1] = LPC_I16(&lpc_tabK2[lpc_lerBits(d, 5)]);
        d->alvoK[2] = LPC_I8(&lpc_tabK3[lpc_lerBits(d, 4)]);
        d->alvoK[3] = LPC_I8(&lpc_tabK4[lpc_lerBits(d, 4)]);
        if (ip) {
            d->alvoK[4] = LPC_I8(&lpc_tabK5[lpc_lerBits(d, 4)]);
            d->alvoK[5] = LPC_I8(&lpc_tabK6[lpc_lerBits(d, 4)]);
            d->alvoK[6] = LPC_I8(&lpc_tabK7[lpc_lerBits(d, 4)]);
            d->alvoK[7] = LPC_I8(&lpc_tabK8[lpc_lerBits(d, 3)]);
            d->alvoK[8] = LPC_I8(&lpc_tabK9[lpc_lerBits(d, 3)]);
            d->alvoK[9] = LPC_I8(&lpc_tabK10[lpc_lerBits(d, 3)]);
        } else {
            for (i = 4; i < 10; i++) d->alvoK[i] = 0;
        }
    }
    /* sem interpolação ao sair do silêncio ou ao trocar sonoro <-> surdo */
    if (d->energia == 0 || ((d->periodo == 0) != (d->alvoPeriodo == 0))) {
        d->periodo = d->alvoPeriodo;
        for (i = 0; i < 10; i++) d->k[i] = d->alvoK[i];
    }
}

static inline void lpc_passo(LpcDecodificador *d) {
    uint8_t i, s;
    if (d->passo == 0) {
        if (d->ultimoQuadro) { d->ativo = 0; return; }
        lpc_carregaQuadro(d);
    }
    s = LPC_U8(&lpc_deslocInterp[d->passo]);
    d->energia += (int16_t)(d->alvoEnergia - d->energia) >> s;
    d->periodo += (int16_t)(d->alvoPeriodo - d->periodo) >> s;
    for (i = 0; i < 10; i++)
        d->k[i] += (int16_t)(d->alvoK[i] - d->k[i]) >> s;
    d->passo = (uint8_t)((d->passo + 1) & 7);
}

/* ------------------------------------------------------------ API pública */
static inline void lpc_zera(LpcDecodificador *d) {
    uint8_t i;
    for (i = 0; i < 10; i++) { d->k[i] = 0; d->alvoK[i] = 0; d->x[i] = 0; }
    d->energia = d->alvoEnergia = 0;
    d->periodo = d->alvoPeriodo = 0;
    d->ruido = 1;
    d->contPeriodo = 0;
    d->contAmostra = 0;
    d->passo = 0;
    d->bit = 0;
    d->ultimoQuadro = 0;
    d->faltouDados = 0;
    d->fifo = 0;
    d->fim = 0;
    d->ativo = 1;
}

/* fala gravada na flash (PROGMEM no AVR) */
static inline void lpc_iniciaFlash(LpcDecodificador *d, const uint8_t *dados) {
    lpc_zera(d); d->fonte = LPC_FONTE_FLASH; d->ptr = dados;
}
/* fala num vetor em RAM com tamanho conhecido */
static inline void lpc_iniciaRam(LpcDecodificador *d, const uint8_t *dados, uint16_t tamanho) {
    lpc_zera(d); d->fonte = LPC_FONTE_RAM; d->ptr = dados; d->fim = dados + tamanho;
}
/* fala chegando aos poucos numa FIFO */
static inline void lpc_iniciaFifo(LpcDecodificador *d, LpcFifo *f) {
    lpc_zera(d); d->fonte = LPC_FONTE_FIFO; d->fifo = f;
}

/* Multiplicações da treliça. Em C: (k * v) >> 7  e  (k * v) >> 15.
 * No AVR há versões em assembly que dão exatamente o mesmo resultado, mas
 * evitam as chamadas __mulhisi3 e os laços de deslocamento de 32 bits
 * (de ~65 e ~110 ciclos para ~16 e ~24 ciclos). */
#if defined(__AVR__) && !defined(LPC_SEM_ASM)
static inline __attribute__((always_inline)) int16_t lpc_q7(int8_t k, int16_t v) {
    uint8_t b0, ext;
    int16_t r;
    __asm__ (
        "muls  %[k], %B[v]      \n\t"   /* r1:r0 = k * v.alto (com sinal)       */
        "movw  %A[r], r0        \n\t"   /* r = byte1:byte2 do produto           */
        "mulsu %[k], %A[v]      \n\t"   /* r1:r0 = k * v.baixo (sem sinal)      */
        "clr   %[e]             \n\t"
        "sbrc  r1, 7            \n\t"
        "com   %[e]             \n\t"   /* extensão de sinal de r1:r0           */
        "mov   %[b0], r0        \n\t"
        "add   %A[r], r1        \n\t"
        "adc   %B[r], %[e]      \n\t"
        "lsl   %[b0]            \n\t"   /* (produto << 1) >> 8 == produto >> 7  */
        "rol   %A[r]            \n\t"
        "rol   %B[r]            \n\t"
        "clr   r1               \n\t"
        : [r] "=&r" (r), [b0] "=&r" (b0), [e] "=&r" (ext)
        : [k] "a" (k), [v] "a" (v)
        : "r0");
    return r;
}
static inline __attribute__((always_inline)) int16_t lpc_q15(int16_t k, int16_t v) {
    uint8_t p0, z;
    uint16_t p1;   /* bytes 1 e 2 do produto */
    uint8_t p3;
    int16_t r;
    __asm__ (
        "clr   %[z]             \n\t"
        "muls  %B[k], %B[v]     \n\t"   /* alto * alto  (AVR201)                */
        "mov   %B[p1], r0       \n\t"
        "mov   %[p3], r1        \n\t"
        "mul   %A[k], %A[v]     \n\t"   /* baixo * baixo                        */
        "mov   %[p0], r0        \n\t"
        "mov   %A[p1], r1       \n\t"
        "mulsu %B[k], %A[v]     \n\t"
        "sbc   %[p3], %[z]      \n\t"
        "add   %A[p1], r0       \n\t"
        "adc   %B[p1], r1       \n\t"
        "adc   %[p3], %[z]      \n\t"
        "mulsu %B[v], %A[k]     \n\t"
        "sbc   %[p3], %[z]      \n\t"
        "add   %A[p1], r0       \n\t"
        "adc   %B[p1], r1       \n\t"
        "adc   %[p3], %[z]      \n\t"
        "clr   r1               \n\t"
        "lsl   %[p0]            \n\t"   /* (produto << 1) >> 16 == produto >> 15 */
        "rol   %A[p1]           \n\t"
        "rol   %B[p1]           \n\t"
        "rol   %[p3]            \n\t"
        "mov   %A[r], %B[p1]    \n\t"
        "mov   %B[r], %[p3]     \n\t"
        : [r] "=&r" (r), [p0] "=&r" (p0), [p1] "=&r" (p1), [p3] "=&r" (p3), [z] "=&r" (z)
        : [k] "a" (k), [v] "a" (v)
        : "r0");
    return r;
}
#define LPC_Q7(k, v)   lpc_q7((int8_t)(k), (v))
#define LPC_Q15(k, v)  lpc_q15((k), (v))
#else
#define LPC_Q7(k, v)   ((int16_t)(((int32_t)(k) * (v)) >> 7))
#define LPC_Q15(k, v)  ((int16_t)(((int32_t)(k) * (v)) >> 15))
#endif

/* Gera a próxima amostra (-2047..2047). Chamar na taxa de amostragem. */
static inline int16_t lpc_proximaAmostra(LpcDecodificador *d) {
    int16_t u, u0, u1, u2, u3, u4, u5, u6, u7, u8;
    int16_t *x = d->x;
    const int16_t *k = d->k;

    if (!d->ativo) return 0;
    if (d->contAmostra == 0) {
        lpc_passo(d);
        if (!d->ativo) return 0;
        d->contAmostra = LPC_AMOSTRAS_POR_PASSO;
    }
    d->contAmostra--;

    /* excitação */
    if (d->periodo) {
        if (++d->contPeriodo >= (uint8_t)d->periodo) d->contPeriodo = 0;
        if (d->contPeriodo < LPC_TAMANHO_CHIRP)
            u = (int16_t)(((int16_t)LPC_I8(&lpc_chirp[d->contPeriodo]) * d->energia) >> 4);
        else
            u = 0;
    } else {
        d->ruido = (uint16_t)((d->ruido >> 1) ^ ((d->ruido & 1) ? 0xB800u : 0u));
        u = (d->ruido & 1) ? (int16_t)(d->energia << 2) : (int16_t)-(d->energia << 2);
    }

    /* treliça: caminho de ida (u10 -> u0) */
    u  = (int16_t)(u  - LPC_Q7(k[9], x[9]));
    u8 = (int16_t)(u  - LPC_Q7(k[8], x[8]));
    u7 = (int16_t)(u8 - LPC_Q7(k[7], x[7]));
    u6 = (int16_t)(u7 - LPC_Q7(k[6], x[6]));
    u5 = (int16_t)(u6 - LPC_Q7(k[5], x[5]));
    u4 = (int16_t)(u5 - LPC_Q7(k[4], x[4]));
    u3 = (int16_t)(u4 - LPC_Q7(k[3], x[3]));
    u2 = (int16_t)(u3 - LPC_Q7(k[2], x[2]));
    u1 = (int16_t)(u2 - LPC_Q15(k[1], x[1]));
    u0 = (int16_t)(u1 - LPC_Q15(k[0], x[0]));
    if (u0 > LPC_SAIDA_MAX) u0 = LPC_SAIDA_MAX;
    if (u0 < -LPC_SAIDA_MAX) u0 = -LPC_SAIDA_MAX;

    /* caminho de volta (onda refletida) */
    x[9] = (int16_t)(x[8] + LPC_Q7(k[8], u8));
    x[8] = (int16_t)(x[7] + LPC_Q7(k[7], u7));
    x[7] = (int16_t)(x[6] + LPC_Q7(k[6], u6));
    x[6] = (int16_t)(x[5] + LPC_Q7(k[5], u5));
    x[5] = (int16_t)(x[4] + LPC_Q7(k[4], u4));
    x[4] = (int16_t)(x[3] + LPC_Q7(k[3], u3));
    x[3] = (int16_t)(x[2] + LPC_Q7(k[2], u2));
    x[2] = (int16_t)(x[1] + LPC_Q15(k[1], u1));
    x[1] = (int16_t)(x[0] + LPC_Q15(k[0], u0));
    x[0] = u0;
    return u0;
}

/* Converte a amostra em valor de PWM (0..255, centro 128).
 * ganho em Q6: 64 = 1x (sem saturar), 128 = 2x, 255 ~ 4x. Acima de 1x os picos
 * são cortados na saída (o estado da treliça não é afetado), o que deixa a
 * fala mais alta sem perder inteligibilidade. */
static inline uint8_t lpc_paraNivel(int16_t a, uint8_t ganho) {
    int16_t v = (int16_t)(((int32_t)a * ganho) >> 10);
    if (v > 127) v = 127;
    if (v < -128) v = -128;
    return (uint8_t)(128 + v);
}

#endif /* LPC_H */
