/*
 * voz.h - Fala sintetizada por LPC no buzzer passivo do Paçoca.
 *
 * Só funciona na porta S3 (D11 / OC2A / MOSI): o áudio sai pelo PWM do Timer2.
 *
 * As falas são geradas no PC com ferramentas/gerar_falas.py, que cria o
 * arquivo falas.h com vetores em PROGMEM (~150-250 bytes por segundo de fala).
 *
 * Uso:
 *   #define SUPORTE_VOZ 1
 *   #define SUPORTE_VOZ_SERIAL 1      // opcional: receber fala pela serial (+145 B de RAM)
 *   #include "brickSimples.h"
 *   #include "falas.h"
 *
 *   Voz voz = Voz(PORTA_BUZZER_3);
 *   brick.adiciona(voz);
 *   voz.falar(FALA_VITIMA_ENCONTRADA);       // espera terminar
 *   voz.iniciaFala(FALA_OBSTACULO);          // volta na hora, fala em segundo plano
 *
 * Enquanto fala: ~40% da CPU vai para o decodificador, servos ficam sem pulso
 * e o Timer2 fica ocupado (veja motorAudio.h).
 */
#ifndef VOZ_H
#define VOZ_H

#include "motorAudio.h"

class Voz {
private:
    uint8_t pino;
    bool invertido;
    bool inicializado;
    char descricaoPorta[6];

#ifdef SUPORTE_VOZ_SERIAL
    /* recepção de pacotes: A5 tipo tamanho dados... soma */
    uint8_t rxEstado = 0, rxTipo = 0, rxTam = 0, rxCont = 0, rxSoma = 0;
    uint8_t rxPosicao = 0;          /* onde os dados estão sendo escritos (ainda não confirmados) */
    uint8_t rxErro = 0;
    uint32_t rxUltimoMs = 0;
    bool streamAtivo = false;
#endif

    bool podeFalar() {
        if (!inicializado) { Serial.println(F("Erro: Voz nao inicializada!")); return false; }
        if (pino != AUDIO_PINO_OC2A) return false;
        return true;
    }

public:
    Voz(PortaBuzzer porta, bool invertido = true) {
        pino = porta.pino;
        this->invertido = invertido;
        inicializado = false;
        strcpy(descricaoPorta, porta.descricao);
    }

    void inicializa() {
        if (pino != AUDIO_PINO_OC2A) {
            Serial.print(F("Erro: a voz so funciona na porta S3 (PWM do Timer2). Porta usada: "));
            Serial.println(descricaoPorta);
            return;
        }
        audio_configuraPino(pino, invertido);
        inicializado = true;
        Serial.print(F("Voz inicializada na porta "));
        Serial.println(descricaoPorta);
    }

    /* Fala gravada na flash (vetor PROGMEM do falas.h) e espera terminar. */
    void falar(const uint8_t *fala) {
        iniciaFala(fala);
        aguarda();
    }

    /* Começa a falar e volta na hora. */
    void iniciaFala(const uint8_t *fala) {
        if (!podeFalar()) return;
        audio_configuraPino(pino, invertido);
        lpc_iniciaFlash(&voz_dec, fala);
        voz_inicia();
    }

    /* Fala que está num vetor em RAM (ex.: recebida inteira pela serial). */
    void falarRam(const uint8_t *dados, uint16_t tamanho) {
        iniciaFalaRam(dados, tamanho);
        aguarda();
    }
    void iniciaFalaRam(const uint8_t *dados, uint16_t tamanho) {
        if (!podeFalar()) return;
        audio_configuraPino(pino, invertido);
        lpc_iniciaRam(&voz_dec, dados, tamanho);
        voz_inicia();
    }

    bool falando() { return voz_ativa(); }

    void aguarda() { while (voz_ativa()) { } }

    void parar() {
        if (voz_ativa()) {
            voz_estado = VOZ_PARADA;
            audio_libera();
        }
    }

    /* Volume em %: 100 = sem distorção. Acima de 100 os picos são cortados,
     * o que deixa a fala mais alta (bom para buzzer). Padrão 200, máximo 400. */
    void volume(uint16_t porcento) {
        if (porcento > 400) porcento = 400;
        uint16_t g = (porcento * 64UL + 50) / 100;
        voz_ganho = (g > 255) ? 255 : (uint8_t)g;
    }

    /* Quantas amostras não ficaram prontas a tempo na última fala (diagnóstico:
     * deve ser 0; se não for, algo está desligando as interrupções). */
    uint16_t atrasos() { return voz_atrasos; }

#ifdef SUPORTE_VOZ_SERIAL
    /*
     * Recebe fala pela serial (protocolo do ferramentas/enviar_fala.py).
     * Chame sempre no loop (não bloqueia). Pacote:
     *   0xA5, tipo, tamanho, dados[tamanho], soma   (soma = tipo+tamanho+dados, 8 bits)
     *   tipo 'D' = dados de fala, 'F' = fim da fala, 'P' = parar, 'S' = só status
     * Resposta a cada pacote: 0x5A, código, bytes livres, estado, verificação
     *   verificação = (código + livres + estado) XOR 0xA5
     *   código 0 = ok, 1 = soma errada, 2 = sem espaço, 3 = tipo desconhecido
     *   estado bit0 = falando
     */
    void atualizaSerial(Stream &s) {
        while (s.available()) {
            uint8_t b = (uint8_t)s.read();
            rxUltimoMs = millis();
            switch (rxEstado) {
            case 0:
                if (b == 0xA5) rxEstado = 1;
                break;
            case 1:
                rxTipo = b; rxSoma = b; rxEstado = 2;
                break;
            case 2:
                rxTam = b; rxSoma += b; rxCont = 0; rxErro = 0;
                if (rxTipo == 'D') {
                    if (!streamAtivo) comecaStream();
                    rxPosicao = voz_fifo.escreve;
                }
                rxEstado = (rxTam == 0) ? 4 : 3;
                break;
            case 3:
                rxSoma += b;
                if (rxTipo == 'D') {
                    /* escreve sem confirmar: só vale se a soma bater */
                    uint8_t prox = (uint8_t)((rxPosicao + 1) & (LPC_TAMANHO_FIFO - 1));
                    if (prox == voz_fifo.le) rxErro = 2;
                    else { voz_fifo.buf[rxPosicao] = b; rxPosicao = prox; }
                }
                if (++rxCont >= rxTam) rxEstado = 4;
                break;
            case 4: {
                uint8_t codigo = 0;
                rxEstado = 0;
                if (b != rxSoma) codigo = 1;
                else if (rxErro) codigo = rxErro;
                else if (rxTipo == 'D') {
                    voz_fifo.escreve = rxPosicao;              /* confirma */
                    /* começa a tocar quando tiver ~0,3 s guardado */
                    if (!voz_ativa() && streamAtivo && lpc_fifoQuantidade(&voz_fifo) >= 64) iniciaStream();
                } else if (rxTipo == 'F') {
                    voz_fifo.terminou = 1;
                    if (!voz_ativa() && streamAtivo && lpc_fifoQuantidade(&voz_fifo) > 0) iniciaStream();
                    streamAtivo = false;
                } else if (rxTipo == 'P') {
                    parar();
                    streamAtivo = false;
                    lpc_fifoLimpa(&voz_fifo);
                } else if (rxTipo != 'S') codigo = 3;
                uint8_t livre = lpc_fifoLivre(&voz_fifo);
                uint8_t estado = voz_ativa() ? 1 : 0;
                s.write((uint8_t)0x5A);
                s.write(codigo);
                s.write(livre);
                s.write(estado);
                s.write((uint8_t)((codigo + livre + estado) ^ 0xA5));
                break;
            }
            }
        }
        /* pacote pela metade há muito tempo: descarta */
        if (rxEstado != 0 && (millis() - rxUltimoMs) > 200) rxEstado = 0;
    }

    /* Fica recebendo e falando até a fala terminar ou passar esperaMaxMs sem
     * chegar nada. Retorna true se falou alguma coisa. */
    bool falarDaSerial(Stream &s, uint16_t esperaMaxMs = 3000) {
        bool falou = false;
        uint32_t t0 = millis();
        rxUltimoMs = t0;
        for (;;) {
            atualizaSerial(s);
            if (voz_ativa()) falou = true;
            if (falou && !voz_ativa() && !streamAtivo) return true;
            if ((millis() - rxUltimoMs) > esperaMaxMs) {
                if (streamAtivo) { voz_fifo.terminou = 1; streamAtivo = false; }
                if (!voz_ativa()) return falou;
            }
        }
        (void)t0;
    }

private:
    void comecaStream() {
        parar();
        lpc_fifoLimpa(&voz_fifo);
        streamAtivo = true;
    }
    void iniciaStream() {
        if (!podeFalar()) return;
        audio_configuraPino(pino, invertido);
        lpc_iniciaFifo(&voz_dec, &voz_fifo);
        voz_inicia();
    }
#endif
};

#endif /* VOZ_H */
