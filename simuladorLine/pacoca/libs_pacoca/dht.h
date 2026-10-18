/*
 * dht.h - Sensores de temperatura e umidade DHT11 e DHT22 (AM2302) para o
 * brick Paçoca, nas portas de 1 fio digital (as mesmas dos servos: S1 a S4).
 *
 * Uso:
 *   #define SUPORTE_DHT 1
 *   #include "brickSimples.h"
 *
 *   DHT dht = DHT(PORTA_DHT_1, DHT22);     // ou DHT11
 *   brick.adiciona(dht);
 *
 *   float t = dht.temperatura();           // °C
 *   float u = dht.umidade();               // %
 *   if (!dht.ok()) Serial.println(dht.textoErro());
 *
 * O sensor só pode ser lido a cada 1 s (DHT11) ou 2 s (DHT22). Pode chamar
 * temperatura()/umidade() quantas vezes quiser: entre uma leitura e outra a
 * biblioteca devolve o último valor sem falar com o sensor. Só a primeira
 * chamada pode esperar (até 1-2 s depois do inicializa(), tempo que o sensor
 * leva para ligar). Cada leitura de verdade leva ~7 ms (DHT22) ou ~25 ms (DHT11).
 *
 * A leitura desliga as interrupções por ~5 ms (o protocolo é por tempo, com
 * bits de 26 e 70 us). Por isso:
 *   - se houver servos, a leitura espera a janela de 16 ms em que os servos
 *     estão sem pulso, para não fazer o servo tremer;
 *   - durante a voz/música (Timer2) a leitura causa um estalo;
 *   - o millis() atrasa ~4 ms a cada leitura.
 *
 * Os módulos com placa já têm o resistor de pull-up. Para o sensor solto,
 * ponha 4,7k a 10k entre o fio de dados e o 5 V (o pull-up interno do AVR
 * também é ligado, mas é fraco).
 */
#ifndef _DHT_H_
#define _DHT_H_

#include <Arduino.h>
#include "portas.h"
#include "janelaServo.h"

#define DHT11 11
#define DHT22 22
#define AM2302 22

class DHT {
public:
    enum Erro : uint8_t { OK = 0, SEM_RESPOSTA, ERRO_TEMPO, ERRO_CHECKSUM, NAO_LIDO };

private:
    uint8_t pino;
    uint8_t modelo;
    char descricaoPorta[6];
    bool inicializado;
    volatile uint8_t *_out, *_ddr, *_in;
    uint8_t _mask;

    uint32_t ultimaLeitura;     /* millis() da última tentativa */
    uint32_t ligadoEm;          /* millis() do inicializa() */
    bool jaLeu;
    bool valido;                /* já houve pelo menos uma leitura boa */
    int16_t tempDecimos;        /* décimos de °C */
    uint16_t umidDecimos;       /* décimos de % */
    Erro _erro;

    uint16_t intervaloMinimo() { return (modelo == DHT11) ? 1000 : 2000; }

    inline void soltaLinha() {        /* entrada com pull-up */
        *_ddr &= (uint8_t)~_mask;
        *_out |= _mask;
    }
    inline void puxaBaixo() {
        *_out &= (uint8_t)~_mask;
        *_ddr |= _mask;
    }

    /* Conta quantas voltas o pino fica no nível dado (pode ser 0).
     * Cada volta tem uns 8 ciclos (0,5 us a 16 MHz); passando de ~250 us
     * devolve DHT_ESTOUROU. */
    #define DHT_ESTOUROU 0xFFFF
    inline uint16_t mede(uint8_t nivel) {
        uint8_t alvo = nivel ? _mask : 0;
        uint16_t n = 0;
        while ((*_in & _mask) == alvo) {
            if (++n == 500) return DHT_ESTOUROU;
        }
        return n;
    }

    bool lerSensor() {
        uint8_t d[5] = {0, 0, 0, 0, 0};
        ultimaLeitura = millis();

        /* sinal de início: nível baixo por 20 ms (DHT11) ou 1,1 ms (DHT22).
         * A leitura (~5 ms, sem interrupções) precisa caber na janela sem
         * pulsos dos servos. No DHT22 tudo cabe: espera a janela antes. No
         * DHT11 os 20 ms não cabem: espera com a linha baixa (só alonga o
         * sinal de início, o que o DHT11 aceita). */
        if (modelo == DHT22) esperaJanelaServo(7300);
        puxaBaixo();
        if (modelo == DHT11) {
            delay(20);
            esperaJanelaServo(6000);
        } else {
            delayMicroseconds(1100);
        }

        uint8_t sreg = SREG;
        cli();
        soltaLinha();
        /* o sensor responde em 20-40 us: 80 us baixo + 80 us alto */
        if (mede(1) == DHT_ESTOUROU || mede(0) == DHT_ESTOUROU || mede(1) == DHT_ESTOUROU) {
            SREG = sreg;
            _erro = SEM_RESPOSTA;
            return false;
        }
        /* 40 bits: 50 us baixo + 26-28 us alto (0) ou 70 us alto (1).
         * Compara o alto com o baixo do mesmo bit: não depende do clock. */
        for (uint8_t i = 0; i < 40; i++) {
            uint16_t baixo = mede(0);
            uint16_t alto = mede(1);
            if (baixo == DHT_ESTOUROU || alto == DHT_ESTOUROU) {
                SREG = sreg;
                _erro = ERRO_TEMPO;
                return false;
            }
            d[i >> 3] = (uint8_t)(d[i >> 3] << 1);
            if (alto > baixo) d[i >> 3] |= 1;
        }
        SREG = sreg;

        if ((uint8_t)(d[0] + d[1] + d[2] + d[3]) != d[4]) {
            _erro = ERRO_CHECKSUM;
            return false;
        }
        if (modelo == DHT11) {
            umidDecimos = (uint16_t)d[0] * 10 + (d[1] % 10);
            tempDecimos = (int16_t)((d[2] & 0x7F) * 10 + (d[3] & 0x0F));
            if ((d[3] & 0x80) || (d[2] & 0x80)) tempDecimos = -tempDecimos;
        } else {
            umidDecimos = ((uint16_t)d[0] << 8) | d[1];
            tempDecimos = (int16_t)((((uint16_t)(d[2] & 0x7F)) << 8) | d[3]);
            if (d[2] & 0x80) tempDecimos = -tempDecimos;
        }
        _erro = OK;
        valido = true;
        return true;
    }

public:
    DHT(PortaDigital porta, uint8_t modelo = DHT22) {
        pino = porta.pino;
        this->modelo = (modelo == DHT11) ? DHT11 : DHT22;
        strncpy(descricaoPorta, porta.descricao, sizeof(descricaoPorta) - 1);
        descricaoPorta[sizeof(descricaoPorta) - 1] = 0;
        inicializado = false;
        jaLeu = false;
        valido = false;
        tempDecimos = 0;
        umidDecimos = 0;
        _erro = NAO_LIDO;
    }

    void inicializa() {
        uint8_t porta = digitalPinToPort(pino);
        _mask = digitalPinToBitMask(pino);
        _out = portOutputRegister(porta);
        _ddr = portModeRegister(porta);
        _in = portInputRegister(porta);
        soltaLinha();
        ligadoEm = millis();
        inicializado = true;
        Serial.print(modelo == DHT11 ? F("DHT11") : F("DHT22"));
        Serial.print(F(" inicializado na porta "));
        Serial.println(descricaoPorta);
    }

    /* Lê o sensor se já passou o intervalo mínimo. Retorna true se a última
     * tentativa deu certo. Não precisa chamar: temperatura() e umidade() chamam. */
    bool atualiza() {
        if (!inicializado) { _erro = NAO_LIDO; return false; }
        if (!jaLeu) {
            /* o sensor precisa de ~1 s (DHT11) / 2 s (DHT22) depois de ligado:
             * só a primeira leitura pode esperar */
            while ((millis() - ligadoEm) < intervaloMinimo()) { }
        } else {
            /* depois de uma falha tenta de novo mais cedo, sem travar o programa */
            uint16_t espera = (_erro == OK) ? intervaloMinimo() : intervaloMinimo() / 4;
            if ((millis() - ultimaLeitura) < espera) return _erro == OK;
        }
        jaLeu = true;
        return lerSensor();
    }

    /* °C. Se a leitura falhar, devolve o último valor bom (NAN se nunca leu). */
    float temperatura() {
        atualiza();
        return valido ? tempDecimos / 10.0f : NAN;
    }
    /* % de umidade relativa. */
    float umidade() {
        atualiza();
        return valido ? umidDecimos / 10.0f : NAN;
    }
    /* Sem float: 253 = 25,3 °C / 456 = 45,6 % */
    int16_t temperaturaDecimos() { atualiza(); return tempDecimos; }
    uint16_t umidadeDecimos() { atualiza(); return umidDecimos; }

    /* Sensação térmica (índice de calor da NOAA), em °C. */
    float sensacaoTermica() {
        float t = temperatura(), u = umidade();
        if (isnan(t) || isnan(u)) return NAN;
        float f = t * 1.8f + 32.0f;
        float hi = 0.5f * (f + 61.0f + ((f - 68.0f) * 1.2f) + (u * 0.094f));
        if (hi > 79.0f) {
            hi = -42.379f + 2.04901523f * f + 10.14333127f * u - 0.22475541f * f * u
                 - 0.00683783f * f * f - 0.05481717f * u * u + 0.00122874f * f * f * u
                 + 0.00085282f * f * u * u - 0.00000199f * f * f * u * u;
            if (u < 13.0f && f >= 80.0f && f <= 112.0f)
                hi -= ((13.0f - u) * 0.25f) * sqrtf((17.0f - fabsf(f - 95.0f)) * 0.05882f);
            else if (u > 85.0f && f >= 80.0f && f <= 87.0f)
                hi += ((u - 85.0f) * 0.1f) * ((87.0f - f) * 0.2f);
        }
        return (hi - 32.0f) / 1.8f;
    }

    bool ok() { return _erro == OK; }
    Erro erro() { return _erro; }
    const __FlashStringHelper *textoErro() {
        switch (_erro) {
        case OK:            return F("ok");
        case SEM_RESPOSTA:  return F("sensor nao respondeu (fio? pull-up? modelo errado?)");
        case ERRO_TEMPO:    return F("erro de tempo na leitura dos bits");
        case ERRO_CHECKSUM: return F("checksum errado (ruido ou fio longo)");
        default:            return F("ainda nao lido");
        }
    }
};

#endif
