// Estrutura para um LED individual WS2812B

struct LED_RGB {
    uint8_t green;
    uint8_t red;
    uint8_t blue;
    LED_RGB* next;
    
    LED_RGB() : red(0), green(0), blue(0), next(nullptr) {}
    LED_RGB(uint8_t r, uint8_t g, uint8_t b) : red(r), green(g), blue(b), next(nullptr) {}
};

class LEDStrip {
private:
    LED_RGB* leds;
    uint8_t numLeds;
    uint8_t pino;
    bool inicializado;
    uint8_t brilho; // 0 a 100
    char descricaoPorta[6];
    // Tabelas de pinos para ATmega328P (Arduino Nano/Uno)
    //static const uint8_t pinBit[];
    //static const uint8_t pinAddr[];
    
    // Função assembly para pino 10 (PORTB bit 2)
    void writeDataPin5(LED_RGB* colors) {
        unsigned int count = numLeds;
        while(count--) {
            // Envia Green, Red, Blue (ordem WS2812B: GRB)
            asm volatile(
                "ld __tmp_reg__, %a[ptr]\n"     // Lê green (offset 0)
                "rcall send_led_strip_byte%=\n"
                "ldd __tmp_reg__, %a[ptr]+1\n"  // Lê red (offset 1)
                "rcall send_led_strip_byte%=\n"
                "ldd __tmp_reg__, %a[ptr]+2\n"  // Lê blue (offset 2)
                "rcall send_led_strip_byte%=\n"
                "rjmp led_strip_asm_end%=\n"
                "send_led_strip_byte%=:\n"
                "rcall send_led_strip_bit%=\n" "rcall send_led_strip_bit%=\n"
                "rcall send_led_strip_bit%=\n" "rcall send_led_strip_bit%=\n"
                "rcall send_led_strip_bit%=\n" "rcall send_led_strip_bit%=\n"
                "rcall send_led_strip_bit%=\n" "rcall send_led_strip_bit%=\n"
                "ret\n"
                "send_led_strip_bit%=:\n"
                "sbi 0x0B, 5\n" "rol __tmp_reg__\n" "nop\n" "nop\n"
                "brcs .+2\n" "cbi 0x0B, 5\n"
                "nop\n" "nop\n" "nop\n" "nop\n" "nop\n"
                "brcc .+2\n" "cbi 0x0B, 5\n" "ret\n"
                "led_strip_asm_end%=:" 
                : 
                : [ptr] "z" (colors)
            );
            colors = colors->next;
        }
    }
    
    // Função assembly para pino 11 (PORTB bit 3)
    void writeDataPin11(LED_RGB* colors) {
        unsigned int count = numLeds;
        while(count--) {
            asm volatile(
                "ld __tmp_reg__, %a[ptr]\n"
                "rcall send_led_strip_byte%=\n"
                "ldd __tmp_reg__, %a[ptr]+1\n"
                "rcall send_led_strip_byte%=\n"
                "ldd __tmp_reg__, %a[ptr]+2\n"
                "rcall send_led_strip_byte%=\n"
                "rjmp led_strip_asm_end%=\n"
                "send_led_strip_byte%=:\n"
                "rcall send_led_strip_bit%=\n" "rcall send_led_strip_bit%=\n"
                "rcall send_led_strip_bit%=\n" "rcall send_led_strip_bit%=\n"
                "rcall send_led_strip_bit%=\n" "rcall send_led_strip_bit%=\n"
                "rcall send_led_strip_bit%=\n" "rcall send_led_strip_bit%=\n"
                "ret\n"
                "send_led_strip_bit%=:\n"
                "sbi 0x05, 3\n" "rol __tmp_reg__\n" "nop\n" "nop\n"
                "brcs .+2\n" "cbi 0x05, 3\n"
                "nop\n" "nop\n" "nop\n" "nop\n" "nop\n"
                "brcc .+2\n" "cbi 0x05, 3\n" "ret\n"
                "led_strip_asm_end%=:" 
                : 
                : [ptr] "z" (colors)
            );
            colors = colors->next;
        }
    }
    
    // Função assembly para pino 12 (PORTB bit 4)
    void writeDataPin12(LED_RGB* colors) {
        unsigned int count = numLeds;
        while(count--) {
            asm volatile(
                "ld __tmp_reg__, %a[ptr]\n"
                "rcall send_led_strip_byte%=\n"
                "ldd __tmp_reg__, %a[ptr]+1\n"
                "rcall send_led_strip_byte%=\n"
                "ldd __tmp_reg__, %a[ptr]+2\n"
                "rcall send_led_strip_byte%=\n"
                "rjmp led_strip_asm_end%=\n"
                "send_led_strip_byte%=:\n"
                "rcall send_led_strip_bit%=\n" "rcall send_led_strip_bit%=\n"
                "rcall send_led_strip_bit%=\n" "rcall send_led_strip_bit%=\n"
                "rcall send_led_strip_bit%=\n" "rcall send_led_strip_bit%=\n"
                "rcall send_led_strip_bit%=\n" "rcall send_led_strip_bit%=\n"
                "ret\n"
                "send_led_strip_bit%=:\n"
                "sbi 0x05, 4\n" "rol __tmp_reg__\n" "nop\n" "nop\n"
                "brcs .+2\n" "cbi 0x05, 4\n"
                "nop\n" "nop\n" "nop\n" "nop\n" "nop\n"
                "brcc .+2\n" "cbi 0x05, 4\n" "ret\n"
                "led_strip_asm_end%=:" 
                : 
                : [ptr] "z" (colors)
            );
            colors = colors->next;
        }
    }
    
    // Função assembly para pino 13 (PORTB bit 5)
    void writeDataPin13(LED_RGB* colors) {
        unsigned int count = numLeds;
        while(count--) {
            asm volatile(
                "ld __tmp_reg__, %a[ptr]\n"
                "rcall send_led_strip_byte%=\n"
                "ldd __tmp_reg__, %a[ptr]+1\n"
                "rcall send_led_strip_byte%=\n"
                "ldd __tmp_reg__, %a[ptr]+2\n"
                "rcall send_led_strip_byte%=\n"
                "rjmp led_strip_asm_end%=\n"
                "send_led_strip_byte%=:\n"
                "rcall send_led_strip_bit%=\n" "rcall send_led_strip_bit%=\n"
                "rcall send_led_strip_bit%=\n" "rcall send_led_strip_bit%=\n"
                "rcall send_led_strip_bit%=\n" "rcall send_led_strip_bit%=\n"
                "rcall send_led_strip_bit%=\n" "rcall send_led_strip_bit%=\n"
                "ret\n"
                "send_led_strip_bit%=:\n"
                "sbi 0x05, 5\n" "rol __tmp_reg__\n" "nop\n" "nop\n"
                "brcs .+2\n" "cbi 0x05, 5\n"
                "nop\n" "nop\n" "nop\n" "nop\n" "nop\n"
                "brcc .+2\n" "cbi 0x05, 5\n" "ret\n"
                "led_strip_asm_end%=:" 
                : 
                : [ptr] "z" (colors)
            );
            colors = colors->next;
        }
    }
    
    // Envia os dados para os LEDs via assembly otimizado
    void writeData() {
        if(!inicializado) return;
        
        // Aplica brilho (0-100%) em um buffer temporário antes de enviar
        LED_RGB buffer[10];
        if(numLeds > 10) return; // segurança

        uint8_t brilhoLocal = brilho;
        for(uint8_t i = 0; i < numLeds; i++) {
            uint8_t r = leds[i].red;
            uint8_t g = leds[i].green;
            uint8_t b = leds[i].blue;

            if(brilhoLocal == 0) {
                r = g = b = 0;
            } else if(brilhoLocal < 100) {
                r = (uint16_t)r * brilhoLocal / 100;
                g = (uint16_t)g * brilhoLocal / 100;
                b = (uint16_t)b * brilhoLocal / 100;
            }

            buffer[i].red = r;
            buffer[i].green = g;
            buffer[i].blue = b;
            buffer[i].next = &buffer[(i + 1) % numLeds];
        }

        LED_RGB* colors = buffer;

        pinMode(pino, OUTPUT);
        digitalWrite(pino, LOW);
        delayMicroseconds(60); // Reset time (>50µs LOW)
        
        cli(); // Desabilita interrupções
        
        // Switch case para as 4 portas LED (pinos 5, 11, 12, 13)
        switch(pino) {
            case 5: writeDataPin5(colors); break; // PORTA_LED_4
            case 11: writeDataPin11(colors); break; // PORTA_LED_3
            case 12: writeDataPin12(colors); break; // PORTA_LED_2
            case 13: writeDataPin13(colors); break; // PORTA_LED_1
            default:
                Serial.println(F("Erro: Pino LED invalido! Use PORTA_LED_1 a PORTA_LED_4"));
                break;
        }
        
        sei(); // Re-habilita interrupções
        delayMicroseconds(60); // Reset time após enviar dados
    }

public:
    LEDStrip(PortaLed porta, int quantidade=10) {
        leds = nullptr;
        numLeds=quantidade;
        pino=porta.pino;
        inicializado=false;
        brilho = 100;
        strcpy(this->descricaoPorta, porta.descricao);
    }
    
    ~LEDStrip() {
        if(leds != nullptr) {
            delete[] leds;
        }
    }
    
    // Inicializa a fita de LEDs em uma porta de servo/led específica
    void inicializa() {
        if(this->numLeds == 0 || this->numLeds > 10) {
            Serial.println(F("Erro: quantidade de LEDs invalida (1-10)"));
            while(1);
        }
        
        // Aloca memória para os LEDs
        leds = new LED_RGB[numLeds];
        
        // Cria lista circular encadeada
        for(uint8_t i = 0; i < numLeds; i++) {
            leds[i].next = &leds[(i + 1) % numLeds];
        }
        
        inicializado = true;
        
        Serial.print(F("Fita LED inicializada na porta "));
        Serial.print(this->descricaoPorta);
        Serial.print(F(" com "));
        Serial.print(numLeds);
        Serial.println(F(" LEDs"));
        
        // Apaga todos os LEDs
        limpar();
        atualiza();
    }
    
    // Define a cor de um LED específico (índice começa em 0)
    void setLED(uint8_t indice, uint8_t r, uint8_t g, uint8_t b) {
        if(!inicializado || indice >= numLeds) return;
       
        leds[indice].red = r;
        leds[indice].green = g;
        leds[indice].blue = b;
    }
    
    // Define a cor de todos os LEDs
    void setTodos(uint8_t r, uint8_t g, uint8_t b) {
        if(!inicializado) return;
        
        for(uint8_t i = 0; i < numLeds; i++) {
            leds[i].red = r;
            leds[i].green = g;
            leds[i].blue = b;
        }
    }

    // Define o brilho global de todos os LEDs (0 a 100%)
    // brilho = 0  -> apaga (0%)
    // brilho = 100 -> brilho máximo das cores definidas
    void setBrilho(uint8_t brilho) {
        if(brilho > 100) brilho = 100;
        this->brilho = brilho;
    }
    
    // Apaga todos os LEDs (preto)
    void limpar() {
        setTodos(0, 0, 0);
    }
    
    // Atualiza a fita de LEDs (envia os dados)
    void atualiza() {
        writeData();
    }
    
    // Método de teste - pisca o LED em cores diferentes
    void teste() {
        Serial.println(F("Teste LED - Vermelho"));
        setTodos(255, 0, 0);
        atualiza();
        delay(1000);
        
        Serial.println(F("Teste LED - Verde"));
        setTodos(0, 255, 0);
        atualiza();
        delay(1000);
        
        Serial.println(F("Teste LED - Azul"));
        setTodos(0, 0, 255);
        atualiza();
        delay(1000);
        
        Serial.println(F("Teste LED - Branco"));
        setTodos(255, 255, 255);
        atualiza();
        delay(1000);
        
        Serial.println(F("Teste LED - Apagar"));
        limpar();
        atualiza();
    }
    
    // Cores pré-definidas
    void vermelho(uint8_t indice = 255) {
        if(indice == 255) setTodos(255, 0, 0);
        else setLED(indice, 255, 0, 0);
    }
    
    void verde(uint8_t indice = 255) {
        if(indice == 255) setTodos(0, 255, 0);
        else setLED(indice, 0, 255, 0);
    }
    
    void azul(uint8_t indice = 255) {
        if(indice == 255) setTodos(0, 0, 255);
        else setLED(indice, 0, 0, 255);
    }
    
    void branco(uint8_t indice = 255) {
        if(indice == 255) setTodos(255, 255, 255);
        else setLED(indice, 255, 255, 255);
    }
    
    void amarelo(uint8_t indice = 255) {
        if(indice == 255) setTodos(255, 255, 0);
        else setLED(indice, 255, 255, 0);
    }
    
    void ciano(uint8_t indice = 255) {
        if(indice == 255) setTodos(0, 255, 255);
        else setLED(indice, 0, 255, 255);
    }
    
    void magenta(uint8_t indice = 255) {
        if(indice == 255) setTodos(255, 0, 255);
        else setLED(indice, 255, 0, 255);
    }
    
    // Efeito arco-íris estático
    void arcoIris() {
        if(!inicializado) return;
        
        for(uint8_t i = 0; i < numLeds; i++) {
            uint8_t hue = (i * 255) / numLeds;
            setLEDHSV(i, hue, 255, 255);
        }
    }
    
    // Animação: arco-íris rotativo
    void arcoIrisRotativo(uint8_t velocidade = 10) {
        static uint8_t offset = 0;
        for(uint8_t i = 0; i < numLeds; i++) {
            uint8_t hue = ((i * 255) / numLeds + offset) % 256;
            setLEDHSV(i, hue, 255, 255);
        }
        atualiza();
        offset += velocidade;
        delay(50);
    }
    
    // Animação: Knight Rider (vai e volta)
    void knightRider(uint8_t r = 255, uint8_t g = 0, uint8_t b = 0, uint8_t velocidade = 50) {
        if(!inicializado || numLeds == 0) return;

        // Usa a cor atual do primeiro LED como base
        uint8_t r_base = leds[0].red;
        uint8_t g_base = leds[0].green;
        uint8_t b_base = leds[0].blue;

        // Se todos estiverem apagados, usa os parâmetros padrão
        if(r_base == 0 && g_base == 0 && b_base == 0) {
            r_base = r;
            g_base = g;
            b_base = b;
        }

        // Ida
        for(uint8_t i = 0; i < numLeds; i++) {
            limpar();
            setLED(i, r_base, g_base, b_base);
            if(i > 0) setLED(i-1, r_base/4, g_base/4, b_base/4);
            if(i < numLeds-1) setLED(i+1, r_base/4, g_base/4, b_base/4);
            atualiza();
            delay(velocidade);
        }
        // Volta
        for(int8_t i = numLeds-1; i >= 0; i--) {
            limpar();
            setLED(i, r_base, g_base, b_base);
            if(i > 0) setLED(i-1, r_base/4, g_base/4, b_base/4);
            if(i < numLeds-1) setLED(i+1, r_base/4, g_base/4, b_base/4);
            atualiza();
            delay(velocidade);
        }
    }
    
    // Animação: Preenche gradualmente
    void preenchimento(uint8_t r = 255, uint8_t g = 255, uint8_t b = 255, uint8_t velocidade = 100) {
        if(!inicializado || numLeds == 0) return;

        uint8_t r_base = leds[0].red;
        uint8_t g_base = leds[0].green;
        uint8_t b_base = leds[0].blue;
        if(r_base == 0 && g_base == 0 && b_base == 0) {
            r_base = r;
            g_base = g;
            b_base = b;
        }

        limpar();
        atualiza();
        for(uint8_t i = 0; i < numLeds; i++) {
            setLED(i, r_base, g_base, b_base);
            atualiza();
            delay(velocidade);
        }
    }
    
    // Animação: Pisca tudo
    void piscar(uint8_t r = 255, uint8_t g = 255, uint8_t b = 255, uint8_t vezes = 3, uint8_t velocidade = 200) {
        if(!inicializado || numLeds == 0) return;

        uint8_t r_base = leds[0].red;
        uint8_t g_base = leds[0].green;
        uint8_t b_base = leds[0].blue;
        if(r_base == 0 && g_base == 0 && b_base == 0) {
            r_base = r;
            g_base = g;
            b_base = b;
        }

        for(uint8_t i = 0; i < vezes; i++) {
            setTodos(r_base, g_base, b_base);
            atualiza();
            delay(velocidade);
            limpar();
            atualiza();
            delay(velocidade);
        }
    }
    
    // Animação: Fade in/out
    void fade(uint8_t r = 255, uint8_t g = 255, uint8_t b = 255) {
        if(!inicializado || numLeds == 0) return;

        uint8_t r_base = leds[0].red;
        uint8_t g_base = leds[0].green;
        uint8_t b_base = leds[0].blue;
        if(r_base == 0 && g_base == 0 && b_base == 0) {
            r_base = r;
            g_base = g;
            b_base = b;
        }
        // Fade in
        for(uint8_t brilho = 0; brilho < 255; brilho += 5) {
            uint8_t r_dim = (r_base * brilho) / 255;
            uint8_t g_dim = (g_base * brilho) / 255;
            uint8_t b_dim = (b_base * brilho) / 255;
            setTodos(r_dim, g_dim, b_dim);
            atualiza();
            delay(20);
        }
        // Fade out
        for(int16_t brilho = 255; brilho >= 0; brilho -= 5) {
            uint8_t r_dim = (r_base * brilho) / 255;
            uint8_t g_dim = (g_base * brilho) / 255;
            uint8_t b_dim = (b_base * brilho) / 255;
            setTodos(r_dim, g_dim, b_dim);
            atualiza();
            delay(20);
        }
        limpar();
        atualiza();
    }
    
    // Animação: Teatro (Chase)
    void teatro(uint8_t r = 255, uint8_t g = 255, uint8_t b = 255, uint8_t ciclos = 10) {
        if(!inicializado || numLeds == 0) return;

        uint8_t r_base = leds[0].red;
        uint8_t g_base = leds[0].green;
        uint8_t b_base = leds[0].blue;
        if(r_base == 0 && g_base == 0 && b_base == 0) {
            r_base = r;
            g_base = g;
            b_base = b;
        }
        for(uint8_t j = 0; j < ciclos; j++) {
            for(uint8_t q = 0; q < 3; q++) {
                limpar();
                for(uint8_t i = q; i < numLeds; i += 3) {
                    setLED(i, r_base, g_base, b_base);
                }
                atualiza();
                delay(100);
            }
        }
    }
    
    // Animação: Sparkle (faíscas aleatórias)
    void sparkle(uint8_t r = 255, uint8_t g = 255, uint8_t b = 255, uint8_t quantidade = 20) {
        if(!inicializado || numLeds == 0) return;

        uint8_t r_base = leds[0].red;
        uint8_t g_base = leds[0].green;
        uint8_t b_base = leds[0].blue;
        if(r_base == 0 && g_base == 0 && b_base == 0) {
            r_base = r;
            g_base = g;
            b_base = b;
        }
        for(uint8_t i = 0; i < quantidade; i++) {
            limpar();
            uint8_t pixel = random(numLeds);
            setLED(pixel, r_base, g_base, b_base);
            atualiza();
            delay(100);
        }
        limpar();
        atualiza();
    }
    
    // Animação: Onda de cor
    void onda(uint8_t velocidade = 50) {
        static uint8_t offset = 0;
        for(uint8_t i = 0; i < numLeds; i++) {
            uint8_t brilho = (sin8(offset + (i * 255 / numLeds)) * 255) / 255;
            setLEDHSV(i, offset, 255, brilho);
        }
        atualiza();
        offset += velocidade;
        delay(50);
    }
    
    // Animação completa: mostra todas as animações
    void demo() {
        Serial.println(F("Demo - Arco-iris"));
        arcoIris();
        atualiza();
        delay(2000);
        
        Serial.println(F("Demo - Knight Rider"));
        knightRider(255, 0, 0, 50);
        knightRider(0, 255, 0, 50);
        knightRider(0, 0, 255, 50);
        
        Serial.println(F("Demo - Preenchimento"));
        preenchimento(255, 0, 255, 100);
        delay(1000);
        
        Serial.println(F("Demo - Piscar"));
        piscar(255, 255, 0, 5, 200);
        
        Serial.println(F("Demo - Fade"));
        fade(0, 255, 255);
        
        Serial.println(F("Demo - Teatro"));
        teatro(255, 100, 0, 10);
        
        Serial.println(F("Demo - Sparkle"));
        sparkle(255, 255, 255, 30);
        
        Serial.println(F("Demo - Arco-iris rotativo"));
        for(uint8_t i = 0; i < 50; i++) {
            arcoIrisRotativo(10);
        }
        
        limpar();
        atualiza();
    }
    
    // Define LED usando HSV (Hue, Saturation, Value)
    void setLEDHSV(uint8_t indice, uint8_t h, uint8_t s, uint8_t v) {
        if(!inicializado || indice >= numLeds) return;
        
        uint8_t r, g, b;
        hsvToRgb(h, s, v, r, g, b);
        setLED(indice, r, g, b);
    }
    
private:
    // Função seno de 8 bits (0-255)
    uint8_t sin8(uint8_t x) {
        static const uint8_t sinTable[64] PROGMEM = {
            128, 140, 152, 164, 176, 187, 198, 208, 218, 227, 235, 243, 249, 254, 
            255, 254, 249, 243, 235, 227, 218, 208, 198, 187, 176, 164, 152, 140,
            128, 115, 103, 91, 79, 68, 57, 47, 37, 28, 20, 12, 6, 1,
            0, 1, 6, 12, 20, 28, 37, 47, 57, 68, 79, 91, 103, 115,
            128, 140, 152, 164, 176, 187, 198, 208
        };
        return pgm_read_byte(&sinTable[x >> 2]);
    }
    
    // Converte HSV para RGB
    void hsvToRgb(uint8_t h, uint8_t s, uint8_t v, uint8_t &r, uint8_t &g, uint8_t &b) {
        if(s == 0) {
            r = g = b = v;
            return;
        }
        
        uint8_t region = h / 43;
        uint8_t remainder = (h - (region * 43)) * 6;
        
        uint8_t p = (v * (255 - s)) >> 8;
        uint8_t q = (v * (255 - ((s * remainder) >> 8))) >> 8;
        uint8_t t = (v * (255 - ((s * (255 - remainder)) >> 8))) >> 8;
        
        switch(region) {
            case 0: r = v; g = t; b = p; break;
            case 1: r = q; g = v; b = p; break;
            case 2: r = p; g = v; b = t; break;
            case 3: r = p; g = q; b = v; break;
            case 4: r = t; g = p; b = v; break;
            default: r = v; g = p; b = q; break;
        }
    }
};