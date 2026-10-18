#ifndef _BMI160_SERIAL_H_
#define _BMI160_SERIAL_H_

#include <Arduino.h>
#include "SoftwareSerial.h"

// Modos de operação do BMI160
#define BMI160_GYRO      0  // Modo giroscópio
#define BMI160_GYRO2     1  // Modo giroscópio alternativo
#define BMI160_GYRO_CAL  2  // Modo calibração

class Giroscopio {
private:
    SoftwareSerial* serial;
    uint8_t pinoRX;
    uint8_t pinoTX;
    bool inicializado;
    uint8_t modoAtual;
    uint32_t baudRate;
    char descricaoPorta[6];
    // Buffer para receber dados (4 valores int16_t = 8 bytes)
    uint8_t bufferRx[10]; //aumentei o tamanho pra evitar overflow
    
    // Valores decodificados
    int16_t angleX;
    int16_t angleY;
    int16_t angleZ;
    int16_t frequencia;
    uint32_t ultimaAtualizacao;
    // Timeout para leitura
    const uint32_t TIMEOUT = 100; // ms
    
public:
    Giroscopio(PortaSerial porta, uint32_t baudRate = 115200) : serial(nullptr), pinoRX(0), pinoTX(0), inicializado(false), modoAtual(BMI160_GYRO) {
        pinoRX = porta.rx;
        pinoTX = porta.tx;
        this->baudRate = baudRate;
        angleX = 0;
        angleY = 0;
        angleZ = 0;
        frequencia = 0;
        strcpy(this->descricaoPorta, porta.descricao);
        ultimaAtualizacao = 0;
    }
    
    ~Giroscopio() {
        if(serial != nullptr) {
            delete serial;
        }
    }
    
    // Inicializa comunicação serial com o BMI160
    // porta: Porta I2C será usada para RX/TX (SDA=RX, SCL=TX)
    void inicializa() {
        // Cria SoftwareSerial
        serial = new SoftwareSerial(pinoRX, pinoTX);
        serial->begin(baudRate);
        
        inicializado = true;
        modoAtual = BMI160_GYRO;
        
        Serial.print(F("Giroscopio Serial inicializado na porta "));
        Serial.print(descricaoPorta);
        Serial.print(F(" (RX="));
        Serial.print(pinoRX);
        Serial.print(F(", TX="));
        Serial.print(pinoTX);
        Serial.print(F(") @ "));
        Serial.print(baudRate);
        Serial.println(F(" baud"));
        
        // Pequeno delay para estabilizar
        delay(100);
        
        // Envia modo padrão
        setModo(BMI160_GYRO);
    }
    
    // Define o modo de operação
    void setModo(uint8_t modo) {
        if(!inicializado) {
            Serial.println(F("Erro: Giroscopio Serial nao inicializado!"));
            return;
        }
        
        if(modo > 2) {
            Serial.println(F("Erro: Modo invalido! Use 0-2"));
            return;
        }
        
        modoAtual = modo;
        //nao envio o modo novo (já que o envio do modo é a solicitação de dados)
        // serial->write(modo);
        
        // // Aguarda processamento
        // delay(10);
    }
    
    // Calibra o giroscópio
    void calibrar() {
        Serial.println(F("Calibrando giroscopio..."));
        setModo(BMI160_GYRO_CAL);
        uint32_t inicio = 1;
        uint8_t bytesRecebidos = 0;
        //a calibracao aguarda receber o byte de confirmação com valor 1
        cli();
        serial->write(modoAtual);
        while(inicio++){// aguardo overflow como timeout
            if(serial->available()){
                bufferRx[bytesRecebidos++] = serial->read();
            }
        }
        sei();
        setModo(BMI160_GYRO); // Volta ao modo normal
        Serial.println(F("Calibracao concluida!"));

    }
    
    // Lê os dados do Giroscopio (solicita e aguarda resposta)
    bool lerDados() {
        if(!inicializado) return false;
        // Envia requisição (envia o modo atual novamente)
        uint16_t inicio = 1;
        uint8_t bytesRecebidos = 0;
        // Aguarda receber 8 bytes
        
        cli();
        serial->write(modoAtual);
        while(inicio++){// aguardo overflow como timeout
            if(serial->available()) {
                bytesRecebidos = serial->readBytes(bufferRx,8);
                break;
            }
        }
        sei();
        // Verifica se recebeu todos os bytes
        if(bytesRecebidos < 8) {
            Serial.println(F(" Timeout: Dados incompletos do Giroscopio"));
            return false;
        }

        // Decodifica os 4 valores int16_t (big-endian)
        angleX = (static_cast<int16_t>(bufferRx[0]) << 8) | bufferRx[1];
        angleY = (static_cast<int16_t>(bufferRx[2]) << 8) | bufferRx[3];
        angleZ = (static_cast<int16_t>(bufferRx[4]) << 8) | bufferRx[5];
        frequencia = (static_cast<int16_t>(bufferRx[6]) << 8) | bufferRx[7];
        ultimaAtualizacao = millis();
        return true;
    }
    
    //precisa de um nome melhor
    void atualizaDadosTimeOut(){
#ifdef SUPORTE_SERVO
        if(millis() - ultimaAtualizacao > TIMEOUT && modoCicloServo == MODO_SERVO_FINALIZADO){
#else
        if(millis() - ultimaAtualizacao > TIMEOUT){
#endif
            lerDados();
        }
    }

    // Retorna ângulo X (pitch) em graus
    int16_t getAnguloX() {
        atualizaDadosTimeOut();
        return angleX;
    }
    
    // Retorna ângulo Y (roll) em graus
    int16_t getAnguloY() {
        atualizaDadosTimeOut();
        return angleY;
    }
    
    // Retorna ângulo Z (yaw) em graus
    int16_t getAnguloZ() {
        atualizaDadosTimeOut();
        return angleZ;
    }
    
    // Retorna frequência de atualização (Hz)
    int16_t getFrequencia() {
        atualizaDadosTimeOut();
        return frequencia;
    }
    
    // Lê e retorna todos os ângulos de uma vez
    void getAngulos(int16_t &x, int16_t &y, int16_t &z) {
        x = angleX;
        y = angleY;
        z = angleZ;
    }
    
    // Imprime os dados no Serial Monitor
    void imprimirDados() {
        Serial.print(F("X: "));
        Serial.print(angleX);
        Serial.print(F("° | Y: "));
        Serial.print(angleY);
        Serial.print(F("° | Z: "));
        Serial.print(angleZ);
        Serial.print(F("° | Freq: "));
        Serial.print(frequencia);
        Serial.println(F(" Hz"));
    }
    
    // Zera o ângulo Z (yaw)
    void zerarZ() {
        // Muda de modo para resetar Z
        uint8_t modoAnterior = modoAtual;
        setModo((modoAtual == BMI160_GYRO) ? BMI160_GYRO2 : BMI160_GYRO);
    }
    
    // Verifica se está inicializado
    bool estaInicializado() {
        return inicializado;
    }
    
    // Retorna o modo atual
    uint8_t getModoAtual() {
        return modoAtual;
    }
    
};


#endif
