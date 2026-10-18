// Seguidor de linha de exemplo para a Rescue Line com o brick Paçoca.
//
// Ponto de partida, não a solução:
//   * PID na posição da linha (4 canais de reflexão do Pro1616)
//   * interseções: marcadores verdes nos sensores de cor da esquerda/direita (os dois = meia-volta)
//   * curva de 90° sem verde: confere se a linha continua reto; se não, gira para o lado do preto
//   * gap: segue reto pelo giroscópio até achar a linha de novo
//   * obstáculo: VL53 da frente -> contorna pela direita
//   * chegada: fita vermelha -> para (a regra pede mais de 5 s parado)
//
// O Paçoca não tem encoder: as distâncias das manobras são por TEMPO (andaMm usa MM_POR_S, a
// velocidade do robô com potência VEL_MANOBRA, e PARTIDA_MS; meça no robô de vocês: os valores
// daqui são do motor amarelo no simulador) e os giros são pelo BMI160.
// Rode uma vez com CALIBRA_GIRO 1 com o robô parado para gravar o viés do giroscópio na EEPROM.
//
// Portas (iguais às do robo_pacoca_*.json do simulador):
//   M1 = motor esquerdo, M2 = motor direito (montado espelhado: MOTOR_INVERTIDO)
//   porta 3 = Pro1616 (serial), porta 5 = BMI160 (I2C), porta 1 = VL53L0X da frente (I2C)

#define SUPORTE_MOTOR 1
#define SUPORTE_SENSOR_LINHA 1
#define SUPORTE_SENSOR_BMI160 1
#define SUPORTE_SENSOR_VL53L0X 1

#include "brickSimples.h"

#define CALIBRA_GIRO 1          // 1 = calibra o giroscópio no começo (robô parado!)

Motor motorEsq(PORTA_MOTOR_1, MOTOR_NORMAL);
Motor motorDir(PORTA_MOTOR_2, MOTOR_INVERTIDO);
SensorLinha linha(PORTA_SERIAL_3);
BMI160 giro(PORTA_I2C_5);
VL53L0X distFrente(PORTA_I2C_1);

// ---------------------------------------------------------------- ajustes
const int VEL = 45;                 // velocidade base (-100 a 100)
const float KP = 0.22;              // erro da linha vai de -150 a 150
const float KD = 0.9;
const uint8_t PRETO = 50;           // reflexão abaixo disso = canal vendo preto (0 preto, ~100 branco)
const uint16_t DIST_OBSTACULO = 75; // mm
const int VEL_MANOBRA = 50;
const float MM_POR_S = 215.0;       // mm/s andando reto com VEL_MANOBRA (MEDIR NO ROBÔ)
const uint32_t PARTIDA_MS = 90;     // tempo que o robô perde acelerando a partir do parado (MEDIR)
const uint16_t GAP_MAX_MM = 280;    // gap da regra: até 20 cm
const uint32_t JANELA_VERDE = 700;  // ms: verde visto há pouco ainda vale na interseção

// ---------------------------------------------------------------- estado
int16_t erroAnt = 0;
bool segurandoReto = false;
int16_t zReto = 0;
uint32_t verdeEsqEm = 0;
uint32_t verdeDirEm = 0;
bool chegou = false;

// ---------------------------------------------------------------- utilidades
void anda(int esq, int dir) { brick.potenciaMotores(constrain(esq, -100, 100), constrain(dir, -100, 100)); }
void para() { brick.pararMotores(); }            // motores soltos
void freia() { brick.frearMotores(); }           // motores em curto: o robô para logo
int16_t z() { return giro.getEixoZ() / 10; }     // getEixoZ() é em décimos de grau; + = girou para a esquerda
bool pretoNoMeio() { return linha.getReflexao(1) < PRETO || linha.getReflexao(2) < PRETO; }
bool algumPreto() {
    for (uint8_t i = 0; i < 4; i++)
        if (linha.getReflexao(i) < PRETO) return true;
    return false;
}

// gira no lugar até o giroscópio andar 'graus' (+ = esquerda)
void gira(int16_t graus) {
    int16_t alvo = z() + graus;
    uint32_t limite = millis() + 4000;
    while (millis() < limite) {
        brick.atualiza();
        int16_t e = alvo - z();
        if (abs(e) <= 3) break;
        int p = constrain(e * 1.5, -40, 40);
        if (abs(p) < 28) p = p > 0 ? 28 : -28;    // abaixo disso o motor nem sai do lugar
        anda(-p, p);
    }
    freia();
    brick.espera(60);
}

// anda reto 'mm' (negativo = de ré) segurando a direção pelo giroscópio.
// paraSe: função opcional que encerra antes (devolve true)
bool andaMm(int16_t mm, bool (*paraSe)() = nullptr) {
    int16_t z0 = z();
    int sentido = mm >= 0 ? 1 : -1;
    uint32_t dur = (uint32_t)(abs(mm) / MM_POR_S * 1000.0) + PARTIDA_MS;
    uint32_t fim = millis() + dur;
    while (millis() < fim) {
        brick.atualiza();
        if (paraSe && paraSe()) {
            freia();
            return true;
        }
        int corr = constrain((z0 - z()) * 4, -35, 35);   // os motores não são iguais: o giro corrige
        anda(sentido * VEL_MANOBRA - corr, sentido * VEL_MANOBRA + corr);
    }
    freia();
    return false;
}

// gira (sentido +1 = esquerda) até os canais do meio verem a linha
bool procuraLinhaGirando(int sentido, int16_t maxGraus) {
    int16_t z0 = z();
    uint32_t limite = millis() + 5000;
    while (abs(z() - z0) < maxGraus && millis() < limite) {
        brick.atualiza();
        if (pretoNoMeio()) {
            freia();
            return true;
        }
        anda(-30 * sentido, 30 * sentido);
    }
    freia();
    return false;
}

// fita vermelha da chegada em pelo menos 2 dos 3 sensores de cor
bool vermelho() {
    uint8_t n = 0;
    for (uint8_t s = SENSOR_COR_ESQUERDA; s <= SENSOR_COR_DIREITA; s++)
        if (linha.getCor(s) == COR_VERMELHO) n++;
    return n >= 2;
}

bool linhaOuVermelho() { return algumPreto() || vermelho(); }

void olhaVerde() {
    uint32_t agora = millis();
    if (linha.getCor(SENSOR_COR_ESQUERDA) == COR_VERDE) verdeEsqEm = agora;
    if (linha.getCor(SENSOR_COR_DIREITA) == COR_VERDE) verdeDirEm = agora;
}

bool verdeEsq() { return verdeEsqEm && millis() - verdeEsqEm < JANELA_VERDE; }
bool verdeDir() { return verdeDirEm && millis() - verdeDirEm < JANELA_VERDE; }

// ---------------------------------------------------------------- situações
// A fileira de reflexão passou por uma faixa preta larga: cruzamento, T ou curva de 90°.
void intersecao(int ladoPreto) {
    olhaVerde();
    bool e = verdeEsq(), d = verdeDir();
    if (e || d) {
        andaMm(75);                                  // o centro do robô chega no cruzamento
        if (e && d) {
            Serial.println(F("verde dos dois lados: meia-volta"));
            gira(150);
            procuraLinhaGirando(+1, 90);
        } else if (e) {
            Serial.println(F("verde a esquerda"));
            gira(45);
            procuraLinhaGirando(+1, 100);
        } else {
            Serial.println(F("verde a direita"));
            gira(-45);
            procuraLinhaGirando(-1, 100);
        }
        verdeEsqEm = verdeDirEm = 0;
        return;
    }
    // sem verde: passa a faixa e vê se a linha continua reto
    andaMm(30);
    if (pretoNoMeio()) {
        Serial.println(F("intersecao sem verde: reto"));
        return;
    }
    Serial.println(F("curva fechada"));
    andaMm(45);
    procuraLinhaGirando(ladoPreto, 120);
}

// a linha sumiu: segue reto pelo giroscópio até achar de novo
void gap() {
    Serial.println(F("gap? seguindo reto"));
    if (andaMm(GAP_MAX_MM, linhaOuVermelho)) return;     // a linha pode acabar na fita vermelha
    Serial.println(F("linha perdida: procurando"));
    andaMm(-GAP_MAX_MM);
    if (!procuraLinhaGirando(+1, 60)) procuraLinhaGirando(-1, 120);
}

// obstáculo na frente: contorna pela direita
void obstaculo() {
    Serial.println(F("obstaculo: contornando"));
    andaMm(-30);
    gira(-90);
    andaMm(170);
    gira(90);
    andaMm(420);                     // passa o obstáculo inteiro (robô + obstáculo + folga)
    gira(90);
    andaMm(260, algumPreto);
    andaMm(60);
    procuraLinhaGirando(-1, 120);
}

// ---------------------------------------------------------------- programa
void setup() {
    brick.inicializa();                  // obrigatório, sempre a primeira linha
    brick.adiciona(motorEsq, motorDir);
    brick.adiciona(linha);
    brick.adiciona(giro);
    brick.adiciona(distFrente);
#if CALIBRA_GIRO
    giro.calibrar();
#endif
    Serial.println(F("Aperte o botao do brick para comecar"));
    while (!brick.botaoApertado()) brick.atualiza();
    while (brick.botaoApertado()) brick.atualiza();
    Serial.println(F("Comecou!"));
}

void loop() {
    brick.atualiza();                    // obrigatório, sempre a primeira linha
    if (chegou) {
        para();
        return;
    }

    uint8_t ir[4];
    linha.getReflexoes(ir);
    olhaVerde();

    // chegada: fita vermelha
    if (vermelho()) {
        Serial.println(F("fita vermelha: chegada!"));
        chegou = true;
        para();
        return;
    }

    if (distFrente.getDistancia() < DIST_OBSTACULO) {
        obstaculo();
        erroAnt = 0;
        return;
    }

    // inclinação pelo acelerômetro: ~45 x seno do ângulo (rampa de 25° ~ 19)
    int16_t incl = max(abs(giro.getPlanoX()), abs(giro.getPlanoY()));
    uint8_t mx = max(max(ir[0], ir[1]), max(ir[2], ir[3]));
    uint8_t mn = min(min(ir[0], ir[1]), min(ir[2], ir[3]));
    // pé e topo da rampa, lombada: o sensor sai da altura normal e TUDO fica escuro por igual.
    // Leitura escura e sem contraste não é linha: segura a direção pelo giroscópio.
    bool semContraste = mx < 70 && mx - mn < 30;
    if (semContraste && incl < 2 && (verdeEsq() || verdeDir())) {
        // robô nivelado, tudo preto e verde visto há pouco: é a faixa de uma interseção
        intersecao(verdeEsq() ? +1 : -1);
        erroAnt = 0;
        return;
    }
    if (semContraste) {
        if (!segurandoReto) {
            segurandoReto = true;
            zReto = z();
        }
        int corr = constrain((zReto - z()) * 3, -30, 30);
        anda(VEL - corr, VEL + corr);
        return;
    }
    segurandoReto = false;
    bool transicao = incl >= 2 && incl <= 14;    // entrando ou saindo de rampa

    bool p[4];
    for (uint8_t i = 0; i < 4; i++) p[i] = ir[i] < PRETO;

    // faixa larga: um canal da ponta + os dois do meio (curva de 90°, T, cruzamento)
    if (!transicao && (p[0] || p[3]) && p[1] && p[2]) {
        int lado;
        if (p[0] && !p[3]) lado = +1;
        else if (p[3] && !p[0]) lado = -1;
        else lado = ir[0] < ir[3] ? +1 : -1;
        intersecao(lado);
        erroAnt = 0;
        return;
    }

    if (!algumPreto() && transicao) {
        anda(VEL, VEL);                           // transição de rampa: reto
        return;
    }
    if (!algumPreto()) {
        if (abs(erroAnt) > 60) {
            // a linha estava escapando para um lado: é curva, não gap
            int16_t z0 = z();
            if (procuraLinhaGirando(erroAnt > 0 ? -1 : +1, 110)) {
                erroAnt = 0;
                return;
            }
            gira(z0 - z());
        }
        gap();
        erroAnt = 0;
        return;
    }

    int16_t erro = linha.getPosicaoLinha();      // + = linha à direita
    int16_t d = erro - erroAnt;
    erroAnt = erro;
    int corr = (int)(KP * erro + KD * d);
    int vel = VEL - abs(erro) / 12;               // mais devagar quando a linha foge do centro
    if (incl > 8) vel += 15;                      // rampa (subindo ou descendo: o PID corrige)
    anda(vel + corr, vel - corr);
}
