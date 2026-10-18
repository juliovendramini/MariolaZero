/*
    Copyright © 2012-2015 Arduino LLC, Limor Fried/Ladyada, Michael Gregg,
    pocketmoon, Neil McNeight

    This file is part of LiquidCrystal_SSD1306.

    LiquidCrystal_SSD1306 is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation, either version 2.1 of the License, or
    (at your option) any later version.

    LiquidCrystal_SSD1306 is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

-------------------------------------------------------------------------------
Change Log
https://github.com/McNeight/LiquidCrystal_SSD1306/tree/master
DATE      VER   WHO   WHAT
06/20/15  1.6.0 NEM   Code cleanup and compatibility with Arduino 1.6.*
2024-11-30  - Simplificação por Julio Vendramini
2024-12-02  - O equipamento terá 3 linhas na tela, as duas primeiras de tamanho 16 e a terceira de tamanho 32
2024-12-04  - Inclusão de opção de ter 3 ou 4 linhas, com a ultima sendo o dobro do tamanho ou não 
-------------------------------------------------------------------------------

 */
#include <Arduino.h>
#include "SoftWire.h"
#include "portas.h"

#ifndef SSD1306_h
#define SSD1306_h

#define swap(a, b) { int8_t t = a; a = b; b = t; }

#define BLACK 0
#define WHITE 1
#define INVERSE 2

#define SSD1306_I2C_ADDRESS   0x3C	// 011110+SA0+RW - 0x3C or 0x3D
// Address for 128x64 is 0x3D (default) or 0x3C (if SA0 is grounded)

/*=========================================================================
    SSD1306 Displays
    -----------------------------------------------------------------------
    The driver is used in multiple displays (128x64, 128x32, etc.).
    Select the appropriate display below to create an appropriately
    sized framebuffer, etc.

    SSD1306_128_64  128x64 pixel display

    SSD1306_128_32  128x32 pixel display

    SSD1306_96_16

    -----------------------------------------------------------------------*/
#define SSD1306_128_64
/*=========================================================================*/


#define DESLOCAMENTO_ESQUERDA 2 //observei que algumas telas nao aceitam o endereço zero e 1, então desloco 2 para a esquerda

#define SSD1306_LCDWIDTH                  128 //estou fazendo isso como solução temporaria para escrita errada do sh1106 ele tem 132 colunas e o display 128
#define SSD1306_LCDHEIGHT                 64

#define TAMANHO_MAXIMO_COLUNAS 21 //tamanho da linha com a fonte grande, que é a maior

#define SSD1306_SETCONTRAST 0x81
#define SSD1306_DISPLAYALLON_RESUME 0xA4
#define SSD1306_DISPLAYALLON 0xA5
#define SSD1306_NORMALDISPLAY 0xA6
#define SSD1306_INVERTDISPLAY 0xA7
#define SSD1306_DISPLAYOFF 0xAE
#define SSD1306_DISPLAYON 0xAF

#define SSD1306_SETDISPLAYOFFSET 0xD3
#define SSD1306_SETCOMPINS 0xDA

#define SSD1306_SETVCOMDETECT 0xDB

#define SSD1306_SETDISPLAYCLOCKDIV 0xD5
#define SSD1306_SETPRECHARGE 0xD9

#define SSD1306_SETMULTIPLEX 0xA8

#define SSD1306_SETLOWCOLUMN 0x00
#define SSD1306_SETHIGHCOLUMN 0x10

#define SSD1306_SETSTARTLINE 0x40

#define SSD1306_MEMORYMODE 0x20
#define SSD1306_COLUMNADDR 0x21
#define SSD1306_PAGEADDR   0x22

#define SSD1306_COMSCANINC 0xC0
#define SSD1306_COMSCANDEC 0xC8

#define SSD1306_SEGREMAP 0xA0

#define SSD1306_CHARGEPUMP 0x8D

#define SSD1306_EXTERNALVCC 0x1
#define SSD1306_SWITCHCAPVCC 0x2

// Scrolling #defines
#define SSD1306_ACTIVATE_SCROLL 0x2F
#define SSD1306_DEACTIVATE_SCROLL 0x2E
#define SSD1306_SET_VERTICAL_SCROLL_AREA 0xA3
#define SSD1306_RIGHT_HORIZONTAL_SCROLL 0x26
#define SSD1306_LEFT_HORIZONTAL_SCROLL 0x27
#define SSD1306_VERTICAL_AND_RIGHT_HORIZONTAL_SCROLL 0x29
#define SSD1306_VERTICAL_AND_LEFT_HORIZONTAL_SCROLL 0x2A

//Set GDDRAM Page Start Address 0xB0 - OxB7
#define SSD1306_SETPAGESTART 0xB0

#define SSD1306_NOOP 0xE3

// Abbreviated ASCII 5x8 font
extern const uint8_t flash_font[] PROGMEM;

//tres linhas (duas primeiras metade da terceira)
//quatro linhas (todas do mesmo tamanho)


class SSD1306 : public Print
{
  public:
    SSD1306(PortaI2C porta, uint8_t vccstate = SSD1306_SWITCHCAPVCC);

    void setBus(SoftWire * bus) { this->bus = bus; }
    SoftWire * getBus() { return bus; }
    void begin();
    void init();
    void clear(bool inverted = false);
    void limpaBuffer();
    void white();
    void home();

    void noDisplay();
    void display();
    void setCursor(uint8_t, uint8_t);
    virtual size_t write(uint8_t);

    void dim(boolean dim);

    void center(uint8_t row);
    // These MAY be overridden by the subclass to provide device-specific
    // optimized code.  Otherwise 'generic' versions are used.
    void drawChar(unsigned char c, bool inverted = false);
    using Print::write;
    void setX(uint8_t x);
    void setY(uint8_t y);
    uint8_t height(void);
    uint8_t width(void);
    void setFonte(uint8_t tamanhoFonte);
    void limpaLinha(uint8_t linha);
    static const uint8_t FONTE_PEQUENA = 1;
    static const uint8_t FONTE_MEDIA = 2;
    static const uint8_t FONTE_GRANDE = 3;
  private:
    SoftWire * bus;
    uint8_t sda;
    uint8_t scl;
    char descricaoPorta[6];
    uint8_t _i2caddr, _vccstate;
    uint8_t _x, _y, // pixel coordinates
            _rows, _cols, // Text w/h
            _r, _c; // character coordinates
    uint8_t _totalLines;
    uint8_t SSD1306_FONT_WIDTH  = 5;
    uint8_t SSD1306_FONT_HEIGHT  = 8;
    uint8_t multiplicadorTamanhoFonte = 1;
    uint8_t bufferLinha[TAMANHO_MAXIMO_COLUNAS];
    void ssd1306_command(uint8_t c);
    void ssd1306_data(uint8_t d);
};

#endif