# 🤖 Titãs da Robótica - Estação de Controle (GCS)

Uma Estação de Controle de Solo (Ground Control Station - GCS) leve, rápida e open-source para robótica móvel, desenvolvida pela equipe **Titãs da Robótica** (IFES Campus Colatina). 

Este painel foi projetado para facilitar a operação de robôs autônomos (como Futebol 2D e Robôs de Resgate/Seguidores de Linha) em ambientes de competição de alto nível, como o Mundial de Robótica na Coreia do Sul.

## ✨ Funcionalidades
* 🚀 **Lançador de Projetos:** Escaneia automaticamente a placa e cria botões de execução para qualquer projeto que contenha um arquivo `main.py`.
* 📊 **Telemetria e Logs em Tempo Real:** Acompanhe a saída do terminal (prints e erros do Python, YOLO, OpenCV) direto no navegador, sem precisar de SSH.
* ⚙️ **Editor de Parâmetros (JSON) Dinâmico:** Ajuste PID, velocidades, HSV da câmera e estratégias no meio da rodada, sem pausar ou reiniciar o código do robô.
* 🛡️ **Arquitetura Segura:** O painel web (Apache/PHP) roda isolado do código de controle (Python). Suporta partições *Read-Only* (somente leitura) para proteger o cartão SD contra corrompimentos indesejados.

---

## 🛠️ Requisitos
* **Hardwares (SBCs):** Banana Pi, Raspberry Pi, Orange Pi, etc.
* **Sistema Operacional:** Linux (Armbian, Debian, Ubuntu, Raspberry Pi OS).
* **Acesso:** Navegador Web (notebook, tablet ou smartphone).

---

## 📦 Instalação Automatizada

Não é necessário compilar nada manualmente. A estrutura deste repositório isola a aplicação na pasta `instalador`. O script contido nela baixa dependências, configura permissões de hardware (I2C, GPIO, Câmera) e ajusta o servidor web em poucos segundos.

### Passo a passo para instalar:

1. Acesse o terminal da sua placa Linux (via SSH ou cabo serial).
2. Clone este repositório e **entre na pasta do instalador**:
```bash
git clone [https://github.com/SEU_USUARIO/Painel-Telemetria-Robo.git](https://github.com/SEU_USUARIO/Painel-Telemetria-Robo.git)
cd Painel-Telemetria-Robo/instalador
```
*(Nota para desenvolvedores locais: Se você enviou os arquivos via script `.bat`, navegue até a pasta gerada, por exemplo: `cd ~/TELEMETRIA/instalador`)*

3. Execute o script de instalação com privilégios de administrador:
```bash
sudo bash install.sh
```

Pronto! Ao final da execução, o script exibirá o **IP da placa**. Basta digitar esse IP no seu navegador para acessar a Estação de Controle.

> **Nota de Segurança:** Se o seu sistema for protegido contra gravação (*Read-Only*), o instalador tentará rodar o arquivo `remonta.sh` automaticamente para liberar a escrita durante a configuração inicial e instalação do Apache.

---

## 📂 Como organizar os seus Projetos Python

Para que o **Lançador Automático** da interface encontre os seus códigos, você deve organizá-los em pastas no diretório principal do seu usuário (ex: `/home/banana/` ou `/home/pi/`).

**Regra de Ouro:** Todo projeto que deve aparecer como botão no painel precisa obrigatoriamente ter um arquivo chamado `main.py`.

### Exemplo de Estrutura de Pastas Esperada:
```text
/home/usuario/
├── meu_venv/                     # (Opcional) Ambiente virtual Python
├── robocup_futebol/              # ← O painel vai criar um botão para este projeto
│   ├── main.py                   # ← Obrigatório para ser detectado pelo Lançador!
│   ├── parametros.json           # Editável pela aba "Editor Avançado"
│   └── visao_computacional.py
└── robocup_resgate/              # ← O painel vai criar um botão para este projeto
    ├── main.py                   # ← Obrigatório para ser detectado pelo Lançador!
    └── parametros.json
```

---

## 🧠 Como o painel interage com o seu código Python?
A Estação de Controle foi projetada para não interferir negativamente na sua lógica nativa:
1. **Integração com Ambientes Virtuais (VENV):** Se você possuir um ambiente virtual chamado `meu_venv` na raiz do seu usuário (`/home/$USER/meu_venv`), o Lançador o utilizará automaticamente para executar o seu `main.py`. Caso não exista, ele usará o interpretador Python global do sistema Linux.
2. **Dados Dinâmicos em Tempo Real:** Salve as variáveis dinâmicas de calibração do seu robô em arquivos `.json` (ex: `parametros.json`) na pasta do projeto. A interface Web permite ler e editar esses arquivos na hora, e o seu código Python só precisa recarregar esse JSON a cada iteração do loop para aplicar as novas configurações sem precisar reiniciar os motores ou a câmera.

---

## 👨‍💻 Desenvolvedores
Desenvolvido por **Bernardo Schmiedel Raymundo**, **Gemini** e equipe **Titãs da Robótica**.
📍 IFES - Instituto Federal do Espírito Santo, Campus Colatina.
📱 Acompanhe nossa jornada para o Mundial de Robótica na Coreia do Sul pelo Instagram: [@titasdarobotica](https://instagram.com/titasdarobotica)

*Software de código aberto (Open Source). Sinta-se livre para clonar, modificar e utilizar em sua equipe!*