//Precisei transformar o tratamento dessas funções em algo global, pois mais de uma classe vai fazer isso desse tipo de interrupção, e não posso ter mais uma 
//FUNCAO de ISR por programa.

//atualmente usando esse código: ultrassonico e bluetooth


// ISRs PCINT simplificadas - apenas para pinos usados: 15, 17, 6, 3, 19
// ISRs PCINT simplificadas - apenas para pinos usados: 14, 16, 8, 2, 18 (precisei trocar as posições dos pinos do ultrassonico para a recepção dele ser o mesmo pino do RX de serial)
//volatile uint8_t estadoAnteriorPCINT0 = 0;
volatile uint8_t estadoAnteriorPCINT1 = 0;
//volatile uint8_t estadoAnteriorPCINT2 = 0;


// PCINT0: Pino D8 (PB0)
ISR(PCINT0_vect) {
    // Apenas D8 usa PCINT0
    #ifdef SUPORTE_SENSOR_ULTRASSONICO
    uint8_t idx = Ultrassonico::pinoParaInstancia[8];
    if(Ultrassonico::instancias[idx]) {
        Ultrassonico::instancias[idx]->handleInterrupt();
    }
    #endif

    #ifdef SUPORTE_BLUETOOTH
    if(Bluetooth::bluetooth_active_object){
        Bluetooth::bluetooth_active_object->handle_interrupt();
    }
    #endif
}

// PCINT1: Pinos D14 (A0/PC0), D16 (A2/PC2), D18 (A4/PC4)
ISR(PCINT1_vect) {
    uint8_t estadoAtual = PINC;
    uint8_t mudancas = estadoAtual ^ estadoAnteriorPCINT1;
    estadoAnteriorPCINT1 = estadoAtual;
    // Verifica apenas os 3 pinos usados
    if(mudancas & (1)) {  // PC0 = D14 (A0)
        #ifdef SUPORTE_SENSOR_ULTRASSONICO
        uint8_t idx = Ultrassonico::pinoParaInstancia[14];
        if(Ultrassonico::instancias[idx]) Ultrassonico::instancias[idx]->handleInterrupt();
        #endif
        #ifdef SUPORTE_BLUETOOTH
        if(Bluetooth::bluetooth_active_object){
            Bluetooth::bluetooth_active_object->handle_interrupt();
        }
        #endif
    }
    if(mudancas & (1 << 2)) {  // PC2 = D16 (A2)
        #ifdef SUPORTE_SENSOR_ULTRASSONICO
        uint8_t idx = Ultrassonico::pinoParaInstancia[16];
        if(Ultrassonico::instancias[idx]) Ultrassonico::instancias[idx]->handleInterrupt();
        #endif
        #ifdef SUPORTE_BLUETOOTH
        if(Bluetooth::bluetooth_active_object){
            Bluetooth::bluetooth_active_object->handle_interrupt();
        }
        #endif
    }
    if(mudancas & (1 << 4)) {  // PC4 = D18 (A4)
        #ifdef SUPORTE_SENSOR_ULTRASSONICO
        uint8_t idx = Ultrassonico::pinoParaInstancia[18];
        if(Ultrassonico::instancias[idx]) Ultrassonico::instancias[idx]->handleInterrupt();
        #endif
        #ifdef SUPORTE_BLUETOOTH
        if(Bluetooth::bluetooth_active_object){
            Bluetooth::bluetooth_active_object->handle_interrupt();
        }
        #endif
    }
}

// PCINT2: Pino D2 (PD2)
ISR(PCINT2_vect) {
    // Apenas D2 usa PCINT2
    #ifdef SUPORTE_SENSOR_ULTRASSONICO
    uint8_t idx = Ultrassonico::pinoParaInstancia[2];
    if(Ultrassonico::instancias[idx]) {
        Ultrassonico::instancias[idx]->handleInterrupt();
    }
    #endif
    #ifdef SUPORTE_BLUETOOTH
    if(Bluetooth::bluetooth_active_object){
        Bluetooth::bluetooth_active_object->handle_interrupt();
    }
    #endif
}

