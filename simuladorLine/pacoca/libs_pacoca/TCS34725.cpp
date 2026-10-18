#include <avr/pgmspace.h>
#include <math.h>
#include <stdlib.h>
#include "TCS34725.h"
#include "portas.h"
/*!
 *  @brief  Implements missing powf function
 *  @param  x
 *          Base number
 *  @param  y
 *          Exponent
 *  @return x raised to the power of y
 */
float powf(const float x, const float y) {
  return (float)(pow((double)x, (double)y));
}

/*!
 *  @brief  Constructor
 *  @param  it
 *          Integration Time
 *  @param  gain
 *          Gain
 */
TCS34725::TCS34725(PortaI2C porta, uint8_t it, tcs34725Gain_t gain) {
  _tcs34725Initialised = false;
  _tcs34725IntegrationTime = it;
  _tcs34725Gain = gain;
  this->sda = porta.sda;
  this->scl = porta.scl;
  strcpy(this->descricaoPorta, porta.descricao);
  
  // Extrai número da porta da descrição (ex: "I2C-1" -> 1)
  if (porta.descricao[4] >= '1' && porta.descricao[4] <= '5') {
    this->numeroPorta = porta.descricao[4] - '0';
  } else {
    this->numeroPorta = 0;  // Porta inválida
  }
}



/*!
 *  @brief  Writes a register and an 8 bit value over I2C
 *  @param  reg
 *  @param  value
 */
void TCS34725::write8(uint8_t reg, uint8_t value) {
  uint8_t buffer[2] = {(uint8_t)(TCS34725_COMMAND_BIT | reg), value};
  bus->beginTransmission(TCS34725_ADDRESS);
  bus->write(buffer, 2);
  last_status = bus->endTransmission();
}

/*!
 *  @brief  Reads an 8 bit value over I2C
 *  @param  reg
 *  @return value
 */
uint8_t TCS34725::read8(uint8_t reg) {
  uint8_t buffer[1] = {(uint8_t)(TCS34725_COMMAND_BIT | reg)};
  bus->beginTransmission(TCS34725_ADDRESS);
  bus->write(buffer[0]);
  last_status = bus->endTransmission();
  bus->requestFrom(TCS34725_ADDRESS, (uint8_t)1);
  buffer[0] = bus->read();
  return buffer[0];
}

/*!
 *  @brief  Reads a 16 bit values over I2C
 *  @param  reg
 *  @return value
 */
uint16_t TCS34725::read16(uint8_t reg) {
  uint8_t buffer[2] = {(uint8_t)(TCS34725_COMMAND_BIT | reg), 0};
  uint16_t value ;
  
  bus->beginTransmission(TCS34725_ADDRESS);
  bus->write(buffer[0]);
  last_status = bus->endTransmission();
  bus->requestFrom(TCS34725_ADDRESS, (uint8_t)2);
  buffer[0]  = bus->read(); // value high byte
  buffer[1]  = bus->read();      // value low byte
  //return buffer[0] << 8 | buffer[1];
  return (uint16_t(buffer[1]) << 8) | (uint16_t(buffer[0]) & 0xFF);
}

void TCS34725::enablePON() {
  write8(TCS34725_ENABLE, TCS34725_ENABLE_PON);
}

void TCS34725::enablePON_AEN() {
  write8(TCS34725_ENABLE, TCS34725_ENABLE_PON | TCS34725_ENABLE_AEN);
}

void TCS34725::ledOff() {
  pinMode(this->sda, OUTPUT);
  digitalWrite(this->sda, LOW); //desliga o led
}

/*!
 *  @brief  Enables the device
 */
void TCS34725::enable(bool wait) {
  enablePON();
  delay(3);
  enablePON_AEN();
  /* Set a delay for the integration time.
    This is only necessary in the case where enabling and then
    immediately trying to read values back. This is because setting
    AEN triggers an automatic integration, so if a read RGBC is
    performed too quickly, the data is not yet valid and all 0's are
    returned */
  /* 12/5 = 2.4, add 1 to account for integer truncation */
  if (wait) {
    delay((256 - _tcs34725IntegrationTime) * 12 / 5 + 2);
  }
  //delay(4);
}


void TCS34725::enableLedOff(bool wait) {
  enablePON();
  delay(3);
  enablePON_AEN();
  ledOff();
  /* Set a delay for the integration time.
    This is only necessary in the case where enabling and then
    immediately trying to read values back. This is because setting
    AEN triggers an automatic integration, so if a read RGBC is
    performed too quickly, the data is not yet valid and all 0's are
    returned */
  /* 12/5 = 2.4, add 1 to account for integer truncation */
  if (wait) {
    delay((256 - _tcs34725IntegrationTime) * 12 / 5 + 2);
  }
  //delay(4);
}

/*!
 *  @brief  Disables the device (putting it in lower power sleep mode)
 */
void TCS34725::disable() {
  /* Turn the device off to save power */
  uint8_t reg = 0;
  reg = read8(TCS34725_ENABLE);
  write8(TCS34725_ENABLE, reg & ~(TCS34725_ENABLE_PON | TCS34725_ENABLE_AEN));
}



/*!
 *  @brief  Initializes I2C and configures the sensor
 *  @param  addr
 *          i2c address
 *  @param  *theWire
 *          The Wire object
 *  @return True if initialization was successful, otherwise false.
 */
// boolean TCS34725::begin(uint8_t addr, uint8_t sda, uint8_t scl) {
//   this->sda = sda;

//   this->scl = scl;
//   bus = new SoftWire(sda, scl); //pinos SDA e SCL escolhidos
//   //return init();
//   return true;
// }

boolean TCS34725::begin() {
  bus = new SoftWire(sda, scl); //pinos SDA e SCL escolhidos
  //return true;
  return init();

}

/*!
 *  @brief  Part of begin
 *  @return True if initialization was successful, otherwise false.
 */
boolean TCS34725::init() {
  bus->setTimeout_ms(10);
  bus->begin();
  bus->setTimeout_ms(10);
  /* Make sure we're actually connected */
  uint8_t x = read8(TCS34725_ID);
  if ((x != 0x4d) && (x != 0x44) && (x != 0x10)) {
    delay(3);
    x = read8(TCS34725_ID); //faço duas tentativas para ler o id
    if ((x != 0x4d) && (x != 0x44) && (x != 0x10)) {
      Serial.print(F("Erro ao detectar o TCS34725 na porta "));
      Serial.println(this->descricaoPorta);
      while(1);
    }
  }
  
  
  _tcs34725Initialised = true;
  
  /* Set default integration time and gain */
  setIntegrationTime(_tcs34725IntegrationTime);
  setGain(_tcs34725Gain);
  
  /* Note: by default, the device is in power down mode on bootup */
  enable();
  Serial.print(F("TCS34725 detectado com sucesso na porta "));
  Serial.println(this->descricaoPorta);
  if(this->carregarCalibracao()) { //carrega calibração padrão
    Serial.println(F("Calibração carregada da EEPROM."));
  } else {
    dadosCalibracao.r = 512;
    dadosCalibracao.g = 512;
    dadosCalibracao.b = 512;
    dadosCalibracao.c = 1024;
    Serial.println(F("Nenhuma calibração válida encontrada na EEPROM, usando calibração padrao sensor."));
    return true;
  }
}

/*!
 *  @brief  Sets the integration time for the TC34725
 *  @param  it
 *          Integration Time
 */
void TCS34725::setIntegrationTime(uint8_t it) {
  /* Update the timing register */
  write8(TCS34725_ATIME, it);

  /* Update value placeholders */
  _tcs34725IntegrationTime = it;
}

/*!
 *  @brief  Adjusts the gain on the TCS34725
 *  @param  gain
 *          Gain (sensitivity to light)
 */
void TCS34725::setGain(tcs34725Gain_t gain) {
  /* Update the timing register */
  write8(TCS34725_CONTROL, gain);

  /* Update value placeholders */
  _tcs34725Gain = gain;
}

/*!
 *  @brief  Reads the raw red, green, blue and clear channel values
 *  @param  *r
 *          Red value
 *  @param  *g
 *          Green value
 *  @param  *b
 *          Blue value
 *  @param  *c
 *          Clear channel value
 */
void TCS34725::getRawData() {
  uint8_t buffer[8]; // 8 bytes: C_low, C_high, R_low, R_high, G_low, G_high, B_low, B_high
  // Envia comando para ler a partir do registrador CDATAL (0x14)
  bus->beginTransmission(TCS34725_ADDRESS);
  bus->write(TCS34725_COMMAND_BIT | TCS34725_CDATAL);
  last_status = bus->endTransmission();
  // Solicita 8 bytes consecutivos (auto-incremento ativado)
  bus->requestFrom(TCS34725_ADDRESS, (uint8_t)8);
  // Lê todos os 8 bytes de uma vez
  for (uint8_t i = 0; i < 8; i++) {
    buffer[i] = bus->read();
  }
  // Monta os valores uint16_t (little-endian: low byte primeiro)
  this->c = (uint16_t(buffer[1]) << 8) | uint16_t(buffer[0]);
  this->r = (uint16_t(buffer[3]) << 8) | uint16_t(buffer[2]);
  this->g = (uint16_t(buffer[5]) << 8) | uint16_t(buffer[4]);
  this->b = (uint16_t(buffer[7]) << 8) | uint16_t(buffer[6]);
  this->ultimaAtualizacao = millis();
  //o delay é pelo codigo e nao aqui
  /* Set a delay for the integration time */
  /* 12/5 = 2.4, add 1 to account for integer truncation */
  //delay((256 - _tcs34725IntegrationTime) * 12 / 5 + 1);
}

/*!
 *  @brief  Reads the raw red, green, blue and clear channel values in
 *          one-shot mode (e.g., wakes from sleep, takes measurement, enters
 *          sleep)
 *  @param  *r
 *          Red value
 *  @param  *g
 *          Green value
 *  @param  *b
 *          Blue value
 *  @param  *c
 *          Clear channel value
 */
void TCS34725::getRawDataOneShot() {
  enable();
  getRawData();
  disable();
}


void TCS34725::getRawDataOneShotOff() {
  enableLedOff();
  getRawData();
  disable();
}  


void TCS34725::getRawDataWithoutInterference() {
  uint16_t red1, green1, blue1, clear1;
  uint16_t red2, green2, blue2, clear2;      
  enable();                                      
  getRawData();
  red1 = this->r;
  green1 = this->g;
  blue1 = this->b;
  clear1 = this->c;
  disable();
  //delay(3);
  enableLedOff();
  getRawData();
  red2 = this->r;
  green2 = this->g;
  blue2 = this->b;
  clear2 = this->c;
  disable();
  //se o led nao estiver desativando, vai dar problema. Então tenho que tratar isso
  this->r = red1 - red2;
  if(this->r > 64000) this->r = 0;
  this->g = green1 - green2;
  if(this->g > 64000) this->g = 0;
  this->b = blue1 - blue2;
  if(this->b > 64000) this->b = 0;
  this->c = clear1 - clear2;
  if(this->c > 64000) this->c = 0;
}

void TCS34725::setRGBCCalibrado(uint16_t red1, uint16_t green1, uint16_t blue1, uint16_t clear1) {
  //se o led nao estiver desativando, vai dar problema. Então tenho que tratar isso
  this->r = red1 - this->r;
  if(this->r > 64000) this->r = 0;
  this->g = green1 - this->g;
  if(this->g > 64000) this->g = 0;
  this->b = blue1 - this->b;
  if(this->b > 64000) this->b = 0;
  this->c = clear1 - this->c;
  if(this->c > 64000) this->c = 0;
  // Aplica calibração
  this->r = (uint32_t)this->r * 255 / dadosCalibracao.r;
  this->g = (uint32_t)this->g * 255 / dadosCalibracao.g;
  this->b = (uint32_t)this->b * 255 / dadosCalibracao.b;
  this->c = (uint32_t)this->c * 255 / dadosCalibracao.c;
  if(this->r > 255) this->r = 255;
  if(this->g > 255) this->g = 255;
  if(this->b > 255) this->b = 255;
  if(this->c > 255) this->c = 255;
}  

void TCS34725::getRGBCCalibrado() {
  uint16_t redRaw, greenRaw, blueRaw, clearRaw;
  getRawDataWithoutInterference();
  redRaw = this->r;
  greenRaw = this->g;
  blueRaw = this->b;
  clearRaw = this->c;
  
  if(this->r > 64000) this->r = 0;
  if(this->g > 64000) this->g = 0;
  if(this->b > 64000) this->b = 0;
  if(this->c > 64000) this->c = 0;
  // Aplica calibração
  this->r = (uint32_t)redRaw * 255 / dadosCalibracao.r;
  this->g = (uint32_t)greenRaw * 255 / dadosCalibracao.g;
  this->b = (uint32_t)blueRaw * 255 / dadosCalibracao.b;
  this->c = (uint32_t)clearRaw * 255 / dadosCalibracao.c;
  if(this->r > 255) this->r = 255;
  if(this->g > 255) this->g = 255;
  if(this->b > 255) this->b = 255;
  if(this->c > 255) this->c = 255;
}

/*!
 *  @brief  Retorna o valor vermelho (red)
 *  @return Valor red
 */
uint16_t TCS34725::getR() {
  if (millis() - ultimaAtualizacao > TEMPO_ATUALIZACAO_SENSOR) {
    getRGBCCalibrado();
  }
  return this->r;
}

/*!
 *  @brief  Retorna o valor verde (green)
 *  @return Valor green
 */
uint16_t TCS34725::getG() {
  if (millis() - ultimaAtualizacao > TEMPO_ATUALIZACAO_SENSOR) {
    getRGBCCalibrado();
  }
  return this->g;
}

/*!
 *  @brief  Retorna o valor azul (blue)
 *  @return Valor blue
 */
uint16_t TCS34725::getB() {
  if (millis() - ultimaAtualizacao > TEMPO_ATUALIZACAO_SENSOR) {
    getRGBCCalibrado();
  }
  return this->b;
}

/*!
 *  @brief  Retorna o valor clear
 *  @return Valor clear
 */
uint16_t TCS34725::getC() {
  if (millis() - ultimaAtualizacao > TEMPO_ATUALIZACAO_SENSOR) {
    getRGBCCalibrado();
  }
  return this->c;
}

/*!
 *  @brief  Retorna os valores RGBC através de parâmetros de referência
 *  @param  red
 *          Referência para armazenar o valor vermelho
 *  @param  green
 *          Referência para armazenar o valor verde
 *  @param  blue
 *          Referência para armazenar o valor azul
 *  @param  clear
 *          Referência para armazenar o valor clear
 */
void TCS34725::getRGBC(uint16_t &red, uint16_t &green, uint16_t &blue, uint16_t &clear) {
  if (millis() - ultimaAtualizacao > TEMPO_ATUALIZACAO_SENSOR) {
    getRGBCCalibrado();
  }
  red = this->r;
  green = this->g;
  blue = this->b;
  clear = this->c;
}

/*!
 *  @brief  Atualiza o timestamp da última atualização
 */
void TCS34725::dadosAtualizados() {
  ultimaAtualizacao = millis();
}

/*!
 *  @brief  Retorna o número da porta I2C (1-5)
 *  @return Número da porta
 */
uint8_t TCS34725::getNumeroPorta() {
  return numeroPorta;
}


// Detecta uma cor básica (preto, branco, vermelho, verde, azul ou amarelo)
TCS34725::CorBasica TCS34725::detectaCorBasica() {
  // Usa as funções de alto nível para garantir atualização/calibração automática
  uint16_t r = getR();
  uint16_t g = getG();
  uint16_t b = getB();
  uint16_t c = getC();

  // Verifica se os valores são muito baixos (sem cor detectada)
  if (c <= 3 && r < 5 && g < 5 && b < 5) {
    return COR_NADA;
  }

  // Trata casos muito escuros e muito claros primeiro
  if (c > 3 && c < 25) {
    return COR_PRETO;
  }

  if (c > 230 && abs((int)r - (int)g) < 20 && abs((int)r - (int)b) < 20 && abs((int)g - (int)b) < 20) {
    return COR_BRANCO;
  }

  // Normaliza em relação ao maior canal para comparar proporcionalmente
  uint16_t maxVal = r;
  if (g > maxVal) maxVal = g;
  if (b > maxVal) maxVal = b;

  if (maxVal == 0) {
    return COR_NADA;
  }

  // Comparações proporcionais com inteiros (g/max > 0,6 e b/max < 0,5),
  // sem float: o float sozinho custava ~600 bytes de flash.

  // Heurísticas simples para distinguir cores básicas
  // Vermelho ou amarelo (vermelho dominante)
  if (r == maxVal) {
    // Se verde também é forte, tende a amarelo; senão é vermelho
    if ((uint32_t)g * 10 > (uint32_t)maxVal * 6 && (uint32_t)b * 2 < maxVal) {
      return COR_AMARELO;
    }
    return COR_VERMELHO;
  }

  // Verde dominante
  if (g == maxVal) {
    // Se azul também alto, pode tender a ciano, mas aqui tratamos só como verde
    return COR_VERDE;
  }

  // Azul dominante
  if (b == maxVal) {
    return COR_AZUL;
  }

  // Caso não encaixe bem em nenhuma regra, decide por branco/preto com base em C
  if (c > 150) {
    return COR_BRANCO;
  }

  return COR_DESCONHECIDA;
}

// Retorna true se a cor detectada for igual à cor passada como parâmetro
bool TCS34725::ehCor(TCS34725::CorBasica cor) {
  return detectaCorBasica() == cor;
}

/*!
 *  @brief  Calibra o sensor e salva os valores na EEPROM
 *          Endereço base: 100 + (numeroPorta - 1) * sizeof(DadosCalibracao)
 *          Exemplo: Porta 1 = endereço 100, Porta 2 = endereço 109, etc.
 */
void TCS34725::calibrar() {
  if (!_tcs34725Initialised) {
    Serial.println(F("Sensor não inicializado. Não é possível calibrar."));
    return;  // Sensor não inicializado
  }
  
  DadosCalibracao dados;
  
  // Lê valores atuais do sensor
  //getRawData(&dados.r, &dados.g, &dados.b, &dados.c);
  getRawDataWithoutInterference();
  dados.r = this->r;
  dados.g = this->g;
  dados.b = this->b;
  dados.c = this->c;
  // Calcula checksum simples (XOR dos bytes)
  dados.checksum = 0;
  uint8_t *ptr = (uint8_t *)&dados;
  for (uint8_t i = 0; i < sizeof(DadosCalibracao) - 1; i++) {
    dados.checksum ^= ptr[i];
  }
  
  // Calcula endereço na EEPROM: 100 + (numeroPorta - 1) * tamanho
  uint16_t enderecoBase = 100 + (numeroPorta - 1) * sizeof(DadosCalibracao);
  
  // Salva na EEPROM
  EEPROM.put(enderecoBase, dados);
  Serial.println(F("Calibração salva na EEPROM."));
}

/*!
 *  @brief  Carrega valores de calibração da EEPROM
 *  @param  dados
 *          Ponteiro para estrutura onde os dados serão carregados
 *  @return true se calibração foi carregada com sucesso (checksum válido)
 */
boolean TCS34725::carregarCalibracao() {
  
  // Calcula endereço na EEPROM
  uint16_t enderecoBase = 100 + (numeroPorta - 1) * sizeof(DadosCalibracao);
  
  // Carrega da EEPROM
  EEPROM.get(enderecoBase, dadosCalibracao);
  
  // Verifica checksum
  uint8_t checksumCalculado = 0;
  uint8_t *ptr = (uint8_t *)&dadosCalibracao;
  for (uint8_t i = 0; i < sizeof(DadosCalibracao) - 1; i++) {
    checksumCalculado ^= ptr[i];
  }
  
  // Retorna true se checksum é válido
  return (checksumCalculado == dadosCalibracao.checksum);
}

void TCS34725::limpaCalibracao(){
  DadosCalibracao dados;
  dados.r = 0;
  dados.g = 0;
  dados.b = 0;
  dados.c = 0;
  dados.checksum = 1;
  // Calcula endereço na EEPROM: 100 + (numeroPorta - 1) * tamanho
  uint16_t enderecoBase = 100 + (numeroPorta - 1) * sizeof(DadosCalibracao);
  // Salva na EEPROM
  EEPROM.put(enderecoBase, dados);
  Serial.println(F("Calibração apagada da EEPROM."));
}

