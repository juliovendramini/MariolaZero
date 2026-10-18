/*
 * musica.h - Toca músicas no formato RTTTL (toque de celular antigo) no buzzer
 * passivo, em segundo plano (não trava o programa).
 *
 * Na porta S3 (D11 / OC2A) o som sai pelo PWM do Timer2: dá para mudar o
 * volume e o timbre (quadrada, triangular, senoidal, dente de serra).
 * Nas outras portas (S1, S2, S4) a música também funciona, mas como onda
 * quadrada simples, sempre no volume máximo.
 *
 * Uso:
 *   #define SUPORTE_MUSICA 1
 *   #include "brickSimples.h"
 *
 *   Musica musica = Musica(PORTA_BUZZER_3);
 *   brick.adiciona(musica);
 *   musica.tocar(MUSICA_ODE_ALEGRIA);                       // volta na hora
 *   musica.tocar(F("teste:d=8,o=5,b=140:c,e,g,4c6"));       // RTTTL próprio
 *   musica.nota(440, 300);                                  // uma nota (Hz, ms)
 *   musica.aguarda();                                       // espera acabar
 *
 * Formato RTTTL:  nome:d=duração,o=oitava,b=bpm:notas
 *   nota = [duração]letra[#][.][oitava]   ex.: 8c#6  4.e  2p (pausa)
 * Há milhares de músicas nesse formato na internet (procure "RTTTL").
 *
 * Usa o Timer2: não toca junto com a Voz e pausa os servos enquanto toca.
 */
#ifndef MUSICA_H
#define MUSICA_H

#include "motorAudio.h"

/* ---------------------------------------------------- músicas prontas (domínio público) */
static const char MUSICA_ODE_ALEGRIA[] PROGMEM =
    "OdeAlegria:d=4,o=5,b=120:e,e,f,g,g,f,e,d,c,c,d,e,e.,8d,2d,"
    "e,e,f,g,g,f,e,d,c,c,d,e,d.,8c,2c";
static const char MUSICA_BRILHA_ESTRELINHA[] PROGMEM =
    "Brilha:d=4,o=5,b=120:c,c,g,g,a,a,2g,f,f,e,e,d,d,2c,"
    "g,g,f,f,e,e,2d,g,g,f,f,e,e,2d,c,c,g,g,a,a,2g,f,f,e,e,d,d,2c";
static const char MUSICA_PARABENS[] PROGMEM =
    "Parabens:d=4,o=5,b=100:8.g,16g,a,g,c6,2b,8.g,16g,a,g,d6,2c6,"
    "8.g,16g,g6,e6,c6,b,a,8.f6,16f6,e6,c6,d6,2c6";
static const char MUSICA_JINGLE_BELLS[] PROGMEM =
    "JingleBells:d=4,o=5,b=170:e,e,2e,e,e,2e,e,g,c.,8d,1e,"
    "f,f,f.,8f,f,e,e,8e,8e,e,d,d,e,2d,2g";
static const char MUSICA_FUR_ELISE[] PROGMEM =
    "FurElise:d=8,o=5,b=125:e6,d#6,e6,d#6,e6,b,d6,c6,4a,p,c,e,a,4b,p,e,g#,b,4c6,p,e,"
    "e6,d#6,e6,d#6,e6,b,d6,c6,4a,p,c,e,a,4b,p,e,c6,b,2a";

/* efeitos curtos */
static const char EFEITO_SUCESSO[] PROGMEM = "Sucesso:d=16,o=6,b=180:c,e,g,4c7";
static const char EFEITO_ERRO[]    PROGMEM = "Erro:d=8,o=5,b=140:g,e,4c";
static const char EFEITO_ALERTA[]  PROGMEM = "Alerta:d=16,o=6,b=200:a,p,a,p,a,p,4a";
static const char EFEITO_INICIO[]  PROGMEM = "Inicio:d=16,o=5,b=160:c,e,g,c6,e6,4g6";

class Musica {
private:
    uint8_t pino;
    bool invertido;
    bool inicializado;
    char descricaoPorta[6];

    /* lê o cabeçalho "nome:d=4,o=5,b=120:" e posiciona nas notas */
    bool preparaRTTTL(const char *r) {
        const char *p = r;
        char c;
        while ((c = pgm_read_byte(p)) && c != ':') p++;
        if (!c) { Serial.println(F("Erro: RTTTL sem ':'")); return false; }
        p++;
        mus_padDur = 4; mus_padOit = 6;
        uint16_t bpm = 63;
        while ((c = pgm_read_byte(p)) && c != ':') {
            if (c == ' ' || c == ',') { p++; continue; }
            char chave = c;
            p++;
            if (pgm_read_byte(p) == '=') p++;
            uint16_t v = mus_lerNumero(&p);
            if (chave == 'd' || chave == 'D') mus_padDur = (uint8_t)(v ? v : 4);
            else if (chave == 'o' || chave == 'O') mus_padOit = (uint8_t)v;
            else if (chave == 'b' || chave == 'B') bpm = v ? v : 63;
        }
        if (!c) { Serial.println(F("Erro: RTTTL sem o segundo ':'")); return false; }
        p++;
        mus_msSemibreve = (uint16_t)(240000UL / bpm);
        mus_inicioNotas = p;
        return true;
    }

public:
    enum Timbre { QUADRADA = MUS_QUADRADA, TRIANGULAR = MUS_TRIANGULAR,
                  SENOIDAL = MUS_SENOIDAL, DENTE_DE_SERRA = MUS_DENTE_DE_SERRA };

    Musica(PortaBuzzer porta, bool invertido = true) {
        pino = porta.pino;
        this->invertido = invertido;
        inicializado = false;
        strcpy(descricaoPorta, porta.descricao);
    }

    void inicializa() {
        audio_configuraPino(pino, invertido);
        inicializado = true;
        Serial.print(F("Musica inicializada na porta "));
        Serial.print(descricaoPorta);
        if (pino != AUDIO_PINO_OC2A) Serial.print(F(" (sem volume/timbre: so a S3 tem PWM do Timer2)"));
        Serial.println();
    }

    /* Toca um RTTTL guardado na flash (PROGMEM). Não espera terminar. */
    void tocar(const char *rtttl) {
        if (!inicializado) { Serial.println(F("Erro: Musica nao inicializada!")); return; }
        audio_configuraPino(pino, invertido);     /* para qualquer som anterior */
        if (!preparaRTTTL(rtttl)) return;
        mus_ptr = mus_inicioNotas;
        mus_restante = 0;
        mus_inc = 0;
        mus_amp = 0;
        mus_inicia();            /* a primeira nota é lida no primeiro ms */
    }
    void tocar(const __FlashStringHelper *rtttl) { tocar((const char *)rtttl); }

    /* Toca e espera terminar. */
    void tocarAteOFim(const char *rtttl) { tocar(rtttl); aguarda(); }
    void tocarAteOFim(const __FlashStringHelper *rtttl) { tocar((const char *)rtttl); aguarda(); }

    /* Uma nota: frequência em Hz (0 = silêncio) e duração em ms. Não espera. */
    void nota(uint16_t frequencia, uint16_t duracaoMs) {
        if (!inicializado) { Serial.println(F("Erro: Musica nao inicializada!")); return; }
        audio_configuraPino(pino, invertido);
        mus_ptr = 0;
        mus_comecaNota(mus_incDaFrequencia(frequencia), duracaoMs);
        mus_pausa = (frequencia == 0) ? duracaoMs : 0;
        mus_inicia();
    }
    void notaAteOFim(uint16_t frequencia, uint16_t duracaoMs) { nota(frequencia, duracaoMs); aguarda(); }

    bool tocando() { return audio_modo == AUDIO_MUSICA; }
    void aguarda() { while (audio_modo == AUDIO_MUSICA) { } }

    void parar() {
        if (audio_modo == AUDIO_MUSICA) {
            mus_tocando = 0;
            audio_libera();
        }
    }

    /* Repete a música sem parar até chamar parar(). */
    void repetir(bool sim) { mus_repetir = sim ? 1 : 0; }

    /* Volume 0..100 % (só na porta S3). */
    void volume(uint8_t porcento) {
        if (porcento > 100) porcento = 100;
        mus_ampMax = (uint8_t)((porcento * 255U) / 100U);
    }

    /* Timbre (só na porta S3): Musica::QUADRADA (mais alto), TRIANGULAR,
     * SENOIDAL (mais suave) ou DENTE_DE_SERRA. */
    void timbre(Timbre t) { mus_timbre = (uint8_t)t; }

    /* Notas com ataque forte que vão sumindo, como piano (só na S3). */
    void decaimento(bool sim) { mus_decai = sim ? 1 : 0; }
};

#endif /* MUSICA_H */
