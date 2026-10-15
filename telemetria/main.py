from gevent import monkey
monkey.patch_all(thread=False)

import cv2, time, json, threading, os
from flask import Flask, Response
from gevent.pywsgi import WSGIServer

app = Flask(__name__)

# Variáveis globais para compartilhamento entre threads
# _cond = threading.Condition()
_latest_jpeg = None
_latest_telem = {}
_seq = 0

# Configurações dinâmicas que virão do PHP
config_robo = {}

def carregar_configuracoes():
    """Lê o JSON salvo pelo PHP em tempo real."""
    global config_robo
    try:
        # Se o arquivo estiver sendo gravado no mesmo milissegundo, ignora o erro e mantém a anterior
        with open("parametros.json", "r") as f:
            config_robo = json.load(f)
    except Exception:
        pass

def loop_processamento():
    global _latest_jpeg, _latest_telem, _seq
    
    # Substitua 0 por "/dev/video_usb3" se for usar o symlink
    cap = cv2.VideoCapture("/dev/video_usb3" , cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    while True:
        # Atualiza as configs vindas da página PHP a cada ciclo
        carregar_configuracoes()

        ok, frame = cap.read()
        if not ok:
            print(" Erro: Não foi possível ler a câmera! Verifique a conexão.")
            time.sleep(1.0)
            continue

        # ===================== TEU PROCESSAMENTO =====================
        # Exemplo de uso da variável lida do PHP:
        velocidade_atual = config_robo.get("velocidade_max", 100)
        
        telem = {
            "ts": time.time(),
            "estado_atual": "Resgate",
            "identificacao": {"vitimas": 1, "triangulos": 2},
            "sensor_linha": {"esq": 4095, "dir": 12},
            "giroscopio_yaw": 180.5
        }
        # =============================================================

        ok, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if not ok:
            continue

        # Apenas atualize as variáveis diretamente
        _latest_jpeg = buf.tobytes()
        _latest_telem = telem
        _seq += 1

def gen_video():
    ultimo = -1
    while True:
        # Se temos um frame novo, envia para o navegador
        if _seq != ultimo and _latest_jpeg is not None:
            ultimo = _seq
            jpeg = _latest_jpeg
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n')
        else:
            # Como o 'time' foi alterado pelo Gevent, esse sleep não trava o servidor!
            # Ele libera o processador para enviar a telemetria enquanto a câmera não manda imagem nova.
            time.sleep(0.01) 

def gen_telem():
    ultimo = -1
    while True:
        if _seq != ultimo and _latest_telem:
            ultimo = _seq
            telem = dict(_latest_telem)
            yield f"data: {json.dumps(telem)}\n\n"
        else:
            time.sleep(0.01)

@app.after_request
def cors(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

@app.route('/video')
def video():
    return Response(gen_video(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/telemetria')
def telemetria():
    r = Response(gen_telem(), mimetype='text/event-stream')
    r.headers['Cache-Control'] = 'no-cache'
    r.headers['X-Accel-Buffering'] = 'no'
    return r

if __name__ == '__main__':
    # Garante que o JSON base exista para não dar erro na primeira inicialização
    if not os.path.exists("parametros.json"):
        with open("parametros.json", "w") as f:
            json.dump({"velocidade_max": 150, "threshold_vitima": 0.8}, f)

    threading.Thread(target=loop_processamento, daemon=True).start()

    porta = 5000
    print(f"Robô online! Vídeo e telemetria rodando via Gevent na porta {porta}...")
    
    # Substitui o app.run() tradicional
    http_server = WSGIServer(('0.0.0.0', porta), app)
    http_server.serve_forever()
    # app.run(host='0.0.0.0', port=5000, threaded=True)