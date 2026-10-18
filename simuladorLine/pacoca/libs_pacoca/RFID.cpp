/*
 * RFID.cpp - MFRC522 por I2C (SoftWire) para o brick Paçoca. Veja RFID.h.
 */
#include "RFID.h"

/* ------------------------------------------------ registradores do MFRC522 */
enum {
    CommandReg = 0x01, ComIEnReg = 0x02, DivIEnReg = 0x03, ComIrqReg = 0x04,
    DivIrqReg = 0x05, ErrorReg = 0x06, Status1Reg = 0x07, Status2Reg = 0x08,
    FIFODataReg = 0x09, FIFOLevelReg = 0x0A, ControlReg = 0x0C, BitFramingReg = 0x0D,
    CollReg = 0x0E, ModeReg = 0x11, TxModeReg = 0x12, RxModeReg = 0x13,
    TxControlReg = 0x14, TxASKReg = 0x15, RFCfgReg = 0x26, TModeReg = 0x2A,
    TPrescalerReg = 0x2B, TReloadRegH = 0x2C, TReloadRegL = 0x2D, VersionReg = 0x37
};
/* comandos do MFRC522 */
enum { PCD_Idle = 0x00, PCD_Transceive = 0x0C, PCD_MFAuthent = 0x0E, PCD_SoftReset = 0x0F };
/* comandos para o cartão (ISO 14443-A / MIFARE) */
enum {
    PICC_REQA = 0x26, PICC_WUPA = 0x52, PICC_CT = 0x88, PICC_SEL_CL1 = 0x93,
    PICC_SEL_CL2 = 0x95, PICC_SEL_CL3 = 0x97, PICC_HLTA = 0x50,
    MF_AUTH_A = 0x60, MF_AUTH_B = 0x61, MF_READ = 0x30, MF_WRITE = 0xA0,
    MF_ACK = 0x0A, UL_WRITE = 0xA2
};

/* tempos limite do timer interno (o cartão responde em microssegundos) */
#define RFID_TEMPO_CURTO_MS  3     /* WUPA, anticolisão, seleção */
#define RFID_TEMPO_HALT_MS   1     /* HLTA: o certo é não responder */
#define RFID_TEMPO_LONGO_MS  25    /* autenticação, leitura e escrita */

RFID::RFID(PortaI2C porta, uint8_t endereco) {
    bus = NULL;
    sda = porta.sda;
    scl = porta.scl;
    this->endereco = endereco;
    strncpy(descricaoPorta, porta.descricao, sizeof(descricaoPorta) - 1);
    descricaoPorta[sizeof(descricaoPorta) - 1] = 0;
    inicializado = false;
    _uidTam = 0;
    _sak = 0;
    _tipo = TIPO_DESCONHECIDO;
    _selecionado = false;
    _presenteAntes = false;
    _uidAnteriorTam = 0;
    _faltas = 0;
    _novoPendente = false;
    _tempoAtual = 0;
    for (uint8_t i = 0; i < 6; i++) _chave[i] = 0xFF;   /* chave de fábrica */
    _chaveB = false;
    _setorAutenticado = -1;
    _status = OK;
}

/* ================================================================ I2C */
void RFID::escreveRegistrador(uint8_t reg, uint8_t valor) {
    bus->beginTransmission(endereco);
    bus->write(reg);
    bus->write(valor);
    bus->endTransmission();
}

void RFID::escreveRegistrador(uint8_t reg, uint8_t n, const uint8_t *valores) {
    bus->beginTransmission(endereco);
    bus->write(reg);
    bus->write(valores, n);               /* o MFRC522 não incrementa o endereço: ideal p/ FIFO */
    bus->endTransmission();
}

uint8_t RFID::lerRegistrador(uint8_t reg) {
    bus->beginTransmission(endereco);
    bus->write(reg);
    bus->endTransmission();
    if (bus->requestFrom(endereco, (uint8_t)1) != 1) return 0;
    return (uint8_t)bus->read();
}

void RFID::lerRegistrador(uint8_t reg, uint8_t n, uint8_t *valores) {
    if (n == 0) return;
    bus->beginTransmission(endereco);
    bus->write(reg);
    bus->endTransmission();
    uint8_t lidos = bus->requestFrom(endereco, n);
    for (uint8_t i = 0; i < n; i++) valores[i] = (i < lidos) ? (uint8_t)bus->read() : 0;
}

void RFID::setaBits(uint8_t reg, uint8_t mascara) {
    escreveRegistrador(reg, lerRegistrador(reg) | mascara);
}

void RFID::limpaBits(uint8_t reg, uint8_t mascara) {
    escreveRegistrador(reg, lerRegistrador(reg) & (uint8_t)~mascara);
}

/* ================================================================ leitor */
void RFID::reset() {
    escreveRegistrador(CommandReg, PCD_SoftReset);
    delay(50);                                       /* partida do oscilador */
    uint32_t t0 = millis();
    while ((lerRegistrador(CommandReg) & 0x10) && (millis() - t0) < 100) { }
    _tempoAtual = 0;
}

void RFID::tempoLimite(uint16_t ms) {
    if (ms == _tempoAtual) return;
    _tempoAtual = ms;
    uint16_t recarga = ms * 40;                      /* timer de 40 kHz (25 us) */
    escreveRegistrador(TReloadRegH, recarga >> 8);
    escreveRegistrador(TReloadRegL, recarga & 0xFF);
}

bool RFID::inicializa() {
    if (bus == NULL) {
        bus = new SoftWire(sda, scl);
        bus->setTimeout_ms(10);
        bus->begin();
    }
    /* o módulo leva alguns ms para ligar: tenta por até ~0,5 s */
    uint8_t v = 0;
    for (uint8_t tentativa = 0; tentativa < 10; tentativa++) {
        bus->beginTransmission(endereco);
        if (bus->endTransmission() == 0) {
            reset();
            v = lerRegistrador(VersionReg);
            if (v != 0x00 && v != 0xFF) break;
        }
        delay(50);
    }
    if (v == 0x00 || v == 0xFF) {
        Serial.print(F("Erro: leitor RFID nao encontrado na porta "));
        Serial.println(descricaoPorta);
        while (1);
    }

    escreveRegistrador(TxModeReg, 0x00);             /* 106 kbit/s */
    escreveRegistrador(RxModeReg, 0x00);
    escreveRegistrador(TModeReg, 0x80);              /* TAuto: timer começa ao fim do envio */
    escreveRegistrador(TPrescalerReg, 0xA9);         /* 13,56 MHz / (2*169+1) = 40 kHz */
    tempoLimite(RFID_TEMPO_LONGO_MS);
    escreveRegistrador(TxASKReg, 0x40);              /* modulação 100% ASK */
    escreveRegistrador(ModeReg, 0x3D);               /* CRC com preset 0x6363 */
    ligaAntena();
    inicializado = true;

    Serial.print(F("RFID (MFRC522 versao 0x"));
    Serial.print(v, HEX);
    Serial.print(F(") encontrado na porta "));
    Serial.println(descricaoPorta);
    return true;
}

uint8_t RFID::versao() { return lerRegistrador(VersionReg); }

void RFID::ligaAntena() {
    uint8_t v = lerRegistrador(TxControlReg);
    if ((v & 0x03) != 0x03) escreveRegistrador(TxControlReg, v | 0x03);
}

void RFID::desligaAntena() {
    limpaBits(TxControlReg, 0x03);
    _selecionado = false;
    _setorAutenticado = -1;
}

void RFID::ganhoAntena(uint8_t nivel) {
    if (nivel > 7) nivel = 7;
    uint8_t v = lerRegistrador(RFCfgReg) & (uint8_t)~0x70;
    escreveRegistrador(RFCfgReg, v | (uint8_t)(nivel << 4));
}

/* CRC_A da ISO 14443-3 (polinômio x^16+x^12+x^5+1, invertido, valor inicial 0x6363).
 * Feito em software: evita ~10 transações I2C por comando. */
void RFID::calculaCRC(const uint8_t *dados, uint8_t n, uint8_t resultado[2]) {
    uint16_t crc = 0x6363;
    for (uint8_t i = 0; i < n; i++) {
        uint8_t b = dados[i] ^ (uint8_t)(crc & 0xFF);
        b ^= (uint8_t)(b << 4);
        crc = (crc >> 8) ^ ((uint16_t)b << 8) ^ ((uint16_t)b << 3) ^ ((uint16_t)b >> 4);
    }
    resultado[0] = (uint8_t)(crc & 0xFF);
    resultado[1] = (uint8_t)(crc >> 8);
}

/* Executa um comando do MFRC522 que fala com o cartão. */
RFID::Status RFID::comunica(uint8_t comando, uint8_t esperaIrq, const uint8_t *envia, uint8_t nEnvia,
                            uint8_t *recebe, uint8_t *nRecebe, uint8_t *bitsValidos, bool confereCRC) {
    uint8_t ultimosBits = bitsValidos ? *bitsValidos : 0;
    escreveRegistrador(CommandReg, PCD_Idle);
    escreveRegistrador(ComIrqReg, 0x7F);             /* limpa as interrupções */
    escreveRegistrador(FIFOLevelReg, 0x80);          /* esvazia a FIFO */
    escreveRegistrador(FIFODataReg, nEnvia, envia);
    escreveRegistrador(CommandReg, comando);
    if (comando == PCD_Transceive)
        escreveRegistrador(BitFramingReg, (uint8_t)(0x80 | ultimosBits));   /* StartSend + bits do último byte */
    else
        escreveRegistrador(BitFramingReg, 0x00);

    uint32_t t0 = millis();
    uint16_t limite = (uint16_t)(_tempoAtual + 30);
    uint8_t irq;
    for (;;) {
        irq = lerRegistrador(ComIrqReg);
        if (irq & esperaIrq) break;
        if (irq & 0x01) return TEMPO_ESGOTADO;       /* TimerIRq: o cartão não respondeu */
        if ((millis() - t0) > limite) return TEMPO_ESGOTADO;
    }

    uint8_t erro = lerRegistrador(ErrorReg);
    if (erro & 0x13) return ERRO;                    /* BufferOvfl, ParityErr, ProtocolErr */

    uint8_t validos = 0;
    if (recebe && nRecebe) {
        uint8_t n = lerRegistrador(FIFOLevelReg) & 0x7F;
        if (n > *nRecebe) return SEM_ESPACO;
        *nRecebe = n;
        lerRegistrador(FIFODataReg, n, recebe);
        if (bitsValidos || confereCRC) {
            validos = lerRegistrador(ControlReg) & 0x07;
            if (bitsValidos) *bitsValidos = validos;
        }
    }
    if (erro & 0x08) return COLISAO;

    if (recebe && nRecebe && confereCRC) {
        if (*nRecebe == 1 && validos == 4) return NACK;
        if (*nRecebe < 2 || validos != 0) return ERRO_CRC;
        uint8_t c[2];
        calculaCRC(recebe, (uint8_t)(*nRecebe - 2), c);
        if (recebe[*nRecebe - 2] != c[0] || recebe[*nRecebe - 1] != c[1]) return ERRO_CRC;
    }
    return OK;
}

RFID::Status RFID::transcepcao(const uint8_t *envia, uint8_t nEnvia, uint8_t *recebe, uint8_t *nRecebe,
                               uint8_t *bitsValidos, bool confereCRC) {
    return comunica(PCD_Transceive, 0x30, envia, nEnvia, recebe, nRecebe, bitsValidos, confereCRC);
}

/* ================================================================ cartão */
RFID::Status RFID::requisita(uint8_t comando) {
    uint8_t cmd = comando;
    uint8_t atqa[2];
    uint8_t n = 2;
    uint8_t bits = 7;                                /* REQA/WUPA são quadros de 7 bits */
    escreveRegistrador(CollReg, 0x00);              /* ValuesAfterColl = 0 */
    tempoLimite(RFID_TEMPO_CURTO_MS);
    Status s = transcepcao(&cmd, 1, atqa, &n, &bits);
    if (s != OK) return s;
    if (n != 2 || bits != 0) return ERRO;
    return OK;
}

/* Anticolisão + seleção nos níveis de cascata 1..3 (UID de 4, 7 ou 10 bytes).
 * Versão simplificada: com dois cartões no campo devolve COLISAO e tenta de novo
 * na próxima leitura. */
RFID::Status RFID::seleciona() {
    static const uint8_t sel[3] = { PICC_SEL_CL1, PICC_SEL_CL2, PICC_SEL_CL3 };
    uint8_t buf[9];
    uint8_t resp[5];
    uint8_t sak[3];
    _uidTam = 0;
    tempoLimite(RFID_TEMPO_CURTO_MS);
    for (uint8_t nivel = 0; nivel < 3; nivel++) {
        buf[0] = sel[nivel];
        buf[1] = 0x20;                               /* NVB: pede o UID inteiro deste nível */
        uint8_t n = 5, bits = 0;
        Status s = transcepcao(buf, 2, resp, &n, &bits);
        if (s != OK) return s;
        if (n != 5 || bits != 0) return ERRO;
        if ((uint8_t)(resp[0] ^ resp[1] ^ resp[2] ^ resp[3]) != resp[4]) return ERRO;   /* BCC */

        buf[1] = 0x70;                               /* SELECT */
        for (uint8_t i = 0; i < 5; i++) buf[2 + i] = resp[i];
        calculaCRC(buf, 7, &buf[7]);
        n = 3;
        s = transcepcao(buf, 9, sak, &n, NULL, true);
        if (s != OK) return s;
        if (n != 3) return ERRO;
        _sak = sak[0];

        bool incompleto = (_sak & 0x04) != 0;
        if (incompleto && resp[0] == PICC_CT) {
            for (uint8_t i = 1; i < 4 && _uidTam < RFID_UID_MAX; i++) _uid[_uidTam++] = resp[i];
            continue;
        }
        for (uint8_t i = 0; i < 4 && _uidTam < RFID_UID_MAX; i++) _uid[_uidTam++] = resp[i];
        break;
    }

    uint8_t s = _sak & 0x7F;
    if (s & 0x04)               _tipo = TIPO_NAO_COMPLETO;
    else if (s == 0x09)         _tipo = TIPO_MIFARE_MINI;
    else if ((s & 0x18) == 0x08) _tipo = TIPO_MIFARE_1K;
    else if ((s & 0x18) == 0x18) _tipo = TIPO_MIFARE_4K;
    else if (s == 0x00)         _tipo = TIPO_ULTRALIGHT;
    else if (s == 0x10 || s == 0x11) _tipo = TIPO_MIFARE_PLUS;
    else if (s & 0x20)          _tipo = TIPO_ISO_14443_4;
    else                        _tipo = TIPO_DESCONHECIDO;
    _selecionado = true;
    _setorAutenticado = -1;
    return OK;
}

void RFID::paraCripto() {
    limpaBits(Status2Reg, 0x08);                     /* MFCrypto1On = 0 */
}

void RFID::dorme() {
    uint8_t buf[4] = { PICC_HLTA, 0x00, 0, 0 };
    calculaCRC(buf, 2, &buf[2]);
    tempoLimite(RFID_TEMPO_HALT_MS);
    transcepcao(buf, 4, NULL, NULL);                 /* não responder = sucesso */
    if (_setorAutenticado >= 0) paraCripto();
    _selecionado = false;
    _setorAutenticado = -1;
}

bool RFID::cartaoPresente() {
    if (!inicializado) { _status = SEM_CARTAO; return false; }
    /* um cartão ativo não responde ao WUPA: põe para dormir antes */
    if (_selecionado) dorme();
    Status s = requisita(PICC_WUPA);
    if (s == TEMPO_ESGOTADO) s = requisita(PICC_WUPA);          /* segunda chance */
    if (s == OK || s == COLISAO) s = seleciona();
    _status = s;
    bool presente = (s == OK);
    if (!presente) _selecionado = false;
    registraPresenca(presente);
    return presente;
}

/* Guarda o histórico para o cartaoNovo(). Uma falha isolada de leitura não
 * conta como "o cartão saiu": precisa falhar 2 vezes seguidas. */
void RFID::registraPresenca(bool presente) {
    if (!presente) {
        if (_faltas < 255) _faltas++;
        if (_faltas >= 2) _presenteAntes = false;
        return;
    }
    _faltas = 0;
    if (!_presenteAntes || !uidIgual(_uidAnterior, _uidAnteriorTam)) _novoPendente = true;
    _presenteAntes = true;
    for (uint8_t i = 0; i < _uidTam; i++) _uidAnterior[i] = _uid[i];
    _uidAnteriorTam = _uidTam;
}

bool RFID::cartaoNovo() {
    cartaoPresente();
    bool novo = _novoPendente;
    _novoPendente = false;
    return novo;
}

bool RFID::esperaCartao(uint32_t timeoutMs) {
    uint32_t t0 = millis();
    while (timeoutMs == 0 || (millis() - t0) < timeoutMs) {
        if (cartaoPresente()) return true;
        delay(10);
    }
    return false;
}

uint32_t RFID::uid32() {
    uint32_t v = 0;
    for (uint8_t i = 0; i < 4 && i < _uidTam; i++) v = (v << 8) | _uid[i];
    return v;
}

bool RFID::uidIgual(const uint8_t *outro, uint8_t tamanho) {
    if (tamanho != _uidTam || _uidTam == 0) return false;
    for (uint8_t i = 0; i < tamanho; i++)
        if (outro[i] != _uid[i]) return false;
    return true;
}

void RFID::imprimeUid(Print &saida) {
    saida.print(F("UID:"));
    for (uint8_t i = 0; i < _uidTam; i++) {
        saida.print(i ? ':' : ' ');
        if (_uid[i] < 0x10) saida.print('0');
        saida.print(_uid[i], HEX);
    }
    saida.println();
}

const __FlashStringHelper *RFID::nomeTipo() {
    switch (_tipo) {
    case TIPO_MIFARE_MINI:  return F("MIFARE Mini");
    case TIPO_MIFARE_1K:    return F("MIFARE Classic 1K");
    case TIPO_MIFARE_4K:    return F("MIFARE Classic 4K");
    case TIPO_ULTRALIGHT:   return F("MIFARE Ultralight/NTAG");
    case TIPO_MIFARE_PLUS:  return F("MIFARE Plus");
    case TIPO_ISO_14443_4:  return F("ISO 14443-4 (DESFire, banco, celular)");
    case TIPO_NAO_COMPLETO: return F("UID incompleto");
    default:                return F("desconhecido");
    }
}

const __FlashStringHelper *RFID::textoStatus(Status s) {
    switch (s) {
    case OK:             return F("ok");
    case ERRO:           return F("erro de comunicacao");
    case COLISAO:        return F("mais de um cartao");
    case TEMPO_ESGOTADO: return F("sem resposta");
    case SEM_ESPACO:     return F("resposta grande demais");
    case ERRO_CRC:       return F("erro de CRC");
    case NACK:           return F("cartao recusou");
    case SEM_CARTAO:     return F("nenhum cartao");
    case AUTENTICACAO:   return F("chave errada");
    case PROIBIDO:       return F("bloco protegido");
    default:             return F("tipo de cartao nao suportado");
    }
}

/* ================================================================ dados */
void RFID::defineChave(const uint8_t chave[6], bool chaveB) {
    for (uint8_t i = 0; i < 6; i++) _chave[i] = chave[i];
    _chaveB = chaveB;
    _setorAutenticado = -1;
}

RFID::Status RFID::preparaCartao() {
    if (_selecionado) return OK;
    if (cartaoPresente()) return OK;
    return SEM_CARTAO;
}

static inline bool rfidClassic(uint8_t t) {
    return t == RFID::TIPO_MIFARE_MINI || t == RFID::TIPO_MIFARE_1K || t == RFID::TIPO_MIFARE_4K;
}

static inline int16_t rfidSetor(uint8_t bloco) {
    return (bloco < 128) ? (bloco >> 2) : (int16_t)(32 + ((bloco - 128) >> 4));
}

RFID::Status RFID::autentica(uint8_t bloco) {
    int16_t setor = rfidSetor(bloco);
    if (setor == _setorAutenticado) return OK;
    uint8_t buf[12];
    buf[0] = _chaveB ? MF_AUTH_B : MF_AUTH_A;
    buf[1] = bloco;
    for (uint8_t i = 0; i < 6; i++) buf[2 + i] = _chave[i];
    for (uint8_t i = 0; i < 4; i++) buf[8 + i] = _uid[_uidTam - 4 + i];   /* últimos 4 bytes do UID */
    tempoLimite(RFID_TEMPO_LONGO_MS);
    Status s = comunica(PCD_MFAuthent, 0x10, buf, 12, NULL, NULL, NULL, false);
    if (s == OK && !(lerRegistrador(Status2Reg) & 0x08)) s = AUTENTICACAO;
    if (s != OK) {
        if (s == TEMPO_ESGOTADO) s = AUTENTICACAO;   /* chave errada: o cartão fica mudo */
        paraCripto();
        _selecionado = false;                        /* o cartão volta a dormir */
        _setorAutenticado = -1;
        return s;
    }
    _setorAutenticado = setor;
    return OK;
}

RFID::Status RFID::mifareLer(uint8_t endereco, uint8_t dados[18]) {
    uint8_t cmd[4] = { MF_READ, endereco, 0, 0 };
    calculaCRC(cmd, 2, &cmd[2]);
    uint8_t n = 18;
    tempoLimite(RFID_TEMPO_LONGO_MS);
    Status s = transcepcao(cmd, 4, dados, &n, NULL, true);
    if (s == OK && n != 18) s = ERRO;
    return s;
}

/* Envia um quadro (o CRC é acrescentado aqui) e espera o ACK de 4 bits. */
RFID::Status RFID::mifareTransacao(const uint8_t *envia, uint8_t n) {
    uint8_t buf[18];
    if (n > 16) return SEM_ESPACO;
    for (uint8_t i = 0; i < n; i++) buf[i] = envia[i];
    calculaCRC(buf, n, &buf[n]);
    uint8_t resp[2];
    uint8_t nr = 2, bits = 0;
    tempoLimite(RFID_TEMPO_LONGO_MS);
    Status s = transcepcao(buf, (uint8_t)(n + 2), resp, &nr, &bits);
    if (s != OK) return s;
    if (nr != 1 || bits != 4 || (resp[0] & 0x0F) != MF_ACK) return NACK;
    return OK;
}

RFID::Status RFID::lerBloco(uint8_t bloco, uint8_t dados[16]) {
    Status s = preparaCartao();
    uint8_t buf[18];
    if (s == OK) {
        if (rfidClassic(_tipo)) {
            s = autentica(bloco);
            if (s == OK) s = mifareLer(bloco, buf);
        } else if (_tipo == TIPO_ULTRALIGHT) {
            if (bloco > 63) s = PROIBIDO;
            else s = mifareLer((uint8_t)(bloco * 4), buf);
        } else {
            s = NAO_SUPORTADO;
        }
    }
    if (s == OK) {
        for (uint8_t i = 0; i < 16; i++) dados[i] = buf[i];
    } else if (s != PROIBIDO && s != NAO_SUPORTADO) {
        _selecionado = false;
        _setorAutenticado = -1;
    }
    _status = s;
    return s;
}

RFID::Status RFID::escreveBloco(uint8_t bloco, const uint8_t dados[16]) {
    Status s = preparaCartao();
    if (s == OK) {
        if (rfidClassic(_tipo)) {
            bool trailer = (bloco < 128) ? ((bloco & 3) == 3) : ((bloco & 15) == 15);
            if (bloco == 0 || trailer) {
                s = PROIBIDO;                        /* evita estragar o cartão */
            } else {
                s = autentica(bloco);
                uint8_t cmd[2] = { MF_WRITE, bloco };
                if (s == OK) s = mifareTransacao(cmd, 2);
                if (s == OK) s = mifareTransacao(dados, 16);
            }
        } else if (_tipo == TIPO_ULTRALIGHT) {
            if (bloco == 0 || bloco > 63) {
                s = PROIBIDO;                        /* páginas 0-3: UID, travas e OTP */
            } else {
                for (uint8_t p = 0; p < 4 && s == OK; p++) {
                    uint8_t cmd[6] = { UL_WRITE, (uint8_t)(bloco * 4 + p),
                                       dados[p * 4], dados[p * 4 + 1], dados[p * 4 + 2], dados[p * 4 + 3] };
                    s = mifareTransacao(cmd, 6);
                }
            }
        } else {
            s = NAO_SUPORTADO;
        }
    }
    if (s != OK && s != PROIBIDO && s != NAO_SUPORTADO) {
        _selecionado = false;
        _setorAutenticado = -1;
    }
    _status = s;
    return s;
}

RFID::Status RFID::escreveTexto(uint8_t bloco, const char *texto) {
    uint8_t buf[16];
    uint8_t i = 0;
    for (; i < 16 && texto[i]; i++) buf[i] = (uint8_t)texto[i];
    for (; i < 16; i++) buf[i] = 0;
    return escreveBloco(bloco, buf);
}

RFID::Status RFID::lerTexto(uint8_t bloco, char texto[17]) {
    uint8_t buf[16];
    Status s = lerBloco(bloco, buf);
    if (s != OK) { texto[0] = 0; return s; }
    for (uint8_t i = 0; i < 16; i++) texto[i] = (char)buf[i];
    texto[16] = 0;
    return OK;
}
