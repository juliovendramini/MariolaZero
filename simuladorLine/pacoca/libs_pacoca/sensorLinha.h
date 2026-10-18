#ifndef _SENSOR_LINHA_H_
#define _SENSOR_LINHA_H_

// Sensor de linha e cor Pro1616 (ATtiny1616, firmware sensorLinhaPro1616), pela serial a 115200.
//
// Protocolo (o mesmo da lib sensorCorReflexao.py do Mariola):
//   0x61 -> o sensor responde 16 bytes:
//           [0-3]   reflexão IR dos 4 canais: 0 = preto, ~100 = branco calibrado
//                   (acima de 100 = mais claro que o branco da calibração)
//           [4-7]   TCS da esquerda (R, G, B, C)
//           [8-11]  TCS do meio     (R, G, B, C)
//           [12-15] TCS da direita  (R, G, B, C)
//           O TCS é calibrado no branco e enviado pela METADE: branco ~127. Sobra espaço até 255
//           para superfícies refletivas: a fita prata passa de 127 (~200) com os LEDs da placa.
//           No IR a prata lê MENOS que o branco (~80): quem vê o prata é o TCS.
//   0x62 -> calibra o branco (~7 s); no fim responde 1
//   0x63 -> calibra o preto  (~2 s); no fim responde 1
//
// O sensor atualiza a ~50 Hz. A lib pede dados no máximo a cada intervaloLeituraMs (10 ms)
// e, como o SoftwareSerial do brick não tem buffer, desliga as interrupções enquanto espera e
// lê a resposta (~2 ms).

#include <Arduino.h>
#include "SoftwareSerial.h"

// comandos do Pro1616
#define PRO1616_LER            0x61
#define PRO1616_CALIBRA_BRANCO 0x62
#define PRO1616_CALIBRA_PRETO  0x63
#define PRO1616_BYTES          16

// sensores de cor (TCS) da placa
#define SENSOR_COR_ESQUERDA 1
#define SENSOR_COR_MEIO     2
#define SENSOR_COR_DIREITA  3

// Cores (mesmos códigos da lib do Mariola)
enum Cor {
    COR_PRETO = 0,
    COR_BRANCO = 1,
    COR_VERMELHO = 2,
    COR_VERDE = 3,
    COR_AZUL = 4,
    COR_AMARELO = 5,
    COR_PRATA = 7,
    COR_INDEFINIDA = -1
};

class SensorLinha {
private:
    SoftwareSerial* serial;
    uint8_t pinoRX;
    uint8_t pinoTX;
    bool inicializado;
    uint32_t baudRate;
    char descricaoPorta[10];

    uint8_t dados[PRO1616_BYTES];   // última leitura completa
    uint8_t bufferRx[PRO1616_BYTES];
    uint32_t ultimaAtualizacao;
    uint16_t falhas;                 // leituras incompletas seguidas

    // espera 1 byte de resposta da calibração (com as interrupções ligadas entre tentativas,
    // para o millis() continuar contando)
    int esperaConfirmacao(uint32_t timeoutMs) {
        uint32_t t0 = millis();
        int r = -1;
        while (r < 0 && millis() - t0 < timeoutMs) {
            cli();
            for (uint16_t i = 0; i < 2000 && r < 0; i++) {   // ~1 ms com as interrupções desligadas
                if (serial->available()) r = serial->read();
            }
            sei();
        }
        return r;
    }

    bool calibra(uint8_t comando, uint32_t timeoutMs) {
        if (!inicializado) return false;
        cli();
        serial->write(comando);
        sei();
        int r = esperaConfirmacao(timeoutMs);
        ultimaAtualizacao = 0;
        return r == 1;
    }

    const uint8_t *tcs(uint8_t sensor) {
        if (sensor < 1 || sensor > 3) sensor = SENSOR_COR_MEIO;
        return &dados[4 + (sensor - 1) * 4];
    }

public:
    // limites da classificação de cor (getCor): ajuste olhando o imprimirDados()
    uint8_t limiarPreto = 20;     // C abaixo disso = preto
    uint8_t limiarBranco = 70;    // cinza com C acima disso = branco (abaixo = preto)
    uint8_t limiarPrata = 160;    // C acima disso = prata (branco ~127)
    uint8_t intervaloLeituraMs = 10;

    SensorLinha(PortaSerial porta, uint32_t baudRate = 115200)
        : serial(nullptr), pinoRX(porta.rx), pinoTX(porta.tx), inicializado(false),
          baudRate(baudRate), ultimaAtualizacao(0), falhas(0) {
        strcpy(this->descricaoPorta, porta.descricao);
        for (uint8_t i = 0; i < PRO1616_BYTES; i++) dados[i] = 0;
    }

    ~SensorLinha() {
        if (serial != nullptr) delete serial;
    }

    void inicializa() {
        serial = new SoftwareSerial(pinoRX, pinoTX);
        serial->begin(baudRate);
        serial->setTimeout(10);
        inicializado = true;

        Serial.print(F("SensorLinha (Pro1616) na porta "));
        Serial.print(descricaoPorta);
        Serial.print(F(" (RX="));
        Serial.print(pinoRX);
        Serial.print(F(", TX="));
        Serial.print(pinoTX);
        Serial.println(F(")"));

        delay(100);
        if (!lerDados()) {
            Serial.println(F("Aviso: o Pro1616 nao respondeu. Confira a porta e o cabo."));
        }
    }

    // Pede uma leitura (0x61) e espera os 16 bytes
    bool lerDados() {
        if (!inicializado) return false;
        uint16_t espera = 1;
        uint8_t recebidos = 0;

        cli();
        serial->write(PRO1616_LER);
        while (espera++) {               // timeout: até o contador dar a volta
            if (serial->available()) {
                recebidos = serial->readBytes(bufferRx, PRO1616_BYTES);
                break;
            }
        }
        sei();

        if (recebidos < PRO1616_BYTES) {
            if (falhas < 65535) falhas++;
            if (falhas == 1 || falhas % 50 == 0) {
                Serial.print(F("SensorLinha: leitura incompleta ("));
                Serial.print(recebidos);
                Serial.println(F(" bytes)"));
            }
            return false;
        }
        falhas = 0;
        for (uint8_t i = 0; i < PRO1616_BYTES; i++) dados[i] = bufferRx[i];
        ultimaAtualizacao = millis();
        return true;
    }

    // Lê de novo se a última leitura tem mais de intervaloLeituraMs (o brick.atualiza() chama isso)
    void atualizaDadosTimeOut() {
        if (ultimaAtualizacao == 0 || millis() - ultimaAtualizacao >= intervaloLeituraMs) {
            lerDados();
        }
    }

    // true se a última leitura deu certo
    bool conectado() {
        return inicializado && falhas == 0 && ultimaAtualizacao != 0;
    }

    // Calibração (robô parado em cima do branco / do preto). Respondem true se o sensor confirmou.
    bool calibrarBranco() {
        Serial.println(F("Calibrando branco (~7 s)..."));
        bool ok = calibra(PRO1616_CALIBRA_BRANCO, 10000);
        Serial.println(ok ? F("Calibracao do branco concluida") : F("Erro na calibracao do branco"));
        return ok;
    }

    bool calibrarPreto() {
        Serial.println(F("Calibrando preto (~2 s)..."));
        bool ok = calibra(PRO1616_CALIBRA_PRETO, 5000);
        Serial.println(ok ? F("Calibracao do preto concluida") : F("Erro na calibracao do preto"));
        return ok;
    }

    // ===== reflexão (IR) =====

    // Reflexão do canal 0..3 (0 = mais à esquerda): 0 = preto, ~100 = branco
    uint8_t getReflexao(uint8_t sensor) {
        if (sensor >= 4) return 0;
        atualizaDadosTimeOut();
        return dados[sensor];
    }

    void getReflexoes(uint8_t valores[4]) {
        atualizaDadosTimeOut();
        for (uint8_t i = 0; i < 4; i++) valores[i] = dados[i];
    }

    // Quanto de linha (preto) o canal vê: 0 = branco, 100 = preto (o contrário da reflexão)
    uint8_t getLinha(uint8_t sensor) {
        uint8_t r = getReflexao(sensor);
        return r >= 100 ? 0 : 100 - r;
    }

    void getLinhas(uint8_t valores[4]) {
        atualizaDadosTimeOut();
        for (uint8_t i = 0; i < 4; i++) valores[i] = dados[i] >= 100 ? 0 : 100 - dados[i];
    }

    // Posição da linha: -150 (embaixo do canal 0, à esquerda) a +150 (canal 3, à direita);
    // 0 = centro ou nenhuma linha
    int16_t getPosicaoLinha() {
        uint8_t v[4];
        getLinhas(v);
        const int16_t posicoes[4] = {-150, -50, 50, 150};
        int32_t somaPonderada = 0;
        int32_t soma = 0;
        for (uint8_t i = 0; i < 4; i++) {
            somaPonderada += (int32_t)v[i] * posicoes[i];
            soma += v[i];
        }
        if (soma == 0) return 0;
        return (int16_t)(somaPonderada / soma);
    }

    // ===== cor (TCS) =====
    // sensor: SENSOR_COR_ESQUERDA (1), SENSOR_COR_MEIO (2) ou SENSOR_COR_DIREITA (3)

    void getRGBC(uint8_t sensor, uint8_t &r, uint8_t &g, uint8_t &b, uint8_t &c) {
        atualizaDadosTimeOut();
        const uint8_t *p = tcs(sensor);
        r = p[0]; g = p[1]; b = p[2]; c = p[3];
    }

    uint8_t getVermelho(uint8_t sensor) { atualizaDadosTimeOut(); return tcs(sensor)[0]; }
    uint8_t getVerde(uint8_t sensor)    { atualizaDadosTimeOut(); return tcs(sensor)[1]; }
    uint8_t getAzul(uint8_t sensor)     { atualizaDadosTimeOut(); return tcs(sensor)[2]; }
    uint8_t getClaridade(uint8_t sensor){ atualizaDadosTimeOut(); return tcs(sensor)[3]; }

    // nomes antigos
    void getCorEsquerda(uint8_t &r, uint8_t &g, uint8_t &b, uint8_t &c) { getRGBC(SENSOR_COR_ESQUERDA, r, g, b, c); }
    void getCorMeio(uint8_t &r, uint8_t &g, uint8_t &b, uint8_t &c)     { getRGBC(SENSOR_COR_MEIO, r, g, b, c); }
    void getCorDireita(uint8_t &r, uint8_t &g, uint8_t &b, uint8_t &c)  { getRGBC(SENSOR_COR_DIREITA, r, g, b, c); }
    uint8_t getRedEsquerda()   { return getVermelho(SENSOR_COR_ESQUERDA); }
    uint8_t getGreenEsquerda() { return getVerde(SENSOR_COR_ESQUERDA); }
    uint8_t getBlueEsquerda()  { return getAzul(SENSOR_COR_ESQUERDA); }
    uint8_t getClearEsquerda() { return getClaridade(SENSOR_COR_ESQUERDA); }
    uint8_t getRedMeio()       { return getVermelho(SENSOR_COR_MEIO); }
    uint8_t getGreenMeio()     { return getVerde(SENSOR_COR_MEIO); }
    uint8_t getBlueMeio()      { return getAzul(SENSOR_COR_MEIO); }
    uint8_t getClearMeio()     { return getClaridade(SENSOR_COR_MEIO); }
    uint8_t getRedDireita()    { return getVermelho(SENSOR_COR_DIREITA); }
    uint8_t getGreenDireita()  { return getVerde(SENSOR_COR_DIREITA); }
    uint8_t getBlueDireita()   { return getAzul(SENSOR_COR_DIREITA); }
    uint8_t getClearDireita()  { return getClaridade(SENSOR_COR_DIREITA); }

    // Classificação simples, só com números inteiros. As porcentagens de R, G e B dizem a cor;
    // o C (claridade) separa preto, branco e prata. Ajuste os limiares no robô.
    Cor detectarCor(uint8_t r, uint8_t g, uint8_t b, uint8_t c) {
        if (c < limiarPreto) return COR_PRETO;
        if (c > limiarPrata) return COR_PRATA;
        uint16_t s = (uint16_t)r + g + b;
        if (s == 0) return COR_PRETO;
        uint8_t pr = (uint16_t)r * 100 / s;
        uint8_t pg = (uint16_t)g * 100 / s;
        uint8_t pb = (uint16_t)b * 100 / s;
        uint8_t maior = max(pr, max(pg, pb));
        uint8_t menor = min(pr, min(pg, pb));
        if (maior - menor < 12) {                       // cinza: branco ou preto
            return c >= limiarBranco ? COR_BRANCO : COR_PRETO;
        }
        if (pb < 22 && pr > 30 && pg > 30) return COR_AMARELO;
        if (pg > pr + 8 && pg > pb + 8) return COR_VERDE;
        if (pr > pg + 15 && pr > pb + 15) return COR_VERMELHO;
        if (pb > pr + 10 && pb > pg) return COR_AZUL;
        return COR_INDEFINIDA;
    }

    Cor getCor(uint8_t sensor) {
        uint8_t r, g, b, c;
        getRGBC(sensor, r, g, b, c);
        return detectarCor(r, g, b, c);
    }

    Cor getCorEsquerda() { return getCor(SENSOR_COR_ESQUERDA); }
    Cor getCorMeio()     { return getCor(SENSOR_COR_MEIO); }
    Cor getCorDireita()  { return getCor(SENSOR_COR_DIREITA); }

    static const __FlashStringHelper *nomeCor(Cor cor) {
        switch (cor) {
            case COR_PRETO: return F("preto");
            case COR_BRANCO: return F("branco");
            case COR_VERMELHO: return F("vermelho");
            case COR_VERDE: return F("verde");
            case COR_AZUL: return F("azul");
            case COR_AMARELO: return F("amarelo");
            case COR_PRATA: return F("prata");
            default: return F("?");
        }
    }

    // ===== auxiliares =====

    void imprimirDados() {
        atualizaDadosTimeOut();
        Serial.print(F("IR: ["));
        for (uint8_t i = 0; i < 4; i++) {
            Serial.print(dados[i]);
            if (i < 3) Serial.print(F(", "));
        }
        Serial.print(F("] pos "));
        Serial.print(getPosicaoLinha());
        const char lados[3] = {'E', 'M', 'D'};
        for (uint8_t s = 1; s <= 3; s++) {
            const uint8_t *p = tcs(s);
            Serial.print(F(" | "));
            Serial.print(lados[s - 1]);
            Serial.print(F(" "));
            Serial.print(p[0]); Serial.print(F(","));
            Serial.print(p[1]); Serial.print(F(","));
            Serial.print(p[2]); Serial.print(F(","));
            Serial.print(p[3]);
            Serial.print(F(" "));
            Serial.print(nomeCor(getCor(s)));
        }
        Serial.println();
    }

    bool estaInicializado() {
        return inicializado;
    }
};

#endif
