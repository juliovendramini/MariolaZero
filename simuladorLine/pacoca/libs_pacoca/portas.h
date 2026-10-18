#ifndef _PORTAS_H_
#define _PORTAS_H_
#include <Arduino.h>


//definições dos registradores do atmega328pb (que é o utilizado) mesmo ele se passando por um 328P, podemos usar os pinos extras e controlar pelos registradores
#define PINE    _SFR_IO8(0x0C)
#define PINE3   3
#define PINE2   2
#define PINE1   1
#define PINE0   0

#define DDRE    _SFR_IO8(0x0D)
#define DDRE3   3
// Inserted "DDE3" from "DDRE3" due to compatibility
#define DDE3    3
#define DDRE2   2
// Inserted "DDE2" from "DDRE2" due to compatibility
#define DDE2    2
#define DDRE1   1
// Inserted "DDE1" from "DDRE1" due to compatibility
#define DDE1    1
#define DDRE0   0
// Inserted "DDE0" from "DDRE0" due to compatibility
#define DDE0    0

#define PORTE   _SFR_IO8(0x0E)
#define PORTE3  3
#define PORTE2  2
#define PORTE1  1
#define PORTE0  0



#define PINO_BATERIA A7


//para cada tipo de sensor, eu devo definir uma struct com os pinos e descrição e 
//depois criar as constantes dentro da classe Portas das portas que são compatíveis com aquele tipo de sensor
struct PortaI2C{
    const uint8_t sda;
    const uint8_t scl;
    const char *descricao;
};

struct PortaServo{
    const uint8_t porta;
    const uint8_t pino;
    const char *descricao;
};

//mesmas portas do servo
struct PortaLed{
    const uint8_t porta;
    const uint8_t pino;
    const char *descricao;
};

//mesmas portas do servo
struct PortaBuzzer{
    const uint8_t porta;
    const uint8_t pino;
    const char *descricao;
};

//sensores de 1 fio digital (DHT11, DHT22, DS18B20): mesmas portas do servo
struct PortaDigital{
    const uint8_t porta;
    const uint8_t pino;
    const char *descricao;
};

struct PortaAnalogica{
    const uint8_t pino1;
    const uint8_t pino2;
};

struct PortaUltrassonico{
    const uint8_t echo;
    const uint8_t trig;
    const char *descricao;
};

struct PortaSerial{
    const uint8_t rx;
    const uint8_t tx;
    const char *descricao;
};

struct PortaMotor{
    const uint8_t pwm;
    const uint8_t dir;
    const char *descricao;
};

// Portas I2C
#define PORTA_I2C_1 {14, 15, "I2C-1"}
#define PORTA_I2C_2 {16, 17, "I2C-2"}
#define PORTA_I2C_3 {8, 6, "I2C-3"}
#define PORTA_I2C_4 {2, 3, "I2C-4"}
#define PORTA_I2C_5 {18, 19, "I2C-5"}

// Portas Serial (Software Serial)
#define PORTA_SERIAL_1 {14, 15, "SER-1"}
#define PORTA_SERIAL_2 {16, 17, "SER-2"}
#define PORTA_SERIAL_3 {8, 6, "SER-3"}
#define PORTA_SERIAL_4 {2, 3, "SER-4"}
#define PORTA_SERIAL_5 {18, 19, "SER-5"}

// Portas Servo
#define PORTA_SERVO_1 {1, 13, "S1"}
#define PORTA_SERVO_2 {2, 12, "S2"}
#define PORTA_SERVO_3 {3, 11, "S3"}
#define PORTA_SERVO_4 {4, 5, "S4"}

// Portas LED
#define PORTA_LED_1 {1, 13, "S1"}
#define PORTA_LED_2 {2, 12, "S2"}
#define PORTA_LED_3 {3, 11, "S3"}
#define PORTA_LED_4 {4, 5, "S4"}

// Ddefinir indice dos leds
# define LED_1 0
# define LED_2 1
# define LED_3 2
# define LED_4 3
# define LED_5 4
# define LED_6 5
# define LED_7 6
# define LED_8 7
# define LED_9 8
# define LED_10 9

// Portas Buzzer
#define PORTA_BUZZER_1 {1, 13, "S1"}
#define PORTA_BUZZER_2 {2, 12, "S2"}
#define PORTA_BUZZER_3 {3, 11, "S3"}
#define PORTA_BUZZER_4 {4, 5, "S4"}

// Portas para sensores digitais de 1 fio (DHT11/DHT22 e DS18B20)
#define PORTA_DHT_1 {1, 13, "S1"}
#define PORTA_DHT_2 {2, 12, "S2"}
#define PORTA_DHT_3 {3, 11, "S3"}
#define PORTA_DHT_4 {4, 5, "S4"}

#define PORTA_DS18B20_1 {1, 13, "S1"}
#define PORTA_DS18B20_2 {2, 12, "S2"}
#define PORTA_DS18B20_3 {3, 11, "S3"}
#define PORTA_DS18B20_4 {4, 5, "S4"}

// Portas Analógicas
#define PORTA_ANALOGICA_1 {A0, A1}
#define PORTA_ANALOGICA_2 {A2, A3}
#define PORTA_ANALOGICA_5 {A4, A5}

// Portas Ultrassônico //ORDEM DOS PINOS: ECHO, TRIGGER
#define PORTA_ULTRASSONICO_1 {14, 15, "US-1"} 
#define PORTA_ULTRASSONICO_2 {16, 17, "US-2"}
#define PORTA_ULTRASSONICO_3 {8, 6, "US-3"}
#define PORTA_ULTRASSONICO_4 {2, 3, "US-4"}
#define PORTA_ULTRASSONICO_5 {18, 19, "US-5"}


#define PORTA_MOTOR_1 {9, 7, "M1"}
#define PORTA_MOTOR_2 {10, 4, "M2"}

#define MOTOR_INVERTIDO true
#define MOTOR_NORMAL false

// // Definições das constantes static (necessário para linker)
// constexpr PortaI2C Portas::PORTA_I2C_1;
// constexpr PortaI2C Portas::PORTA_I2C_2;
// constexpr PortaI2C Portas::PORTA_I2C_3;
// constexpr PortaI2C Portas::PORTA_I2C_4;
// constexpr PortaI2C Portas::PORTA_I2C_5;

#endif