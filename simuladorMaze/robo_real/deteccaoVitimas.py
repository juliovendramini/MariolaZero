"""deteccaoVitimas.py — versão do ROBÔ REAL (modelo para a equipe completar).

No simulador este módulo é substituído automaticamente pela versão simulada,
então o código do aluno só usa a interface abaixo:

    cam = DeteccaoVitimas()
    v = cam.detecta()              # olha todas as câmeras
    v = cam.detecta('esquerda')    # só uma câmera
    # v é None ou um dict:
    # {'camera': 'esquerda'|'direita', 'tipo': 'letra'|'cognitivo',
    #  'status': 'ferida'|'estavel'|'ilesa', 'kits': 2|1|0,
    #  'letra': 'H'|'S'|'U' (só para letras), 'distancia_mm': int}
    lista = cam.detecta_todas()    # todas as vítimas vistas, da mais perto para a mais longe

Para respeitar a interface, retorne exatamente essas chaves.
"""

KITS = {'ferida': 2, 'estavel': 1, 'ilesa': 0}


class DeteccaoVitimas:
    ESQUERDA = 'esquerda'
    DIREITA = 'direita'
    FERIDA = 'ferida'
    ESTAVEL = 'estavel'
    ILESA = 'ilesa'

    def __init__(self, cameras=None):
        # TODO: abrir as câmeras (cv2.VideoCapture), carregar o modelo (YOLO/ONNX), etc.
        # cameras: dict nome -> índice/caminho, ex.: {'esquerda': 0, 'direita': 2}
        self.cameras = cameras or {'esquerda': 0, 'direita': 2}

    def _processa(self, nome):
        """Captura um quadro da câmera `nome` e devolve uma lista de dicts (pode ser vazia).
        TODO: implementar com o pipeline de visão da equipe:
          * letras Φ (ferida), Ψ (estável), Ω (ilesa)
          * alvos cognitivos: somar os 5 anéis (preto -2, vermelho -1, amarelo 0, verde 1, azul 2);
            soma 2 = ferida, 1 = estável, 0 = ilesa, outra soma = não é vítima
        """
        raise NotImplementedError('implemente a detecção de vítimas do robô real')

    def detecta_todas(self, camera=None):
        nomes = [camera] if camera else list(self.cameras)
        res = []
        for n in nomes:
            res.extend(self._processa(n))
        res.sort(key=lambda v: v.get('distancia_mm', 0))
        return res

    def detecta(self, camera=None):
        v = self.detecta_todas(camera)
        return v[0] if v else None

    def fechar(self):
        pass
