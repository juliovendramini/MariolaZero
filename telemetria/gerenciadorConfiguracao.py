import json
import os

class GerenciadorConfiguracao:
    def __init__(self, caminho_arquivo="config.json"):
        self.caminho_arquivo = caminho_arquivo

    def salvar_parametro(self, chave, valor, tipo="text", min_val=None, max_val=None, step=None):
        #Salva ou atualiza um parâmetro individual mantendo a estrutura exigida pelo servico web.
        dados = self.carregar_bruto()
        
        # Monta a estrutura de metadados que o gerador HTML do JS consome
        param_data = {
            "valor": valor,
            "tipo": tipo
        }
        
        if min_val is not None:
            param_data["min"] = min_val
        if max_val is not None:
            param_data["max"] = max_val
        if step is not None:
            param_data["step"] = step

        dados[chave] = param_data
        self._escrever_arquivo(dados)

    def salvar_lote(self, novos_dados):

        #Salva múltiplos parâmetros de uma só vez.
        #'novos_dados' pode ser um dicionário onde a chave aponta diretamente para o valor ou para o dicionário completo com tipo.
        dados = self.carregar_bruto()
        
        for chave, info in novos_dados.items():
            if isinstance(info, dict) and "valor" in info and "tipo" in info:
                dados[chave] = info
            else:
                # Inferência básica caso passe apenas o valor cru
                tipo = "number" if isinstance(info, (int, float)) else "checkbox" if isinstance(info, bool) else "text"
                dados[chave] = {"valor": 1 if isinstance(info, bool) and info else (0 if isinstance(info, bool) else info), "tipo": tipo}
                
        self._escrever_arquivo(dados)

    def ler_parametro(self, chave):
        """Lê apenas um parâmetro específico do arquivo JSON."""
        dados = self.carregar_bruto()
        
        # Verifica se a chave existe no dicionário
        if chave in dados:
            return dados[chave]  # Retorna o dicionário completo ({"valor": X, "tipo": Y, ...})
            
        return None # Retorna None se a chave não existir

    def carregar_bruto(self):
        #Carrega o JSON atual do arquivo ou retorna um dicionário vazio se não existir.
        if os.path.exists(self.caminho_arquivo):
            try:
                with open(self.caminho_arquivo, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def apagar_arquivo_completo(self):
        #Remove o arquivo de configuração inteiro do disco.
        if os.path.exists(self.caminho_arquivo):
            os.remove(self.caminho_arquivo)
            print(f"O arquivo '{self.caminho_arquivo}' foi deletado.")
        else:
            print("O arquivo não existe para ser apagado.")

    def limpar_tudo(self):
        # Apaga todas as configurações, resetando o arquivo para um JSON vazio
        self._escrever_arquivo({})

    def _escrever_arquivo(self, dados):
        #Grava o dicionário formatado de volta no disco.
        with open(self.caminho_arquivo, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)


# ==========================================
# EXEMPLOS DE USO (EXECUTÁVEL)
# ==========================================
if __name__ == "__main__":
    # 1. Inicializando o gerenciador para um arquivo específico
    config = GerenciadorConfiguracao("resgate_config.json")
    print("Gerenciador inicializado para 'resgate_config.json'.\n")

    # 2. Usando 'salvar_parametro' (alterando/criando um item por vez)
    print("-> Salvando parâmetros individuais...")
    config.salvar_parametro(
        chave="limiar_sensor", 
        valor=512, 
        tipo="range", 
        min_val=0, 
        max_val=1023
    )
    
    config.salvar_parametro(
        chave="usar_camera_frontal", 
        valor=True, 
        tipo="checkbox"
    )

    config.salvar_parametro(
        chave="kp_direcao", 
        valor=1.25, 
        tipo="number", 
        step="0.01"
    )

    # 3. Usando 'salvar_lote' (alterando vários itens de uma vez)
    print("-> Salvando múltiplos parâmetros em lote...")
    novos_dados = {
        "velocidade_motor": {
            "valor": 150,
            "tipo": "number",
            "step": "1"
        },
        "tempo_espera": {
            "valor": 3.5,
            "tipo": "number",
            "step": "0.5"
        },
        "modo_silencioso": {
            "valor": False,
            "tipo": "checkbox"
        }
    }
    config.salvar_lote(novos_dados)

    # Pegando as informações completas de um parâmetro específico
    print("\n-> Lendo parametro especifico salvo no arquivo:")
    parametro = config.ler_parametro("limiar_sensor")

    if parametro:
        # Acessando apenas o valor de dentro do parâmetro
        valor_atual = parametro["valor"]
        tipo_atual = parametro["tipo"]
        
        print(f"O valor de limiar_sensor é {valor_atual} (tipo: {tipo_atual})")
    else:
        print("Esse parâmetro ainda não existe no arquivo!")

    # 4. Usando 'carregar_bruto' (lendo os dados do arquivo gerado)
    print("\n-> Lendo dados atuais salvos no arquivo:")
    dados_atuais = config.carregar_bruto()
    
    for chave, conteudo in dados_atuais.items():
        print(f"  • {chave} ➔ Valor: {conteudo['valor']} | Tipo: {conteudo['tipo']}")