// Arduino.h do simulador: o programa do Paçoca compila para o PC (g++) e conversa com o
// simulador pela ponte (pacoca/ponte.py). O tempo é virtual: cada função do Arduino "gasta"
// mais ou menos o tempo que gasta no ATmega328PB a 16 MHz.
//
// Diferenças conhecidas para o robô (documentadas no README):
//   * int tem 32 bits aqui (16 no AVR) e double tem 64 (32 no AVR)
//   * a RAM não tem o limite de 2 KB
//   * o cálculo do programa não gasta tempo; só as funções do Arduino gastam
#ifndef SIM_ARDUINO_H
#define SIM_ARDUINO_H

#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <ctype.h>
#include <math.h>
#include <inttypes.h>

#ifdef __cplusplus
#include <string>
#endif

#define F_CPU 16000000UL
#define ARDUINO 10819
#define ARDUINO_AVR_NANO 1
#define SIMULADOR_PACOCA 1

typedef uint8_t byte;
typedef bool boolean;
typedef uint16_t word;

#define HIGH 0x1
#define LOW 0x0
#define INPUT 0x0
#define OUTPUT 0x1
#define INPUT_PULLUP 0x2
#define LSBFIRST 0
#define MSBFIRST 1
#define CHANGE 1
#define FALLING 2
#define RISING 3
#define DEFAULT 1
#define EXTERNAL 0
#define INTERNAL 3

#define LED_BUILTIN 13
#define PIN_A0 14
#define PIN_A1 15
#define PIN_A2 16
#define PIN_A3 17
#define PIN_A4 18
#define PIN_A5 19
#define PIN_A6 20
#define PIN_A7 21
static const uint8_t A0 = 14;
static const uint8_t A1 = 15;
static const uint8_t A2 = 16;
static const uint8_t A3 = 17;
static const uint8_t A4 = 18;
static const uint8_t A5 = 19;
static const uint8_t A6 = 20;
static const uint8_t A7 = 21;
static const uint8_t SS = 10;
static const uint8_t MOSI = 11;
static const uint8_t MISO = 12;
static const uint8_t SCK = 13;
static const uint8_t SDA = 18;
static const uint8_t SCL = 19;
#define NUM_DIGITAL_PINS 22
#define NUM_ANALOG_INPUTS 8

#define PI 3.1415926535897932384626433832795
#define HALF_PI 1.5707963267948966192313216916398
#define TWO_PI 6.283185307179586476925286766559
#define DEG_TO_RAD 0.017453292519943295769236907684886
#define RAD_TO_DEG 57.295779513082320876798154814105
#define EULER 2.718281828459045235360287471352
#define SERIAL 0x0
#define DISPLAY 0x1

#ifdef __cplusplus
// como no core do AVR (macros); por isso nenhum cabeçalho da STL pode vir depois do Arduino.h
#ifndef min
#define min(a, b) ((a) < (b) ? (a) : (b))
#endif
#ifndef max
#define max(a, b) ((a) > (b) ? (a) : (b))
#endif
#endif
#define constrain(amt, low, high) ((amt) < (low) ? (low) : ((amt) > (high) ? (high) : (amt)))
#define radians(deg) ((deg) * DEG_TO_RAD)
#define degrees(rad) ((rad) * RAD_TO_DEG)
#define sq(x) ((x) * (x))
#define lowByte(w) ((uint8_t)((w) & 0xff))
#define highByte(w) ((uint8_t)((w) >> 8))
#define bitRead(value, bit) (((value) >> (bit)) & 0x01)
#define bitSet(value, bit) ((value) |= (1UL << (bit)))
#define bitClear(value, bit) ((value) &= ~(1UL << (bit)))
#define bitToggle(value, bit) ((value) ^= (1UL << (bit)))
#define bitWrite(value, bit, bitvalue) ((bitvalue) ? bitSet(value, bit) : bitClear(value, bit))
#define bit(b) (1UL << (b))
#ifndef _BV
#define _BV(b) (1 << (b))
#endif
#define clockCyclesPerMicrosecond() (F_CPU / 1000000L)
#define clockCyclesToMicroseconds(a) ((a) / clockCyclesPerMicrosecond())
#define microsecondsToClockCycles(a) ((a) * clockCyclesPerMicrosecond())
#define digitalPinToInterrupt(p) ((p) == 2 ? 0 : ((p) == 3 ? 1 : -1))
#define NOT_AN_INTERRUPT -1

// ------------------------------------------------------------------ memória de programa
#define PROGMEM
#define PGM_P const char *
#define PGM_VOID_P const void *
#define PSTR(s) (s)
#define pgm_read_byte(addr) (*(const uint8_t *)(addr))
#define pgm_read_byte_near(addr) pgm_read_byte(addr)
#define pgm_read_byte_far(addr) pgm_read_byte(addr)
#define pgm_read_word(addr) (*(const uint16_t *)(addr))
#define pgm_read_word_near(addr) pgm_read_word(addr)
#define pgm_read_dword(addr) (*(const uint32_t *)(addr))
#define pgm_read_dword_near(addr) pgm_read_dword(addr)
#define pgm_read_float(addr) (*(const float *)(addr))
#define pgm_read_float_near(addr) pgm_read_float(addr)
#define pgm_read_ptr(addr) (*(void *const *)(addr))
#define memcpy_P memcpy
#define memcmp_P memcmp
#define strcpy_P strcpy
#define strncpy_P strncpy
#define strcat_P strcat
#define strcmp_P strcmp
#define strncmp_P strncmp
#define strlen_P strlen
#define strstr_P strstr
#define sprintf_P sprintf
#define snprintf_P snprintf
#define printf_P printf

#ifdef __cplusplus
class __FlashStringHelper;
#define F(string_literal) (reinterpret_cast<const __FlashStringHelper *>(string_literal))
#endif

// ------------------------------------------------------------------ registradores
// Os registradores viram bytes de memória comum. Escrever neles não liga nada no robô
// simulado, a não ser os pinos dos motores (ver pinos.cpp). Servem para o código que mexe
// direto em registrador (LED interno, prescaler do Timer1...) compilar e rodar.
#ifdef __cplusplus
extern "C" {
#endif
extern volatile uint8_t __sim_regs[256];
#ifdef __cplusplus
}
#endif
#define _SFR_MEM8(a) (__sim_regs[(a)])
#define _SFR_MEM16(a) (*(volatile uint16_t *)&__sim_regs[(a)])
#define _SFR_IO8(a) (__sim_regs[(a) + 0x20])
#define _SFR_IO16(a) (*(volatile uint16_t *)&__sim_regs[(a) + 0x20])
#define _SFR_BYTE(sfr) (sfr)
#define _SFR_WORD(sfr) (sfr)
#define _SFR_ADDR(sfr) ((uint16_t)(&(sfr) - &__sim_regs[0]))
#define _SFR_IO_ADDR(sfr) (_SFR_ADDR(sfr) - 0x20)
#define _SFR_MEM_ADDR(sfr) _SFR_ADDR(sfr)

#include "sim_registradores.h"

#ifdef __cplusplus
// SREG: o bit I (7) liga e desliga as interrupções (cli/sei/SREG = antigo)
struct SimSREG {
    operator uint8_t() const;
    SimSREG &operator=(uint8_t v);
    SimSREG &operator|=(uint8_t v);
    SimSREG &operator&=(uint8_t v);
};
extern SimSREG SREG;
#endif

#ifdef __cplusplus
extern "C" {
#endif
void sim_cli(void);
void sim_sei(void);
#ifdef __cplusplus
}
#endif
#define cli() sim_cli()
#define sei() sim_sei()
#define interrupts() sim_sei()
#define noInterrupts() sim_cli()

// ISRs não rodam no simulador: viram funções que ninguém chama
#define ISR_BLOCK
#define ISR_NOBLOCK
#define ISR_NAKED
#define ISR_ALIASOF(v)
#define ISR(vector, ...) static void __attribute__((unused)) __sim_isr_##vector(void)
#define SIGNAL(vector) ISR(vector)
#define EMPTY_INTERRUPT(vector) ISR(vector) {}
#define reti()

// ------------------------------------------------------------------ funções do Arduino
#ifdef __cplusplus
extern "C" {
#endif
void pinMode(uint8_t pin, uint8_t mode);
void digitalWrite(uint8_t pin, uint8_t val);
int digitalRead(uint8_t pin);
int analogRead(uint8_t pin);
void analogReference(uint8_t mode);
void analogWrite(uint8_t pin, int val);
unsigned long millis(void);
unsigned long micros(void);
void delay(unsigned long ms);
void delayMicroseconds(unsigned int us);
unsigned long pulseIn(uint8_t pin, uint8_t state, unsigned long timeout);
unsigned long pulseInLong(uint8_t pin, uint8_t state, unsigned long timeout);
void shiftOut(uint8_t dataPin, uint8_t clockPin, uint8_t bitOrder, uint8_t val);
uint8_t shiftIn(uint8_t dataPin, uint8_t clockPin, uint8_t bitOrder);
void attachInterrupt(uint8_t interruptNum, void (*userFunc)(void), int mode);
void detachInterrupt(uint8_t interruptNum);
void yield(void);
void setup(void);
void loop(void);

// tempo gasto por um trecho de código que não chama o Arduino (ex.: um laço de contas)
void sim_gasta_us(double us);
void sim_gasta_ciclos(uint32_t ciclos);
void sim_reset(void);
#ifdef __cplusplus
}
#endif

#ifdef __cplusplus
unsigned long pulseIn(uint8_t pin, uint8_t state);
void tone(uint8_t pin, unsigned int frequency, unsigned long duration = 0);
void noTone(uint8_t pin);
long random(long howbig);
long random(long howsmall, long howbig);
void randomSeed(unsigned long seed);
long map(long x, long in_min, long in_max, long out_min, long out_max);
uint16_t makeWord(uint16_t w);
uint16_t makeWord(uint8_t h, uint8_t l);
#define word(...) makeWord(__VA_ARGS__)

// abs e round do AVR são macros; aqui viram funções que funcionam com qualquer tipo
template <typename T> static inline T __sim_abs(T x) { return x > 0 ? x : -x; }
#define abs(x) __sim_abs(x)

#include "WString.h"
#include "Print.h"
#include "Stream.h"
#include "HardwareSerial.h"
#endif

// digitalPinToPort e companhia (para código que acessa os registradores dos pinos)
#ifdef __cplusplus
extern "C" {
#endif
extern const uint8_t digital_pin_to_port_PGM[];
extern const uint8_t digital_pin_to_bit_mask_PGM[];
extern const uint8_t digital_pin_to_timer_PGM[];
extern const uint16_t port_to_mode_PGM[];
extern const uint16_t port_to_output_PGM[];
extern const uint16_t port_to_input_PGM[];
#ifdef __cplusplus
}
#endif
#define NOT_A_PIN 0
#define NOT_A_PORT 0
#define NOT_ON_TIMER 0
#define PB 2
#define PC 3
#define PD 4
#define PE 5
#define digitalPinToPort(P) (pgm_read_byte(digital_pin_to_port_PGM + (P)))
#define digitalPinToBitMask(P) (pgm_read_byte(digital_pin_to_bit_mask_PGM + (P)))
#define digitalPinToTimer(P) (pgm_read_byte(digital_pin_to_timer_PGM + (P)))
#define analogInPinToBit(P) (P)
#define portOutputRegister(P) ((volatile uint8_t *)(&__sim_regs[pgm_read_word(port_to_output_PGM + (P))]))
#define portInputRegister(P) ((volatile uint8_t *)(&__sim_regs[pgm_read_word(port_to_input_PGM + (P))]))
#define portModeRegister(P) ((volatile uint8_t *)(&__sim_regs[pgm_read_word(port_to_mode_PGM + (P))]))
#define digitalPinToPCICR(p) (((p) >= 0 && (p) <= 21) ? (&PCICR) : ((uint8_t *)0))
#define digitalPinToPCICRbit(p) (((p) <= 7) ? 2 : (((p) <= 13) ? 0 : 1))
#define digitalPinToPCMSK(p) (((p) <= 7) ? (&PCMSK2) : (((p) <= 13) ? (&PCMSK0) : (((p) <= 21) ? (&PCMSK1) : ((uint8_t *)0))))
#define digitalPinToPCMSKbit(p) (((p) <= 7) ? (p) : (((p) <= 13) ? ((p) - 8) : ((p) - 14)))

#endif
