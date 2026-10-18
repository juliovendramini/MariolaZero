// Servo do simulador: guarda o ângulo e mostra no terminal; o servo não aparece no robô simulado.
#ifndef Servo_h
#define Servo_h
#include <Arduino.h>

#define Servo_VERSION 2
#define MIN_PULSE_WIDTH 544
#define MAX_PULSE_WIDTH 2400
#define DEFAULT_PULSE_WIDTH 1500
#define SERVOS_PER_TIMER 4
#define MAX_SERVOS SERVOS_PER_TIMER
#define INVALID_SERVO 255

class Servo {
public:
    Servo() {}
    uint8_t attach(uint8_t pin) { return attach(pin, MIN_PULSE_WIDTH, MAX_PULSE_WIDTH); }
    uint8_t attach(uint8_t pin, int mn, int mx) {
        _pino = pin;
        _min = mn;
        _max = mx;
        _ligado = true;
        pinMode(pin, OUTPUT);
        return 1;
    }
    void detach() { _ligado = false; }
    void write(int value) {
        if (value < MIN_PULSE_WIDTH) {
            if (value < 0) value = 0;
            if (value > 180) value = 180;
            _angulo = value;
        } else {
            _angulo = (int)map(value, _min, _max, 0, 180);
        }
    }
    void writeMicroseconds(int us) { write(us); }
    void writeTicks(uint8_t ticks) { write(ticks * 16); }
    int read() { return _angulo; }
    bool attached() { return _ligado; }

private:
    uint8_t _pino = 0;
    int _min = MIN_PULSE_WIDTH, _max = MAX_PULSE_WIDTH;
    int _angulo = 90;
    bool _ligado = false;
};

#define MODO_SERVO_FINALIZADO 0
#define MODO_SERVO_ATIVO 1
static volatile uint8_t modoCicloServo = 0;

#endif
