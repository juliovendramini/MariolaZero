/* 
  A servo is activated by creating an instance of the Servo class passing 
  the desired pin to the attach() method.
  The servos are pulsed in the background using the value most recently 
  written using the write() method.

  Note that analogWrite of PWM on pins associated with the timer are 
  disabled when the first servo is attached.
  Timers are seized as needed in groups of 12 servos - 24 servos use two 
  timers, 48 servos will use four.
  The sequence used to seize timers is defined in timers.h

  The methods are:

    Servo - Class for manipulating servo motors connected to Arduino pins.

    attach(pin )  - Attaches a servo motor to an I/O pin.
    attach(pin, min, max  ) - Attaches to a pin setting min and max values in microseconds
    default min is 544, max is 2400  
 
    write()     - Sets the servo angle in degrees.  (invalid angle that is valid as pulse in microseconds is treated as microseconds)
    writeMicroseconds() - Sets the servo pulse width in microseconds 
    read()      - Gets the last written servo pulse width as an angle between 0 and 180. 
    readMicroseconds()   - Gets the last written servo pulse width in microseconds. (was read_us() in first release)
    attached()  - Returns true if there is a servo attached. 
    detach()    - Stops an attached servos from pulsing its I/O pin. 
 */

#ifndef Servo_h
#define Servo_h

#include <inttypes.h>

/* 
 Biblioteca usando o timer2 para controle de servos.
 Adaptada da classe original de servos do timer1, porém muito modificada
 */

#define Servo_VERSION           2     // software version of this library

#define MIN_PULSE_WIDTH       544     // the shortest pulse sent to a servo  
#define MAX_PULSE_WIDTH      2400     // the longest pulse sent to a servo 
#define DEFAULT_PULSE_WIDTH  1500     // default pulse width when servo is attached

#define SERVOS_PER_TIMER       4     // the maximum number of servos controlled by one timer 
#define MAX_SERVOS   SERVOS_PER_TIMER  

#define INVALID_SERVO         255     // flag indicating an invalid servo index

typedef struct  {
  uint8_t nbr        :6 ;             // a pin number from 0 to 63
  uint8_t isActive   :1 ;             // true if this channel is enabled, pin not pulsed if false 
} ServoPin_t   ;  

typedef struct {
  ServoPin_t Pin;
  volatile uint8_t ticks;
  // Cached register pointers for fast access
  volatile uint8_t *portOut;          // PORT register (PORTx)
  uint8_t pinMask;                    // bit mask for the pin
  uint8_t estadoPino;              //0 - desligado, 1 - ligado
} servo_t;

class Servo
{
public:
  Servo();
  uint8_t attach(uint8_t pin);           // attach the given pin to the next free channel, sets pinMode, returns channel number or 0 if failure
  uint8_t attach(uint8_t pin, int min, int max); // as above but also sets min and max values for writes. 
  void detach();
  void write(int value);          
  void writeTicks(uint8_t  value); 
  int read();                        // returns current pulse width as an angle between 0 and 180 degrees
  bool attached();                   // return true if this servo is attached, otherwise false 
private:
   uint8_t servoIndex;               // index into the channel data for this servo
   uint8_t min;                       // valor guardado em ticks, 1 tick = 16us
   uint8_t max;                       // valor guardado em ticks, 1 tick = 16us
};



#define MODO_SERVO_FINALIZADO 0
#define MODO_SERVO_ATIVO 1
static volatile uint8_t modoCicloServo = 0; // 1 - ativado, 0 - esperando o clico acabar


#endif
