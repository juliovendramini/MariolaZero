#ifndef _ULTRASSONICO_H_
#define _ULTRASSONICO_H_

#include <Arduino.h>
#include "portas.h"

// Macros para acesso direto aos registradores (igual SoftWire)
#define digitalPinToPort(P) ( pgm_read_byte( digital_pin_to_port_PGM + (P) ) )
#define digitalPinToBitMask(P) ( pgm_read_byte( digital_pin_to_bit_mask_PGM + (P) ) )
#define portOutputRegister(P) ( (volatile uint8_t *)( pgm_read_word( port_to_output_PGM + (P))) )
#define portInputRegister(P) ( (volatile uint8_t *)( pgm_read_word( port_to_input_PGM + (P))) )
#define portModeRegister(P) ( (volatile uint8_t *)( pgm_read_word( port_to_mode_PGM + (P))) )

class Ultrassonico {
private:
    uint8_t pinoTrig;
    uint8_t pinoEcho;
    bool inicializado;
    char descricao[5];
    
    // Timeout em microsegundos (19ms = ~3.25m de alcance máximo)
    const uint32_t TIMEOUT = 19000UL;
    
    // Cache de registradores para TRIG (calculados uma vez)
    volatile uint8_t *_trigOut;
    volatile uint8_t *_trigDdr;
    uint8_t _trigMask;
    
    // Cache de registradores para ECHO (calculados uma vez)
    volatile uint8_t *_echoIn;
    volatile uint8_t *_echoDdr;
    volatile uint8_t *_echoOut;
    uint8_t _echoMask;
    
    // Variáveis para leitura assíncrona
    volatile uint32_t tempoInicio;
    volatile uint32_t tempoFim;
    volatile bool medicaoEmAndamento;
    volatile bool medicaoCompleta;
    uint32_t ultimaMedicao;
    int16_t distancia;

    public:
    volatile uint32_t ultimaAtualizacao;
    // Ponteiro estático para ISR, necessário para vinculação das interrupções externas
    static Ultrassonico* instancias[5];
    static uint8_t numInstancias;
    
    // Mapeamento de pino para índice de instância
    static uint8_t pinoParaInstancia[20];  // Array para mapear pino -> índice
    static uint8_t estadoAnteriorPCINT0;   // Estado anterior PCINT0 (D8-D13)
    static uint8_t estadoAnteriorPCINT1;   // Estado anterior PCINT1 (A0-A5)
    static uint8_t estadoAnteriorPCINT2;   // Estado anterior PCINT2 (D0-D7)
    
    // Constantes para cálculo de distância
    // Som viaja ~343m/s = 0.0343cm/µs
    // Distância = (tempo_ida_e_volta / 2) * velocidade_som
    // Distância(cm) = tempo(µs) / 58.0
    // Distância(mm) = tempo(µs) / 5.8
    
    // ISRs PCINT processam vários pinos - definidas fora da classe
    
    // Handler de interrupção - OTIMIZADO com acesso direto a registradores
    void handleInterrupt() {
        if(*_echoIn & _echoMask) {
            // Rising edge - inicia contagem
            tempoInicio = micros();
        } else {
            // Falling edge - finaliza contagem
            tempoFim = micros();
            medicaoCompleta = true;
            medicaoEmAndamento = false;
            ultimaAtualizacao = millis();
        }
    }
    
    // Retorna o banco PCINT do pino (0, 1 ou 2)
    uint8_t getPCINTBank() {
        // PCINT0 (PCMSK0): D8-D13 (PB0-PB5)
        if(pinoEcho >= 8 && pinoEcho <= 13) return 0;
        // PCINT1 (PCMSK1): A0-A5 (PC0-PC5) = D14-D19
        if(pinoEcho >= 14 && pinoEcho <= 19) return 1;
        // PCINT2 (PCMSK2): D0-D7 (PD0-PD7)
        if(pinoEcho >= 0 && pinoEcho <= 7) return 2;
        return 255; // Inválido
    }
    
    // Retorna o bit no registrador PCMSK
    uint8_t getPCINTBit() {
        if(pinoEcho >= 8 && pinoEcho <= 13) return pinoEcho - 8;   // PB0-PB5
        if(pinoEcho >= 14 && pinoEcho <= 19) return pinoEcho - 14; // PC0-PC5
        if(pinoEcho >= 0 && pinoEcho <= 7) return pinoEcho;        // PD0-PD7
        return 255;
    }

    
    // Anexa interrupção PCINT
    void anexarInterrupcao() {
        uint8_t bank = getPCINTBank();
        uint8_t bit = getPCINTBit();
        
        if(bank == 255 || bit == 255) return;
        
        // Registra esta instância
        uint8_t meuIndice = numInstancias;
        if(numInstancias < 5) {
            instancias[numInstancias++] = this;
            pinoParaInstancia[pinoEcho] = meuIndice;
        }
        
        // Habilita PCINT no banco correspondente
        PCICR |= (1 << bank);  // Habilita PCIE0, PCIE1 ou PCIE2
        
        // Habilita máscara do pino específico
        if(bank == 0) {
            PCMSK0 |= (1 << bit);
            estadoAnteriorPCINT0 = PINB;  // Lê estado inicial
        } else if(bank == 1) {
            PCMSK1 |= (1 << bit);
            estadoAnteriorPCINT1 = PINC;
        } else if(bank == 2) {
            PCMSK2 |= (1 << bit);
            estadoAnteriorPCINT2 = PIND;
        }
    }
    
    // Desanexa interrupção PCINT
    void desanexarInterrupcao() {
        uint8_t bank = getPCINTBank();
        uint8_t bit = getPCINTBit();
        
        if(bank == 255 || bit == 255) return;
        
        // Desabilita máscara do pino específico
        if(bank == 0) {
            PCMSK0 &= ~(1 << bit);
            if(PCMSK0 == 0) PCICR &= ~(1 << 0);  // Desabilita banco se vazio
        } else if(bank == 1) {
            PCMSK1 &= ~(1 << bit);
            if(PCMSK1 == 0) PCICR &= ~(1 << 1);
        } else if(bank == 2) {
            PCMSK2 &= ~(1 << bit);
            if(PCMSK2 == 0) PCICR &= ~(1 << 2);
        }
    }

public:
    Ultrassonico(PortaUltrassonico porta){
        pinoTrig = porta.trig;
        pinoEcho = porta.echo;
        strcpy(descricao, porta.descricao);
        inicializado = false;
        medicaoEmAndamento = false;
        medicaoCompleta = false;
        tempoInicio = 0;
        tempoFim = 0;
        ultimaMedicao = 0;
    }
    
    ~Ultrassonico() {
        if(inicializado) {
            desanexarInterrupcao();
        }
    }
    
    // Inicializa o sensor ultrassônico em uma porta específica
    void inicializa() {
        
        // Calcula e cacheia registradores do TRIG
        uint8_t trigPort = digitalPinToPort(pinoTrig);
        _trigMask = digitalPinToBitMask(pinoTrig);
        _trigOut = portOutputRegister(trigPort);
        _trigDdr = portModeRegister(trigPort);
        
        // Calcula e cacheia registradores do ECHO
        uint8_t echoPort = digitalPinToPort(pinoEcho);
        _echoMask = digitalPinToBitMask(pinoEcho);
        _echoIn = portInputRegister(echoPort);
        _echoDdr = portModeRegister(echoPort);
        _echoOut = portOutputRegister(echoPort);
        
        // Configura pinos usando registradores diretos
        *_trigOut &= ~_trigMask;  // TRIG = LOW
        *_trigDdr |= _trigMask;   // TRIG = OUTPUT
        
        *_echoDdr &= ~_echoMask;  // ECHO = INPUT
        *_echoOut &= ~_echoMask;  // ECHO sem pull-up
        
        // Anexa interrupção para leitura assíncrona
        anexarInterrupcao();
        ultimaAtualizacao = 0;
        distancia = -1;
        inicializado = true;
        
        Serial.print(F("Sensor Ultrassonico HC-SR04 inicializado na porta "));
        Serial.println(descricao);
    }
    
    // Envia pulso de trigger (10µs) - inicia medição assíncrona - OTIMIZADO
    void enviarPulso() {
        medicaoCompleta = false;
        medicaoEmAndamento = true;
        tempoInicio = 0;
        tempoFim = 0;
        this->anexarInterrupcao();
        // Pulso de trigger usando registradores diretos
        *_trigOut &= ~_trigMask;  // LOW
        delayMicroseconds(2);
        *_trigOut |= _trigMask;   // HIGH
        delayMicroseconds(10);
        *_trigOut &= ~_trigMask;  // LOW
    }
    
    // Inicia medição assíncrona (não-bloqueante)
    void iniciaMedicao() {
        if(!medicaoEmAndamento) {
            enviarPulso();
        }
    }
    
    // Verifica se medição está completa
    bool medicaoPronta() {
        // Timeout de 19ms
        if(medicaoEmAndamento && (micros() - tempoInicio) > TIMEOUT) {
            medicaoEmAndamento = false;
            medicaoCompleta = false;
            return true; // Timeout conta como "pronto" mas sem dados válidos
        }
        return medicaoCompleta;
    }
    
    // Lê a duração do pulso (resultado da última medição)
    uint32_t lerPulso() {
        if(medicaoCompleta && tempoFim > tempoInicio) {
            ultimaMedicao = tempoFim - tempoInicio;
            return ultimaMedicao;
        }
        return 0; // Timeout ou não pronto
    }
    
    // Lê a duração da última medição válida (sem bloquear)
    uint32_t lerPulsoUltimo() {
        return ultimaMedicao;
    }
    
    //Mede e retorna a distância em centímetros
    int getDistancia(){
        if(!inicializado) {
            Serial.println(F("Erro: Sensor ultrassonico nao inicializado!"));
            return -1;
        }
        if(millis() - ultimaAtualizacao > 100) {//se passou do timeout eu faço outra medição para atualizar os valores
            iniciaMedicao();
            // Aguarda medição (bloqueante)
            uint32_t timeout = millis() + 25; // 25ms max
            while(!medicaoPronta() && millis() < timeout) {
                delayMicroseconds(10);
            }
        }
        
        uint32_t duracao = lerPulso();
        
        if(duracao == 0) {
            // Timeout - objeto muito longe ou sem retorno
            this->distancia = -1;
            return this->distancia;
        }
        // Converte tempo para distância em cm
        duracao = (duracao*1000) / 58;
        duracao = duracao/1000;
        this->distancia = (int16_t)(duracao+1);
        return this->distancia;
    }
    
    
    // // Teste do sensor
    // void teste(uint8_t segundos = 10) {
    //     Serial.println(F("=== TESTE SENSOR ULTRASSONICO ==="));
    //     Serial.print(F("Lendo distancia por "));
    //     Serial.print(segundos);
    //     Serial.println(F(" segundos..."));
        
    //     uint32_t inicio = millis();
    //     while(millis() - inicio < (segundos * 1000UL)) {
    //         float dist = distanciaCm();
            
    //         Serial.print(F("Distancia: "));
    //         if(dist < 0) {
    //             Serial.println(F("Fora de alcance ou erro"));
    //         } else {
    //             Serial.print(dist, 1);
    //             Serial.println(F(" cm"));
    //         }
            
    //         delay(500);
    //     }
        
    //     Serial.println(F("Teste concluido!"));
    // }
    
    // // Teste assíncrono
    // void testeAsync(uint8_t segundos = 10) {
    //     Serial.println(F("=== TESTE ASSINCRONO SENSOR ULTRASSONICO ==="));
        
    //     uint32_t inicio = millis();
    //     uint32_t proximaLeitura = millis();
        
    //     iniciarMedicao();
        
    //     while(millis() - inicio < (segundos * 1000UL)) {
    //         // Processa outras tarefas aqui...
            
    //         // Verifica se medição está pronta
    //         if(medicaoPronta()) {
    //             float dist = distanciaCmAsync();
                
    //             Serial.print(F("Distancia: "));
    //             if(dist < 0) {
    //                 Serial.println(F("Erro"));
    //             } else {
    //                 Serial.print(dist, 1);
    //                 Serial.println(F(" cm"));
    //             }
                
    //             // Inicia próxima medição
    //             delay(100); // Delay mínimo entre medições
    //             iniciarMedicao();
    //         }
    //     }
        
    //     Serial.println(F("Teste concluido!"));
    // }
};

// Inicialização de variáveis estáticas
Ultrassonico* Ultrassonico::instancias[5] = {NULL, NULL, NULL, NULL, NULL};
uint8_t Ultrassonico::numInstancias = 0;
uint8_t Ultrassonico::pinoParaInstancia[20] = {0};
uint8_t Ultrassonico::estadoAnteriorPCINT0 = 0;
uint8_t Ultrassonico::estadoAnteriorPCINT1 = 0;
uint8_t Ultrassonico::estadoAnteriorPCINT2 = 0;

#endif
