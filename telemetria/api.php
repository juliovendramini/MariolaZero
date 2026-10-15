<?php
// Configura o cabeçalho para que todas as respostas retornem como JSON
header('Content-Type: application/json');

// Define a ação solicitada pela API via AJAX (GET ou POST)
$acao = $_REQUEST['api'] ?? '';

// Garante o caminho absoluto da pasta atual onde este arquivo está guardado
// $pasta = __DIR__ . '/';
$pasta = '/home/banana/telemetria/';

// =========================================================================
// 1. TERMINAL DINÂMICO
// =========================================================================
if ($acao === 'executar_comando') {
    $comando = $_POST['comando'] ?? '';
    if (trim($comando) !== '') {
        // O "2>&1" joga os erros do Linux na saída padrão para que apareçam na tela
        $saida = shell_exec($comando . ' 2>&1');
        echo json_encode(['saida' => $saida === null ? '' : $saida]);
    } else {
        echo json_encode(['saida' => '']);
    }
    exit;
}

// =========================================================================
// 2. LISTAR ARQUIVOS JSON
// =========================================================================
if ($acao === 'listar_arquivos') {
    // Busca todos os arquivos .json na pasta absoluta do projeto
    $arquivos_encontrados = glob($pasta . '*.json');
    $arquivos = [];
    
    if (!empty($arquivos_encontrados)) {
        foreach ($arquivos_encontrados as $caminho_completo) {
            // Pega apenas o nome do arquivo (ex: "parametros.json") e remove o caminho longo
            $arquivos[] = basename($caminho_completo);
        }
    }
    
    // Se a pasta estiver vazia, cria um arquivo padrão para a interface não quebrar
    if (empty($arquivos)) {
        file_put_contents($pasta . 'geral.json', "{}");
        $arquivos = ['geral.json'];
    }
    
    echo json_encode(['arquivos' => $arquivos]);
    exit;
}

// =========================================================================
// 3. LER ARQUIVO JSON
// =========================================================================
if ($acao === 'ler_arquivo') {
    $arquivo = $_GET['file'] ?? '';
    // basename() impede ataques de "Directory Traversal" (fazer ../../ para ler arquivos do sistema)
    $caminho = $pasta . basename($arquivo);
    
    if (file_exists($caminho) && !empty($arquivo)) {
        echo json_encode(['conteudo' => file_get_contents($caminho)]);
    } else {
        echo json_encode(['conteudo' => '{}']);
    }
    exit;
}

// =========================================================================
// 4. SALVAR EDITOR AVANÇADO (RAW)
// =========================================================================
if ($acao === 'salvar_raw') {
    $arquivo = $_POST['file'] ?? '';
    $caminho = $pasta . basename($arquivo);
    $novo_json = $_POST['dados_json'] ?? '';
    
    if (empty($arquivo)) {
        echo json_encode(['status' => 'erro', 'msg' => 'Nenhum arquivo especificado.']);
        exit;
    }

    // Valida se o texto enviado é realmente um JSON válido antes de salvar no disco
    if (json_decode($novo_json) !== null) {
        file_put_contents($caminho, $novo_json);
        echo json_encode(['status' => 'ok', 'msg' => "Arquivo '$arquivo' salvo com sucesso!"]);
    } else {
        echo json_encode(['status' => 'erro', 'msg' => "Erro de sintaxe! O JSON inserido é inválido."]);
    }
    exit;
}

// =========================================================================
// 5. SALVAR PAINEL INTERATIVO (DINÂMICO)
// =========================================================================
if ($acao === 'salvar_dinamico') {
    $arquivo = $_POST['file'] ?? '';
    $caminho = $pasta . basename($arquivo);
    
    if (empty($arquivo) || !file_exists($caminho)) {
        echo json_encode(['status' => 'erro', 'msg' => 'Arquivo não encontrado para aplicar modificações.']);
        exit;
    }
    
    // Carrega o JSON atual estruturado para preservar os tipos (tipo, min, max, etc)
    $json_original = json_decode(file_get_contents($caminho), true);

    if (is_array($json_original)) {
        foreach ($json_original as $key => $meta) {
            // Ignora se o campo não seguir a estrutura padrão do painel de controle
            if (!is_array($meta) || !isset($meta['valor'])) continue;

            // Se o campo veio na requisição POST, atualiza seu valor mantendo o tipo original
            if (isset($_POST[$key])) {
                $new_val = $_POST[$key];
                $old_val = $meta['valor'];
                
                if (is_int($old_val)) {
                    $json_original[$key]['valor'] = (int)$new_val;
                } elseif (is_float($old_val)) {
                    $json_original[$key]['valor'] = (float)$new_val;
                } elseif (is_bool($old_val)) {
                    $json_original[$key]['valor'] = filter_var($new_val, FILTER_VALIDATE_BOOLEAN);
                } else {
                    $json_original[$key]['valor'] = $new_val;
                }
            } 
            // Se for um checkbox e não veio no POST, significa que o usuário o desmarcou
            elseif ($meta['tipo'] === 'checkbox') {
                $json_original[$key]['valor'] = false;
            }
        }
        
        // Salva de volta formatado de forma legível para o Python ler sem problemas
        file_put_contents($caminho, json_encode($json_original, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
        echo json_encode(['status' => 'ok', 'msg' => "Parâmetros aplicados em '$arquivo'!"]);
    } else {
        echo json_encode(['status' => 'erro', 'msg' => 'Falha ao processar a estrutura do arquivo original.']);
    }
    exit;
}

// =========================================================================
// 6. LISTAR PASTAS COM MAIN.PY
// =========================================================================
if ($acao === 'listar_projetos') {
    $base_dir = '/home/banana/';
    $projetos = [];
    
    // Puxa apenas as pastas dentro do diretório do usuário
    $pastas = glob($base_dir . '*', GLOB_ONLYDIR);
    foreach ($pastas as $pasta) {
        // Se existir um main.py lá dentro, é um projeto válido
        if (file_exists($pasta . '/main.py')) {
            $projetos[] = basename($pasta);
        }
    }
    echo json_encode(['projetos' => $projetos]);
    exit;
}

// =========================================================================
// 7. INICIAR PROJETO (RODANDO COMO USUÁRIO BANANA)
// =========================================================================
if ($acao === 'iniciar_projeto') {
    $projeto = $_POST['projeto'] ?? '';
    $pasta_projeto = '/home/banana/' . basename($projeto);
    $caminho_main = $pasta_projeto . '/main.py';
    
    $arquivo_log = '/tmp/robo_painel.log'; 

    if (!empty($projeto) && file_exists($caminho_main)) {
        // O "-n" impede que o sudo trave pedindo senha. Se ele não tiver permissão, vai cuspir um erro no log!
        shell_exec('sudo -n -u banana pkill -f main.py');
        
        $python_bin = file_exists('/home/banana/meu_venv/bin/python3') 
                      ? '/home/banana/meu_venv/bin/python3' 
                      : 'python3';
        
        shell_exec("echo '--- Iniciando projeto: $projeto ---' > $arquivo_log");
        shell_exec("chmod 777 $arquivo_log");
        
        // Esta é a linha definitiva. Usamos nohup por fora do sudo, exportamos o unbuffered e desconectamos do Apache (< /dev/null)
        $comando = "nohup sudo -n -u banana bash -c 'cd \"$pasta_projeto\" && export PYTHONUNBUFFERED=1 && \"$python_bin\" -u \"$caminho_main\"' >> $arquivo_log 2>&1 < /dev/null &";
        shell_exec($comando);
        
        echo json_encode(['status' => 'ok', 'msg' => "Lançamento: '$projeto' iniciado!"]);
    } else {
        echo json_encode(['status' => 'erro', 'msg' => "Projeto não encontrado!"]);
    }
    exit;
}

// =========================================================================
// 8. PARAR ROBÔ
// =========================================================================
if ($acao === 'parar_robo') {
    shell_exec('sudo -n -u banana pkill -f main.py');
    echo json_encode(['status' => 'ok', 'msg' => "Processos parados! Motores livres."]);
    exit;
}

// =========================================================================
// 9. LER LOG EM TEMPO REAL
// =========================================================================
if ($acao === 'ler_log') {
    // Aponta a leitura para o mesmo local seguro
    $arquivo_log = '/tmp/robo_painel.log'; 
    
    if (file_exists($arquivo_log)) {
        $log = shell_exec("tail -n 50 " . escapeshellarg($arquivo_log));
        echo json_encode(['log' => $log ?: 'Log vazio (Nenhum print feito ainda).']);
    } else {
        echo json_encode(['log' => 'Aguardando sistema criar o arquivo de log...']);
    }
    exit;
}
// Se cair aqui, a rota solicitada não existe na nossa API
echo json_encode(['status' => 'erro', 'msg' => 'Ação de API inválida ou não especificada.']);