#include "portas.h"
#include "SoftWire.h"



#ifdef SUPORTE_SERVO
#include "Servo.h"
#endif

#ifdef SUPORTE_SENSOR_TCS34725
#include "TCS34725.h"
#endif

#ifdef SUPORTE_SENSOR_VL53L0X
#include "VL53L0X.h"
#endif

#ifdef SUPORTE_RFID
#include "RFID.h"
#endif

#ifdef SUPORTE_DHT
#include "dht.h"
#endif

#ifdef SUPORTE_DS18B20
#include "ds18b20.h"
#endif

#ifdef SUPORTE_SENSOR_BMI160
#include "BMI160.h"
#endif

#ifdef SUPORTE_LED
#include "led.h"
#endif

#ifdef SUPORTE_SENSOR_ULTRASSONICO
#include "ultrassonico.h"
#endif


#ifdef SUPORTE_BUZZER
#include "buzzer.h"
#endif

#ifdef SUPORTE_VOZ
#include "voz.h"
#endif

#ifdef SUPORTE_MUSICA
#include "musica.h"
#endif

#ifdef SUPORTE_SENSOR_GIROSCOPIO
#include "giroscopio.h"
#endif

#ifdef SUPORTE_SENSOR_LINHA
#include "sensorLinha.h"
#endif

#ifdef SUPORTE_BLUETOOTH
#include "Bluetooth.h"
#endif

#ifdef SUPORTE_DISPLAY_SSD1306
#include "SSD1306.h"
#endif

#ifdef SUPORTE_TECLADO
#include "Teclado.h"
#endif

#include "interrupcoes.h"


#define MAXIMO_SENSORES 5
#define MAXIMO_MOTORES 2
#define MAXIMO_SERVOS 4

#ifdef SUPORTE_MOTOR
class Motor{ //nao vou usar a struct PortaMotor porque não quero usar alocação dinamica
private:
    uint8_t pwm;
    uint8_t dir;
    char descricaoPorta[6];
    int potenciaAtual = 0;
    int potenciaPadraoMotor = 60;
    bool invertido = false;
public:
    Motor(PortaMotor p, bool invertido=false){
        pwm = p.pwm;
        dir = p.dir;
        strcpy(this->descricaoPorta, p.descricao);
        pinMode(pwm, OUTPUT);
        pinMode(dir, OUTPUT);
        digitalWrite(pwm, LOW);
        digitalWrite(dir, LOW);
        this->invertido = invertido;
    }

    ~Motor(){
    }
    void setPotenciaPadrao(int potencia){
        potencia = constrain(potencia, -100, 100);
        this->potenciaPadraoMotor = potencia;
    }

    int getPotenciaPadrao(){
        return this->potenciaPadraoMotor;
    }

    void potencia(){
        potencia(this->potenciaPadraoMotor);
    }

    void acionaPorTempo(unsigned long tempoMs){
        potencia(this->potenciaPadraoMotor);
        delay(tempoMs);
        parar();
    }

    void acionaPorTempo(int potenciaAcionamento, unsigned long tempoMs){
        potencia(potenciaAcionamento);
        delay(tempoMs);
        parar();
    }

    void potencia(int potencia){
        // Agora a potência é de -100 a 100 (regra de 3 para 0-255 no PWM)
        potencia = constrain(potencia, -100, 100);
        if(invertido) potencia = -potencia;
        this->potenciaAtual = potencia;

        if(potencia >= 0){
            // Frente: converte de 0-100 para 0-255 (regra de 3 manual)
            int pwmValor = (potencia * 255) / 100; // 0 -> 0, 100 -> 255
            analogWrite(pwm, pwmValor);
            digitalWrite(dir, LOW);
        } else {
            // Reverso: usa módulo da potência, converte 0-100 para 0-255 (regra de 3 manual)
            int potAbs = -potencia;       // potAbs vai de 0 a 100
            int pwmValor = (potAbs * 255) / 100; // 0 -> 0, 100 -> 255
            analogWrite(pwm, 255 - pwmValor); // mantém a lógica original invertendo o valor
            digitalWrite(dir, HIGH);
        }
    }
    // Ponte H L9110S: com os dois pinos iguais (LOW/LOW ou HIGH/HIGH) as saidas ficam em curto e o
    // motor freia. Por isso frear() e parar() fazem a mesma coisa: nao existe "motor solto" nessa ponte.
    // Na frente o PWM alterna frente/freio; na re (analogWrite(255 - pwm) com dir HIGH) alterna re/freio.
    void frear(){
        digitalWrite(pwm, HIGH);
        digitalWrite(dir, HIGH);
    }

    void parar(){
        digitalWrite(pwm, LOW);
        digitalWrite(dir, LOW);
    }
    void setInvertido(bool invertido){
        this->invertido = invertido;
        potencia(this->potenciaAtual);
    }
};
#endif

class BrickSimples{
public:
    private:
    bool motor1Invertido = false;
    bool motor2Invertido = false;
    int potenciaPadraoBrick = 60;
    int16_t posicaoGiroscopioZInicioMovimento = 0;
    bool usandoGiroscopioNoMovimento = false;
    int delta = 0;
    
    #ifdef SUPORTE_SENSOR_TCS34725
    TCS34725 *listaTCS34725[MAXIMO_SENSORES]={NULL, NULL, NULL, NULL, NULL};
    #endif

    #ifdef SUPORTE_SENSOR_VL53L0X
    VL53L0X *listaVL53L0X[MAXIMO_SENSORES]={NULL, NULL, NULL, NULL, NULL};
    #endif
        
    #ifdef SUPORTE_SENSOR_ULTRASSONICO
    Ultrassonico *listaUltrassonico[MAXIMO_SENSORES]={NULL, NULL, NULL, NULL, NULL};
    #endif
    
    #ifdef SUPORTE_MOTOR
    Motor *listaMotor[MAXIMO_MOTORES]={NULL, NULL};
    #endif

    #ifdef SUPORTE_LED
    LEDStrip *ledStrip[MAXIMO_SERVOS] = {NULL, NULL, NULL, NULL};
    #endif
    
    #ifdef SUPORTE_BUZZER
    Buzzer *buzzer[MAXIMO_SERVOS] = {NULL, NULL, NULL, NULL};
    #endif

    #ifdef SUPORTE_SENSOR_GIROSCOPIO
    Giroscopio *giroscopio = NULL;
    #endif
    
    #ifdef SUPORTE_SENSOR_BMI160
    BMI160 *bmi160 = NULL; //teremos apenas 1 BMI160 por brick
    #endif
    
    #ifdef SUPORTE_SENSOR_LINHA
    SensorLinha *sensorLinha = NULL;
    #endif

    #ifdef SUPORTE_DISPLAY_SSD1306
    SSD1306 *display = NULL; //teremos apenas 1 display por brick
    #endif

    #ifdef SUPORTE_TECLADO
    Teclado *teclado = NULL; //teremos apenas 1 teclado por brick
    #endif

    #ifdef SUPORTE_BLUETOOTH
    Bluetooth *bluetooth = NULL; //teremos apenas 1 módulo bluetooth por brick
    #endif

    public:
    BrickSimples(){
    }
    ~BrickSimples(){
    }
    void inicializa(){
        Serial.begin(115200);
        
        //Vou fazer a configuração na classe do brick, porque mesmo que os motores não sejam usados, garanto que todos os pinos ficarão como devem
        // Configura Timer1 para PWM em ~122Hz (prescaler 1024)
        // Timer1 controla PWM dos pinos 9 e 10 (motores)
        TCCR1B = (TCCR1B & 0b11111000) | 0x05; // Prescaler 1024 (~31Hz PWM)
        
        //(os pinos abaixo estão sendo iniciados na declaração dos motores)
        //PINOS MOTOR ESQUERDO
        // pinMode(9, OUTPUT);
        // pinMode(7, OUTPUT);
        // digitalWrite(9, LOW);
        // digitalWrite(7, LOW);

        // //PINOS MOTOR DIREITO
        // pinMode(10, OUTPUT);
        // pinMode(4, OUTPUT);
        // digitalWrite(10, LOW);
        // digitalWrite(4, LOW);

        DDRE |= (1 << DDE0); // Configura PE0 como saída (pino do LED interno)
        ativaLedInterno();
        Serial.println(F("Hello, Brick Simples!!!!!!!"));
        Serial.print(F("Tensao da bateria: "));
        uint32_t tensao = analogRead(PINO_BATERIA);
        tensao = 4887 * tensao; //microvolt (estou fazendo isso para nao usar float)
        tensao = tensao / 1000; //milivolt
        Serial.print(tensao);
        Serial.println(F(" mV"));
        if(tensao <= 2000){ //milivolt
            Serial.println(F("Brick ligado apenas na USB, para ele funcionar, ligue a chave liga/desliga."));
            desativaLedInterno();
            while(1){
                tensao = analogRead(PINO_BATERIA);
                tensao = 4887 * tensao; //microvolt (estou fazendo isso para nao usar float)
                tensao = tensao / 1000; //milivolt
                if(tensao > 2000) break;
                delay(500);
            }
        }
        if(tensao > 2000 && tensao < 3100){ //milivolt
            Serial.println(F("Bateria fraca!"));
            Serial.println(F("Coloque o brick para carregar e aguarde."));
            desativaLedInterno();
            while(1);
        }
        Serial.println(F("Brick ligado, começando o código"));
        desativaLedInterno();
        return;
    }

    void espera(uint32_t ms){ //assim espero atualizando as coisas do brick
        uint32_t tempoFim = millis();
        tempoFim += ms;
        while(millis() < tempoFim){
            this->atualiza();
        }
    }


    uint32_t millis(){
        return ::millis();
    }

    #ifdef SUPORTE_MOTOR
    void setPotenciaPadrao(int potencia){
        potencia = constrain(potencia, -100, 100);
        this->potenciaPadraoBrick = potencia;
        if (listaMotor[0] != NULL){
            listaMotor[0]->setPotenciaPadrao(potencia);
        }
        if (listaMotor[1] != NULL){
            listaMotor[1]->setPotenciaPadrao(potencia);
        }
    }

    int getPotenciaPadrao(){
        return this->potenciaPadraoBrick;
    }

    // Controla ambos os motores usando a potência padrão configurada
    void potenciaMotores(){
        if (listaMotor[0] == NULL || listaMotor[1] == NULL){
            erroMotorNaoInicializado();
            return;
        }
        listaMotor[0]->potencia();
        listaMotor[1]->potencia();
    }

    void andarPraFrente(int potencia, bool giroscopioInvertido=false){
        if(listaMotor[0] == NULL || listaMotor[1] == NULL){
            erroMotorNaoInicializado();
            return;
        }
        int16_t posicaoAtualZ = 0;
        #ifdef SUPORTE_SENSOR_BMI160
        if(usandoGiroscopioNoMovimento && bmi160 != NULL){
            posicaoAtualZ = bmi160->getEixoZ()/10;
        }else{
            posicaoGiroscopioZInicioMovimento = bmi160->getEixoZ()/10;
            usandoGiroscopioNoMovimento = true;
        }
        #endif
        int16_t delta = posicaoGiroscopioZInicioMovimento - posicaoAtualZ;
        if(giroscopioInvertido) delta = -delta;
        listaMotor[0]->potencia(potencia-delta);
        listaMotor[1]->potencia(potencia+delta);
    }
    
    // Controla ambos os motores com a mesma potência
    // potencia: -100 a 100 (negativo = reverso, positivo = frente)
    void potenciaMotores(int potencia){
        if (listaMotor[0] == NULL || listaMotor[1] == NULL){
            erroMotorNaoInicializado();
            return;
        }
        usandoGiroscopioNoMovimento = false;
        listaMotor[0]->potencia(potencia);
        listaMotor[1]->potencia(potencia);
    }

    // Controla motores independentemente
    // potenciaEsq, potenciaDir: -100 a 100
    void potenciaMotores(int pot1, int pot2){
        if (listaMotor[0] == NULL || listaMotor[1] == NULL){
            erroMotorNaoInicializado();
            return;
        }
        usandoGiroscopioNoMovimento = false;
        listaMotor[0]->potencia(pot1);
        listaMotor[1]->potencia(pot2);
    }

    // Aciona ambos os motores pela potencia padrao por um tempo em ms
    void acionaMotoresPorTempo(unsigned long tempoMs){
        if (listaMotor[0] == NULL || listaMotor[1] == NULL){
            erroMotorNaoInicializado();
            return;
        }
        // Liga os dois motores praticamente ao mesmo tempo
        usandoGiroscopioNoMovimento = false;
        listaMotor[0]->potencia();
        listaMotor[1]->potencia();
        delay(tempoMs);
        // Para os dois motores juntos
        listaMotor[0]->parar();
        listaMotor[1]->parar();
    }

    // Aciona ambos os motores por um tempo em ms com a potencia informada
    void acionaMotoresPorTempo(int potencia, unsigned long tempoMs){
        if (listaMotor[0] == NULL || listaMotor[1] == NULL){
            erroMotorNaoInicializado();
            return;
        }
        usandoGiroscopioNoMovimento = false;
        // Liga os dois com a mesma potencia praticamente ao mesmo tempo
        listaMotor[0]->potencia(potencia);
        listaMotor[1]->potencia(potencia);
        delay(tempoMs);
        // Para os dois juntos
        listaMotor[0]->parar();
        listaMotor[1]->parar();
    }

    // Aciona ambos os motores por um tempo em ms com potencias independentes
    void acionaMotoresPorTempo(int potencia1, int potencia2, unsigned long tempoMs){
        if (listaMotor[0] == NULL || listaMotor[1] == NULL){
            erroMotorNaoInicializado();
            return;
        }
        usandoGiroscopioNoMovimento = false;
        // Liga os dois com a mesma potencia praticamente ao mesmo tempo
        listaMotor[0]->potencia(potencia1);
        listaMotor[1]->potencia(potencia2);
        delay(tempoMs);
        // Para os dois juntos
        listaMotor[0]->parar();
        listaMotor[1]->parar();
    }

    // Gira o robo por um tempo em ms usando potencias independentes nos motores
    // pot1: potencia do motor 1 (-100 a 100)
    // pot2: potencia do motor 2 (-100 a 100)
    // tempoMs: tempo em milissegundos
    void gireMotoresPorTempo(int pot1, int pot2, unsigned long tempoMs){
        potenciaMotores(pot1, pot2);
        delay(tempoMs);
        pararMotores();
    }


    // Para ambos os motores
    void pararMotores(){
        if (listaMotor[0] == NULL || listaMotor[1] == NULL){
            erroMotorNaoInicializado();
            return;
        }
        usandoGiroscopioNoMovimento = false;
        listaMotor[0]->parar();
        listaMotor[1]->parar();
    }

    void frearMotores(){
        if (listaMotor[0] == NULL || listaMotor[1] == NULL){
            erroMotorNaoInicializado();
            return;
        }
        usandoGiroscopioNoMovimento = false;
        listaMotor[0]->frear();
        listaMotor[1]->frear();
    }

    void erroMotorNaoInicializado(){
        Serial.println(F("Erro: Motor nao inicializado! Use brick.adiciona(motor1, motor2) antes de controlar os motores."));
    }
    #endif //SUPORTE_MOTOR


    bool botaoApertado(){
        uint16_t valor = analogRead(A6);
        if(valor < 100){
            return true;
        }else{
            return false;
        }
    }

    void atualiza(){
        //vejo se a chave foi desligada, se foi, reseto o código para parar de fazer qualquer coisa
        uint32_t tensao = analogRead(PINO_BATERIA);
        tensao = 4887 * tensao; //microvolt (estou fazendo isso para nao usar float)
        tensao = tensao / 1000; //milivolt
        if(tensao <= 2000){ //milivolt
            delay(100);
            this->reset();
        }
        bool giroscopioAtualizado = false;
        bool sensorLinhaAtualizado = false;

        #ifdef SUPORTE_SENSOR_VL53L0X
        for(uint8_t i=0; i<MAXIMO_SENSORES; i++){
            if(listaVL53L0X[i] != NULL){
                listaVL53L0X[i]->iniciaLeituraEmMilimetros();
            }
        }
        #endif

        #ifdef SUPORTE_SENSOR_ULTRASSONICO
        for(uint8_t i=0; i<MAXIMO_SENSORES; i++){
            if(listaUltrassonico[i] != NULL){
                listaUltrassonico[i]->iniciaMedicao();
            }
        }
        #endif
        
        uint32_t microsInicio = micros();

        #ifdef SUPORTE_SENSOR_TCS34725
        for(uint8_t i=0; i<MAXIMO_SENSORES; i++){
            if(listaTCS34725[i] != NULL){
                listaTCS34725[i]->enablePON();
            }
        }
        #endif

        //caso o tempo de atualização, seja menor que o tempo necessário para iniciar os sensores, espero o tempo restante
        while(micros() - microsInicio < 2500); //pequena espera para garantir que os sensores estejam prontos
        //delayMicroseconds(2500); //pequena espera para garantir que os sensores estejam prontos
        

        // microsInicio = micros();
        
        #ifdef SUPORTE_SENSOR_TCS34725
        for(uint8_t i=0; i<MAXIMO_SENSORES; i++){
            if(listaTCS34725[i] != NULL){
                listaTCS34725[i]->enablePON_AEN();
            }
        }
        #endif

        //while(micros() - microsInicio < 3800);
        microsInicio = micros();
        //AQUI EMBAIXO POSSO ADICIONAR MAIS FUNCÕES JÁ QUE ESPERO 5MS

        //como a leitura dos sensores serais que desenvolvi são rapidas (115200bps), preciso desativar todas as interrupções na hora da leitura da serial
        //então só posso fazer isso, porque a demora pode afetar os servos, então só faço se o servo não estiver ativo
        #ifdef SUPORTE_SERVO //tenho q remover o IF se nao tiver servo
        if(modoCicloServo == MODO_SERVO_FINALIZADO){ //posso atualizar o giroscopio (gasto aproximadamente 900uS)
        #endif
            #ifdef SUPORTE_SENSOR_GIROSCOPIO
            if(giroscopio != NULL){
                giroscopio->lerDados();
                giroscopioAtualizado = true;
            }
            #endif

            #ifdef SUPORTE_SENSOR_LINHA
            //Se tiver sensor de linha, vou ler aqui
            if(sensorLinha != NULL){
                sensorLinha->atualizaDadosTimeOut();
                sensorLinhaAtualizado = true;
            }
            #endif
        #ifdef SUPORTE_SERVO //tenho q remover o IF se nao tiver servo
        }
        #endif


        // else{
        //     delayMicroseconds(900);    
        // }
        // delayMicroseconds(3300);

        while(micros() - microsInicio < 5000); //pequena espera para garantir que os sensores estejam prontos

        #ifdef SUPORTE_SENSOR_TCS34725
        for(uint8_t i=0; i<MAXIMO_SENSORES; i++){
            if(listaTCS34725[i] != NULL){
                listaTCS34725[i]->getRawData();
            }
        }
        for(uint8_t i=0; i<MAXIMO_SENSORES; i++){
            if(listaTCS34725[i] != NULL){
                listaTCS34725[i]->disable();
            }
        }
        #endif
        
        microsInicio = micros();

        #ifdef SUPORTE_SENSOR_TCS34725
        for(uint8_t i=0; i<MAXIMO_SENSORES; i++){
            if(listaTCS34725[i] != NULL){
                listaTCS34725[i]->enablePON();
            }
        }
        #endif
        while(micros() - microsInicio < 2500); //pequena espera para garantir que os sensores estejam prontos
        
        //delayMicroseconds(2500); //pequena espera para garantir que os sensores estejam prontos
        //microsInicio = micros();
        #ifdef SUPORTE_SENSOR_TCS34725
        for(uint8_t i=0; i<MAXIMO_SENSORES; i++){
            if(listaTCS34725[i] != NULL){
                listaTCS34725[i]->enablePON_AEN();
                listaTCS34725[i]->ledOff();
            }
        }
        #endif
        
        microsInicio = micros();

        //tento atualizar novamente se nao consegui lá em cima
        //isso pode acontecer pelo tempo de movimentação de como os servos funcionam, então faço as duas tentativas. O ideal é por todos os sensores
        //serial dessa forma, tentando duas vezes com essa verificação para evitar espasmos nos servos, já que eu preciso desativar as interrupções
        //enquanto leio o retorno da serial dos sensores
        #ifdef SUPORTE_SERVO //tenho q remover o IF completo, pois já fiz ele lá em cima
        if(modoCicloServo == MODO_SERVO_FINALIZADO){
            #ifdef SUPORTE_SENSOR_GIROSCOPIO
            if(!giroscopioAtualizado){ //posso atualizar o giroscopio (gasto aproximadamente 900uS)
                if(giroscopio != NULL){
                    giroscopio->lerDados();
                    giroscopioAtualizado = true;
                }
            }
            #endif
            #ifdef SUPORTE_SENSOR_LINHA
            if(!sensorLinhaAtualizado){
                if(sensorLinha != NULL){
                    sensorLinha->atualizaDadosTimeOut();
                    sensorLinhaAtualizado = true;
                }
            }
            #endif
        }
        #endif
        #ifdef SUPORTE_SENSOR_BMI160
        if(!giroscopioAtualizado){ //posso atualizar o giroscopio (gasto aproximadamente 900uS)
            if(bmi160 != NULL){
                bmi160->atualizaDados();
                giroscopioAtualizado = true;
            }
        }
        #endif
        // else{
        //     delayMicroseconds(900);    
        // }
        // delayMicroseconds(3300);
        while(micros() - microsInicio < 5000);

        #ifdef SUPORTE_SENSOR_TCS34725
        uint16_t r_on, g_on, b_on, c_on;
        for(uint8_t i=0; i<MAXIMO_SENSORES; i++){
            if(listaTCS34725[i] != NULL){
                r_on = listaTCS34725[i]->getR();
                g_on = listaTCS34725[i]->getG();
                b_on = listaTCS34725[i]->getB();
                c_on = listaTCS34725[i]->getC();
                listaTCS34725[i]->getRawData();
                listaTCS34725[i]->setRGBCCalibrado(r_on, g_on, b_on, c_on); //preciso fazer assim para poder partir o processo e paralellizar em todos os sensores para ganhar tempo
            }
        }
        for(uint8_t i=0; i<MAXIMO_SENSORES; i++){
            if(listaTCS34725[i] != NULL){
                listaTCS34725[i]->disable();
            }
        }
        #endif

        #ifdef SUPORTE_SENSOR_VL53L0X
        for(uint8_t i=0; i<MAXIMO_SENSORES; i++){
            if(listaVL53L0X[i] != NULL){
                listaVL53L0X[i]->finalizaLeituraEmMilimetros();
            }
        }
        #endif

        // for(uint8_t i=0; i<MAXIMO_SENSORES; i++){
        //     if(listaUltrassonico[i] != NULL){
        //         listaUltrassonico[i]->medicaoPronta();
        //     }
        // }
    }

    #ifdef SUPORTE_SENSOR_TCS34725
    void adiciona(TCS34725 &sensor){
        for(int i=0; i<MAXIMO_SENSORES; i++){
            if(listaTCS34725[i] == NULL){
                listaTCS34725[i] = &sensor;
                break;
            }
        }
        sensor.begin();
    }
    #endif

    #ifdef SUPORTE_SENSOR_VL53L0X
    void adiciona(VL53L0X &sensor){
        for(int i=0; i<MAXIMO_SENSORES; i++){
            if(listaVL53L0X[i] == NULL){
                listaVL53L0X[i] =  &sensor;
                break;
            }
        }
        sensor.init();
    }
    #endif

    #ifdef SUPORTE_SENSOR_BMI160
    void adiciona(BMI160 &sensor){
        if(this->bmi160 == NULL){
            this->bmi160 = &sensor;
        }else{
            Serial.println(F("Erro: Apenas um sensor BMI160 pode ser adicionado por Brick!"));
            while(1);
        }
        sensor.begin();
    }
    #endif

    #ifdef SUPORTE_SENSOR_ULTRASSONICO
    void adiciona(Ultrassonico &sensor){
        for(int i=0; i<MAXIMO_SENSORES; i++){
            if(listaUltrassonico[i] == NULL){
                listaUltrassonico[i] = &sensor;
                break;
            }
        }
        sensor.inicializa();
    }
    #endif

    #ifdef SUPORTE_LED
    void adiciona(LEDStrip &leds){
        for(int i=0; i<MAXIMO_SERVOS; i++){ // quantidade de portas de servo/led
            if(ledStrip[i] == NULL){
                ledStrip[i] = &leds;
                break;
            }
        }
        leds.inicializa();
    }
    #endif

    #ifdef SUPORTE_BUZZER
    void adiciona(Buzzer &buzzer){
        for(int i=0; i<MAXIMO_SERVOS; i++){ // quantidade de portas de servo/led/buzzer
            if(this->buzzer[i] == NULL){
                this->buzzer[i] = &buzzer;
                break;
            }
        }
        buzzer.inicializa();
    }
    #endif

    #ifdef SUPORTE_DHT
    void adiciona(DHT &dht){ //DHT11/DHT22 nas portas de 1 fio (S1 a S4)
        dht.inicializa();
    }
    #endif

    #ifdef SUPORTE_DS18B20
    void adiciona(DS18B20 &sensor){ //DS18B20 nas portas de 1 fio (S1 a S4), até 4 por porta
        sensor.inicializa();
    }
    #endif

    #ifdef SUPORTE_RFID
    void adiciona(RFID &rfid){ //leitor RFID MFRC522 I2C, em qualquer porta I2C (1 a 5)
        rfid.inicializa();
    }
    #endif

    #ifdef SUPORTE_VOZ
    void adiciona(Voz &voz){ //só funciona na porta S3 (usa o Timer2)
        voz.inicializa();
    }
    #endif

    #ifdef SUPORTE_MUSICA
    void adiciona(Musica &musica){ //volume e timbre só na porta S3 (usa o Timer2)
        musica.inicializa();
    }
    #endif

    #ifdef SUPORTE_SENSOR_GIROSCOPIO
    void adiciona(Giroscopio &giro){
        this->giroscopio = &giro;
        giro.inicializa();
    }
    #endif

    #ifdef SUPORTE_SENSOR_LINHA
    void adiciona(SensorLinha &sensorLinha){
        this->sensorLinha = &sensorLinha;
        sensorLinha.inicializa();
    }
    #endif
    
    #ifdef SUPORTE_DISPLAY_SSD1306
    void adiciona(SSD1306 &display){
        if(this->display == NULL){
            this->display = &display;
        }else{
            Serial.println(F("Erro: Apenas um display SSD1306 pode ser adicionado por Brick!"));
            while(1);
        }
        display.init();
    }
    #endif

    #ifdef SUPORTE_TECLADO
    void adiciona(Teclado &teclado){
        if(this->teclado == NULL){
            this->teclado = &teclado;
        }else{
            Serial.println(F("Erro: Apenas um teclado pode ser adicionado por Brick!"));
            while(1);
        }
        teclado.init();
    }
    #endif

    #ifdef SUPORTE_BLUETOOTH
    void adiciona(Bluetooth &bluetooth){
        if(this->bluetooth == NULL){
            this->bluetooth = &bluetooth;
        }else{
            Serial.println(F("Erro: Apenas um módulo Bluetooth pode ser adicionado por Brick!"));
            while(1);
        }
        bluetooth.begin();
    }
    #endif

    #ifdef SUPORTE_MOTOR
    void adiciona(Motor &motor1, Motor &motor2){ //não tem porque adicionar um motor somente pra usar o "modo drive"
        listaMotor[0] = &motor1;
        listaMotor[1] = &motor2;
    }
    #endif

    void ativaLedInterno(){
        PORTE |= (1 << PINE0); // Define PE0 como alto
    }

    void desativaLedInterno(){
        PORTE &= ~(1 << PINE0); // Define PE0 como baixo
    }

    void reset(){
        // Configura todos os pinos das portas seriais como entrada
        pinMode(14, INPUT);
        pinMode(15, INPUT);
        pinMode(16, INPUT);
        pinMode(17, INPUT);
        pinMode(8, INPUT);
        pinMode(6, INPUT);
        pinMode(2, INPUT);
        pinMode(3, INPUT);
        pinMode(18, INPUT);
        pinMode(19, INPUT);
        asm volatile ("jmp 0x0000");
    }



};


BrickSimples brick;

#ifdef SUPORTE_SERVO
class Servos{
    private:
    Servo *servos;
    // const static uint8_t PINO_SERVO_1 = 13;
    // const static uint8_t PINO_SERVO_2 = 12;
    // const static uint8_t PINO_SERVO_3 = 11;
    // const static uint8_t PINO_SERVO_4 = 10;



    public:
    //definições de constantes
    // const static uint8_t PORTA_SERVO_1 = 1;
    // const static uint8_t PORTA_SERVO_2 = 2;
    // const static uint8_t PORTA_SERVO_3 = 3;
    // const static uint8_t PORTA_SERVO_4 = 4;

    Servos(){
        servos = new Servo[4]();
    }
    ~Servos(){
        delete[] servos;
    }
    void iniciaServo(PortaServo porta){
        if(porta.porta < 1 || porta.porta > 4){
            Serial.println(F("Erro: numero de porta de servo invalido!"));
            while(1);
        }  
        uint8_t pinoServo = 0;
        switch(porta.porta){
            case 1:
                pinoServo = porta.pino;
                break;
            case 2:
                pinoServo = porta.pino;
                break;
            case 3:
                pinoServo = porta.pino;
                break;
            case 4:
                pinoServo = porta.pino;
                break;
        }
        servos[porta.porta - 1].attach(pinoServo);
        Serial.print(F("Servo iniciado na porta "));
        Serial.println(porta.descricao);
    }
    void moveServo(PortaServo porta, int angulo){
        if(porta.porta < 1 || porta.porta > 4) return; //número inválido
        servos[porta.porta - 1].write(angulo);
    }
        void moveServoTempo(PortaServo porta, int anguloDestino, unsigned long tempoMs){
        if(porta.porta < 1 || porta.porta > 4) return; // número inválido

        // Garante limite de ângulo dentro do suportado pela biblioteca
        anguloDestino = constrain(anguloDestino, 0, 180);

        uint8_t indice = porta.porta - 1;
        int anguloAtual = servos[indice].read();

        int diferenca = anguloDestino - anguloAtual;
        int passos = abs(diferenca);

        // Se já está na posição desejada ou não há tempo, apenas posiciona
        if(passos == 0 || tempoMs == 0){
            servos[indice].write(anguloDestino);
            return;
        }

        // Define o intervalo entre cada passo em ms
        unsigned long intervalo = tempoMs / passos;
        if(intervalo == 0){
            intervalo = 1; // passo mínimo de 1 ms
        }

        // Tempo total realmente gasto com os passos
        unsigned long tempoUsado = intervalo * passos;
        long ajusteFinal = (long)tempoMs - (long)tempoUsado;

        int incremento = (diferenca > 0) ? 1 : -1;
        int angulo = anguloAtual;

        for(int i = 0; i < passos; i++){
            angulo += incremento;
            servos[indice].write(angulo);
            delay(intervalo);
        }

        // Se ainda sobrou um pequeno tempo por causa de arredondamento, espera ele
        if(ajusteFinal > 0){
            delay((unsigned long)ajusteFinal);
        }
    }
    void desanexaServo(PortaServo porta){
        if(porta.porta < 1 || porta.porta > 4) return; //número inválido
        servos[porta.porta - 1].detach();
    }

};


Servos servos;

#endif