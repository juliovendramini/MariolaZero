"""Monta o site do curso: curso/curso-mariola.html, um HTML só com todo o conteúdo embutido.

    python curso/site/monta.py

Lê os .md, .py e .json de curso/ (menos esta pasta site/) e as imagens de curso/imagens/, e
injeta tudo no modelo.html (que tem o CSS e o JavaScript da página). Rode depois de mudar
qualquer módulo, referência ou código do curso.
"""
import base64, glob, json, os, re

SITE = os.path.dirname(os.path.abspath(__file__))
CURSO = os.path.dirname(SITE)
os.chdir(CURSO)
arquivos = {}
for p in sorted(glob.glob('**/*', recursive=True)):
    p_os, p = p, p.replace(os.sep, '/')          # no Windows o glob devolve "\"
    if os.path.isdir(p_os) or p.startswith(('imagens/', 'site/')) or p == 'CLAUDE.md':
        continue
    if p.endswith(('.md', '.py', '.json')):
        arquivos[p] = open(p_os, encoding='utf-8').read()
imagens = {}
for p in sorted(glob.glob('imagens/*')):
    p = p.replace(os.sep, '/')
    tipo = 'image/jpeg' if p.endswith('.jpg') else 'image/png'
    imagens[p] = f'data:{tipo};base64,' + base64.b64encode(open(p, 'rb').read()).decode()

def titulo(p):
    m = re.search(r'^#\s+(.+)$', arquivos[p], re.M)
    t = m.group(1) if m else p
    t = re.sub(r'^Módulo \d+ — ', '', t)
    return t

modulos = sorted(f for f in arquivos if re.match(r'\d\d-.*\.md$', f))
grupos = [('Começando', 1, 3), ('Atuadores e sensores', 4, 10), ('Simuladores e organização', 11, 13), ('Projetos', 14, 18)]
partes = [{'titulo': 'Início', 'trilho': False, 'itens': [{'caminho': 'README.md', 'titulo': 'Apresentação do curso', 'n': ''}]}]
for nome, a, b in grupos:
    itens = [{'caminho': f, 'titulo': titulo(f), 'n': str(int(f[:2]))} for f in modulos if a <= int(f[:2]) <= b]
    partes.append({'titulo': nome, 'trilho': True, 'itens': itens})
ref_ordem = ['README', 'portas', 'motores', 'placaControleMotor', 'placaControleServo', 'giroscopio',
             'sensorCorReflexao', 'vl53', 'tcs34725', 'bno085', 'placasMux', 'botoes', 'pinosDigitais',
             'teclado-tela', 'cronometro', 'extras', 'modulos-simulador']
curtos = {'README': 'Visão geral das bibliotecas', 'portas': 'Portas', 'motores': 'Motores',
          'placaControleMotor': 'PlacaControleMotor', 'placaControleServo': 'PlacaControleServo',
          'giroscopio': 'Giroscopio', 'sensorCorReflexao': 'CorReflexao (sensor de linha)', 'vl53': 'VL53L0X',
          'tcs34725': 'TCS34725', 'bno085': 'BNO085', 'placasMux': 'Placas mux (VL53 e TCS)', 'botoes': 'Botões',
          'pinosDigitais': 'PinosDigitais', 'teclado-tela': 'Teclado e Tela', 'cronometro': 'Cronometro',
          'extras': 'Lidar, Bluetooth e câmera', 'modulos-simulador': 'simdebug, visao, vítimas e kits'}
faltando = set(f[len('referencia/'):-3] for f in arquivos if f.startswith('referencia/')) - set(ref_ordem)
assert not faltando, faltando
partes.append({'titulo': 'Referência das bibliotecas', 'trilho': False,
               'itens': [{'caminho': f'referencia/{r}.md', 'titulo': curtos[r], 'n': ''} for r in ref_ordem]})
partes.append({'titulo': 'Material', 'trilho': False,
               'itens': [{'caminho': 'codigos/README.md', 'titulo': 'Programas dos tutoriais', 'n': ''}]})

dados = json.dumps({'arquivos': arquivos, 'imagens': imagens, 'partes': partes}, ensure_ascii=False)
dados = dados.replace('</', '<\\/')
html = open(os.path.join(SITE, 'modelo.html'), encoding='utf-8').read().replace('/*__DADOS__*/', dados)
with open(os.path.join(CURSO, 'curso-mariola.html'), 'w', encoding='utf-8', newline='\n') as f:
    f.write(html)
print('ok', len(arquivos), 'arquivos,', len(imagens), 'imagens,', round(len(html) / 1024), 'KB')
