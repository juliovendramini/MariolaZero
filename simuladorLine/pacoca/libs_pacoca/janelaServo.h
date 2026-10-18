/*
 * janelaServo.h - Ajuda sensores que precisam desligar as interrupções
 * (DHT, DS18B20) a não atrapalhar os servos.
 *
 * O Servo.cpp do brick usa o Timer2 assim, num ciclo de ~20 ms:
 *   - prescaler 256 (CS22|CS21) enquanto gera os pulsos (até ~4 ms);
 *   - prescaler 1024 (CS22|CS21|CS20) na espera (~16 ms, TCNT2 de 0 a 255,
 *     64 us por passo), quando nenhum servo está com o pino em nível alto.
 * Desligar as interrupções durante um pulso estica o pulso e o servo treme.
 * esperaJanelaServo(us) espera estar na espera com pelo menos 'us' livres.
 */
#ifndef _JANELA_SERVO_H_
#define _JANELA_SERVO_H_

#include <Arduino.h>

static inline bool janelaServoLivre(uint8_t limite) {
    if (!(TIMSK2 & _BV(OCIE2A))) return true;          /* sem servos (ou Timer2 com outro dono) */
    if ((TCCR2B & 7) != 7) return false;               /* gerando pulsos */
    if (TIFR2 & _BV(OCF2A)) return false;              /* a interrupção do servo vai entrar agora */
    uint8_t t = TCNT2;
    /* t == 0 também pode ser o fim da espera dando a volta (255 -> 0) antes
     * da interrupção do servo rodar: espera o t sair do 0 */
    return t >= 1 && t < limite;
}

static void esperaJanelaServo(uint16_t us) {
    uint16_t passos = (uint16_t)(us / 64 + 2);
    uint8_t limite = (passos >= 250) ? 5 : (uint8_t)(255 - passos);
    if (janelaServoLivre(limite)) return;
    uint32_t t0 = millis();
    while (!janelaServoLivre(limite) && (millis() - t0) < 25) { }
}

#endif
