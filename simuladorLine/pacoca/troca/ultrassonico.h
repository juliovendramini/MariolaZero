// Ultrassônico HC-SR04 do simulador: mesma interface da lib do brick. O pulso de trigger pede
// a distância à ponte; o eco começa ~0,46 ms depois e dura 5,83 us por mm (ida e volta).
// Sem obstáculo no alcance o eco não volta antes do timeout de 19 ms da lib.
#ifndef _ULTRASSONICO_H_
#define _ULTRASSONICO_H_

#include <Arduino.h>
#include "portas.h"
#include "sim_ponte.h"

class Ultrassonico {
private:
    uint8_t pinoTrig;
    uint8_t pinoEcho;
    bool inicializado;
    char descricao[6];
    const uint32_t TIMEOUT = 19000UL;

    volatile uint32_t tempoInicio;
    volatile uint32_t tempoFim;
    volatile bool medicaoEmAndamento;
    volatile bool medicaoCompleta;
    uint32_t ultimaMedicao;
    int16_t distancia;
    int64_t fimEcoNs;        // quando o eco termina (tempo do simulador), -1 = sem eco

    void confere() {
        if (medicaoEmAndamento && fimEcoNs >= 0 && sim_t_ns >= fimEcoNs) {
            medicaoEmAndamento = false;
            medicaoCompleta = true;
            ultimaAtualizacao = millis();
        }
    }

public:
    volatile uint32_t ultimaAtualizacao;
    static Ultrassonico *instancias[5];
    static uint8_t numInstancias;
    static uint8_t pinoParaInstancia[20];

    Ultrassonico(PortaUltrassonico porta) {
        pinoTrig = porta.trig;
        pinoEcho = porta.echo;
        strncpy(descricao, porta.descricao, sizeof descricao - 1);
        descricao[sizeof descricao - 1] = 0;
        inicializado = false;
        medicaoEmAndamento = false;
        medicaoCompleta = false;
        tempoInicio = tempoFim = 0;
        ultimaMedicao = 0;
        distancia = -1;
        fimEcoNs = -1;
        ultimaAtualizacao = 0;
    }

    void inicializa() {
        pinMode(pinoTrig, OUTPUT);
        digitalWrite(pinoTrig, LOW);
        pinMode(pinoEcho, INPUT);
        inicializado = true;
        Serial.print(F("Sensor Ultrassonico HC-SR04 inicializado na porta "));
        Serial.println(descricao);
    }

    void handleInterrupt() {}

    void enviarPulso() {
        medicaoCompleta = false;
        medicaoEmAndamento = true;
        delayMicroseconds(12);
        SimReq r;
        SimResp s;
        r.u8(pinoTrig);
        r.u8(pinoEcho);
        int32_t mm = -1;
        if (sim_chamar(OP_ULTRASSOM, r, s)) mm = s.i32();
        int64_t inicio = sim_t_ns + 460000;
        if (mm >= 0) {
            int64_t dur = (int64_t)(mm * 5830.0);
            fimEcoNs = inicio + dur;
            tempoInicio = (uint32_t)(micros() + 460);
            tempoFim = (uint32_t)(tempoInicio + dur / 1000);
        } else {
            fimEcoNs = -1;
            tempoInicio = (uint32_t)micros();
            tempoFim = 0;
        }
    }

    void iniciaMedicao() {
        if (!medicaoEmAndamento) enviarPulso();
    }

    bool medicaoPronta() {
        confere();
        if (medicaoEmAndamento && (micros() - tempoInicio) > TIMEOUT) {
            medicaoEmAndamento = false;
            medicaoCompleta = false;
            return true;
        }
        return medicaoCompleta;
    }

    uint32_t lerPulso() {
        confere();
        if (medicaoCompleta && tempoFim > tempoInicio) {
            ultimaMedicao = tempoFim - tempoInicio;
            return ultimaMedicao;
        }
        return 0;
    }

    uint32_t lerPulsoUltimo() { return ultimaMedicao; }

    int getDistancia() {
        if (!inicializado) {
            Serial.println(F("Erro: Sensor ultrassonico nao inicializado!"));
            return -1;
        }
        if (millis() - ultimaAtualizacao > 100) {
            iniciaMedicao();
            uint32_t timeout = millis() + 25;
            while (!medicaoPronta() && millis() < timeout) {
                delayMicroseconds(10);
            }
        }
        uint32_t duracao = lerPulso();
        if (duracao == 0) {
            distancia = -1;
            return distancia;
        }
        duracao = (duracao * 1000) / 58;
        duracao = duracao / 1000;
        distancia = (int16_t)(duracao + 1);
        return distancia;
    }
};

inline Ultrassonico *Ultrassonico::instancias[5] = {NULL, NULL, NULL, NULL, NULL};
inline uint8_t Ultrassonico::numInstancias = 0;
inline uint8_t Ultrassonico::pinoParaInstancia[20] = {0};

#endif
