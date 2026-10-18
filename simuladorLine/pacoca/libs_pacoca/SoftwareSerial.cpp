/*
SoftwareSerial.cpp (formerly NewSoftSerial.cpp) - 
Multi-instance software serial library for Arduino/Wiring
-- Interrupt-driven receive and other improvements by ladyada
   (http://ladyada.net)
-- Tuning, circular buffer, derivation from class Print/Stream,
   multi-instance support, porting to 8MHz processors,
   various optimizations, PROGMEM delay tables, inverse logic and 
   direct port writing by Mikal Hart (http://www.arduiniana.org)
-- Pin change interrupt macros by Paul Stoffregen (http://www.pjrc.com)
-- 20MHz processor support by Garrett Mace (http://www.macetech.com)
-- ATmega1280/2560 support by Brett Hagman (http://www.roguerobotics.com/)

This library is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation; either
version 2.1 of the License, or (at your option) any later version.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this library; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

The latest version of this library can always be found at
http://arduiniana.org.
*/

// 
// Includes
// 
#include <avr/interrupt.h>
#include <avr/pgmspace.h>
#include <Arduino.h>
#include "SoftwareSerial.h"
#include <util/delay_basic.h>



//
// Private methods
//

/* static */ 
inline void SoftwareSerial::tunedDelay(uint16_t delay) { 
  _delay_loop_2(delay);
}

//
// Leitura bloqueante de um byte - otimizada para 115200 baud
//
int SoftwareSerial::readByteDirect()
{
  uint8_t d = 0;
  uint8_t oldSREG = SREG;
  
  // Aguarda start bit (linha vai para LOW) - timeout baseado em loops
  uint16_t timeout_count = 0;
  while (*_receivePortRegister & _receiveBitMask)
  {
    if (++timeout_count > _timeout_loops)
      return -1;  // Timeout
  }

  //cli();  // Desabilita interrupções para timing preciso

  // Wait approximately 1/2 of a bit width to "center" the sample
  tunedDelay(_rx_delay_centering);

  // Read each of the 8 bits
  for (uint8_t i=0; i < 8; i++)
  {
    tunedDelay(_rx_delay_intrabit);
    d >>= 1;
    
    if (*_receivePortRegister & _receiveBitMask)
      d |= 0x80;
  }

  // skip the stop bit
  tunedDelay(_rx_delay_stopbit);
  
  SREG = oldSREG;  // Restaura interrupções

  return d;
}

uint8_t SoftwareSerial::rx_pin_read()
{
  return *_receivePortRegister & _receiveBitMask;
}

//
// Interrupt handling removido - agora usa leitura bloqueante
//

//
// Constructor
//
SoftwareSerial::SoftwareSerial(uint8_t receivePin, uint8_t transmitPin) : 
  _rx_delay_centering(0),
  _rx_delay_intrabit(0),
  _rx_delay_stopbit(0),
  _tx_delay(0),
  _timeout_loops(30000)  // ~10ms timeout @ 16MHz (ajustar conforme necessário)
{
  setTX(transmitPin);
  setRX(receivePin);
}

//
// Destructor
//
SoftwareSerial::~SoftwareSerial()
{
  end();
}

void SoftwareSerial::setTX(uint8_t tx)
{
  // First write, then set output. If we do this the other way around,
  // the pin would be output low for a short while before switching to
  // output high. Now, it is input with pullup for a short while, which is fine.
  digitalWrite(tx, HIGH);
  pinMode(tx, OUTPUT);
  _transmitBitMask = digitalPinToBitMask(tx);
  uint8_t port = digitalPinToPort(tx);
  _transmitPortRegister = portOutputRegister(port);
}

void SoftwareSerial::setRX(uint8_t rx)
{
  pinMode(rx, INPUT);
  digitalWrite(rx, HIGH);  // pullup for normal logic!
  _receivePin = rx;
  _receiveBitMask = digitalPinToBitMask(rx);
  uint8_t port = digitalPinToPort(rx);
  _receivePortRegister = portInputRegister(port);
}

uint16_t SoftwareSerial::subtract_cap(uint16_t num, uint16_t sub) {
  if (num > sub)
    return num - sub;
  else
    return 1;
}

//
// Public methods
//

void SoftwareSerial::begin(long speed)
{
  _rx_delay_centering = _rx_delay_intrabit = _rx_delay_stopbit = _tx_delay = 0;

  // Precalculate the various delays, in number of 4-cycle delays
  uint16_t bit_delay = (F_CPU / speed) / 4;

  // Otimização para 115200 baud @ 16MHz:
  // Bit time = 1/115200 = 8.68 µs = 138.88 cycles @ 16MHz
  // bit_delay = 138.88 / 4 = 34.72 ~ 35 loops de 4 ciclos
  
  //TX: overhead de ~15 ciclos (store registers, bit test, etc)
  _tx_delay = subtract_cap(bit_delay, 15 / 4);

  // RX com interrupções desabilitadas: overhead mínimo ~10-12 ciclos
  // Centering: metade do bit menos overhead de detecção start bit (~12 ciclos)
  _rx_delay_centering = subtract_cap(bit_delay / 2, 20 / 4);
  
  // Intrabit: tempo total do bit menos overhead do loop (~10 ciclos)
  _rx_delay_intrabit = subtract_cap(bit_delay, 16 / 4);
  
  // Stop bit: tempo do bit menos overhead final (~10 ciclos)
  _rx_delay_stopbit = subtract_cap(bit_delay, 10 / 4);

  // _tx_delay = bit_delay;
  _rx_delay_centering = bit_delay / 4;
  // _rx_delay_intrabit = bit_delay;
  // _rx_delay_stopbit = bit_delay;

  tunedDelay(_tx_delay); // if we were low this establishes the end
}

void SoftwareSerial::end()
{
  // Nada para fazer sem interrupções
}


// Leitura bloqueante de 1 byte com timeout
int SoftwareSerial::read()
{
  return readByteDirect();
}

// Leitura bloqueante de múltiplos bytes com timeout
size_t SoftwareSerial::readBytes(uint8_t *buffer, size_t length)
{
  size_t count = 0;
  while (count < length)
  {
    int c = readByteDirect();
    if (c < 0)
      break;  // Timeout
    buffer[count++] = (uint8_t)c;
  }
  return count;
}

int SoftwareSerial::available()
{
  // Sem buffer - verifica apenas se há start bit presente (LOW)
  return rx_pin_read() ? 0 : 1;
}

size_t SoftwareSerial::write(uint8_t b)
{
  if (_tx_delay == 0) {
    setWriteError();
    return 0;
  }

  // By declaring these as local variables, the compiler will put them
  // in registers _before_ disabling interrupts and entering the
  // critical timing sections below, which makes it a lot easier to
  // verify the cycle timings
  volatile uint8_t *reg = _transmitPortRegister;
  uint8_t reg_mask = _transmitBitMask;
  uint8_t inv_mask = ~_transmitBitMask;
  uint8_t oldSREG = SREG;
  uint16_t delay = _tx_delay;

  cli();  // turn off interrupts for a clean txmit

  // Write the start bit (LOW)
  *reg &= inv_mask;

  tunedDelay(delay);

  // Write each of the 8 bits
  for (uint8_t i = 8; i > 0; --i)
  {
    if (b & 1) // choose bit
      *reg |= reg_mask; // send 1
    else
      *reg &= inv_mask; // send 0

    tunedDelay(delay);
    b >>= 1;
  }

  // restore pin to natural state (HIGH)
  *reg |= reg_mask;

  SREG = oldSREG; // turn interrupts back on
  tunedDelay(_tx_delay);
  
  return 1;
}

void SoftwareSerial::flush()
{
  // There is no tx buffering, simply return
}

int SoftwareSerial::peek()
{
  // Peek não é possível sem buffer de interrupção
  return -1;
}
