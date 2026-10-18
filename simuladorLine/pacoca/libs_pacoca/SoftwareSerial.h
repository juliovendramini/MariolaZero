/*
SoftwareSerial.h (formerly NewSoftSerial.h) - 
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

#ifndef SoftwareSerial_h
#define SoftwareSerial_h

#include <inttypes.h>
#include <Stream.h>

/******************************************************************************
* Definitions
******************************************************************************/

#ifndef _SS_MAX_RX_BUFF
#define _SS_MAX_RX_BUFF 64 // RX buffer size
#endif

#ifndef GCC_VERSION
#define GCC_VERSION (__GNUC__ * 10000 + __GNUC_MINOR__ * 100 + __GNUC_PATCHLEVEL__)
#endif

class SoftwareSerial : public Stream
{
private:
  // per object data
  uint8_t _receivePin;
  uint8_t _receiveBitMask;
  volatile uint8_t *_receivePortRegister;
  uint8_t _transmitBitMask;
  volatile uint8_t *_transmitPortRegister;

  // Expressed as 4-cycle delays (must never be 0!)
  uint16_t _rx_delay_centering;
  uint16_t _rx_delay_intrabit;
  uint16_t _rx_delay_stopbit;
  uint16_t _tx_delay;
  
  // Timeout baseado em loops (sem usar millis)
  uint16_t _timeout_loops;

  // private methods
  int readByteDirect();  // Lê um byte diretamente (bloqueante)
  uint8_t rx_pin_read();
  void setTX(uint8_t transmitPin);
  void setRX(uint8_t receivePin);

  // Return num - sub, or 1 if the result would be < 1
  static uint16_t subtract_cap(uint16_t num, uint16_t sub);

  // private static method for timing
  static inline void tunedDelay(uint16_t delay);

public:
  // public methods
  SoftwareSerial(uint8_t receivePin, uint8_t transmitPin);
  ~SoftwareSerial();
  void begin(long speed);
  void end();
  void setTimeout(unsigned long timeout_ms) { 
    // Converte ms para loops (aproximadamente 3 ciclos por loop @ 16MHz)
    _timeout_loops = (timeout_ms * (F_CPU / 1000)) / 3;
  }
  int peek();

  virtual size_t write(uint8_t byte);
  virtual int read();  // Lê 1 byte com timeout
  virtual int available();
  virtual void flush();
  size_t readBytes(uint8_t *buffer, size_t length);  // Lê múltiplos bytes com timeout
  operator bool() { return true; }
  
  using Print::write;
};

#endif
