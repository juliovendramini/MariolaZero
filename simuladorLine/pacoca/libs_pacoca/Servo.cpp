#include <avr/interrupt.h>
#include <Arduino.h>

#include "Servo.h"


static volatile servo_t servos[MAX_SERVOS];                          // static array of servo structures
#define SERVO(_Canal)  (servos[_Canal])                    // acesso direto por canal

uint8_t ServoCount = 0;                                     // the total number of attached servos
// convenience macros - Timer2 apenas

#define SERVO_MIN this->min   // minimum value in ticks for this servo
#define SERVO_MAX this->max  // maximum value in ticks for this servo

/************ static functions common to all instances ***********************/
//o tempo de ciclo é 20ms, 4ms de um modoCicloServo e 16ms do outro
//a ideia nessa interrupção é ter duas partes. A primeira (valor 1, é curta e nao é recomendável desativar interrupções em nenhum lugar do código)
//já no valor 0, estamos esperando o próximo ciclo, que demora 16ms, então nesse tempo podemos desativar interrupções se necessário
static inline void handle_interrupts()
{
  uint8_t menorPulso = 255;
  uint8_t Canal;
  if(modoCicloServo == MODO_SERVO_FINALIZADO){//o ciclo acabou, vou começar um novo
    //mudo a velocidade do presscaller
    TCCR2B = _BV(CS22) | _BV(CS21);     // set prescaler of 256
    TCNT2 = 0;
    //para todos os canais: coloco os servos como ativos
    Canal=0;    // increment to the next Canal
    while(Canal < ServoCount){
        if(SERVO(Canal).Pin.isActive == true){ // check if activated
          *SERVO(Canal).portOut |= SERVO(Canal).pinMask; // pulse this Canal HIGH - direct register access
          SERVO(Canal).estadoPino = 1;
          if(menorPulso > SERVO(Canal).ticks){
            menorPulso = SERVO(Canal).ticks;
          }
        }  
        Canal++;
    }
    modoCicloServo = MODO_SERVO_ATIVO ;//modoCicloServo ativado
    OCR2A = TCNT2 + menorPulso;
    return;
  }
  if(modoCicloServo == MODO_SERVO_ATIVO){
    //ve qual que tem q desativar
    if(OCR2A == 255){//chegou no final do ciclo de servos
      modoCicloServo = MODO_SERVO_FINALIZADO; //mudo para o modoCicloServo de espera do próximo ciclo (longo)
      TCCR2B = _BV(CS22) | _BV(CS21) | _BV(CS20); // set prescaler of 1024
      OCR2A = 255;
      TCNT2 = 0;
      return;
    }
    Canal = 0;
    while(Canal < ServoCount){
      if(SERVO(Canal).Pin.isActive == true && SERVO(Canal).estadoPino == 1){ // check if activated  
        if(TCNT2 >= SERVO(Canal).ticks){
          *SERVO(Canal).portOut &= ~SERVO(Canal).pinMask; // pulse this Canal LOW - direct register access  
          SERVO(Canal).estadoPino = 0;
        }
        if(SERVO(Canal).estadoPino == 1){//ainda está ativo
          if(menorPulso > SERVO(Canal).ticks){
            menorPulso = SERVO(Canal).ticks;
          }
        }
      }
      Canal++;
    }
    OCR2A = menorPulso; //o pulso já tem o valor todos desde zero
    return;
  }
}

ISR(TIMER2_COMPA_vect)
{
  handle_interrupts();
}

static void initISR()
{
  TCCR2A = 0;             // normal counting mode
  TCCR2B = _BV(CS22) | _BV(CS21);     // set prescaler of 256
  TCNT2 = 0;              // clear the timer count
  TIFR2 = _BV(OCF2A);     // clear any pending interrupts
  TIMSK2 =  _BV(OCIE2A) ; // enable the output compare interrupt
}



static void finISR()
{
  TIMSK2 &= ~_BV(OCIE2A);  // disable timer2 output compare A interrupt
}

static boolean isTimerActive()
{
  // returns true if any servo is active
  for(uint8_t Canal=0; Canal < SERVOS_PER_TIMER; Canal++) {
    if(SERVO(Canal).Pin.isActive == true)
      return true;
  }
  return false;
}

/****************** end of static functions ******************************/

Servo::Servo()
{
  if( ServoCount < MAX_SERVOS) {
    this->servoIndex = ServoCount++;                    // assign a servo index to this instance
    servos[this->servoIndex].ticks = DEFAULT_PULSE_WIDTH/16; 
  }
  else {
    this->servoIndex = INVALID_SERVO ;  // too many servos
  }
}

uint8_t Servo::attach(uint8_t pin)
{
  return this->attach(pin, MIN_PULSE_WIDTH, MAX_PULSE_WIDTH);
}

uint8_t Servo::attach(uint8_t pin, int min, int max)
{
  if(this->servoIndex < MAX_SERVOS ) {
    pinMode( pin, OUTPUT) ;                                   // set servo pin to output
    servos[this->servoIndex].Pin.nbr = pin;
    
    // Cache register pointers for fast ISR access (read once, use many times)
    uint8_t port = digitalPinToPort(pin);
    servos[this->servoIndex].portOut = portOutputRegister(port);
    servos[this->servoIndex].pinMask = digitalPinToBitMask(pin);
    
    this->min  = (min)/16; //resolution of min/max is 16 us
    this->max  = (max)/16;
    // initialize Timer2 if it has not already been initialized
    if(isTimerActive() == false)
      initISR();
    servos[this->servoIndex].Pin.isActive = true;  // this must be set after the check for isTimerActive
  }
  return this->servoIndex ;
}

void Servo::detach()
{
  servos[this->servoIndex].Pin.isActive = false;
  if(isTimerActive() == false) {
    finISR();
  }
}

void Servo::write(int value) //somente angulo
{
  if(value < 0) value = 0;
  if(value > 180) value = 180;
  value = map(value, 0, 180, this->min,  this->max); //mapeando para ticks
  this->writeTicks(value);
}

void Servo::writeTicks(uint8_t value)
{
  // calculate and store the values for the given Canal
  byte Canal = this->servoIndex;
  if( (Canal < MAX_SERVOS) )   // ensure Canal is valid
  {
    if( value < SERVO_MIN )          // ensure pulse width is valid
      value = SERVO_MIN;
    else if( value > SERVO_MAX )
      value = SERVO_MAX;


    uint8_t oldSREG = SREG;
    cli();
    servos[Canal].ticks = value;
    SREG = oldSREG;
  }
}

int Servo::read() // return the value as degrees
{
  return  map(servos[this->servoIndex].ticks+1, SERVO_MIN, SERVO_MAX, 0, 180);
}

bool Servo::attached()
{
  return servos[this->servoIndex].Pin.isActive;
}
