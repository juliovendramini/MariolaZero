// simulador: o motor de áudio (Timer2) não roda; voz e música só aparecem no terminal
#ifndef MOTOR_AUDIO_H
#define MOTOR_AUDIO_H
#include <Arduino.h>
#define AUDIO_PINO_OC2A 11
enum { AUDIO_PARADO = 0, AUDIO_VOZ = 1, AUDIO_MUSICA = 2 };
enum { MUS_QUADRADA = 0, MUS_TRIANGULAR = 1, MUS_SENOIDAL = 2, MUS_DENTE_DE_SERRA = 3 };
static volatile uint8_t audio_modo = AUDIO_PARADO;
#endif
