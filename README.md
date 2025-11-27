# Serviço de TTS e STT - Local e Remoto

Sistema completo de Text-to-Speech (TTS) e Speech-to-Text (STT) com suporte para modelos locais (Whisper + Piper) e remotos (OpenAI).

## 🎯 Funcionalidades

- **TTS Local**: Geração de áudio em alemão usando Piper-TTS
- **STT Local**: Transcrição de áudio usando Whisper (GPU)
- **STT Remoto**: Transcrição de áudio usando OpenAI Whisper API
- **Interface Gráfica**: Aplicação para gravar e comparar transcrições
- **Controle de Velocidade**: Ajuste de velocidade da fala (0.5x - 2.0x)

## 📋 Requisitos

- Python 3.13+
- CUDA (para aceleração GPU do Whisper local)
- Piper-TTS executável
- Conta OpenAI (para transcrição remota)

## 🚀 Instalação

### 1. Instalar Dependências Python

```bash
pip install -r requirements.txt
```

### 2. Instalar PyAudio (Windows)

```bash
pip install pipwin
pipwin install pyaudio
```

### 3. Configurar Variáveis de Ambiente

Edite o arquivo `.env` e configure:

```env
# Configurações do Serviço
SERVICE_PORT=3015
SERVICE_HOST=127.0.0.1

# OpenAI (obrigatório para transcrição remota)
OPENAI_API_KEY=sk-...
MODELO_TRANSCRICAO_OPENAI=whisper-1
```

### 4. Baixar Piper-TTS

**Windows:**
- Baixe de: https://github.com/rhasspy/piper/releases
- Extraia para a pasta `piper/` no diretório do projeto

**Ou execute o setup automático:**
```bash
setup_windows.bat
```

## 🎮 Uso

### Iniciar o Serviço

```bash
python servico_tts_e_stt.py
```

O serviço estará disponível em: `http://127.0.0.1:3015`

### Usar a Interface Gráfica

```bash
python gravador_transcricao.py
```

**Funcionalidades da Interface:**

1. **Gravar Áudio**: Clique em "🔴 Iniciar Gravação" para começar
2. **Parar Gravação**: Clique novamente para parar e salvar
3. **Transcrever Local**: Usa o Whisper local (GPU)
4. **Transcrever OpenAI**: Usa a API OpenAI
5. **Comparar**: Veja os resultados lado a lado

Os áudios são salvos em: `audios/`

## 📡 Endpoints da API

### Health Check
```http
GET /health
```

### Gerar Áudio (TTS)
```http
POST /api/generate-audio
Content-Type: application/json

{
  "text": "Ich bin sechsundfünfzig Jahre alt.",
  "voice": "Kore",
  "speed": 1.0
}
```

### Transcrever Áudio Local
```http
POST /api/transcribe-audio
Content-Type: multipart/form-data

file: [arquivo de áudio]
```

### Transcrever Áudio OpenAI
```http
POST /api/transcribe-audio-openai
Content-Type: multipart/form-data

file: [arquivo de áudio]
```

## 🔧 Configuração Avançada

### Ajustar Modelo Whisper Local

No arquivo `servico_tts_e_stt.py`, linha 137:

```python
whisper_model = whisper.load_model("large", device="cuda")
```

Modelos disponíveis: `tiny`, `base`, `small`, `medium`, `large`

### Ajustar Velocidade da Fala

Use o parâmetro `speed` no endpoint `/api/generate-audio`:

- `0.5` = Muito lento
- `1.0` = Normal
- `2.0` = Muito rápido

## 🐛 Solução de Problemas

### Erro: "Piper não encontrado"

1. Baixe o Piper de: https://github.com/rhasspy/piper/releases
2. Coloque em `piper/piper.exe`
3. Ou adicione ao PATH do sistema

### Erro: "OPENAI_API_KEY não configurada"

1. Obtenha sua chave em: https://platform.openai.com/api-keys
2. Adicione ao arquivo `.env`

### Erro: PyAudio não instala

**Windows:**
```bash
pip install pipwin
pipwin install pyaudio
```

**Linux:**
```bash
sudo apt-get install portaudio19-dev python3-pyaudio
pip install pyaudio
```

### Interface gráfica não abre

Verifique se o Tkinter está instalado:
```bash
python -m tkinter
```

## 📁 Estrutura do Projeto

```
servico_tts_e_stt/
├── servico_tts_e_stt.py           # API principal (Local + Remoto)
├── gravador_transcricao.py        # Interface gráfica
├── verificar_instalacao.py        # Script de verificação
├── requirements.txt               # Dependências completas
├── requirements-minimal.txt       # Dependências mínimas (só OpenAI)
├── .env                           # Configurações
├── README.md                      # Documentação
├── .gitignore                     # Ignorar arquivos sensíveis
├── audios/                        # Áudios gravados
├── piper/                         # Executável Piper
│   └── piper.exe
└── piper_models/                  # Modelos Piper
    └── de_DE-thorsten-medium.onnx
```

## 📊 Comparação: Local vs OpenAI

| Aspecto | Local (Whisper) | OpenAI |
|---------|----------------|--------|
| Velocidade | Média-Rápida (GPU) | Rápida |
| Custo | Gratuito | Pago ($0.006/min) |
| Privacidade | 100% local | Nuvem |
| Precisão | Alta | Muito Alta |
| Idiomas | 99+ | 99+ |
| Requisitos | GPU NVIDIA | API Key |

## 🎯 Casos de Uso

1. **Desenvolvimento Local**: Use Whisper local para testes
2. **Produção**: Use OpenAI para máxima precisão
3. **Privacidade**: Use apenas modelos locais
4. **Comparação**: Use a interface gráfica para testar ambos

## 🔗 Integração com Aplicação

Este serviço é usado pela aplicação Estudo de Idiomas nas funcionalidades:
- Prática de Audição (geração de áudio)
- Prática de Diálogo (geração de áudio e transcrição)

Certifique-se de que a aplicação está configurada para acessar este serviço na porta correta (3015).

## 📝 Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `SERVICE_PORT` | 3015 | Porta do serviço |
| `SERVICE_HOST` | 127.0.0.1 | Host do serviço |
| `CORS_ORIGINS` | (múltiplos) | Origens permitidas para CORS |
| `OPENAI_API_KEY` | - | Chave da API OpenAI |
| `MODELO_TRANSCRICAO_OPENAI` | whisper-1 | Modelo OpenAI para transcrição |

---

**Desenvolvido com ❤️ usando Python, FastAPI, Whisper, Piper e OpenAI**
