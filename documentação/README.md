# Documentação das Classes - MariolaZero

Este diretório contém a documentação completa de todas as classes disponíveis no projeto MariolaZero. Cada arquivo documenta uma classe específica com exemplos de uso, métodos disponíveis e requisitos.

---

## 📚 Índice das Classes

### 🔧 Controle e I/O
- **[Botoes](Botoes.md)** - Interface para leitura de botões GPIO
- **[Teclado](Teclado.md)** - Controle de botões e LEDs via PCF8574A I2C
- **[Portas](Portas.md)** - Gerenciamento de portas seriais USB e fixas

### ⏱️ Tempo e Cronometragem
- **[Cronometro](Cronometro.md)** - Medição de tempo com persistência opcional

### 📺 Display e Interface
- **[Tela](Tela.md)** - Controle de display OLED SSD1306

### 🎨 Sensores de Cor
- **[TCS34725](Tcs34725.md)** - Sensor de cor individual via multiplexador I2C
- **[PlacaMuxTCS34725](PlacaMuxTCS34725.md)** - Múltiplos sensores TCS34725 via serial
- **[CorReflexao](CorReflexao.md)** - Sensor de cor e reflexão integrado

### 📏 Sensores de Distância
- **[VL53L0X](Vl53.md)** - Sensor laser de distância individual
- **[PlacaMuxVl53l0x](PlacaMuxVl53l0x.md)** - Múltiplos sensores VL53L0X via serial

### 🔄 Movimento e Orientação
- **[Motores](Motores.md)** - Controle de motores e servos
- **[Giroscopio](Giroscopio.md)** - Leitura de orientação e movimento

---

## 🚀 Como Usar

1. **Importe a classe desejada:**
   ```python
   from libs.nome_da_classe import NomeDaClasse
   ```

2. **Consulte a documentação específica** para exemplos de uso e métodos disponíveis

3. **Verifique os requisitos** de cada classe antes de usar

---

## 📋 Convenções

- Todas as classes seguem o padrão **snake_case** para métodos e variáveis
- Documentação em formato **Markdown** compatível com GitHub
- Exemplos práticos em todos os arquivos
- Seção de requisitos com dependências necessárias

---

## 🔗 Links Úteis

- [README Principal](../README.md)
- [Exemplos de Código](../exemplos/)
- [Tutoriais](../tutoriais.md)

---

## 📄 Licença

MIT License - Veja cada arquivo individual para detalhes específicos.
