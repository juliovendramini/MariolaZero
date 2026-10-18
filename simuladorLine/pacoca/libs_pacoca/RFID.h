/*
 * RFID.h - Leitor RFID MFRC522 com interface I2C (módulo nulllab/Emakefun, endereço 0x28)
 * para o brick Paçoca, usando SoftWire em qualquer uma das 5 portas I2C.
 *
 * Baseado na biblioteca MFRC522 (Miguel Balboa / Søren Thing Andersen) e na
 * versão I2C de Ahmet Remzi Ozcan usada pela nulllab
 * (https://github.com/nulllaborg/rfid), reescrita e reduzida para o brick.
 *
 * Cartões suportados: MIFARE Classic 1K/4K/Mini (S50/S70), MIFARE Ultralight
 * e NTAG21x (chaveiros e adesivos). Para os outros (cartão de ônibus com
 * DESFire, celular) dá para ler o UID, mas não os dados.
 *
 * Uso:
 *   #define SUPORTE_RFID 1
 *   #include "brickSimples.h"
 *
 *   RFID rfid = RFID(PORTA_I2C_2);
 *   brick.adiciona(rfid);
 *
 *   if (rfid.cartaoNovo()) {            // true uma vez quando um cartão chega
 *       rfid.imprimeUid();              // ex.: "UID: 04:A2:3B:1C"
 *       if (rfid.uid32() == 0x04A23B1C) { ... }
 *   }
 *   if (rfid.cartaoPresente()) { ... }  // true enquanto houver cartão perto
 *
 *   rfid.escreveTexto(1, "VITIMA");     // até 16 caracteres no bloco 1
 *   char txt[17]; rfid.lerTexto(1, txt);
 *
 * Cada porta tem seu próprio barramento SoftWire, então dá para usar até 5
 * leitores ao mesmo tempo (todos com o endereço 0x28).
 *
 * Tempo (estimado com o SoftWire a ~90 kHz): cartaoPresente()/cartaoNovo()
 * ~25 ms com cartão e ~13 ms sem cartão; lerTexto() ~8-15 ms; escreveTexto()
 * ~15 ms. Nada disso desliga as interrupções (pode usar junto com a voz).
 */
#ifndef _RFID_H_
#define _RFID_H_

#include <Arduino.h>
#include "SoftWire.h"
#include "portas.h"

#define RFID_ENDERECO_PADRAO 0x28
#define RFID_UID_MAX 10

class RFID {
public:
    /* resultado das operações */
    enum Status : uint8_t {
        OK = 0,
        ERRO,            /* erro de comunicação com o cartão */
        COLISAO,         /* mais de um cartão no campo */
        TEMPO_ESGOTADO,  /* nenhum cartão respondeu */
        SEM_ESPACO,      /* resposta maior que o buffer */
        ERRO_CRC,
        NACK,            /* o cartão recusou (ex.: bloco protegido) */
        SEM_CARTAO,      /* nenhum cartão selecionado */
        AUTENTICACAO,    /* chave errada */
        PROIBIDO,        /* bloco protegido pela biblioteca (fabricante/trailer) */
        NAO_SUPORTADO    /* tipo de cartão sem suporte para esta operação */
    };

    enum Tipo : uint8_t {
        TIPO_DESCONHECIDO = 0,
        TIPO_MIFARE_MINI,
        TIPO_MIFARE_1K,
        TIPO_MIFARE_4K,
        TIPO_ULTRALIGHT,      /* também NTAG213/215/216 */
        TIPO_MIFARE_PLUS,
        TIPO_ISO_14443_4,     /* DESFire, cartões bancários, celulares */
        TIPO_NAO_COMPLETO
    };

    RFID(PortaI2C porta, uint8_t endereco = RFID_ENDERECO_PADRAO);

    /* Chamado pelo brick.adiciona(). Trava com mensagem se o leitor não responder. */
    bool inicializa();

    /* ---------- detecção ---------- */
    /* true enquanto houver um cartão perto da antena (atualiza o UID) */
    bool cartaoPresente();
    /* true uma vez para cada cartão que chega (ou troca), mesmo que ele tenha
     * sido visto antes por cartaoPresente() */
    bool cartaoNovo();
    /* espera um cartão por até timeoutMs (0 = para sempre) */
    bool esperaCartao(uint32_t timeoutMs = 0);

    /* ---------- UID do último cartão lido ---------- */
    uint8_t tamanhoUid() { return _uidTam; }            /* 4, 7 ou 10 bytes */
    uint8_t byteUid(uint8_t i) { return i < _uidTam ? _uid[i] : 0; }
    const uint8_t *uid() { return _uid; }
    uint32_t uid32();                                    /* 4 primeiros bytes */
    bool uidIgual(const uint8_t *outro, uint8_t tamanho);
    bool uidIgual(uint32_t outro) { return uid32() == outro; }
    void imprimeUid(Print &saida = Serial);
    Tipo tipo() { return _tipo; }
    const __FlashStringHelper *nomeTipo();

    /* ---------- dados (blocos de 16 bytes) ----------
     * MIFARE Classic: bloco 0..63 (1K). O bloco 0 e os blocos de chave
     *   (3, 7, 11, ...) são protegidos contra escrita. Usa a chave A padrão
     *   FF FF FF FF FF FF (mude com defineChave()).
     * Ultralight/NTAG: bloco N = páginas 4N..4N+3. O bloco 0 (UID e
     *   travas) é protegido contra escrita. Bloco 1 em diante é livre.
     */
    Status lerBloco(uint8_t bloco, uint8_t dados[16]);
    Status escreveBloco(uint8_t bloco, const uint8_t dados[16]);
    Status escreveTexto(uint8_t bloco, const char *texto);              /* até 16 caracteres */
    Status lerTexto(uint8_t bloco, char texto[17]);
    void defineChave(const uint8_t chave[6], bool chaveB = false);

    /* ---------- leitor ---------- */
    uint8_t versao();                 /* 0x91/0x92 = MFRC522, 0x88 = clone FM17522 */
    void ganhoAntena(uint8_t nivel);  /* 0 (18 dB) .. 7 (48 dB). Mais ganho = mais alcance */
    void ligaAntena();
    void desligaAntena();             /* economiza ~10 mA */
    Status ultimoStatus() { return _status; }
    const __FlashStringHelper *textoStatus(Status s);

    /* ---------- baixo nível (para quem quiser ir além) ---------- */
    void escreveRegistrador(uint8_t reg, uint8_t valor);
    uint8_t lerRegistrador(uint8_t reg);
    SoftWire *getBus() { return bus; }

private:
    SoftWire *bus;
    uint8_t sda, scl, endereco;
    char descricaoPorta[6];
    bool inicializado;

    uint8_t _uid[RFID_UID_MAX];
    uint8_t _uidTam;
    uint8_t _sak;
    Tipo _tipo;
    bool _selecionado;          /* cartão ativo (pronto para ler/escrever) */
    bool _presenteAntes;
    uint8_t _uidAnterior[RFID_UID_MAX];
    uint8_t _uidAnteriorTam;
    uint8_t _chave[6];
    bool _chaveB;
    int16_t _setorAutenticado;  /* -1 = nenhum */
    Status _status;

    void escreveRegistrador(uint8_t reg, uint8_t n, const uint8_t *valores);
    void lerRegistrador(uint8_t reg, uint8_t n, uint8_t *valores);
    void setaBits(uint8_t reg, uint8_t mascara);
    void limpaBits(uint8_t reg, uint8_t mascara);
    void reset();
    void tempoLimite(uint16_t ms);
    static void calculaCRC(const uint8_t *dados, uint8_t n, uint8_t resultado[2]);  /* CRC_A em software */
    Status comunica(uint8_t comando, uint8_t esperaIrq, const uint8_t *envia, uint8_t nEnvia,
                    uint8_t *recebe, uint8_t *nRecebe, uint8_t *bitsValidos, bool confereCRC);
    Status transcepcao(const uint8_t *envia, uint8_t nEnvia, uint8_t *recebe, uint8_t *nRecebe,
                       uint8_t *bitsValidos = NULL, bool confereCRC = false);
    Status requisita(uint8_t comando);      /* REQA (0x26) ou WUPA (0x52) */
    Status seleciona();
    void dorme();                           /* HLTA + fim da criptografia */
    Status autentica(uint8_t bloco);
    void paraCripto();
    Status mifareLer(uint8_t blocoOuPagina, uint8_t dados[18]);
    Status mifareTransacao(const uint8_t *envia, uint8_t n);
    Status preparaCartao();
    uint8_t _faltas;            /* leituras seguidas sem cartão */
    bool _novoPendente;         /* chegou cartão desde o último cartaoNovo() */
    void registraPresenca(bool presente);
    uint16_t _tempoAtual;       /* timeout do timer do MFRC522 em ms */
};

#endif
