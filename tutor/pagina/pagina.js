// Página do aluno do robô tutor (tutor/servidor.py). Editor = Monaco; complemento = Jedi no servidor.
'use strict';

const $ = (id) => document.getElementById(id);
let editor = null, monacoRef = null;
let desafio = null, desafios = [], ocupado = false, rodadas = [];
let marcaLinha = [];
let tempoSalva = null, tempoSintaxe = null;

async function api(caminho, dados) {
  const op = dados === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dados)
  };
  const r = await fetch(caminho, op);
  return r.json();
}

// ------------------------------------------------------------------ desafios
function tema() {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'vs-dark' : 'vs';
}

async function carregaDesafios() {
  desafios = await api('/api/desafios');
  const sel = $('desafio');
  let grupo = null, og = null;
  for (const d of desafios) {
    if (d.nivel !== grupo) {
      grupo = d.nivel; og = document.createElement('optgroup'); og.label = grupo; sel.appendChild(og);
    }
    const o = document.createElement('option');
    o.value = d.id; o.textContent = `${d.id}: ${d.titulo}`;
    og.appendChild(o);
  }
  let guardado = null;
  try { guardado = localStorage.getItem('tutor_desafio'); } catch (e) { /* sem armazenamento */ }
  sel.value = desafios.some(d => d.id === guardado) ? guardado : desafios[0].id;
  sel.addEventListener('change', () => abre(sel.value));
  await abre(sel.value);
}

async function abre(id) {
  if (desafio && editor) await salva();
  desafio = id;
  try { localStorage.setItem('tutor_desafio', id); } catch (e) { /* sem armazenamento */ }
  const d = desafios.find(x => x.id === id);
  $('d_nivel').textContent = d.nivel || '';
  $('d_titulo').textContent = `${d.id}: ${d.titulo}`;
  $('d_descricao').textContent = d.descricao || '';
  $('d_meta').textContent = d.meta || '';
  $('ver').disabled = !d.janela;
  const r = await api('/api/abre?desafio=' + id);
  $('arquivo').textContent = r.arquivo;
  editor.setValue(r.codigo);
  editor.setScrollTop(0);
  $('conversa').innerHTML = '';
  for (const f of r.falas) poeFala(f);
  if (!r.falas.length) poeFala({ quem: 'tutor', texto: 'Oi! Escreva o seu programa e aperte Rodar. Depois eu conto o que o robô fez e a gente pensa junto.' });
  mostraPlacar(r.estado);
  if (r.estado.fase === 'rodando' || r.estado.fase === 'pensando') acompanha();
  $('salvo').textContent = '';
  conferirSintaxe();
}

// ------------------------------------------------------------------ editor
function criaEditor() {
  return new Promise((ok) => {
    require.config({ paths: { vs: '/monaco/vs' } });
    require(['vs/editor/editor.main'], () => {
      monacoRef = monaco;
      editor = monaco.editor.create($('editor'), {
        value: '', language: 'python', theme: tema(), fontSize: 15, automaticLayout: true,
        minimap: { enabled: false }, tabSize: 4, insertSpaces: true, detectIndentation: false,
        scrollBeyondLastLine: false, wordBasedSuggestions: 'off', renderWhitespace: 'boundary',
        quickSuggestions: { other: true, comments: false, strings: false }, fixedOverflowWidgets: true,
      });
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => monaco.editor.setTheme(tema()));
      editor.onDidChangeModelContent(() => {
        $('salvo').textContent = 'editando...';
        clearTimeout(tempoSalva); tempoSalva = setTimeout(salva, 1200);
        clearTimeout(tempoSintaxe); tempoSintaxe = setTimeout(conferirSintaxe, 700);
        limpaLinha();
      });
      editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, salva);
      editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, roda);
      registraJedi(monaco);
      ok();
    });
  });
}

const TIPOS = () => ({
  funcao: monacoRef.languages.CompletionItemKind.Function, classe: monacoRef.languages.CompletionItemKind.Class,
  modulo: monacoRef.languages.CompletionItemKind.Module, variavel: monacoRef.languages.CompletionItemKind.Variable,
  palavra: monacoRef.languages.CompletionItemKind.Keyword, propriedade: monacoRef.languages.CompletionItemKind.Property,
  arquivo: monacoRef.languages.CompletionItemKind.File,
});

function pedidoJedi(model, pos) {
  // Monaco conta a coluna a partir de 1; o Jedi, a partir de 0
  return { codigo: model.getValue(), linha: pos.lineNumber, coluna: pos.column - 1, desafio };
}

function registraJedi(monaco) {
  monaco.languages.registerCompletionItemProvider('python', {
    triggerCharacters: ['.'],
    provideCompletionItems: async (model, pos) => {
      const r = await api('/api/completa', pedidoJedi(model, pos));
      const p = model.getWordUntilPosition(pos);
      const faixa = new monaco.Range(pos.lineNumber, p.startColumn, pos.lineNumber, p.endColumn);
      const k = TIPOS();
      return {
        suggestions: (r.r || []).map((c, i) => ({
          label: c.nome, kind: k[c.tipo] || k.variavel, insertText: c.nome, range: faixa,
          detail: c.detalhe, documentation: c.doc ? { value: '```\n' + c.doc + '\n```' } : undefined,
          sortText: String(i).padStart(3, '0'),
        })),
      };
    },
  });
  monaco.languages.registerSignatureHelpProvider('python', {
    signatureHelpTriggerCharacters: ['(', ','],
    provideSignatureHelp: async (model, pos) => {
      const r = await api('/api/assinatura', pedidoJedi(model, pos));
      if (!r.r || !r.r.length) return null;
      return {
        value: {
          signatures: r.r.map(a => ({
            label: a.texto, documentation: a.doc ? { value: '```\n' + a.doc + '\n```' } : undefined,
            parameters: a.params.map(p => ({ label: p })),
          })),
          activeSignature: 0, activeParameter: r.r[0].ativo || 0,
        },
        dispose() {},
      };
    },
  });
  monaco.languages.registerHoverProvider('python', {
    provideHover: async (model, pos) => {
      if (!model.getWordAtPosition(pos)) return null;
      const r = await api('/api/ajuda', pedidoJedi(model, pos));
      if (!r.r) return null;
      const partes = [{ value: '```python\n' + r.r.titulo + '\n```' }];
      if (r.r.doc) partes.push({ value: '```\n' + r.r.doc + '\n```' });
      return { contents: partes };
    },
  });
}

async function salva() {
  if (!editor || !desafio) return;
  clearTimeout(tempoSalva);
  await api('/api/salva', { desafio, codigo: editor.getValue() });
  $('salvo').textContent = 'salvo ' + new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

async function conferirSintaxe() {
  const r = await api('/api/sintaxe', { codigo: editor.getValue() });
  const marcas = [];
  if (r.erro) {
    const m = /^linha (\d+): (.*)$/.exec(r.erro);
    const n = m ? parseInt(m[1]) : 1;
    marcas.push({
      severity: monacoRef.MarkerSeverity.Error, message: m ? m[2] : r.erro,
      startLineNumber: n, endLineNumber: n, startColumn: 1, endColumn: editor.getModel().getLineMaxColumn(Math.min(n, editor.getModel().getLineCount())),
    });
  }
  monacoRef.editor.setModelMarkers(editor.getModel(), 'python', marcas);
  $('sintaxe').textContent = r.erro ? 'O Python não consegue ler: ' + r.erro : '';
}

function mostraLinha(n) {
  const total = editor.getModel().getLineCount();
  if (n < 1 || n > total) return;
  editor.revealLineInCenter(n);
  marcaLinha = editor.deltaDecorations(marcaLinha, [{
    range: new monacoRef.Range(n, 1, n, 1), options: { isWholeLine: true, className: 'linha-tutor' },
  }]);
  editor.setPosition({ lineNumber: n, column: 1 });
  editor.focus();
}

function limpaLinha() {
  if (marcaLinha.length) marcaLinha = editor.deltaDecorations(marcaLinha, []);
}

// ------------------------------------------------------------------ conversa
const NOMES_NIVEL = { 1: 'dica nível 1: pergunta', 2: 'dica nível 2: pista', 3: 'dica nível 3: apontar' };

function poeFala(f) {
  const div = document.createElement('div');
  if (f.rodou) {
    div.className = 'fala rodou';
    div.textContent = f.texto;
  } else {
    div.className = 'fala ' + f.quem;
    // "linha 14", "linhas 12 e 13": viram links que mostram a linha no editor
    const partes = f.texto.split(/(\blinhas? \d+(?:(?:,| e| a) \d+)*)/g);
    for (const p of partes) {
      if (/^linhas? \d/.test(p)) {
        const nums = p.match(/\d+/g).map(Number);
        const pedacos = p.split(/(\d+)/);
        for (const q of pedacos) {
          if (/^\d+$/.test(q)) {
            const a = document.createElement('a');
            a.className = 'linha'; a.textContent = q; a.onclick = () => mostraLinha(parseInt(q));
            div.appendChild(a);
          } else div.appendChild(document.createTextNode(q));
        }
        void nums;
      } else div.appendChild(document.createTextNode(p));
    }
    if (f.quem === 'tutor' && f.nivel) {
      const s = document.createElement('span'); s.className = 'dica'; s.textContent = NOMES_NIVEL[f.nivel] || '';
      div.appendChild(s);
    }
  }
  $('conversa').appendChild(div);
  $('conversa').scrollTop = $('conversa').scrollHeight;
  return div;
}

function pensando(texto) {
  const d = poeFala({ quem: 'tutor', texto });
  d.classList.add('pensando');
  return d;
}

async function pergunta(ev) {
  ev.preventDefault();
  const texto = $('texto').value.trim();
  if (!texto || ocupado) return;
  $('texto').value = '';
  poeFala({ quem: 'aluno', texto });
  trava(true);
  const p = pensando('pensando...');
  try {
    const r = await api('/api/pergunta', { desafio, texto, codigo: editor.getValue() });
    p.remove();
    poeFala({ quem: 'tutor', texto: r.fala || r.erro || '(sem resposta)', nivel: r.nivel });
  } catch (e) {
    p.remove();
    poeFala({ quem: 'tutor', texto: 'Não consegui falar com o tutor: ' + e });
  }
  trava(false);
}

// ------------------------------------------------------------------ rodar
function trava(sim) {
  ocupado = sim;
  $('rodar').disabled = sim; $('enviar').disabled = sim;
}

async function roda() {
  if (ocupado) return;
  await salva();
  const r = await api('/api/roda', { desafio, codigo: editor.getValue() });
  if (r.sintaxe) {
    conferirSintaxe();
    const n = parseInt((/linha (\d+)/.exec(r.sintaxe) || [0, 1])[1]);
    mostraLinha(n);
    $('status').textContent = 'O Python não consegue ler o programa (' + r.sintaxe + '). Corrija e rode de novo, ou pergunte ao tutor.';
    return;
  }
  if (r.erro) { $('status').textContent = r.erro; return; }
  acompanha();
}

let pensandoDiv = null;
async function acompanha() {
  trava(true);
  $('placar').className = 'placar vazio';
  $('placar').textContent = 'O juiz está olhando...';
  while (true) {
    const e = await api('/api/estado?desafio=' + desafio);
    if (e.fase === 'rodando') {
      $('status').textContent = `rodando no simulador... ${e.segundos || 0} s`;
    } else if (e.fase === 'pensando') {
      mostraPlacar(e);
      $('status').textContent = 'o tutor está olhando a volta...';
      if (!pensandoDiv) { poeFala({ quem: 'aluno', texto: `(rodou a tentativa ${e.tentativa})`, rodou: true }); pensandoDiv = pensando('pensando...'); }
    } else {
      if (pensandoDiv) { pensandoDiv.remove(); pensandoDiv = null; }
      if (e.fase === 'pronto') {
        // a fala "rodou" já entrou se passou pelo "pensando"; senão, põe agora
        const ultimas = [...document.querySelectorAll('.fala.rodou')];
        if (!ultimas.length || ultimas[ultimas.length - 1].textContent !== `(rodou a tentativa ${e.tentativa})`)
          poeFala({ quem: 'aluno', texto: `(rodou a tentativa ${e.tentativa})`, rodou: true });
        mostraPlacar(e);
        poeFala({ quem: 'tutor', texto: e.fala, nivel: e.nivel });
        $('status').textContent = '';
      } else if (e.fase === 'erro') {
        $('placar').className = 'placar vazio';
        $('placar').textContent = 'Deu um problema ao rodar.';
        $('status').textContent = '';
        poeFala({ quem: 'tutor', texto: 'Não consegui rodar o simulador: ' + (e.erro || '') });
      }
      break;
    }
    await new Promise(ok => setTimeout(ok, 1000));
  }
  trava(false);
}

function mostraPlacar(e) {
  const p = $('placar');
  if (!e || !e.placar) {
    p.className = 'placar vazio'; p.textContent = 'Rode o programa para ver o placar do juiz.'; return;
  }
  rodadas = e.rodadas || [];
  p.className = 'placar' + (e.aprovado ? ' ok' : '');
  p.innerHTML = '';
  for (const l of e.placar.split('\n')) {
    // a regra do juiz ("chegou and lop == 0") é para o tutor; o aluno lê a meta no cartão do desafio
    const t = l.trim().replace(/cumpriram ".*?"/, 'cumpriram a meta');
    const div = document.createElement('div');
    if (t === 'DESAFIO CUMPRIDO' || t === 'desafio ainda não cumprido') {
      div.className = 'veredito'; div.textContent = t === 'DESAFIO CUMPRIDO' ? 'Desafio cumprido!' : 'Desafio ainda não cumprido.';
    } else div.textContent = t;
    p.appendChild(div);
  }
}

async function verVolta() {
  // a pior rodada (menos pontos), que é a que mais interessa ver
  let s = 1;
  if (rodadas.length) s = rodadas.reduce((a, b) => ((b.total || 0) < (a.total || 0) ? b : a)).semente;
  await salva();
  const r = await api('/api/ver', { desafio, semente: s });
  $('status').textContent = r.erro || `abrindo a janela do simulador (semente ${s})...`;
  setTimeout(() => { if (!ocupado) $('status').textContent = ''; }, 6000);
}

// ------------------------------------------------------------------ começo
$('rodar').onclick = roda;
$('ver').onclick = verVolta;
$('form').addEventListener('submit', pergunta);
$('texto').addEventListener('keydown', (ev) => {
  if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); $('form').requestSubmit(); }
});
window.addEventListener('beforeunload', () => { if (editor) navigator.sendBeacon('/api/salva', JSON.stringify({ desafio, codigo: editor.getValue() })); });

criaEditor().then(carregaDesafios);
