/*
 * motorAudio.h - Motor de áudio do Paçoca usando o Timer2.
 *
 * Usado pelas classes Voz (voz.h) e Musica (musica.h). Não inclua direto:
 * defina SUPORTE_VOZ e/ou SUPORTE_MUSICA antes de incluir brickSimples.h.
 *
 * Como funciona
 *   Timer2 em PWM phase-correct de 8 bits, sem prescaler: 16 MHz / 510 = 31,37 kHz.
 *   A portadora fica acima do audível e o próprio buzzer filtra.
 *   - Na porta S3 (D11 = OC2A = MOSI) o PWM sai direto no pino: o valor de OCR2A
 *     é a amostra de áudio (voz e música com volume e timbre).
 *   - Nas outras portas só a música funciona, como onda quadrada gerada na
 *     interrupção (sem volume nem timbre).
 *
 *   Interrupções:
 *   - TIMER2_OVF (31,37 kHz): música -> calcula a onda a cada ciclo.
 *                             voz    -> a cada 4 ciclos (7843 Hz) tira uma amostra
 *                                       do buffer e pede mais quando há espaço.
 *   - TIMER2_COMPB (voz): decodifica LPC e enche o buffer COM as interrupções
 *                         ligadas (o OVF continua tocando enquanto ele calcula).
 *     O decodificador gasta ~800 ciclos por amostra (~40% da CPU enquanto fala).
 *
 * Conflitos (um anula o outro enquanto o som toca):
 *   - Servos (Servo.cpp também usa o Timer2): os servos param de receber pulso
 *     durante o som e voltam sozinhos quando ele acaba.
 *   - analogWrite() no pino 3, Buzzer/LED/servo na porta S3 durante o som.
 *   - Código que desliga interrupções por muito tempo (fita de LED, leitura
 *     do giroscópio/sensor de linha dentro de brick.atualiza()) causa estalos.
 */
#ifndef MOTOR_AUDIO_H
#define MOTOR_AUDIO_H

#include <Arduino.h>
#include <avr/interrupt.h>
#include <avr/pgmspace.h>

#ifdef SUPORTE_VOZ
#include "lpc.h"
#endif

#define AUDIO_PINO_OC2A   11      /* porta S3 */

#ifndef AUDIO_DEPURA
#define AUDIO_DEPURA(v)           /* gancho para testes (registra cada valor do PWM) */
#endif

enum { AUDIO_PARADO = 0, AUDIO_VOZ = 1, AUDIO_MUSICA = 2 };

static volatile uint8_t audio_modo = AUDIO_PARADO;
static uint8_t audio_pino = 255;
static uint8_t audio_invertido = 1;          /* buzzer ativo em nível baixo */
static uint8_t audio_usaOC2A = 0;
static volatile uint8_t *audio_porta = 0;
static uint8_t audio_mascara = 0;

/* registradores do Timer2 guardados para devolver ao dono anterior (servos) */
static uint8_t audio_salvoTCCR2A, audio_salvoTCCR2B, audio_salvoOCR2A, audio_salvoOCR2B, audio_salvoTIMSK2;

static inline __attribute__((always_inline)) void audio_pinoDesligado() {
    /* nível que deixa o buzzer sem corrente */
    if (audio_invertido) *audio_porta |= audio_mascara;
    else                 *audio_porta &= (uint8_t)~audio_mascara;
}

static inline __attribute__((always_inline)) void audio_pinoLigado() {
    if (audio_invertido) *audio_porta &= (uint8_t)~audio_mascara;
    else                 *audio_porta |= audio_mascara;
}

static void audio_libera();

/* Configura o pino (para qualquer som que esteja tocando antes). */
static void audio_configuraPino(uint8_t pino, bool invertido) {
    if (audio_modo != AUDIO_PARADO) audio_libera();
    audio_pino = pino;
    audio_invertido = invertido ? 1 : 0;
    audio_usaOC2A = (pino == AUDIO_PINO_OC2A);
    audio_porta = portOutputRegister(digitalPinToPort(pino));
    audio_mascara = digitalPinToBitMask(pino);
    pinMode(pino, OUTPUT);
    audio_pinoDesligado();
}

/* Devolve o Timer2. Pode ser chamada de dentro das interrupções. */
static void audio_libera() {
    uint8_t sreg = SREG;
    cli();
    TIMSK2 &= (uint8_t)~(_BV(TOIE2) | _BV(OCIE2B));
    TCCR2A &= (uint8_t)~(_BV(COM2A1) | _BV(COM2A0));    /* solta o OC2A */
    if (audio_porta) audio_pinoDesligado();
    if (audio_salvoTIMSK2 & _BV(OCIE2A)) {
        /* havia servos: recomeça o ciclo deles na fase de espera (prescaler 1024) */
        TCCR2A = 0;
        TCNT2 = 0;
        OCR2A = 255;
        TCCR2B = _BV(CS22) | _BV(CS21) | _BV(CS20);
        TIFR2 = _BV(OCF2A) | _BV(OCF2B) | _BV(TOV2);
        TIMSK2 = _BV(OCIE2A);
    } else {
        TCCR2B = audio_salvoTCCR2B;
        TCCR2A = audio_salvoTCCR2A;
        OCR2A = audio_salvoOCR2A;
        OCR2B = audio_salvoOCR2B;
        TIFR2 = _BV(OCF2A) | _BV(OCF2B) | _BV(TOV2);
        TIMSK2 = audio_salvoTIMSK2;
    }
    audio_modo = AUDIO_PARADO;
    SREG = sreg;
}

/* Pega o Timer2 para o áudio. Se houver servos ativos, espera eles terminarem
 * o pulso (no máximo ~20 ms) para não deixar nenhum servo com o pino em nível alto. */
static void audio_assume() {
    if (audio_modo != AUDIO_PARADO) audio_libera();
    if (TIMSK2 & _BV(OCIE2A)) {
        uint32_t t0 = millis();
        while ((TCCR2B & 7) != 7 && (millis() - t0) < 25) { }
    }
    uint8_t sreg = SREG;
    cli();
    audio_salvoTCCR2A = TCCR2A;
    audio_salvoTCCR2B = TCCR2B;
    audio_salvoOCR2A = OCR2A;
    audio_salvoOCR2B = OCR2B;
    audio_salvoTIMSK2 = TIMSK2;
    TIMSK2 = 0;
    TCCR2B = 0;
    TCNT2 = 0;
    OCR2A = 0;                         /* 0 = buzzer sem corrente nos dois modos */
    OCR2B = 128;                       /* referência da interrupção de cálculo da voz */
    uint8_t com = 0;
    if (audio_usaOC2A) com = audio_invertido ? (_BV(COM2A1) | _BV(COM2A0)) : _BV(COM2A1);
    TCCR2A = com | (TCCR2A & (_BV(COM2B1) | _BV(COM2B0))) | _BV(WGM20);   /* phase-correct, TOP=0xFF */
    TIFR2 = _BV(OCF2A) | _BV(OCF2B) | _BV(TOV2);
    TCCR2B = _BV(CS20);                /* sem prescaler: 31,37 kHz */
    SREG = sreg;
}

/* ====================================================================== VOZ */
#ifdef SUPORTE_VOZ

#define VOZ_TAM_BUF 16                 /* amostras já calculadas (potência de 2) */
#define VOZ_MASC   (VOZ_TAM_BUF - 1)

enum { VOZ_PARADA = 0, VOZ_SUBINDO, VOZ_FALANDO, VOZ_DESCENDO, VOZ_TERMINADA };

static LpcDecodificador voz_dec;
static uint8_t voz_buf[VOZ_TAM_BUF];
static volatile uint8_t voz_le = 0, voz_escreve = 0;
static volatile uint8_t voz_estado = VOZ_PARADA;
static volatile uint8_t voz_calculando = 0;
static uint8_t voz_rampa = 0;
static volatile uint8_t voz_divisor = 0;
static uint8_t voz_ganho = 128;        /* Q6: 64 = 1x */
static volatile uint16_t voz_atrasos = 0;   /* amostras que não ficaram prontas a tempo */
#ifdef SUPORTE_VOZ_SERIAL
static LpcFifo voz_fifo;
#endif

/* Próximo valor de PWM. Roda dentro da interrupção de cálculo. */
static uint8_t voz_amostra() {
    switch (voz_estado) {
    case VOZ_SUBINDO:                  /* rampa de 0 até o centro (~8 ms): evita estalo */
        voz_rampa += 2;
        if (voz_rampa >= 128) { voz_rampa = 128; voz_estado = VOZ_FALANDO; }
        return voz_rampa;
    case VOZ_FALANDO: {
        int16_t a = lpc_proximaAmostra(&voz_dec);
        if (!voz_dec.ativo) { voz_estado = VOZ_DESCENDO; return 128; }
        return lpc_paraNivel(a, voz_ganho);
    }
    case VOZ_DESCENDO:
        if (voz_rampa > 2) voz_rampa -= 2;
        else { voz_rampa = 0; voz_estado = VOZ_TERMINADA; }
        return voz_rampa;
    default:
        return 0;
    }
}

static void voz_inicia() {
    audio_assume();
    voz_le = 0;
    voz_escreve = 0;
    voz_rampa = 0;
    voz_divisor = 0;
    voz_atrasos = 0;
    voz_calculando = 0;
    voz_estado = VOZ_SUBINDO;
    /* já deixa o buffer cheio antes de ligar */
    while (((voz_escreve + 1) & VOZ_MASC) != voz_le) {
        voz_buf[voz_escreve] = voz_amostra();
        voz_escreve = (voz_escreve + 1) & VOZ_MASC;
    }
    audio_modo = AUDIO_VOZ;
    TIFR2 = _BV(TOV2);
    TIMSK2 = _BV(TOIE2);
}

static inline bool voz_ativa() { return audio_modo == AUDIO_VOZ; }

#endif /* SUPORTE_VOZ */

/* =================================================================== MÚSICA */
#ifdef SUPORTE_MUSICA

enum { MUS_QUADRADA = 0, MUS_TRIANGULAR = 1, MUS_SENOIDAL = 2, MUS_DENTE_DE_SERRA = 3 };

/* incremento de fase (16 bits por ciclo de 31,37 kHz) das notas da oitava 8 (C8..B8) */
static const uint16_t mus_incOitava8[12] PROGMEM = {
    8744, 9264, 9815, 10399, 11017, 11672, 12366, 13102, 13881, 14706, 15581, 16507 };

/* meia senoide de 0..255 (só o primeiro quarto, 65 pontos) */
static const uint8_t mus_seno[65] PROGMEM = {
    128,131,134,137,140,144,147,150,153,156,159,162,165,168,171,174,
    177,179,182,185,188,191,193,196,199,201,204,206,209,211,213,216,
    218,220,222,224,226,228,230,232,234,235,237,239,240,241,243,244,
    245,246,248,249,250,250,251,252,253,253,254,254,254,255,255,255,255 };

static volatile uint16_t mus_fase = 0;
static volatile uint16_t mus_inc = 0;
static volatile uint8_t  mus_amp = 0;        /* amplitude atual (0..255) */
static uint16_t mus_amp16 = 0;               /* amplitude com fração, para o decaimento */
static uint8_t  mus_ampMax = 255;            /* volume */
static uint8_t  mus_timbre = MUS_QUADRADA;
static uint8_t  mus_decai = 0;
static uint8_t  mus_subms = 31, mus_frac = 0;
static uint16_t mus_restante = 0;            /* ms até o fim da nota */
static uint16_t mus_pausa = 0;               /* ms finais da nota em silêncio */
static const char *mus_ptr = 0;              /* próximo caractere do RTTTL (PROGMEM) */
static const char *mus_inicioNotas = 0;
static uint8_t  mus_padDur = 4, mus_padOit = 6;
static uint16_t mus_msSemibreve = 2000;      /* 4 tempos em ms */
static uint8_t  mus_repetir = 0;
static volatile uint8_t mus_tocando = 0;
static volatile uint8_t mus_msPendentes = 0;      /* ms contados no OVF e ainda não tratados */

static inline uint16_t mus_incDaFrequencia(uint16_t f) {
    return (uint16_t)(((uint32_t)f * 68452UL) >> 15);   /* f * 65536 / 31372,5 */
}

static void mus_comecaNota(uint16_t inc, uint16_t ms) {
    mus_inc = inc;
    mus_restante = ms;
    uint16_t p = ms / 10;
    if (p > 30) p = 30;
    if (p < 5 && ms > 20) p = 5;
    mus_pausa = (inc == 0) ? ms : p;
    mus_amp16 = (inc == 0) ? 0 : ((uint16_t)mus_ampMax << 8);
    mus_amp = (uint8_t)(mus_amp16 >> 8);
}

static uint16_t mus_lerNumero(const char **p) {
    uint16_t n = 0;
    char c;
    while ((c = pgm_read_byte(*p)) >= '0' && c <= '9') { n = n * 10 + (c - '0'); (*p)++; }
    return n;
}

/* Lê a próxima nota do RTTTL. Retorna false no fim. */
static bool mus_proximaNota() {
    if (!mus_ptr) return false;
    const char *p = mus_ptr;
    char c;
    while ((c = pgm_read_byte(p)) == ' ' || c == ',') p++;
    if (c == 0) {
        if (!mus_repetir) return false;
        p = mus_inicioNotas;
    }
    uint16_t dur = mus_lerNumero(&p);
    if (dur == 0) dur = mus_padDur;
    uint8_t pontuada = 0;
    if (pgm_read_byte(p) == '.') { pontuada = 1; p++; }     /* "8.g" */
    c = pgm_read_byte(p);
    if (c >= 'A' && c <= 'Z') c += 32;
    int8_t semitom = -1;
    switch (c) {
        case 'c': semitom = 0; break;  case 'd': semitom = 2; break;
        case 'e': semitom = 4; break;  case 'f': semitom = 5; break;
        case 'g': semitom = 7; break;  case 'a': semitom = 9; break;
        case 'b': case 'h': semitom = 11; break;
        case 'p': semitom = -1; break;
        default: mus_ptr = 0; return false;   /* texto inválido: para */
    }
    p++;
    if (pgm_read_byte(p) == '#') { semitom++; p++; }
    if (pgm_read_byte(p) == '.') { pontuada = 1; p++; }
    uint8_t oit = mus_padOit;
    c = pgm_read_byte(p);
    if (c >= '0' && c <= '9') { oit = c - '0'; p++; }
    if (pgm_read_byte(p) == '.') { pontuada = 1; p++; }
    mus_ptr = p;

    uint32_t ms = mus_msSemibreve / dur;
    if (pontuada) ms += ms / 2;
    uint16_t inc = 0;
    if (semitom >= 0) {
        if (semitom == 12) { semitom = 0; oit++; }   /* b# */
        if (oit > 8) oit = 8;
        if (oit < 3) oit = 3;
        inc = pgm_read_word(&mus_incOitava8[semitom]) >> (8 - oit);
    }
    mus_comecaNota(inc, (uint16_t)ms);
    return true;
}

/* Chamado a cada 1 ms (de dentro do OVF). */
static void mus_tickMs() {
    if (mus_restante) {
        mus_restante--;
        if (mus_restante <= mus_pausa) { mus_amp = 0; mus_amp16 = 0; }
        else if (mus_decai) { mus_amp16 -= mus_amp16 >> 8; mus_amp = (uint8_t)(mus_amp16 >> 8); }
        return;
    }
    if (!mus_proximaNota()) {
        mus_tocando = 0;
        audio_libera();
    }
}

static inline __attribute__((always_inline)) uint8_t mus_onda(uint16_t fase) {
    uint8_t f = (uint8_t)(fase >> 8);
    switch (mus_timbre) {
    case MUS_TRIANGULAR:  return (f & 0x80) ? (uint8_t)((255 - f) << 1) : (uint8_t)(f << 1);
    case MUS_DENTE_DE_SERRA: return f;
    case MUS_SENOIDAL: {
        uint8_t q = f & 0x3F;
        switch (f >> 6) {
        case 0:  return pgm_read_byte(&mus_seno[q]);
        case 1:  return pgm_read_byte(&mus_seno[64 - q]);
        case 2:  return (uint8_t)(255 - pgm_read_byte(&mus_seno[q]));
        default: return (uint8_t)(255 - pgm_read_byte(&mus_seno[64 - q]));
        }
    }
    default: return (f & 0x80) ? 255 : 0;
    }
}

static void mus_inicia() {
    audio_assume();
    mus_fase = 0;
    mus_subms = 31;
    mus_frac = 0;
    mus_msPendentes = 0;
    mus_tocando = 1;
    audio_modo = AUDIO_MUSICA;
    TIFR2 = _BV(TOV2);
    TIMSK2 = _BV(TOIE2);
}
#endif /* SUPORTE_MUSICA */

/* ============================================================ interrupções
 *
 * TIMER2_OVF (31,37 kHz) precisa ser leve:
 *   - a entrada é "naked" em assembly: na voz, 3 de cada 4 ciclos só contam e
 *     saem (~14 ciclos de CPU). Nos outros casos pula para __vector_audio_t2ovf.
 *   - __vector_audio_t2ovf não chama nenhuma função, então o compilador salva
 *     poucos registradores.
 * TIMER2_COMPB é usado como "interrupção de software": o OVF liga o OCIE2B
 * quando há trabalho pesado (decodificar voz, trocar de nota, liberar o timer)
 * e esse trabalho roda com as interrupções habilitadas.
 */
#if defined(SUPORTE_VOZ) || defined(SUPORTE_MUSICA)

#ifndef SUPORTE_VOZ
static volatile uint8_t voz_divisor = 0;
#endif

extern "C" void __vector_audio_t2ovf(void) __attribute__((signal, used, externally_visible));

ISR(TIMER2_OVF_vect, ISR_NAKED) {
    __asm__ __volatile__(
        "push r24                   \n\t"
        "in   r24, __SREG__         \n\t"
        "push r24                   \n\t"
        "lds  r24, %[modo]          \n\t"
        "cpi  r24, %[voz]           \n\t"
        "brne 1f                    \n\t"
        "lds  r24, %[div]           \n\t"
        "inc  r24                   \n\t"
        "sts  %[div], r24           \n\t"
        "andi r24, 3                \n\t"   /* voz: 1 amostra a cada 4 ciclos */
        "breq 1f                    \n\t"
        "pop  r24                   \n\t"
        "out  __SREG__, r24         \n\t"
        "pop  r24                   \n\t"
        "reti                       \n\t"
        "1:                         \n\t"
        "pop  r24                   \n\t"
        "out  __SREG__, r24         \n\t"
        "pop  r24                   \n\t"
        "jmp  __vector_audio_t2ovf  \n\t"
        :
        : [modo] "i" (&audio_modo), [div] "i" (&voz_divisor), [voz] "M" (AUDIO_VOZ));
}

void __vector_audio_t2ovf(void) {
#ifdef SUPORTE_VOZ
    if (audio_modo == AUDIO_VOZ) {
        uint8_t le = voz_le;
        if (le != voz_escreve) {
            OCR2A = voz_buf[le];
            AUDIO_DEPURA(voz_buf[le]);
            le = (le + 1) & VOZ_MASC;
            voz_le = le;
        } else if (voz_estado == VOZ_TERMINADA) {
            TIMSK2 |= _BV(OCIE2B);             /* o COMPB libera o timer */
            return;
        } else {
            voz_atrasos++;
        }
        /* pede mais amostras quando há pelo menos 4 lugares livres */
        if (!voz_calculando && (((le - voz_escreve - 1) & VOZ_MASC) >= 4))
            TIMSK2 |= _BV(OCIE2B);
        return;
    }
#endif
#ifdef SUPORTE_MUSICA
    if (audio_modo == AUDIO_MUSICA) {
        uint16_t f = mus_fase + mus_inc;
        mus_fase = f;
        if (audio_usaOC2A) {
            uint8_t v = (uint8_t)(((uint16_t)mus_onda(f) * mus_amp) >> 8);
            OCR2A = v;
            AUDIO_DEPURA(v);
        } else {
            if ((f & 0x8000) && mus_amp) audio_pinoLigado();
            else audio_pinoDesligado();
        }
        if (--mus_subms == 0) {
            uint8_t fr = mus_frac;
            mus_frac = (uint8_t)(fr + 95);     /* 31 + 95/256 = 31,37 ciclos por ms */
            mus_subms = (mus_frac < fr) ? 32 : 31;
            mus_msPendentes++;
            TIMSK2 |= _BV(OCIE2B);
        }
    }
#endif
}

ISR(TIMER2_COMPB_vect) {
    TIMSK2 &= (uint8_t)~_BV(OCIE2B);           /* não entra de novo enquanto trabalha */
#ifdef SUPORTE_MUSICA
    if (audio_modo == AUDIO_MUSICA) {
        sei();
        uint8_t n;
        while (audio_modo == AUDIO_MUSICA) {
            cli();
            n = mus_msPendentes;
            if (n) mus_msPendentes = n - 1;
            sei();
            if (!n) break;
            mus_tickMs();
        }
        cli();
        return;
    }
#endif
#ifdef SUPORTE_VOZ
    if (audio_modo == AUDIO_VOZ) {
        if (voz_estado == VOZ_TERMINADA && voz_le == voz_escreve) {
            voz_estado = VOZ_PARADA;
            audio_libera();
            return;
        }
        voz_calculando = 1;
        sei();
        uint8_t e = voz_escreve;
        while (((e + 1) & VOZ_MASC) != voz_le && voz_estado != VOZ_TERMINADA) {
            voz_buf[e] = voz_amostra();
            e = (e + 1) & VOZ_MASC;
            voz_escreve = e;
        }
        cli();
        voz_calculando = 0;
    }
#endif
}
#endif

#endif /* MOTOR_AUDIO_H */
