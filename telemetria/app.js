const BASE_PYTHON = `http://${window.location.hostname}:5000`;
const API_PHP = `api.php`;
let arquivoAtual = '';

// ==========================================
// 1. SISTEMA DE TEMAS E UI
// ==========================================
const inputBg = document.getElementById('cor-bg');
const inputOk = document.getElementById('cor-ok');
const toast = document.getElementById('toast');

const savedBg = localStorage.getItem('theme-bg') || '#0f1115';
const savedOk = localStorage.getItem('theme-ok') || '#3ddc84';

function aplicarTema(corFundo, corDestaque) {
    document.documentElement.style.setProperty('--bg', corFundo);
    document.documentElement.style.setProperty('--ok', corDestaque);
    document.documentElement.style.setProperty('--card', shadeColor(corFundo, 10));
    inputBg.value = corFundo;
    inputOk.value = corDestaque;
}

function shadeColor(color, percent) {
    let R = parseInt(color.substring(1,3),16), G = parseInt(color.substring(3,5),16), B = parseInt(color.substring(5,7),16);
    R = parseInt(R * (100 + percent) / 100); G = parseInt(G * (100 + percent) / 100); B = parseInt(B * (100 + percent) / 100);
    R = (R<255)?R:255; G = (G<255)?G:255; B = (B<255)?B:255;
    return "#"+((R.toString(16).length==1)?"0"+R.toString(16):R.toString(16)) +
               ((G.toString(16).length==1)?"0"+G.toString(16):G.toString(16)) +
               ((B.toString(16).length==1)?"0"+B.toString(16):B.toString(16));
}

inputBg.addEventListener('input', (e) => { aplicarTema(e.target.value, inputOk.value); localStorage.setItem('theme-bg', e.target.value); });
inputOk.addEventListener('input', (e) => { aplicarTema(inputBg.value, e.target.value); localStorage.setItem('theme-ok', e.target.value); });
aplicarTema(savedBg, savedOk);

function mostrarToast(msg, tipo) {
    toast.textContent = msg;
    toast.className = `show toast-${tipo}`;
    setTimeout(() => toast.classList.remove('show'), 3000);
}

// ==========================================
// 2. SISTEMA DE ABAS
// ==========================================
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.target).classList.add('active');
        if(btn.dataset.target === 'tab-terminal') document.getElementById('terminal-input').focus();
    });
});

// ==========================================
// 3. VÍDEO E TELEMETRIA (SUBSTITUA ESTE BLOCO NO SEU APP.JS)
// ==========================================
const es = new EventSource(`${BASE_PYTHON}/telemetria`);
let ultimoTs = 0;
let servidorOnline = false;

es.onopen = () => { 
    document.getElementById('dot').classList.add('on'); 
    document.getElementById('conn').textContent = 'conectado'; 
    if (!servidorOnline) {
        document.getElementById('cam').src = `${BASE_PYTHON}/video?t=${Date.now()}`;
        servidorOnline = true;
    }
};

es.onerror = () => { 
    document.getElementById('dot').classList.remove('on'); 
    document.getElementById('conn').textContent = 'reconectando...'; 
    if (servidorOnline) {
        document.getElementById('cam').src = ''; 
        servidorOnline = false;
    }
};

es.onmessage = (e) => {
    const telemetria = JSON.parse(e.data);
    ultimoTs = performance.now();
    const container = document.getElementById('telemetria-cards');
    
    // Limpa o container antes de injetar os novos cards
    container.innerHTML = '';
    
    for (const [chave, valor] of Object.entries(telemetria)) {
        if (chave === 'ts') continue;
        
        // Cria a estrutura do Card usando as classes do seu style.css
        const card = document.createElement('div');
        card.className = 'card';
        
        let html = `<h3>${chave.replace(/_/g, ' ').toUpperCase()}</h3>`;
        
        if (typeof valor === 'object' && valor !== null && !Array.isArray(valor)) {
            html += `<div class="grid2">`;
            for (const [sKey, sVal] of Object.entries(valor)) {
                html += `
                    <div class="row">
                        <span style="color:var(--dim)">${sKey.toUpperCase()}</span>
                        <span style="font-family:monospace; color:var(--ok); font-weight:bold;">${sVal}</span>
                    </div>`;
            }
            html += `</div>`;
        } else {
            html += `<div class="big" style="color:var(--txt);">${valor}</div>`;
        }
        
        card.innerHTML = html;
        container.appendChild(card);
    }
};

setInterval(() => {
const dt = (performance.now() - ultimoTs) / 1000;
const el = document.getElementById('age');
if (!ultimoTs) { el.textContent = 'sem dados ainda'; return; }
el.textContent = `atualizado: ${dt.toFixed(1)}s atrás`;
el.className = dt > 2 ? 'stale' : '';
}, 250);

// ==========================================
// 4. EDITOR JSON (Arquivos e Salvamento)
// ==========================================
async function carregarListaArquivos() {
    const res = await fetch(`${API_PHP}?api=listar_arquivos`);
    const data = await res.json();
    arquivoAtual = data.arquivos[0];
    
    const options = data.arquivos.map(f => `<option value="${f}">📄 ${f}</option>`).join('');
    document.getElementById('select-form').innerHTML = options;
    document.getElementById('select-config').innerHTML = options;
    carregarConteudoArquivo();
}

async function carregarConteudoArquivo() {
    const res = await fetch(`${API_PHP}?api=ler_arquivo&file=${encodeURIComponent(arquivoAtual)}&t=${Date.now()}`);
    const data = await res.json();
    document.getElementById('json-area').value = data.conteudo;

    try {
        gerarPainelHTML(JSON.parse(data.conteudo));
    } catch(e) {
        document.getElementById('grid-dinamica').innerHTML = `<p style="color:var(--bad)">Erro de Sintaxe no JSON. Corrija no Editor Avançado.</p>`;
    }
}

document.querySelectorAll('.combo-files').forEach(combo => {
    combo.addEventListener('change', (e) => {
        arquivoAtual = e.target.value;
        document.getElementById('select-form').value = arquivoAtual;
        document.getElementById('select-config').value = arquivoAtual;
        carregarConteudoArquivo();
    });
});

function gerarPainelHTML(dados) {
    let html = '';
    for (const [key, meta] of Object.entries(dados)) {
        if (!meta || typeof meta !== 'object' || meta.tipo === undefined) continue;
        const label = key.replace(/_/g, ' ').toUpperCase(), valor = meta.valor, tipo = meta.tipo;
        
        html += `<div class="param-card"><label>${label}</label>`;
        if (tipo === 'range') html += `<div class='slider-wrap'><input type='range' name='${key}' min='${meta.min||0}' max='${meta.max||100}' value='${valor}' oninput="this.nextElementSibling.innerText = this.value"><span class='range-val'>${valor}</span></div>`;
        else if (tipo === 'number') html += `<input type='number' name='${key}' value='${valor}' step='${meta.step||'any'}'>`;
        else if (tipo === 'checkbox') html += `<div class='check-wrap'><input type='hidden' name='${key}' value='0'><input type='checkbox' name='${key}' value='1' ${valor?'checked':''} onchange="this.nextElementSibling.innerText = this.checked ? 'ATIVADO' : 'DESATIVADO'"><span>${valor?'ATIVADO':'DESATIVADO'}</span></div>`;
        else html += `<input type='text' name='${key}' value='${valor}'>`;
        html += `</div>`;
    }
    document.getElementById('grid-dinamica').innerHTML = html || `<p style="color:var(--dim); padding:20px;">Sem parâmetros estruturados neste arquivo.</p>`;
}

async function salvarDados(url, formData, btn) {
    btn.disabled = true; const txt = btn.textContent; btn.textContent = "Salvando...";
    try {
        const res = await fetch(url, { method: 'POST', body: formData });
        const resp = await res.json();
        mostrarToast(resp.msg, resp.status);
        if(resp.status === 'ok') carregarConteudoArquivo();
    } catch (e) { mostrarToast("Erro de conexão", "erro"); }
    btn.disabled = false; btn.textContent = txt;
}

document.getElementById('form-dinamico').addEventListener('submit', (e) => { e.preventDefault(); const fd = new FormData(e.target); fd.append('file', arquivoAtual); salvarDados(`${API_PHP}?api=salvar_dinamico`, fd, e.target.querySelector('.btn-submit')); });
document.getElementById('form-raw').addEventListener('submit', (e) => { e.preventDefault(); const fd = new FormData(e.target); fd.append('file', arquivoAtual); salvarDados(`${API_PHP}?api=salvar_raw`, fd, e.target.querySelector('.btn-submit')); });

// ==========================================
// 5. TERMINAL AJAX
// ==========================================
const formTerminal = document.getElementById('form-terminal'), inputTerminal = document.getElementById('terminal-input'), outputTerminal = document.getElementById('terminal-output');
formTerminal.addEventListener('submit', async (e) => {
    e.preventDefault();
    const cmd = inputTerminal.value.trim(); if (!cmd) return;
    
    outputTerminal.textContent += `\nbanana@robo:~$ ${cmd}\n`;
    inputTerminal.value = ''; inputTerminal.disabled = true;
    
    const fd = new FormData(); fd.append('comando', cmd);
    try {
        const res = await fetch(`${API_PHP}?api=executar_comando`, { method: 'POST', body: fd });
        const data = await res.json();
        if (data.saida) outputTerminal.textContent += data.saida;
    } catch (e) { outputTerminal.textContent += `Erro de servidor.\n`; }
    
    inputTerminal.disabled = false; inputTerminal.focus();
    outputTerminal.scrollTop = outputTerminal.scrollHeight;
});

// ==========================================
// 6. LANÇADOR DE PROJETOS
// ==========================================
async function carregarProjetos() {
    try {
        const res = await fetch(`${API_PHP}?api=listar_projetos`);
        const data = await res.json();
        const container = document.getElementById('lista-projetos');
        
        if (data.projetos.length === 0) {
            container.innerHTML = '<p style="color:var(--dim)">Nenhuma pasta com main.py encontrada.</p>';
            return;
        }

        let html = '';
        data.projetos.forEach(proj => {
            // Monta botões gigantes usando a classe form-grid nativa
            html += `
            <div class="param-card" style="text-align: center; cursor: pointer; border: 2px solid var(--line); transition: 0.2s;" 
                 onclick="iniciarProjeto('${proj}')" 
                 onmouseover="this.style.borderColor='var(--ok)'" 
                 onmouseout="this.style.borderColor='var(--line)'">
                <div style="font-size: 32px; margin-bottom: 5px;">🤖</div>
                <h3 style="color: var(--ok); margin: 0; font-size: 16px;">${proj}</h3>
                <p style="color: var(--dim); font-size: 11px; margin-top: 5px;">▶️ CLIQUE PARA INICIAR</p>
            </div>`;
        });
        container.innerHTML = html;
    } catch (e) {
        console.error("Erro ao carregar projetos:", e);
    }
}

let logInterval = null; // Guarda o relógio do log

async function iniciarProjeto(nome) {
    if(!confirm(`Deseja MATAR o código atual e rodar [ ${nome} ] ?`)) return;
    
    const fd = new FormData();
    fd.append('projeto', nome);
    document.getElementById('status-projeto').innerHTML = `<span style="color:var(--warn)">Lançando ${nome}...</span>`;
    
    const logEl = document.getElementById('projeto-log');
    if(logEl) logEl.textContent = "Limpando log e iniciando...";
    
    try {
        const res = await fetch(`${API_PHP}?api=iniciar_projeto`, { method: 'POST', body: fd });
        const data = await res.json();
        mostrarToast(data.msg, data.status);
        
        if(data.status === 'ok') {
            document.getElementById('status-projeto').innerHTML = `<span style="color:var(--ok)">Rodando: ${nome}</span>`;
            
            // Ativa a leitura do log a cada 1 segundo (1000ms)
            if(logInterval) clearInterval(logInterval);
            logInterval = setInterval(() => atualizarLog(nome), 1000);
        }
    } catch (e) {
        mostrarToast("Erro ao iniciar", "erro");
    }
}

async function atualizarLog(nome) {
    try {
        const res = await fetch(`${API_PHP}?api=ler_log&projeto=${nome}`);
        const data = await res.json();
        const logEl = document.getElementById('projeto-log');
        if (logEl) {
            // Atualiza o texto e rola a barra para o final automaticamente
            logEl.textContent = data.log;
            logEl.scrollTop = logEl.scrollHeight;
        }
    } catch(e) {}
}

async function pararRobo() {
    try {
        const res = await fetch(`${API_PHP}?api=parar_robo`, { method: 'POST' });
        const data = await res.json();
        mostrarToast(data.msg, data.status);
        document.getElementById('status-projeto').innerHTML = `<span style="color:var(--bad)">Inativo (Nenhum Python rodando)</span>`;
        
        // Para o relógio de log e avisa na tela
        if(logInterval) clearInterval(logInterval);
        const logEl = document.getElementById('projeto-log');
        if(logEl) logEl.textContent += "\n\n[ PROCESSO INTERROMPIDO PELO USUÁRIO ]";
    } catch (e) {
        mostrarToast("Erro ao parar", "erro");
    }
}

// Invoca a função assim que a página carrega para desenhar a lista
carregarProjetos();

// Inicia
carregarListaArquivos();