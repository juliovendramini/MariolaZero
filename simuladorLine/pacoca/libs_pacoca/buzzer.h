class Buzzer{
    private:
    uint8_t pino;
    bool inicializado;
    char descricaoPorta[6];

    public:
    Buzzer(PortaBuzzer porta){
        pino=porta.pino;
        inicializado=false;
        strcpy(this->descricaoPorta, porta.descricao);
    }
    
    ~Buzzer() {
        if(inicializado) {
            parar();
        }
    }

    // Inicializa o buzzer
    void inicializa() {
        pinMode(pino, OUTPUT);
        digitalWrite(pino, HIGH); // Buzzer invertido: HIGH = desligado
        inicializado = true;
        Serial.print(F("Buzzer inicializado na porta "));
        Serial.println(this->descricaoPorta);
    }

    // Emite um tom em frequência específica por um tempo específico
    // frequencia: Hz (ex: 440 para Lá, 262 para Dó, etc)
    // duracao: milissegundos (0 = som contínuo até chamar parar())
    void tocar(uint16_t frequencia, uint32_t duracao) { //zero nao toca nada
        if(!inicializado) {
            Serial.println(F("Erro: Buzzer nao inicializado!"));
            return;
        }
        if(duracao > 0) {
            // Gera PWM manual com lógica invertida
            uint32_t periodo = 1000000UL / frequencia; // período em microssegundos
            uint32_t tempoAlto = periodo / 2; // 50% duty cycle (HIGH = desligado)
            uint32_t tempoBaixo = periodo / 2; // 50% duty cycle (LOW = ligado)
            uint32_t inicio = millis();
            while(millis() - inicio < duracao) {
                digitalWrite(this->pino, HIGH); // Buzzer desligado
                delayMicroseconds(tempoAlto);
                digitalWrite(this->pino, LOW);  // Buzzer ligado
                delayMicroseconds(tempoBaixo);
            }
            digitalWrite(this->pino, HIGH); // Garante que termina desligado
        }
    }

    // Para o som
    void parar() {
        if(inicializado) {
            digitalWrite(this->pino, HIGH); // Desligado para buzzer invertido
        }
    }

    // Toca uma melodia simples (beep curto)
    void beep(uint16_t frequencia = 1000, uint16_t duracao = 100) {
        tocar(frequencia, duracao);
    }

    // Toca um beep de alerta (dois beeps rápidos)
    void alerta() {
        beep(1500, 100);
        delay(100);
        beep(1500, 100);
    }

    // Toca um beep de sucesso (tom ascendente)
    void sucesso() {
        beep(523, 100);  // Dó
        delay(50);
        beep(659, 100);  // Mi
        delay(50);
        beep(784, 150);  // Sol
    }

    // Toca um beep de erro (tom descendente)
    void erro() {
        beep(784, 100);  // Sol
        delay(50);
        beep(659, 100);  // Mi
        delay(50);
        beep(523, 150);  // Dó
    }

    // Toca a melodia de Jingle Bells
    void jingleBells() {
        // Jingle bells, jingle bells, jingle all the way
        tocar(MI, 250);
        delay(100);;
        tocar(MI, 250);
        delay(100);;
        tocar(MI, 500);
        delay(100);;
        
        tocar(MI, 250);
        delay(100);;
        tocar(MI, 250);
        delay(100);;
        tocar(MI, 500);
        delay(100);;
        
        tocar(MI, 250);
        delay(100);;
        tocar(SOL, 250);
        delay(100);;
        tocar(DO, 375);
        delay(125);
        tocar(RE, 125);
        delay(125);
        tocar(MI, 500);
        delay(500);
        
        // Oh what fun it is to ride
        tocar(FA, 250);
        delay(100);;
        tocar(FA, 250);
        delay(100);;
        tocar(FA, 375);
        delay(125);
        tocar(FA, 125);
        delay(125);
        tocar(FA, 250);
        delay(100);;
        tocar(MI, 250);
        delay(100);;
        tocar(MI, 250);
        delay(125);
        tocar(MI, 125);
        delay(125);
        
        tocar(MI, 250);
        delay(100);;
        tocar(RE, 250);
        delay(100);;
        tocar(RE, 250);
        delay(100);;
        tocar(MI, 250);
        delay(100);;
        tocar(RE, 500);
        delay(100);;
        tocar(SOL, 500);
        delay(500);
    }

    // Toca o tema dos Power Rangers (Go Go Power Rangers!)
    void powerRangers() {
        // "Go Go Power Rangers!"
        // Parte característica: Sol Sol La Sol Mi Re
        tocar(SOL, 150);
        delay(50);
        tocar(SOL, 150);
        delay(50);
        tocar(LA, 150);
        delay(50);
        tocar(SOL, 200);
        delay(50);
        tocar(MI, 200);
        delay(50);
        tocar(RE, 300);
        delay(200);
        
        // Repetição mais intensa
        tocar(SOL, 150);
        delay(50);
        tocar(SOL, 150);
        delay(50);
        tocar(LA, 150);
        delay(50);
        tocar(SOL, 200);
        delay(50);
        tocar(MI, 200);
        delay(50);
        tocar(RE, 300);
        delay(200);
        
        // Parte final energética
        tocar(DO_ALTO, 200);
        delay(50);
        tocar(SI, 200);
        delay(50);
        tocar(LA, 200);
        delay(50);
        tocar(SOL, 200);
        delay(50);
        tocar(LA, 150);
        delay(50);
        tocar(SOL, 150);
        delay(50);
        tocar(MI, 400);
        delay(100);
    }

    // Notas musicais (frequências em Hz)
    enum Notas {
        DO = 262,
        DO_S = 277,
        RE = 294,
        RE_S = 311,
        MI = 330,
        FA = 349,
        FA_S = 370,
        SOL = 392,
        SOL_S = 415,
        LA = 440,
        LA_S = 466,
        SI = 494,
        DO_ALTO = 523
    };
};

