"""Mensagens JSON com prefixo de tamanho (4 bytes, big-endian) sobre TCP local."""

import json
import struct


def envia(sock, obj):
    dados = json.dumps(obj, separators=(',', ':')).encode('utf-8')
    sock.sendall(struct.pack('>I', len(dados)) + dados)


def _le_exato(sock, n):
    buf = bytearray()
    while len(buf) < n:
        parte = sock.recv(n - len(buf))
        if not parte:
            raise ConnectionError('conexão fechada')
        buf += parte
    return bytes(buf)


def recebe(sock):
    n = struct.unpack('>I', _le_exato(sock, 4))[0]
    return json.loads(_le_exato(sock, n).decode('utf-8'))
