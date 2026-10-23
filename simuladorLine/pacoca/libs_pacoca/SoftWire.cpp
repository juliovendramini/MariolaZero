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

// 2026-10-23 - sdaLow/sdaHigh/sclLow/sclHigh/readSda/readScl agora são inline no SoftWire.h


// Parte lenta do liberaSclEspera() (SoftWire.h): o SCL não subiu nas leituras rápidas, então o
// escravo está segurando o clock (clock stretching) ou o barramento travou => espera com timeout
bool SoftWire::esperaSclStretch(void) const
{
  AsyncDelay timeout(_timeout_ms, AsyncDelay::MILLIS);
  while (readScl(this) == LOW) {
    if (timeout.isExpired()) {
      stop(false); // Reset bus. Do not allow clock stretching here
      return false;
    }
  }
  return true;
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
  _transmissionInProgress = false;

  // Force SCL low
  SoftWire::sclLow(this);
  _delay_us(DELAY_TIME_US);

  // Force SDA low
  SoftWire::sdaLow(this);
  _delay_us(DELAY_TIME_US);

  // Release SCL
  if (allowClockStretch) {
    if (!liberaSclEspera())
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

  // Force SCL low
  SoftWire::sclLow(this);
  _delay_us(DELAY_TIME_US);

  // Release SDA
  SoftWire::sdaHigh(this);
  _delay_us(DELAY_TIME_US);

  // Release SCL
  if (!liberaSclEspera())
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


// 2026-10-23 - laço de bits do llWrite/llRead: os ponteiros dos registradores e as máscaras ficam em
// variáveis locais (registradores do AVR) durante o byte inteiro. Com as funções que recebem o objeto
// (sclLow(this)...), cada operação de pino relia do objeto os 2 ponteiros e a máscara: a escrita num
// ponteiro volatile obriga o compilador a reler tudo. Mesma sequência de pinos de antes.

// pino em LOW: saída em LOW e depois OUTPUT (nunca empurra o pino para HIGH)
static inline void pinoBaixo(volatile uint8_t *out, volatile uint8_t *ddr, uint8_t m, uint8_t nm)
  __attribute__((always_inline));
static inline void pinoBaixo(volatile uint8_t *out, volatile uint8_t *ddr, uint8_t m, uint8_t nm)
{
  SOFTWIRE_ATOMICO
  {
    *out &= nm;
    *ddr |= m;
  }
}

// pino solto: INPUT e depois o pull-up interno (pull = máscara, ou 0 sem pull-up)
static inline void pinoSolto(volatile uint8_t *out, volatile uint8_t *ddr, uint8_t nm, uint8_t pull)
  __attribute__((always_inline));
static inline void pinoSolto(volatile uint8_t *out, volatile uint8_t *ddr, uint8_t nm, uint8_t pull)
{
  SOFTWIRE_ATOMICO
  {
    *ddr &= nm;
    *out = (*out & nm) | pull;
  }
}

// leituras rápidas do SCL depois de soltar (a parte rápida do liberaSclEspera)
static inline bool sclSubiu(volatile uint8_t *in, uint8_t m) __attribute__((always_inline));
static inline bool sclSubiu(volatile uint8_t *in, uint8_t m)
{
  for (uint8_t i = LEITURAS_RAPIDAS_SCL; i; --i) {
    if (*in & m)
      return true;
  }
  return false;
}

// ponteiros e máscaras do SDA e do SCL em variáveis locais (usado no começo do llWrite/llRead)
#define SOFTWIRE_PINOS_LOCAIS                                                         \
  volatile uint8_t *const sclOut = _sclOut, *const sclDdr = _sclDdr, *const sclIn = _sclIn; \
  volatile uint8_t *const sdaOut = _sdaOut, *const sdaDdr = _sdaDdr, *const sdaIn = _sdaIn; \
  const uint8_t sclM = _sclMask, sclNM = ~_sclMask, sdaM = _sdaMask, sdaNM = ~_sdaMask;    \
  const uint8_t sclPull = (_inputMode == INPUT_PULLUP) ? sclM : 0;                          \
  const uint8_t sdaPull = (_inputMode == INPUT_PULLUP) ? sdaM : 0

SoftWire::result_t SoftWire::llWrite(uint8_t data) const
{
  //2026-10-23 - sem timeout por bit: o timeout (millis) só é criado se houver clock stretching
  SOFTWIRE_PINOS_LOCAIS;

  for (uint8_t i = 8; i; --i) {
    // Force SCL low
    pinoBaixo(sclOut, sclDdr, sclM, sclNM);

    if (data & 0x80) {
      // Release SDA
      pinoSolto(sdaOut, sdaDdr, sdaNM, sdaPull);
    }
    else {
      // Force SDA low
      pinoBaixo(sdaOut, sdaDdr, sdaM, sdaNM);
    }
    _delay_us(DELAY_TIME_US);

    // Release SCL e espera subir (clock stretching: esperaSclStretch, com timeout)
    pinoSolto(sclOut, sclDdr, sclNM, sclPull);
    if (!sclSubiu(sclIn, sclM) && !esperaSclStretch())
      return timedOut;

    _delay_us(DELAY_TIME_US);

    data <<= 1;
  }

  // Get ACK
  // Force SCL low
  pinoBaixo(sclOut, sclDdr, sclM, sclNM);

  // Release SDA
  pinoSolto(sdaOut, sdaDdr, sdaNM, sdaPull);

  _delay_us(DELAY_TIME_US);

  // Release SCL
  pinoSolto(sclOut, sclDdr, sclNM, sclPull);
  if (!sclSubiu(sclIn, sclM) && !esperaSclStretch())
    return timedOut;

  result_t res = ((*sdaIn & sdaM) ? nack : ack);

  _delay_us(DELAY_TIME_US);

  // Keep SCL low between bytes
  pinoBaixo(sclOut, sclDdr, sclM, sclNM);

  return res;
}


SoftWire::result_t SoftWire::llRead(uint8_t &data, bool sendAck) const
{
  SOFTWIRE_PINOS_LOCAIS;
  uint8_t lido = 0;

  // Force SCL low e Release SDA (do ACK anterior). O SDA fica solto nos 8 bits: antes ele era
  // solto de novo a cada bit, sem efeito
  pinoBaixo(sclOut, sclDdr, sclM, sclNM);
  pinoSolto(sdaOut, sdaDdr, sdaNM, sdaPull);

  for (uint8_t i = 8; i; --i) {
    lido <<= 1;
    _delay_us(DELAY_TIME_US);

    // Release SCL e espera subir (inclusive com clock stretching)
    pinoSolto(sclOut, sclDdr, sclNM, sclPull);
    if (!sclSubiu(sclIn, sclM) && !esperaSclStretch()) {
      data = lido;
      return timedOut;
    }
    _delay_us(DELAY_TIME_US);

    if (*sdaIn & sdaM)
      lido |= 1;

    // Force SCL low
    pinoBaixo(sclOut, sclDdr, sclM, sclNM);
  }
  data = lido;

  // Put ACK/NACK (SCL já está em LOW)
  if (sendAck) {
    // Force SDA low
    pinoBaixo(sdaOut, sdaDdr, sdaM, sdaNM);
  }
  else {
    // Release SDA
    pinoSolto(sdaOut, sdaDdr, sdaNM, sdaPull);
  }

  _delay_us(DELAY_TIME_US);

  // Release SCL
  pinoSolto(sclOut, sclDdr, sclNM, sclPull);
  if (!sclSubiu(sclIn, sclM) && !esperaSclStretch())
    return timedOut;
  _delay_us(DELAY_TIME_US);

  // Keep SCL low between bytes
  pinoBaixo(sclOut, sclDdr, sclM, sclNM);

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

