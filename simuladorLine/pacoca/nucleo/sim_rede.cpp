// Rede com a ponte (TCP local). Este arquivo não inclui o Arduino.h para não brigar com
// os cabeçalhos do Windows.
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
typedef SOCKET sock_t;
#define SOCK_INVALIDO INVALID_SOCKET
#define fecha_sock closesocket
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <unistd.h>
typedef int sock_t;
#define SOCK_INVALIDO (-1)
#define fecha_sock close
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <thread>

#include "sim_ponte.h"

static sock_t s_principal = SOCK_INVALIDO;
static sock_t s_vida = SOCK_INVALIDO;
static bool ativa = false;

static char saida[2048];
static int n_saida = 0;

void sim_saida_flush(void) {
    if (n_saida) {
        fwrite(saida, 1, n_saida, stdout);
        n_saida = 0;
    }
    fflush(stdout);
}

void sim_saida(const char *s, int n) {
    for (int i = 0; i < n; i++) {
        char c = s[i];
        if (c == '\r') continue;
        saida[n_saida++] = c;
        if (c == '\n' || n_saida >= (int)sizeof(saida) - 1) {
            fwrite(saida, 1, n_saida, stdout);
            fflush(stdout);
            n_saida = 0;
        }
    }
}

static void encerra(int codigo) {
    sim_saida_flush();
    _exit(codigo);
}

static bool envia_tudo(sock_t s, const uint8_t *b, int n) {
    while (n > 0) {
        int k = (int)send(s, (const char *)b, n, 0);
        if (k <= 0) return false;
        b += k;
        n -= k;
    }
    return true;
}

static bool recebe_tudo(sock_t s, uint8_t *b, int n) {
    while (n > 0) {
        int k = (int)recv(s, (char *)b, n, 0);
        if (k <= 0) return false;
        b += k;
        n -= k;
    }
    return true;
}

static sock_t abre(int porta, char tipo) {
    sock_t s = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (s == SOCK_INVALIDO) return s;
    struct sockaddr_in a;
    memset(&a, 0, sizeof a);
    a.sin_family = AF_INET;
    a.sin_port = htons((unsigned short)porta);
    a.sin_addr.s_addr = htonl(0x7F000001);
    if (connect(s, (struct sockaddr *)&a, sizeof a) != 0) {
        fecha_sock(s);
        return SOCK_INVALIDO;
    }
    int um = 1;
    setsockopt(s, IPPROTO_TCP, TCP_NODELAY, (const char *)&um, sizeof um);
    uint8_t t = (uint8_t)tipo;
    envia_tudo(s, &t, 1);
    return s;
}

static void vigia_vida() {
    // se a ponte morrer (simulador fechou, botão Parar), o programa morre junto
    uint8_t b;
    while (true) {
        int k = (int)recv(s_vida, (char *)&b, 1, 0);
        if (k <= 0) encerra(0);
        if (b == 'P') encerra(0);      // pedido de parar
    }
}

bool sim_rede_conecta(void) {
    const char *p = getenv("PACOCA_PONTE");
    if (!p || !*p) return false;
#ifdef _WIN32
    WSADATA w;
    WSAStartup(MAKEWORD(2, 2), &w);
#endif
    int porta = atoi(p);
    s_principal = abre(porta, 'P');
    if (s_principal == SOCK_INVALIDO) {
        fprintf(stderr, "[simulador] não consegui falar com a ponte na porta %d\n", porta);
        exit(3);
    }
    s_vida = abre(porta, 'V');
    if (s_vida != SOCK_INVALIDO) std::thread(vigia_vida).detach();
    ativa = true;
    return true;
}

bool sim_rede_ativa(void) { return ativa; }

bool sim_rede_chamar(uint8_t op, int64_t t_ns, const SimReq &req, SimResp &resp) {
    resp.flags = 0;
    resp.n = 0;
    resp.pos = 0;
    if (!ativa) return false;
    uint8_t cab[13];
    uint32_t tam = 9 + (uint32_t)req.n;
    cab[0] = tam & 0xFF;
    cab[1] = (tam >> 8) & 0xFF;
    cab[2] = (tam >> 16) & 0xFF;
    cab[3] = (tam >> 24) & 0xFF;
    cab[4] = op;
    uint64_t t = (uint64_t)t_ns;
    for (int i = 0; i < 8; i++) cab[5 + i] = (uint8_t)(t >> (8 * i));
    if (!envia_tudo(s_principal, cab, 13) || (req.n && !envia_tudo(s_principal, req.d, req.n))) encerra(0);
    uint8_t h[4];
    if (!recebe_tudo(s_principal, h, 4)) encerra(0);
    uint32_t n = h[0] | (h[1] << 8) | (h[2] << 16) | ((uint32_t)h[3] << 24);
    if (n < 1 || n > sizeof(resp.d) + 1) encerra(4);
    if (!recebe_tudo(s_principal, &resp.flags, 1)) encerra(0);
    resp.n = (int)n - 1;
    if (resp.n && !recebe_tudo(s_principal, resp.d, resp.n)) encerra(0);
    if (resp.flags & 1) encerra(0);
    return true;
}
