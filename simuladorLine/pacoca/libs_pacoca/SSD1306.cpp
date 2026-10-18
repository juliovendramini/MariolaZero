/*
    Copyright © 2012-2015 Arduino LLC, Limor Fried/Ladyada, Michael Gregg,
    pocketmoon, Neil McNeight

    This file is part of SSD1306.

    SSD1306 is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation, either version 2.1 of the License, or
    (at your option) any later version.

    SSD1306 is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

-------------------------------------------------------------------------------
Change Log

DATE      VER   WHO   WHAT
06/20/15  1.6.0 NEM   Code cleanup and compatibility with Arduino 1.6.*
2026-02-10  - Simplificação por Julio Vendramini
            - Remoção do código que utiliza EEPROM para salvar as letras da fonte
            - Agora aceita apenas o formato 128x64
-------------------------------------------------------------------------------
*/


#include "SSD1306.h"

#include <avr/pgmspace.h>
const uint8_t flash_font[] PROGMEM = {
  // Abbreviated ASCII 5x7 font from
  // SSD1306NoBuffer/SSD1306_NoBuffer/LCD_font_5x7.h
  0x00, 0x00, 0x00, 0x00, 0x00, // " "
  0x00, 0x00, 0x4f, 0x00, 0x00, // !
  0x00, 0x03, 0x00, 0x03, 0x00, // "
  0x14, 0x3e, 0x14, 0x3e, 0x14, // #
  0x24, 0x2a, 0x7f, 0x2a, 0x12, // $
  0x63, 0x13, 0x08, 0x64, 0x63, // %
  0x36, 0x49, 0x55, 0x22, 0x50, // &
  0x00, 0x00, 0x07, 0x00, 0x00, // '
  0x00, 0x1c, 0x22, 0x41, 0x00, // (
  0x00, 0x41, 0x22, 0x1c, 0x00, // )
  0x0a, 0x04, 0x1f, 0x04, 0x0a, // *
  0x04, 0x04, 0x1f, 0x04, 0x04, // +
  0x50, 0x30, 0x00, 0x00, 0x00, // ,
  0x08, 0x08, 0x08, 0x08, 0x08, // -
  0x60, 0x60, 0x00, 0x00, 0x00, // .
  0x00, 0x60, 0x1c, 0x03, 0x00, // /
  0x3e, 0x41, 0x49, 0x41, 0x3e, // 0
  0x00, 0x02, 0x7f, 0x00, 0x00, // 1
  0x46, 0x61, 0x51, 0x49, 0x46, // 2
  0x21, 0x49, 0x4d, 0x4b, 0x31, // 3
  0x18, 0x14, 0x12, 0x7f, 0x10, // 4
  0x4f, 0x49, 0x49, 0x49, 0x31, // 5
  0x3e, 0x51, 0x49, 0x49, 0x32, // 6
  0x01, 0x01, 0x71, 0x0d, 0x03, // 7
  0x36, 0x49, 0x49, 0x49, 0x36, // 8
  0x26, 0x49, 0x49, 0x49, 0x3e, // 9
  0x33, 0x33, 0x00, 0x00, 0x00, // : //alterado para ficar mais a esquerda possível
  0x00, 0x53, 0x33, 0x00, 0x00, // ;
  0x00, 0x08, 0x14, 0x22, 0x41, // <
  0x14, 0x14, 0x14, 0x14, 0x14, // =
  0x41, 0x22, 0x14, 0x08, 0x00, // >
  0x06, 0x01, 0x51, 0x09, 0x06, // ?
  0x3e, 0x41, 0x49, 0x15, 0x1e, // @
  0x78, 0x16, 0x11, 0x16, 0x78, // A
  0x7f, 0x49, 0x49, 0x49, 0x36, // B
  0x3e, 0x41, 0x41, 0x41, 0x22, // C
  0x7f, 0x41, 0x41, 0x41, 0x3e, // D
  0x7f, 0x49, 0x49, 0x49, 0x49, // E
  0x7f, 0x09, 0x09, 0x09, 0x09, // F
  0x3e, 0x41, 0x41, 0x49, 0x7b, // G
  0x7f, 0x08, 0x08, 0x08, 0x7f, // H
  0x00, 0x00, 0x7f, 0x00, 0x00, // I
  0x38, 0x40, 0x40, 0x41, 0x3f, // J
  0x7f, 0x08, 0x08, 0x14, 0x63, // K
  0x7f, 0x40, 0x40, 0x40, 0x40, // L
  0x7f, 0x06, 0x18, 0x06, 0x7f, // M
  0x7f, 0x06, 0x18, 0x60, 0x7f, // N
  0x3e, 0x41, 0x41, 0x41, 0x3e, // O
  0x7f, 0x09, 0x09, 0x09, 0x06, // P
  0x3e, 0x41, 0x51, 0x21, 0x5e, // Q
  0x7f, 0x09, 0x19, 0x29, 0x46, // R
  0x26, 0x49, 0x49, 0x49, 0x32, // S
  0x01, 0x01, 0x7f, 0x01, 0x01, // T
  0x3f, 0x40, 0x40, 0x40, 0x7f, // U
  0x0f, 0x30, 0x40, 0x30, 0x0f, // V
  0x1f, 0x60, 0x1c, 0x60, 0x1f, // W
  0x63, 0x14, 0x08, 0x14, 0x63, // X
  0x03, 0x04, 0x78, 0x04, 0x03, // Y
  0x61, 0x51, 0x49, 0x45, 0x43, // Z
  0x00, 0x7f, 0x41, 0x00, 0x00, // [
  0x03, 0x1c, 0x60, 0x00, 0x00, // / other way around
  0x00, 0x41, 0x7f, 0x00, 0x00, // ]
  0x0c, 0x02, 0x01, 0x02, 0x0c, // ^
  0x40, 0x40, 0x40, 0x40, 0x40, // _
  0x00, 0x01, 0x02, 0x04, 0x00, // `
  0x20, 0x54, 0x54, 0x54, 0x78, // a
  0x7f, 0x48, 0x44, 0x44, 0x38, // b
  0x38, 0x44, 0x44, 0x44, 0x44, // c
  0x38, 0x44, 0x44, 0x48, 0x7f, // d
  0x38, 0x54, 0x54, 0x54, 0x18, // e
  0x08, 0x7e, 0x09, 0x09, 0x00, // f
  0x0c, 0x52, 0x52, 0x54, 0x3e, // g
  0x7f, 0x08, 0x04, 0x04, 0x78, // h
  0x00, 0x00, 0x7d, 0x00, 0x00, // i
  0x00, 0x40, 0x3d, 0x00, 0x00, // j
  0x7f, 0x10, 0x28, 0x44, 0x00, // k
  0x00, 0x00, 0x3f, 0x40, 0x00, // l
  0x7c, 0x04, 0x18, 0x04, 0x78, // m
  0x7c, 0x08, 0x04, 0x04, 0x78, // n
  0x38, 0x44, 0x44, 0x44, 0x38, // o
  0x7f, 0x12, 0x11, 0x11, 0x0e, // p
  0x0e, 0x11, 0x11, 0x12, 0x7f, // q
  0x00, 0x7c, 0x08, 0x04, 0x04, // r
  0x48, 0x54, 0x54, 0x54, 0x24, // s
  0x04, 0x3e, 0x44, 0x44, 0x00, // t
  0x3c, 0x40, 0x40, 0x20, 0x7c, // u
  0x1c, 0x20, 0x40, 0x20, 0x1c, // v
  0x1c, 0x60, 0x18, 0x60, 0x1c, // w
  0x44, 0x28, 0x10, 0x28, 0x44, // x
  0x46, 0x28, 0x10, 0x08, 0x06, // y
  0x44, 0x64, 0x54, 0x4c, 0x44, // z
  0x00, 0x08, 0x77, 0x41, 0x00, // {
  0x00, 0x00, 0x00, 0x00, 0x7f, // | 
  0x00, 0x41, 0x77, 0x08, 0x00, // }
  0x10, 0x08, 0x18, 0x10, 0x08  // ~
};

SSD1306::SSD1306(PortaI2C porta, uint8_t vccstate)
{
  this->sda = porta.sda;
  this->scl = porta.scl;
  strcpy(this->descricaoPorta, porta.descricao);
  this->bus = NULL;
  _vccstate = vccstate;
  _i2caddr  = SSD1306_I2C_ADDRESS;
  _y        = _x = 0;
  _r        = _c = 0;

}

void SSD1306::init()
{
  begin();
}


void SSD1306::begin() //a quantidade de colunas e linhas é definida pelo tamanho da fonte, que é definida por setFontePequena, setFonteMedia ou setFonteGrande
{
  //inicia como fonte pequena, (padrao)
  multiplicadorTamanhoFonte = 1;
  SSD1306_FONT_WIDTH = 5;
  SSD1306_FONT_HEIGHT = 8; 
  _cols = 21;
  _rows = 8;
  bus = new SoftWire(sda, scl);
  bus->setTimeout_ms(10);
  bus->begin();
  bus->setTimeout_ms(10);
  //verifico se a tela existe
	bus->beginTransmission(SSD1306_I2C_ADDRESS);
  byte error = bus->endTransmission();
	if(error){
		Serial.print(F("Erro ao detectar a tela SSD1306 na porta "));
    Serial.println(this->descricaoPorta);
    while(1);
	}
  Serial.print(F("Tela SSD1306 detectada com sucesso na porta "));
  Serial.println(this->descricaoPorta);
  // Software Configuration
  // 1 Set MUX Ratio: A8h, 3Fh
  // 2 Set Display Offset: D3h, 00h
  // 3 Set Display Start Line: 40h
  // 4 Set Segment re-map: A0h/A1h
  // 5 Set COM Output Scan Direction: C0h/C8h
  // 6 Set COM Pins hardware configuration: DAh, 02
  // 7 Set Contrast Control: 81h, 7Fh
  // 8 Disable Entire Display On: A4h
  // 9 Set Normal Display: A6h
  // A Set Osc Frequency: D5h, 80h
  // B Enable charge pump regulator: 8Dh, 14h
  // C Display On: AFh
  // Combined initialization sequence
  noDisplay();                    // 0xAE
  ssd1306_command(SSD1306_MEMORYMODE);                    // 0x20
  ssd1306_command(0x00);                                  // 0x0 act like ks0108
  //ssd1306_command(0x00); // Horizontal Addressing Mode
  //ssd1306_command(0x01); // Vertical Addressing Mode
  //ssd1306_command(0x02); // Page Addressing Mode n10

  // 1 Set MUX Ratio: A8h, 3Fh
  ssd1306_command(SSD1306_SETMULTIPLEX);                  // 0xA8
  // Init sequence for 128x64 OLED module
  ssd1306_command(0x3F);

  // 2 Set Display Offset: D3h, 00h
  ssd1306_command(SSD1306_SETDISPLAYOFFSET);              // 0xD3
  ssd1306_command(0x0);                                   // no offset
  // 3 Set Display Start Line: 40h
  ssd1306_command(SSD1306_SETSTARTLINE | 0x0);            // line #0
  // 4 Set Segment re-map: A0h/A1h
  ssd1306_command(SSD1306_SEGREMAP | 0x1);
  // 5 Set COM Output Scan Direction: C0h/C8h
  ssd1306_command(SSD1306_COMSCANDEC);
  // 6 Set COM Pins hardware configuration: DAh, 02
  ssd1306_command(SSD1306_SETCOMPINS);                    // 0xDA
  ssd1306_command(0x12);
  // 7 Set Contrast Control: 81h, 7Fh
  ssd1306_command(SSD1306_SETCONTRAST);                   // 0x81
  if (_vccstate == SSD1306_EXTERNALVCC)
  {
    ssd1306_command(0x9F);
  }
  else
  {
    ssd1306_command(0xCF);
  }
  //
  ssd1306_command(SSD1306_SETPRECHARGE);                  // 0xD9
  if (_vccstate == SSD1306_EXTERNALVCC)
  {
    ssd1306_command(0x22);
  }
  else
  {
    ssd1306_command(0xF1);
  }
  //
  ssd1306_command(SSD1306_SETVCOMDETECT);                 // 0xDB
  ssd1306_command(0x40);
  // 8 Disable Entire Display On: A4h
  ssd1306_command(SSD1306_DISPLAYALLON_RESUME);           // 0xA4
  // 9 Set Normal Display: A6h
  ssd1306_command(SSD1306_NORMALDISPLAY);                 // 0xA6
  // A Set Osc Frequency: D5h, 80h
  ssd1306_command(SSD1306_SETDISPLAYCLOCKDIV);            // 0xD5
  ssd1306_command(0x80);                                  // the suggested ratio 0x80
  // B Enable charge pump regulator: 8Dh, 14h
  ssd1306_command(SSD1306_CHARGEPUMP);                    // 0x8D
  if (_vccstate == SSD1306_EXTERNALVCC)
  {
    ssd1306_command(0x10);
  }
  else
  {
    ssd1306_command(0x14);
  }
  // C Display On: AFh
  display(); //--turn on oled panel
  //if (!_reset)
  //{
  clear();
  //}
}

// clear everything - VERSÃO OTIMIZADA
void SSD1306::clear(bool inverted)
{
  ssd1306_command(SSD1306_COLUMNADDR);                    // 0x21
  ssd1306_command(0);   // Column start address (0 = reset)
  ssd1306_command(SSD1306_LCDWIDTH - 1); // Column end address (127 = reset)

  ssd1306_command(SSD1306_PAGEADDR);                      // 0x22
  ssd1306_command(0); // Page start address (0 = reset)
  ssd1306_command(7); // Page end address
  
  // Calcular total de bytes a enviar por página
  uint16_t totalBytes = DESLOCAMENTO_ESQUERDA + SSD1306_LCDWIDTH + DESLOCAMENTO_ESQUERDA;
  
  // Para cada página (8 páginas)
  for(int8_t page = 0; page < 8; page++){
    ssd1306_command(SSD1306_SETPAGESTART | page);
    ssd1306_command(SSD1306_SETLOWCOLUMN);
    ssd1306_command(SSD1306_SETHIGHCOLUMN);
    
    // Enviar todos os bytes da página em blocos
    uint16_t bytesRestantes = totalBytes;
    
    while(bytesRestantes > 0) {
      // Wire buffer é tipicamente 32 bytes, usar 31 para dados (1 byte para controle)
      uint8_t chunkSize = (bytesRestantes > 31) ? 31 : bytesRestantes;
      
      bus->beginTransmission(_i2caddr);
      bus->write(0x40); // Co = 0, D/C = 1 (dados)
      
      for(uint8_t i = 0; i < chunkSize; i++) {
        bus->write(0x00);
      }
      
      bus->endTransmission();
      bytesRestantes -= chunkSize;
    }
  }
  limpaBuffer();
  setCursor(0, 0);
}

void SSD1306::limpaBuffer(){
  for(int8_t i = 0; i < TAMANHO_MAXIMO_COLUNAS; i++){
    bufferLinha[i] = ' ';
  }
}

void SSD1306::home()
{
  setCursor(0, 0);
}

//cada row são 8 pixels de linha na memoria MAS, a ideia é ter 4 linhas ou 3 (com a ultima sendo o dobro do tamanho)
//logo o ultimo row é 4
void SSD1306::setCursor(uint8_t col, uint8_t row)
{
  if ((col < _cols) && (row < _rows)){
    _c = col;
    if(_r != row){
      limpaBuffer();
    }
    _r = row;
    _x = _c * (SSD1306_FONT_WIDTH + 1); // +1 for space between characters
    _y = _r * SSD1306_FONT_HEIGHT;  
    _r = _r * multiplicadorTamanhoFonte; //o _r sempre tem q olhar a linha como 8 pixels, devido a estrutura do display
    /*
    ssd1306_command(SSD1306_SETPAGESTART | (_r));
    //ssd1306_command(SSD1306_SETSTARTLINE | (_r));
    ssd1306_command(SSD1306_SETLOWCOLUMN | (_x & 0x0F));
    ssd1306_command(SSD1306_SETHIGHCOLUMN | ((_x & 0xF0) >> 4));
    */
  }
}

void SSD1306::setX(uint8_t x){
    this->_x = x;
}
void SSD1306::setY(uint8_t y){
    this->_y = y;
}

// Turn the display on/off (quickly)
void SSD1306::noDisplay()
{
  ssd1306_command(SSD1306_DISPLAYOFF);
}

void SSD1306::display()
{
  ssd1306_command(SSD1306_DISPLAYON);
}


inline size_t SSD1306::write(uint8_t value)
{
  if (value == '\n')
  {
    _y += SSD1306_FONT_HEIGHT;
    //_r++;
    _r += multiplicadorTamanhoFonte; //o _r sempre tem q olhar a linha como 8 pixels, devido a estrutura do display
    _x = DESLOCAMENTO_ESQUERDA;
    _c = 0;
    limpaBuffer();
  }
  else if (value == '\r'){
    for(uint8_t col = _c; col < this->_cols;col++){
        drawChar(' ');
        bufferLinha[col] = ' ';
    }
    _x = DESLOCAMENTO_ESQUERDA;
    _c = 0;
  }
  else{
      drawChar(value);
      //_c++; //passou pra funcao drawChar
    
  }
  return 1; // assume success
}

// Dim the display
// dim = true: display is dimmed
// dim = false: display is normal
void SSD1306::dim(boolean dim)
{
  uint8_t contrast;

  if (dim)
  {
    contrast = 0; // Dimmed display
  }
  else
  {
    if (_vccstate == SSD1306_EXTERNALVCC)
    {
      contrast = 0x9F;
    }
    else
    {
      contrast = 0xCF;
    }
  }
  // the range of contrast to too small to be really useful
  // it is useful to dim the display
  ssd1306_command(SSD1306_SETCONTRAST);
  ssd1306_command(contrast);
}


//2026-02-12 - Joguei a analise do buffer aqui dentro, pois preciso alterar outras variaveis
void SSD1306::drawChar(unsigned char c, bool inverted){
  //cada fonte ocupa o multiplicadorTamanho de altura
	int8_t multiplicadorTamanho = multiplicadorTamanhoFonte; 
  int8_t tamanhoXLetra = SSD1306_FONT_WIDTH;
  int8_t tamanhoYLetra = SSD1306_FONT_HEIGHT;
  if (((_x-DESLOCAMENTO_ESQUERDA) > (SSD1306_LCDWIDTH - tamanhoXLetra))    || // Clip right
      (_y > (SSD1306_LCDHEIGHT - tamanhoYLetra))  || // Clip bottom
      (_x < 0)                                || // Clip left
      (_y < 0))                                  // Clip top
      {
        return;
      }
 
  // Buffer para acumular dados de uma linha (página) - máximo: 5 colunas * 4 multiplicador + espaçamento = ~24 bytes
  uint8_t buffer[32]; 
  uint8_t bufferIndex;
  
  // top half
  uint8_t x_inicio = _x;
  uint8_t paginaInicial = 0;
  // mas cada gravação, vai em 8 linhas
  uint8_t linhaTela = _r;
  //este for abaixo desenha o caractere de acordo com o multiplicador, ou seja, se for 2, ele desenha a letra em 2 partes, se for 4, ele desenha em 4 partes
  for(int8_t parte = multiplicadorTamanho-1; parte >= 0; parte--){
		_x = x_inicio;
    if(_x == 0){
      _x = DESLOCAMENTO_ESQUERDA; //caso a primeira coluna seja 0, eu coloco DESLOCAMENTO_ESQUERDA para nao cortar
    }
    
    if(bufferLinha[_c] != c){ //só redesenha a letra se for diferente da que já está no buffer
      ssd1306_command(SSD1306_SETPAGESTART | linhaTela);
      //ssd1306_command(SSD1306_SETSTARTLINE | (_y / SSD1306_FONT_HEIGHT));
      ssd1306_command(SSD1306_SETLOWCOLUMN | (_x & 0x0F));
      ssd1306_command(SSD1306_SETHIGHCOLUMN | ((_x & 0xF0) >> 4));
      
      // Acumular dados no buffer
      bufferIndex = 0;
      
      for (uint8_t i = 0; i < 5; ++i){
        uint8_t b = pgm_read_byte(&flash_font[((c - 0x20) * 5) + i]);
        if (inverted)
        {
          b ^= 0xFF;
        }
        uint8_t temp=0; 
        int8_t inicioFor = (7-(parte*(8/multiplicadorTamanho)));
        int8_t fimFor = inicioFor - 8/multiplicadorTamanho + 1;
        for(int8_t k = inicioFor ; k >= fimFor; k--){
          for(uint8_t i = 0; i < multiplicadorTamanho; ++i){
            temp = (temp << 1);
            temp = temp | ((b >> k) & 0x01);
          }
        }
        b = temp;
        for(uint8_t i = 0; i < multiplicadorTamanho; ++i){
          buffer[bufferIndex++] = b;
        }
      }
      // Adicionar espaçamento
      for(int8_t espacamento = multiplicadorTamanho-1; espacamento >= 0; espacamento--){
        buffer[bufferIndex++] = 0x00;
      }
      
    
        // Enviar todos os dados de uma vez
        bus->beginTransmission(_i2caddr);
        bus->write(0x40); // Co = 0, D/C = 1
        for(uint8_t i = 0; i < bufferIndex; i++){
          bus->write(buffer[i]);
        }
        bus->endTransmission();
    }
    linhaTela++;
	}
  this->bufferLinha[this->_c] = c;
  this->_c++;
	_x += tamanhoXLetra + multiplicadorTamanho;
}



void SSD1306::ssd1306_command(uint8_t c)
{
  // I2C
  bus->beginTransmission(_i2caddr);
  bus->write(0x00); // Co = 0, D/C = 0
  bus->write(c);
  bus->endTransmission();
}

void SSD1306::ssd1306_data(uint8_t d)
{
  // I2C
  bus->beginTransmission(_i2caddr);
  bus->write(0x40); // Co = 0, D/C = 1
  bus->write(d);
  bus->endTransmission();
}

void SSD1306::setFonte(uint8_t tamanhoFonte){
  if(tamanhoFonte > 3){ //nao existe esse valor
    return;
  }
  if(tamanhoFonte == FONTE_PEQUENA){
    multiplicadorTamanhoFonte = 1;
    SSD1306_FONT_WIDTH = 5;
    SSD1306_FONT_HEIGHT = 8; 
    _cols = 21;
    _rows = 8;
  }
  if(tamanhoFonte == FONTE_MEDIA){
    multiplicadorTamanhoFonte = 2;
    SSD1306_FONT_WIDTH = 10;
    SSD1306_FONT_HEIGHT = 16;
    _cols = 10;
    _rows = 4;
  }
  if(tamanhoFonte == FONTE_GRANDE){
    multiplicadorTamanhoFonte = 4;
    SSD1306_FONT_WIDTH = 20;
    SSD1306_FONT_HEIGHT = 32;
    _cols = 5;
    _rows = 2;
  }
  this->clear();
}



void SSD1306::limpaLinha(uint8_t linha){
  if(multiplicadorTamanhoFonte == 1){
    if(linha > 7){
      return;
    }
    this->setCursor(0, linha);
    this->print(F("                     ")); // 21 espaços para limpar a linha
  }
  if(multiplicadorTamanhoFonte == 2){
    if(linha > 3){
      return;
    }
    this->setCursor(0, linha);
    this->print(F("          ")); // 10 espaços para limpar a linha
  }
  if(multiplicadorTamanhoFonte == 4){
    if(linha > 1){
      return;
    }
    this->setCursor(0, linha);
    this->print(F("     ")); // 5 espaços para limpar a linha
  }
  this->setCursor(0, linha);
}