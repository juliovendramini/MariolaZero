// If possible disable interrupts whilst switching pin direction. Sadly
// there is no generic Arduino function to read the current interrupt
// status, only to enable and disable interrupts.  As a result the
// protection against spurious signals on the I2C bus is only available
// for AVR architectures where ATOMIC_BLOCK is defined.
#include "SoftWire.h"
#if defined(ARDUINO_ARCH_AVR)
#include <util/atomic.h>
#include <util/delay.h>
#endif

// Definição dos membros static (compartilhados entre todas as instâncias)
uint8_t SoftWire::_rxBuffer[32];
const uint8_t SoftWire::_rxBufferSize;
uint8_t SoftWire::_rxBufferIndex = 0;
uint8_t SoftWire::_rxBufferBytesRead = 0;

uint8_t SoftWire::_txAddress = 8;  // First non-reserved address
uint8_t SoftWire::_txBuffer[32];
const uint8_t SoftWire::_txBufferSize;
uint8_t SoftWire::_txBufferIndex = 0;

// Macro para obter os registradores PORT, DDR e PIN de um pino digital
#define digitalPinToPort(P) ( pgm_read_byte( digital_pin_to_port_PGM + (P) ) )
#define digitalPinToBitMask(P) ( pgm_read_byte( digital_pin_to_bit_mask_PGM + (P) ) )
#define portOutputRegister(P) ( (volatile uint8_t *)( pgm_read_word( port_to_output_PGM + (P))) )
#define portInputRegister(P) ( (volatile uint8_t *)( pgm_read_word( port_to_input_PGM + (P))) )
#define portModeRegister(P) ( (volatile uint8_t *)( pgm_read_word( port_to_mode_PGM + (P))) )

// Force SDA low - OTIMIZADO usando cache de registradores
void SoftWire::sdaLow(const SoftWire *p)
{
#ifdef ATOMIC_BLOCK
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE)
#endif
  {
    *p->_sdaOut &= ~p->_sdaMask;  // Coloca saída em LOW
    *p->_sdaDdr |= p->_sdaMask;   // Configura como OUTPUT
  }
}


// Release SDA to float high - OTIMIZADO usando cache de registradores
void SoftWire::sdaHigh(const SoftWire *p)
{
  *p->_sdaDdr &= ~p->_sdaMask;  // Configura como INPUT
  if (p->getInputMode() == INPUT_PULLUP) {
    *p->_sdaOut |= p->_sdaMask;   // Ativa pull-up
  } else {
    *p->_sdaOut &= ~p->_sdaMask;  // Desativa pull-up
  }
}


// Force SCL low - OTIMIZADO usando cache de registradores
void SoftWire::sclLow(const SoftWire *p)
{
#ifdef ATOMIC_BLOCK
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE)
#endif
  {
    *p->_sclOut &= ~p->_sclMask;  // Coloca saída em LOW
    *p->_sclDdr |= p->_sclMask;   // Configura como OUTPUT
  }
}


// Release SCL to float high - OTIMIZADO usando cache de registradores
void SoftWire::sclHigh(const SoftWire *p)
{
  *p->_sclDdr &= ~p->_sclMask;  // Configura como INPUT
  if (p->getInputMode() == INPUT_PULLUP) {
    *p->_sclOut |= p->_sclMask;   // Ativa pull-up
  } else {
    *p->_sclOut &= ~p->_sclMask;  // Desativa pull-up
  }
}


// Read SDA (for data read) - OTIMIZADO usando cache de registradores
uint8_t SoftWire::readSda(const SoftWire *p)
{
  return (*p->_sdaIn & p->_sdaMask) ? HIGH : LOW;
}


// Read SCL (to detect clock-stretching) - OTIMIZADO usando cache de registradores
uint8_t SoftWire::readScl(const SoftWire *p)
{
  return (*p->_sclIn & p->_sclMask) ? HIGH : LOW;
}


// For testing the CRC-8 calculator may be useful:
// http://smbus.org/faq/crc8Applet.htm
uint8_t SoftWire::crc8_update(uint8_t crc, uint8_t data)
{
  const uint16_t polynomial = 0x107;
  crc ^= data;
  for (uint8_t i = 8; i; --i) {
    if (crc & 0x80)
      crc = (uint16_t(crc) << 1) ^ polynomial;
    else
      crc <<= 1;
  }

  return crc;
}


SoftWire::SoftWire(uint8_t sda, uint8_t scl) :
  _sda(sda),
  _scl(scl),
  _inputMode(INPUT_PULLUP), // Pullups disabled by default
  _timeout_ms(defaultTimeout_ms),
  _transmissionInProgress(false)
{
  // Calcula e cacheia registradores e máscaras do SDA (leitura única!)
  uint8_t sdaPort = digitalPinToPort(sda);
  _sdaMask = digitalPinToBitMask(sda);
  _sdaOut = portOutputRegister(sdaPort);
  _sdaDdr = portModeRegister(sdaPort);
  _sdaIn = portInputRegister(sdaPort);
  
  // Calcula e cacheia registradores e máscaras do SCL (leitura única!)
  uint8_t sclPort = digitalPinToPort(scl);
  _sclMask = digitalPinToBitMask(scl);
  _sclOut = portOutputRegister(sclPort);
  _sclDdr = portModeRegister(sclPort);
  _sclIn = portInputRegister(sclPort);
}


void SoftWire::begin(void) const
{
  /*
    // Release SDA and SCL
    SoftWire::sdaHigh(this);
    delayMicroseconds(_delay_us);
    SoftWire::sclHigh(this);
  */
  stop();
}


SoftWire::result_t SoftWire::stop(bool allowClockStretch) const
{
  AsyncDelay timeout(_timeout_ms, AsyncDelay::MILLIS);
  _transmissionInProgress = false;

  // Force SCL low
  SoftWire::sclLow(this);
  _delay_us(DELAY_TIME_US);

  // Force SDA low
  SoftWire::sdaLow(this);
  _delay_us(DELAY_TIME_US);

  // Release SCL
  if (allowClockStretch) {
    if (!sclHighAndStretch(timeout))
      return timedOut;
  } else {
    sclHigh();
  }
  _delay_us(DELAY_TIME_US);

  // Release SDA
  SoftWire::sdaHigh(this);
  _delay_us(DELAY_TIME_US);

  return ack;
}


SoftWire::result_t SoftWire::llStart(uint8_t rawAddr) const
{

  // Force SDA low
  SoftWire::sdaLow(this);
  _delay_us(DELAY_TIME_US);

  // Force SCL low
  SoftWire::sclLow(this);
  _delay_us(DELAY_TIME_US);
  return llWrite(rawAddr);
}


SoftWire::result_t SoftWire::llRepeatedStart(uint8_t rawAddr) const
{
  AsyncDelay timeout(_timeout_ms, AsyncDelay::MILLIS);

  // Force SCL low
  SoftWire::sclLow(this);
  _delay_us(DELAY_TIME_US);

  // Release SDA
  SoftWire::sdaHigh(this);
  _delay_us(DELAY_TIME_US);

  // Release SCL
  if (!sclHighAndStretch(timeout))
    return timedOut;
  _delay_us(DELAY_TIME_US);

  // Force SDA low
  SoftWire::sdaLow(this);
  _delay_us(DELAY_TIME_US);

  return llWrite(rawAddr);
}


SoftWire::result_t SoftWire::llStartWait(uint8_t rawAddr) const
{
  AsyncDelay timeout(_timeout_ms, AsyncDelay::MILLIS);

  while (!timeout.isExpired()) {
    // Force SDA low
    SoftWire::sdaLow(this);
    _delay_us(DELAY_TIME_US);

    switch (llWrite(rawAddr)) {
      case ack:
        return ack;
      case nack:
        stop();
        return nack;
      default:
        // timeout, and anything else we don't know about
        stop();
        return timedOut;
    }
  }
  return timedOut;
}


SoftWire::result_t SoftWire::llWrite(uint8_t data) const
{
  AsyncDelay timeout(_timeout_ms, AsyncDelay::MILLIS);
  for (uint8_t i = 8; i; --i) {
    // Force SCL low
    SoftWire::sclLow(this);

    if (data & 0x80) {
      // Release SDA
      SoftWire::sdaHigh(this);
    }
    else {
      // Force SDA low
      SoftWire::sdaLow(this);
    }
    _delay_us(DELAY_TIME_US);

    // Release SCL
    if (!sclHighAndStretch(timeout))
      return timedOut;

    _delay_us(DELAY_TIME_US);

    data <<= 1;
    if (timeout.isExpired()) {
      stop(); // Reset bus
      return timedOut;
    }
  }

  // Get ACK
  // Force SCL low
  SoftWire::sclLow(this);

  // Release SDA
  SoftWire::sdaHigh(this);

  _delay_us(DELAY_TIME_US);

  // Release SCL
  if (!sclHighAndStretch(timeout))
    return timedOut;

  result_t res = (SoftWire::readSda(this) == LOW ? ack : nack);

  _delay_us(DELAY_TIME_US);

  // Keep SCL low between bytes
  SoftWire::sclLow(this);

  return res;
}


SoftWire::result_t SoftWire::llRead(uint8_t &data, bool sendAck) const
{
  data = 0;
  AsyncDelay timeout(_timeout_ms, AsyncDelay::MILLIS);

  for (uint8_t i = 8; i; --i) {
    data <<= 1;

    // Force SCL low
    SoftWire::sclLow(this);

    // Release SDA (from previous ACK)
    SoftWire::sdaHigh(this);
    _delay_us(DELAY_TIME_US);

    // Release SCL
    if (!sclHighAndStretch(timeout))
      return timedOut;
    _delay_us(DELAY_TIME_US);

    // Read clock stretch
    while (SoftWire::readScl(this) == LOW)
      if (timeout.isExpired()) {
        stop(); // Reset bus
        return timedOut;
      }

    if (SoftWire::readSda(this))
      data |= 1;
  }

  // Put ACK/NACK
  // Force SCL low
  SoftWire::sclLow(this);
  if (sendAck) {
    // Force SDA low
    SoftWire::sdaLow(this);
  }
  else {
    // Release SDA
    SoftWire::sdaHigh(this);
  }

  _delay_us(DELAY_TIME_US);

  // Release SCL
  if (!sclHighAndStretch(timeout))
    return timedOut;
  _delay_us(DELAY_TIME_US);

  // Wait for SCL to return high
  while (SoftWire::readScl(this) == LOW)
    if (timeout.isExpired()) {
      stop(); // Reset bus
      return timedOut;
    }

  _delay_us(DELAY_TIME_US);

  // Keep SCL low between bytes
  SoftWire::sclLow(this);

  return ack;
}


int SoftWire::available(void)
{
  return _rxBufferBytesRead - _rxBufferIndex;
}


size_t SoftWire::write(uint8_t data)
{
  if (_txBufferIndex >= _txBufferSize) {
    setWriteError();
    return 0;
  }

  _txBuffer[_txBufferIndex++] = data;
  return 1;
}


// Unlike the Wire version this function returns the actual amount of data written into the buffer
size_t SoftWire::write(const uint8_t *data, size_t quantity)
{
  size_t r = 0;
  for (size_t i = 0; i < quantity; ++i) {
    r += write(data[i]);
  }
  return r;
}


int SoftWire::read(void)
{
  if (_rxBufferIndex < _rxBufferBytesRead)
    return _rxBuffer[_rxBufferIndex++];
  else
    return -1;
}


int SoftWire::peek(void)
{
  if (_rxBufferIndex < _rxBufferBytesRead)
    return _rxBuffer[_rxBufferIndex];
  else
    return -1;
}


// Restore pins to inputs, with no pullups
void SoftWire::end(void)
{
  enablePullups(false);
  SoftWire::sdaHigh(this);
  SoftWire::sclHigh(this);
}


void SoftWire::setClock(uint32_t frequency)
{
  // Limita frequência máxima a 400kHz
  // Nota: delay é fixo em DELAY_TIME_US (2us para 400kHz)
  // Esta função mantida apenas para compatibilidade com Wire
  if (frequency > 400000UL)
    frequency = 400000UL;
}


void SoftWire::beginTransmission(uint8_t address)
{
  _txAddress = address;
  _txBufferIndex = 0;
}


uint8_t SoftWire::endTransmission(uint8_t sendStop)
{
  uint8_t r = endTransmissionInner();
  if (sendStop)
    stop();
  else
    _transmissionInProgress = true;
  return r;
}


uint8_t SoftWire::endTransmissionInner(void) const
{
  result_t r;
  if (_transmissionInProgress) {
    r = repeatedStart(_txAddress, writeMode);
  } else {
    r = start(_txAddress, writeMode);
  }
  if (r == nack)
    return 2;
  else if (r == timedOut)
    return 4;

  for (uint8_t i = 0; i < _txBufferIndex; ++i) {
    r = llWrite(_txBuffer[i]);
    if (r == nack)
      return 3;
    else if (r == timedOut)
      return 4;
  }

  return 0;
}


uint8_t SoftWire::requestFrom(uint8_t address, uint8_t quantity, uint8_t sendStop)
{
  result_t r;
  _rxBufferIndex = 0;
  _rxBufferBytesRead = 0;

  if (_transmissionInProgress) {
    r = repeatedStart(address, readMode);
  } else {
    r = start(address, readMode);
  }

  if (r == ack) {
    for (uint8_t i = 0; i < quantity; ++i) {
      if (i >= _rxBufferSize)
        break; // Don't write beyond buffer
      result_t res = llRead(_rxBuffer[i], i != (quantity - 1));
      if (res != ack)
        break;

      ++_rxBufferBytesRead;
    }
  }

  if (sendStop) {
    stop();
  } else {
    _transmissionInProgress = true;
  }

  return _rxBufferBytesRead;
}

