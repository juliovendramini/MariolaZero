#ifndef SOFTWIRE_H
#define SOFTWIRE_H

#define SOFTWIRE_VERSION "2.0.9"
#define DELAY_TIME_US 1  // Delay padrão para 400kHz (2.5us mínimo, usando 2us)

#include <Arduino.h>
#include <stdint.h>
#include "AsyncDelay.h"


class SoftWire : public Stream {
  public:
    enum result_t {
      ack = 0,
      nack = 1,
      timedOut = 2,
    };

    enum mode_t {
      writeMode = 0,
      readMode = 1,
    };

    static const uint8_t defaultDelay_us = 2;  // Otimizado para 400kHz (m\u00e1ximo suportado)
    static const uint16_t defaultTimeout_ms = 100;

    static void sdaLow(const SoftWire *p);
    static void sdaHigh(const SoftWire *p);
    static void sclLow(const SoftWire *p);
    static void sclHigh(const SoftWire *p);
    static uint8_t readSda(const SoftWire *p);
    static uint8_t readScl(const SoftWire *p);

    // SMBus uses CRC-8 for its PEC
    static uint8_t crc8_update(uint8_t crc, uint8_t data);

    SoftWire(uint8_t sda, uint8_t scl);
    inline uint8_t getSda(void) const;
    inline uint8_t getScl(void) const;
    inline uint8_t getDelay_us(void) const;
    inline uint16_t getTimeout_ms(void) const;
    inline uint8_t getInputMode(void) const;

    // begin() must be called after any changes are made to SDA and/or
    // SCL pins.
    inline void setSda(uint8_t sda);
    inline void setScl(uint8_t scl);
    inline void enablePullups(bool enablePullups = true);

    inline void setTimeout_ms(uint16_t timeout_ms);

    // begin() must be called before use, and after any changes are made
    // to the SDA and/or SCL pins.
    void begin(void) const;
    void end(void); // Restore pins to inputs

    // Functions which take raw addresses (ie address passed must
    // already indicate read/write mode)
    result_t llStart(uint8_t rawAddr) const;
    result_t llRepeatedStart(uint8_t rawAddr) const;
    result_t llStartWait(uint8_t rawAddr) const;

    result_t stop(bool allowClockStretch = true) const;

    inline result_t startRead(uint8_t addr) const;
    inline result_t startWrite(uint8_t addr) const;
    inline result_t repeatedStartRead(uint8_t addr) const;
    inline result_t repeatedStartWrite(uint8_t addr) const;
    inline result_t startReadWait(uint8_t addr) const;
    inline result_t startWriteWait(uint8_t addr) const;

    inline result_t start(uint8_t addr, mode_t rwMode) const;
    inline result_t repeatedStart(uint8_t addr, mode_t rwMode) const;
    inline result_t startWait(uint8_t addr, mode_t rwMode) const;

    result_t llWrite(uint8_t data) const;
    result_t llRead(uint8_t &data, bool sendAck = true) const;
    inline result_t readThenAck(uint8_t &data) const;
    inline result_t readThenNack(uint8_t &data) const;

    inline void sdaLow(void) const;
    inline void sdaHigh(void) const;
    inline void sclLow(void) const;
    inline void sclHigh(void) const;
    inline bool sclHighAndStretch(AsyncDelay& timeout) const;

    // Wrapper functions to provide direct compatibility with the Wire library (TwoWire class)
    virtual int available(void);
    virtual size_t write(uint8_t data);
    virtual size_t write(const uint8_t *data, size_t quantity);
    virtual int read(void);
    virtual int peek(void);
    inline virtual void flush (void) {
      // TODO: (to be implemented in Wire)
    }

    void setClock(uint32_t frequency); // Approximate frequency in Hz
    void beginTransmission(uint8_t address);
    inline void beginTransmission(int address) {
      beginTransmission((uint8_t)address);
    }

    uint8_t endTransmission(uint8_t);
    uint8_t endTransmission(void) {
      return endTransmission(true);
    }


    uint8_t requestFrom(uint8_t address, uint8_t quantity, uint8_t sendStop = true);
    // inline uint8_t requestFrom(int address, int quantity) {
    //     return requestFrom((uint8_t)address, (uint8_t)quantity, (uint8_t)true);
    // }

  private:
    uint8_t _sda;
    uint8_t _scl;
    uint8_t _inputMode;
    uint16_t _timeout_ms;

    // Cache de registradores e máscaras para otimização (calculados uma vez no construtor)
    volatile uint8_t *_sdaOut;   // Ponteiro para PORTx do SDA
    volatile uint8_t *_sdaDdr;   // Ponteiro para DDRx do SDA
    volatile uint8_t *_sdaIn;    // Ponteiro para PINx do SDA
    uint8_t _sdaMask;            // Máscara de bit do SDA
    
    volatile uint8_t *_sclOut;   // Ponteiro para PORTx do SCL
    volatile uint8_t *_sclDdr;   // Ponteiro para DDRx do SCL
    volatile uint8_t *_sclIn;    // Ponteiro para PINx do SCL
    uint8_t _sclMask;            // Máscara de bit do SCL

    // Additional member variables to support compatibility with Wire library
    // Static para economizar RAM - todas as instâncias compartilham os mesmos buffers
    static uint8_t _rxBuffer[32];    // era 128: nenhum sensor lê mais que 30 de uma vez
    static const uint8_t _rxBufferSize = 32;
    static uint8_t _rxBufferIndex;
    static uint8_t _rxBufferBytesRead;

    static uint8_t _txAddress; // The address where data is to be sent to
    static uint8_t _txBuffer[32]; // Address of user-supplied buffer
    static const uint8_t _txBufferSize = 32; // Size of user-supplied buffer
    static uint8_t _txBufferIndex; // Index into buffer
    mutable bool _transmissionInProgress;


    uint8_t endTransmissionInner(void) const;
};


uint8_t SoftWire::getSda(void) const
{
  return _sda;
}


uint8_t SoftWire::getScl(void) const
{
  return _scl;
}


uint8_t SoftWire::getDelay_us(void) const
{
  return DELAY_TIME_US;
}


uint16_t SoftWire::getTimeout_ms(void) const
{
  return _timeout_ms;
}


uint8_t SoftWire::getInputMode(void) const
{
  return _inputMode;
}


void SoftWire::setSda(uint8_t sda)
{
  _sda = sda;
}


void SoftWire::setScl(uint8_t scl)
{
  _scl = scl;
}


void SoftWire::enablePullups(bool enable)
{
  _inputMode = (enable ? INPUT_PULLUP : INPUT);
}


void SoftWire::setTimeout_ms(uint16_t timeout_ms)
{
  _timeout_ms = timeout_ms;
}


SoftWire::result_t SoftWire::startRead(uint8_t addr) const
{
  return llStart((addr << 1) + readMode);
}


SoftWire::result_t SoftWire::startWrite(uint8_t addr) const
{
  return llStart((addr << 1) + writeMode);
}


SoftWire::result_t SoftWire::repeatedStartRead(uint8_t addr) const
{
  return llRepeatedStart((addr << 1) + readMode);
}


SoftWire::result_t SoftWire::repeatedStartWrite(uint8_t addr) const
{
  return llRepeatedStart((addr << 1) + writeMode);
}


SoftWire::result_t SoftWire::startReadWait(uint8_t addr) const
{
  return llStartWait((addr << 1) + readMode);
}


SoftWire::result_t SoftWire::startWriteWait(uint8_t addr) const
{
  return llStartWait((addr << 1) + writeMode);
}


SoftWire::result_t SoftWire::start(uint8_t addr, mode_t rwMode) const
{
  return llStart((addr << 1) + rwMode);
}


SoftWire::result_t SoftWire::repeatedStart(uint8_t addr, mode_t rwMode) const
{
  return llRepeatedStart((addr << 1) + rwMode);
}


SoftWire::result_t SoftWire::startWait(uint8_t addr, mode_t rwMode) const
{
  return llStartWait((addr << 1) + rwMode);
}


SoftWire::result_t SoftWire::readThenAck(uint8_t &data) const
{
  return llRead(data, true);
}


SoftWire::result_t SoftWire::readThenNack(uint8_t &data) const
{
  return llRead(data, false);
}


void SoftWire::sdaLow(void) const
{
  SoftWire::sdaLow(this);
}


void SoftWire::sdaHigh(void) const
{
  SoftWire::sdaHigh(this);
}


void SoftWire::sclLow(void) const
{
  SoftWire::sclLow(this);
}


void SoftWire::sclHigh(void) const
{
  SoftWire::sclHigh(this);
}


bool SoftWire::sclHighAndStretch(AsyncDelay& timeout) const
{
  SoftWire::sclHigh(this);

  // Wait for SCL to actually become high in case the slave keeps
  // it low (clock stretching).
  while (SoftWire::readScl(this) == LOW)
    if (timeout.isExpired()) {
      stop(false); // Reset bus. Do not allow clock stretching here
      return false;
    }

  return true;
}

#endif
