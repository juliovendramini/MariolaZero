/*
 * ds18b20.h - Sensor de temperatura DS18B20 (1-Wire) para o brick Paçoca,
 * nas portas de 1 fio digital (as mesmas dos servos: S1 a S4).
 * Também lê DS18S20 e DS1822.
 *
 * Uso:
 *   #define SUPORTE_DS18B20 1
 *   #include "brickSimples.h"
 *
 *   DS18B20 termometro = DS18B20(PORTA_DS18B20_2);
 *   brick.adiciona(termometro);
 *
 *   float t = termometro.temperatura();         // °C
 *
 * Vários sensores no mesmo fio: até 4 por porta (ligados em paralelo).
 *   termometro.quantidade();                    // quantos achou
 *   termometro.temperatura(1);                  // o segundo sensor
 *
 * Não bloqueia: a conversão do sensor leva até 750 ms (12 bits), então a
 * biblioteca deixa uma conversão sempre rodando e temperatura() devolve a
 * última pronta. Só a primeira chamada espera a primeira conversão.
 * Para conversão mais rápida (menos precisão): resolucao(9) = 94 ms, 0,5 °C.
 *
 * Precisa de um resistor de 4,7k entre o fio de dados e o 5 V (os módulos
 * com placa já têm). O pull-up interno do AVR também é ligado e costuma
 * bastar para um sensor com fio curto. Modo "parasita" (só 2 fios) não é
 * suportado: ligue o VDD do sensor no 5 V.
 *
 * Cada bit do protocolo desliga as interrupções por até ~70 us: não atrapalha
 * os servos de forma visível, mas pode dar pequenos estalos na voz/música.
 */
#ifndef _DS18B20_H_
#define _DS18B20_H_

#include <Arduino.h>
#include "portas.h"
#include "janelaServo.h"

#define DS18B20_MAX_SENSORES 4
#define DS18B20_ERRO -12700        /* centésimos: -127,00 °C */

class DS18B20 {
private:
    uint8_t pino;
    char descricaoPorta[6];
    bool inicializado;
    volatile uint8_t *_out, *_ddr, *_in;
    uint8_t _mask;

    uint8_t rom[DS18B20_MAX_SENSORES][8];
    int16_t centesimos[DS18B20_MAX_SENSORES];
    bool valido[DS18B20_MAX_SENSORES];
    uint8_t qtd;
    uint8_t bits;                 /* resolução: 9..12 */
    bool convertendo;
    uint32_t inicioConversao;
    bool ultimaOk;
    bool semResposta;
    uint32_t ultimaFalha;
    bool jaEsperou;               /* a espera da primeira conversão só acontece uma vez */

    /* ------------------------------------------------------ 1-Wire */
    inline void solta() { *_ddr &= (uint8_t)~_mask; *_out |= _mask; }      /* entrada com pull-up */
    inline void baixo() { *_out &= (uint8_t)~_mask; *_ddr |= _mask; }
    inline bool le() { return (*_in & _mask) != 0; }

    /* Cada bit desliga as interrupções por até ~70 us: com servos, espera a
     * parte do ciclo sem pulsos (veja janelaServo.h). O 1-Wire aceita qualquer
     * intervalo entre bits, então a espera só deixa a comunicação mais lenta. */
    inline void esperaJanelaServoDS(uint16_t us) {
        if (!(TIMSK2 & _BV(OCIE2A))) return;
        esperaJanelaServo(us);
    }

    /* Pulso de reset. Retorna true se algum sensor respondeu (presença). */
    bool reset() {
        uint8_t sreg = SREG;
        solta();
        uint8_t n = 125;                      /* espera a linha subir (até ~250 us) */
        while (!le()) {
            if (--n == 0) return false;       /* linha em curto com o GND */
            delayMicroseconds(2);
        }
        esperaJanelaServoDS(700);             /* o reset inteiro cabe na janela */
        cli();
        baixo();
        SREG = sreg;
        delayMicroseconds(480);
        cli();
        solta();
        delayMicroseconds(70);
        bool presente = !le();
        SREG = sreg;
        delayMicroseconds(410);
        return presente;
    }

    void escreveBit(bool b) {
        esperaJanelaServoDS(80);
        uint8_t sreg = SREG;
        cli();
        baixo();
        if (b) {
            delayMicroseconds(10);
            solta();
            SREG = sreg;
            delayMicroseconds(55);
        } else {
            delayMicroseconds(65);
            solta();
            SREG = sreg;
            delayMicroseconds(5);
        }
    }

    bool leBit() {
        esperaJanelaServoDS(80);
        uint8_t sreg = SREG;
        cli();
        baixo();
        delayMicroseconds(3);
        solta();
        delayMicroseconds(10);
        bool b = le();
        SREG = sreg;
        delayMicroseconds(53);
        return b;
    }

    void escreveByte(uint8_t v) {
        for (uint8_t i = 0; i < 8; i++) { escreveBit(v & 1); v >>= 1; }
    }

    uint8_t leByte() {
        uint8_t v = 0;
        for (uint8_t i = 0; i < 8; i++) { v >>= 1; if (leBit()) v |= 0x80; }
        return v;
    }

    static uint8_t crc8(const uint8_t *d, uint8_t n) {
        uint8_t crc = 0;
        while (n--) {
            uint8_t b = *d++;
            for (uint8_t i = 0; i < 8; i++) {
                uint8_t mix = (crc ^ b) & 1;
                crc >>= 1;
                if (mix) crc ^= 0x8C;
                b >>= 1;
            }
        }
        return crc;
    }

    /* Busca de ROM (algoritmo da nota de aplicação 187 da Maxim). */
    uint8_t buscaUltimaDiscrepancia;
    bool buscaFim;
    bool busca(uint8_t r[8]) {
        if (buscaFim) return false;
        if (!reset()) { buscaFim = true; return false; }
        escreveByte(0xF0);                    /* SEARCH ROM */
        uint8_t ultimoZero = 0;
        for (uint8_t i = 1; i <= 64; i++) {
            uint8_t byte = (uint8_t)((i - 1) >> 3);
            uint8_t mask = (uint8_t)(1 << ((i - 1) & 7));
            bool b = leBit();
            bool cb = leBit();
            bool dir;
            if (b && cb) { buscaFim = true; return false; }   /* ninguém respondeu */
            if (b != cb) dir = b;
            else {
                if (i < buscaUltimaDiscrepancia) dir = (r[byte] & mask) != 0;
                else dir = (i == buscaUltimaDiscrepancia);
                if (!dir) ultimoZero = i;
            }
            if (dir) r[byte] |= mask; else r[byte] &= (uint8_t)~mask;
            escreveBit(dir);
        }
        buscaUltimaDiscrepancia = ultimoZero;
        if (ultimoZero == 0) buscaFim = true;
        return true;
    }

    void selecionaSensor(uint8_t i) {
        if (qtd == 1) {
            escreveByte(0xCC);                /* SKIP ROM */
        } else {
            escreveByte(0x55);                /* MATCH ROM */
            for (uint8_t k = 0; k < 8; k++) escreveByte(rom[i][k]);
        }
    }

    uint16_t tempoConversao() {               /* ms, com folga */
        switch (bits) {
            case 9:  return 100;
            case 10: return 190;
            case 11: return 380;
            default: return 760;
        }
    }

    void iniciaConversao() {
        if (!reset()) {
            /* ninguém respondeu (fio solto?): tenta de novo só daqui a 500 ms,
             * para não gastar ~1 ms em cada chamada */
            ultimaOk = false;
            semResposta = true;
            ultimaFalha = millis();
            return;
        }
        semResposta = false;
        escreveByte(0xCC);                    /* todos ao mesmo tempo */
        escreveByte(0x44);                    /* CONVERT T */
        convertendo = true;
        inicioConversao = millis();
    }

    bool lerSensor(uint8_t i) {
        uint8_t d[9];
        if (!reset()) return false;
        selecionaSensor(i);
        escreveByte(0xBE);                    /* READ SCRATCHPAD */
        for (uint8_t k = 0; k < 9; k++) d[k] = leByte();
        if (crc8(d, 8) != d[8]) return false;
        bool todosZero = true;
        for (uint8_t k = 0; k < 9; k++) if (d[k]) todosZero = false;
        if (todosZero) return false;

        int16_t bruto = (int16_t)(((uint16_t)d[1] << 8) | d[0]);
        if (rom[i][0] == 0x10) {              /* DS18S20: 9 bits + COUNT_REMAIN */
            bruto = (int16_t)(bruto << 3);
            if (d[7] == 0x10) bruto = (int16_t)((bruto & 0xFFF0) + 12 - d[6]);
        } else {
            uint8_t cfg = d[4] & 0x60;        /* zera os bits indefinidos */
            if (cfg == 0x00) bruto &= ~7;
            else if (cfg == 0x20) bruto &= ~3;
            else if (cfg == 0x40) bruto &= ~1;
        }
        int32_t x = (int32_t)bruto * 25;                     /* 1/16 °C -> centésimos, arredondado */
        int16_t c = (int16_t)((x + (x >= 0 ? 2 : -2)) / 4);
        /* 85,00 °C é o valor de quando a conversão não aconteceu (queda de energia) */
        if (c == 8500 && !(valido[i] && centesimos[i] > 8000)) return false;
        centesimos[i] = c;
        valido[i] = true;
        return true;
    }

    void escreveResolucao() {
        uint8_t cfg = (uint8_t)(((bits - 9) << 5) | 0x1F);
        if (!reset()) return;
        escreveByte(0xCC);
        escreveByte(0x4E);                    /* WRITE SCRATCHPAD: TH, TL, config */
        escreveByte(0x4B);
        escreveByte(0x46);
        escreveByte(cfg);
    }

public:
    DS18B20(PortaDigital porta) {
        pino = porta.pino;
        strncpy(descricaoPorta, porta.descricao, sizeof(descricaoPorta) - 1);
        descricaoPorta[sizeof(descricaoPorta) - 1] = 0;
        inicializado = false;
        qtd = 0;
        bits = 12;
        convertendo = false;
        ultimaOk = false;
        semResposta = false;
        ultimaFalha = 0;
        jaEsperou = false;
        for (uint8_t i = 0; i < DS18B20_MAX_SENSORES; i++) { valido[i] = false; centesimos[i] = DS18B20_ERRO; }
    }

    void inicializa() {
        uint8_t porta = digitalPinToPort(pino);
        _mask = digitalPinToBitMask(pino);
        _out = portOutputRegister(porta);
        _ddr = portModeRegister(porta);
        _in = portInputRegister(porta);
        solta();
        delay(2);

        /* procura os sensores no fio */
        qtd = 0;
        buscaUltimaDiscrepancia = 0;
        buscaFim = false;
        uint8_t r[8] = {0};
        uint8_t tentativas = 0;
        while (qtd < DS18B20_MAX_SENSORES && tentativas < 10) {
            tentativas++;
            if (!busca(r)) break;
            if (crc8(r, 7) != r[7]) continue;                        /* leitura ruim */
            if (r[0] != 0x28 && r[0] != 0x10 && r[0] != 0x22) continue;   /* não é termômetro */
            bool repetido = false;
            for (uint8_t i = 0; i < qtd; i++) if (memcmp(rom[i], r, 8) == 0) repetido = true;
            if (repetido) continue;
            memcpy(rom[qtd++], r, 8);
        }
        if (qtd == 0) {
            Serial.print(F("Erro: nenhum DS18B20 encontrado na porta "));
            Serial.println(descricaoPorta);
            while (1);
        }
        escreveResolucao();
        inicializado = true;
        Serial.print(F("DS18B20: "));
        Serial.print(qtd);
        Serial.print(F(" sensor(es) na porta "));
        Serial.println(descricaoPorta);
        iniciaConversao();
    }

private:
    /* Se a conversão em andamento terminou, lê os sensores. */
    bool colheConversao() {
        if (!convertendo || (millis() - inicioConversao) < tempoConversao()) return false;
        convertendo = false;
        ultimaOk = true;
        for (uint8_t i = 0; i < qtd; i++) {
            bool ok = lerSensor(i);
            if (!ok) ok = lerSensor(i);           /* segunda chance */
            if (!ok) ultimaOk = false;
        }
        return true;
    }

    /* Espera a conversão em andamento terminar e lê (sem começar outra). */
    void terminaConversao() {
        while (convertendo) colheConversao();
    }

public:
    /* Mantém as conversões rodando. Não precisa chamar: temperatura() chama.
     * Retorna true quando acabou de ler valores novos. */
    bool atualiza() {
        if (!inicializado) return false;
        bool leu = colheConversao();
        if (!convertendo && !(semResposta && (millis() - ultimaFalha) < 500)) iniciaConversao();
        return leu;
    }

    /* Temperatura em centésimos de °C (2534 = 25,34 °C), sem float. */
    int16_t temperaturaCentesimos(uint8_t indice = 0) {
        if (!inicializado || indice >= qtd) return DS18B20_ERRO;
        atualiza();
        if (!valido[indice] && !jaEsperou) {           /* primeira vez: espera a conversão */
            jaEsperou = true;
            uint32_t t0 = millis();
            while (!valido[indice] && (millis() - t0) < 2 * tempoConversao() + 50) atualiza();
            if (!valido[indice]) return DS18B20_ERRO;
        }
        return centesimos[indice];
    }

    /* °C. Se a leitura falhar devolve o último valor bom (NAN se nunca leu). */
    float temperatura(uint8_t indice = 0) {
        int16_t c = temperaturaCentesimos(indice);
        if (c == DS18B20_ERRO && !(indice < qtd && valido[indice])) return NAN;
        return c / 100.0f;
    }

    /* Converte e lê na hora (bloqueia até 750 ms). */
    float temperaturaAgora(uint8_t indice = 0) {
        if (!inicializado || indice >= qtd) return NAN;
        terminaConversao();                           /* a que estava rodando */
        iniciaConversao();
        terminaConversao();
        float t = valido[indice] ? centesimos[indice] / 100.0f : NAN;
        iniciaConversao();                            /* deixa a próxima rodando */
        return t;
    }

    uint8_t quantidade() { return qtd; }
    bool ok() { return ultimaOk; }

    /* 9 bits (0,5 °C, 94 ms) .. 12 bits (0,0625 °C, 750 ms). Padrão 12. */
    void resolucao(uint8_t b) {
        if (b < 9) b = 9;
        if (b > 12) b = 12;
        bits = b;
        if (!inicializado) return;
        terminaConversao();
        escreveResolucao();
        iniciaConversao();
    }

    /* Endereço de 8 bytes do sensor (para saber qual é qual). */
    void endereco(uint8_t indice, uint8_t destino[8]) {
        for (uint8_t k = 0; k < 8; k++) destino[k] = (indice < qtd) ? rom[indice][k] : 0;
    }
    void imprimeEnderecos(Print &saida = Serial) {
        for (uint8_t i = 0; i < qtd; i++) {
            saida.print(F("Sensor "));
            saida.print(i);
            saida.print(F(": "));
            for (uint8_t k = 0; k < 8; k++) {
                if (rom[i][k] < 0x10) saida.print('0');
                saida.print(rom[i][k], HEX);
                if (k < 7) saida.print(':');
            }
            saida.println();
        }
    }
};

#endif
