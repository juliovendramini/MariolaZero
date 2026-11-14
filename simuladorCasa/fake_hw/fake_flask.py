"""Flask falso (o servidor web que algumas equipes sobem no robô para ver o mapa ao vivo).

No simulador o servidor não roda: a thread dele fica parada esperando conexão (select do socket), o
relógio sincronizado não vê isso como espera e a partida inteira passaria a andar pelo relógio real.
Aqui Flask(), @app.route/get/post e app.run() existem, mas o run() só avisa e volta.
"""

import types


class Flask:
    def __init__(self, *a, **k):
        pass

    def route(self, *a, **k):
        return lambda f: f

    get = post = route

    def run(self, *a, **k):
        print('[simulador] Flask não roda no simulador (o servidor web e o mapa ao vivo ficam desligados)')


def jsonify(*a, **k):
    return a[0] if len(a) == 1 and not k else (dict(k) if k else list(a))


def modulos():
    m = types.ModuleType('flask')
    m.Flask, m.jsonify = Flask, jsonify
    return {'flask': m}
