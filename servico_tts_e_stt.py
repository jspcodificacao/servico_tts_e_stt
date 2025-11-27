"""
Serviço Local de LLM para Transcrição e TTS
Compatível com a interface do Gemini Service
Usando Piper-TTS para Python 3.13+
COM CONTROLE DE VELOCIDADE DA FALA
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import whisper
import torch
from typing import List, Dict, Optional
import tempfile
import os
import base64
import subprocess
import json
import wave
import requests
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Carregar variáveis de ambiente
load_dotenv()

# Configurações do serviço
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "3015"))
SERVICE_HOST = os.getenv("SERVICE_HOST", "127.0.0.1")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3005,http://localhost:5173,http://localhost:3010").split(",")

app = FastAPI(title="Local LLM Service")

# Configurar CORS para permitir requests do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# CONFIGURAÇÃO OPENAI
# ============================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODELO_TRANSCRICAO_OPENAI = os.getenv("MODELO_TRANSCRICAO_OPENAI", "whisper-1")

if OPENAI_API_KEY:
    client_openai = OpenAI(api_key=OPENAI_API_KEY)
else:
    client_openai = None

# ============================================
# CONFIGURAÇÃO PIPER-TTS
# ============================================

# Diretório para modelos Piper
PIPER_MODELS_DIR = Path("piper_models")
PIPER_MODELS_DIR.mkdir(exist_ok=True)

# Configuração do modelo de voz alemã
PIPER_MODEL_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx"
PIPER_CONFIG_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json"

PIPER_MODEL_PATH = PIPER_MODELS_DIR / "de_DE-thorsten-medium.onnx"
PIPER_CONFIG_PATH = PIPER_MODELS_DIR / "de_DE-thorsten-medium.onnx.json"

# ============================================
# FUNÇÕES AUXILIARES PIPER
# ============================================

def download_piper_model():
    """Baixa o modelo Piper se não existir"""
    if not PIPER_MODEL_PATH.exists():
        print("📥 Baixando modelo Piper alemão...")
        
        # Baixar modelo
        response = requests.get(PIPER_MODEL_URL, stream=True)
        with open(PIPER_MODEL_PATH, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("✓ Modelo baixado")
        
        # Baixar config
        response = requests.get(PIPER_CONFIG_URL)
        with open(PIPER_CONFIG_PATH, 'wb') as f:
            f.write(response.content)
        print("✓ Configuração baixada")
    else:
        print("✓ Modelo Piper já existe")

def get_piper_executable():
    """Encontra o executável do Piper no sistema"""
    # Possíveis localizações no Windows
    possible_paths = [
        "piper\\piper.exe",  # Diretório local (extraído do ZIP)
        "piper.exe",  # No PATH
        str(Path("venv") / "Scripts" / "piper.exe"),
        str(Path.cwd() / "piper" / "piper.exe"),
    ]
    
    for path in possible_paths:
        path_obj = Path(path)
        if path_obj.exists() and path_obj.is_file():
            print(f"✓ Piper encontrado em: {path_obj.absolute()}")
            return str(path_obj.absolute())
    
    # Tentar encontrar no PATH do sistema
    try:
        result = subprocess.run(
            ["where", "piper.exe"] if os.name == "nt" else ["which", "piper"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            piper_path = result.stdout.strip().split('\n')[0]
            print(f"✓ Piper encontrado no PATH: {piper_path}")
            return piper_path
    except Exception:
        pass
    
    raise FileNotFoundError(
        "❌ Piper não encontrado!\n"
        "Opções:\n"
        "1. Execute setup_windows.bat para baixar automaticamente\n"
        "2. Baixe manualmente de: https://github.com/rhasspy/piper/releases\n"
        "3. Instale via pip: pip install piper-tts (e adicione ao PATH)"
    )

# ============================================
# INICIALIZAÇÃO DOS MODELOS
# ============================================

print("Carregando modelos...")

# Baixar modelo Piper se necessário
try:
    download_piper_model()
    PIPER_EXECUTABLE = get_piper_executable()
    print(f"✓ Piper executável: {PIPER_EXECUTABLE}")
except Exception as e:
    print(f"⚠️ Aviso Piper: {e}")
    PIPER_EXECUTABLE = None

# Whisper para transcrição
whisper_model = whisper.load_model("large", device="cuda")
print("✓ Whisper carregado")

# Verificar VRAM disponível
if torch.cuda.is_available():
    print(f"✓ GPU: {torch.cuda.get_device_name(0)}")
    print(f"✓ VRAM disponível: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")

# ============================================
# MODELOS DE DADOS
# ============================================

class GenerateAudioRequest(BaseModel):
    text: str
    voice: str = "Kore"  # Mantém compatibilidade com API original
    speed: Optional[float] = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description="Velocidade da fala: 0.5 (lento) a 2.0 (rápido). Padrão: 1.0"
    )

class DialogueTurn(BaseModel):
    type: str  # "QUESTION" ou "ANSWER"
    text: str

class GenerateSummaryRequest(BaseModel):
    dialogue: List[DialogueTurn]

# ============================================
# ENDPOINTS
# ============================================

@app.get("/health")
async def health_check():
    """Verificar se o serviço está rodando"""
    return {
        "status": "healthy",
        "models": {
            "whisper": "large",
            "tts": "piper (de_DE-thorsten-medium)",
            "openai_transcription": MODELO_TRANSCRICAO_OPENAI if OPENAI_API_KEY else "not configured"
        },
        "gpu": torch.cuda.is_available(),
        "piper_available": PIPER_EXECUTABLE is not None,
        "openai_available": client_openai is not None,
        "features": {
            "speed_control": True,
            "speed_range": "0.5 - 2.0"
        }
    }

@app.post("/api/generate-audio")
async def generate_audio(request: GenerateAudioRequest):
    """
    Gerar áudio a partir de texto (TTS)
    Equivalente ao generateAudio() do Gemini
    Usando Piper-TTS com controle de velocidade
    
    Args:
        text: Texto para sintetizar
        voice: Voz (compatibilidade, não utilizado)
        speed: Velocidade da fala (0.5 = lento, 1.0 = normal, 2.0 = rápido)
    """
    if not PIPER_EXECUTABLE:
        raise HTTPException(
            status_code=503,
            detail="Piper TTS não disponível. Instale com: pip install piper-tts"
        )
    
    try:
        # Criar arquivo temporário para o áudio
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            output_path = temp_file.name
        
        # Criar arquivo temporário para o texto
        with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False, encoding='utf-8') as text_file:
            text_file.write(request.text)
            text_path = text_file.name
        
        # Calcular length_scale (inverso da velocidade)
        # speed=2.0 -> length_scale=0.5 (mais rápido)
        # speed=1.0 -> length_scale=1.0 (normal)
        # speed=0.5 -> length_scale=2.0 (mais lento)
        length_scale = 1.0 / request.speed
        
        print(f"🎤 Gerando áudio com velocidade: {request.speed}x (length_scale: {length_scale:.2f})")
        
        # Executar Piper via linha de comando com length-scale
        cmd = [
            PIPER_EXECUTABLE,
            "--model", str(PIPER_MODEL_PATH),
            "--config", str(PIPER_CONFIG_PATH),
            "--output_file", output_path,
            "--length_scale", str(length_scale)  # Controle de velocidade
        ]
        
        # Executar comando
        result = subprocess.run(
            cmd,
            input=request.text.encode('utf-8'),
            capture_output=True,
            check=True
        )
        
        # Verificar se o arquivo foi criado
        if not Path(output_path).exists():
            raise Exception("Arquivo de áudio não foi gerado")
        
        # Ler e codificar em base64
        with open(output_path, "rb") as audio_file:
            audio_bytes = audio_file.read()
            base64_audio = base64.b64encode(audio_bytes).decode("utf-8")
        
        # Limpar arquivos temporários
        os.unlink(output_path)
        os.unlink(text_path)
        
        return JSONResponse({
            "audio": base64_audio,
            "mimeType": "audio/wav",
            "metadata": {
                "speed": request.speed,
                "length_scale": length_scale
            }
        })
    
    except subprocess.CalledProcessError as e:
        print(f"Erro ao executar Piper: {e}")
        print(f"STDOUT: {e.stdout.decode('utf-8', errors='ignore')}")
        print(f"STDERR: {e.stderr.decode('utf-8', errors='ignore')}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate audio with Piper: {e.stderr.decode('utf-8', errors='ignore')}"
        )
    
    except Exception as e:
        print(f"Erro ao gerar áudio: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate audio: {str(e)}")
    
    finally:
        # Limpar cache CUDA se necessário
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

@app.post("/api/transcribe-audio")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Transcrever áudio para texto (STT)
    Equivalente ao transcribeAudio() do Gemini
    """
    temp_path = None
    try:
        # Ler arquivo de áudio
        audio_bytes = await file.read()
        
        # Determinar extensão baseada no content type ou filename
        file_extension = Path(file.filename).suffix if file.filename else ".wav"
        if not file_extension:
            file_extension = ".wav"
        
        # Salvar temporariamente com a extensão correta
        with tempfile.NamedTemporaryFile(
            suffix=file_extension, 
            delete=False,
            mode='wb'
        ) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name
        
        print(f"📄 Arquivo temporário criado: {temp_path}")
        print(f"📊 Tamanho: {len(audio_bytes)} bytes")
        
        # Verificar se o arquivo existe
        if not Path(temp_path).exists():
            raise FileNotFoundError(f"Arquivo temporário não foi criado: {temp_path}")
        
        # Transcrever com Whisper
        print("🎤 Iniciando transcrição com Whisper...")
        result = whisper_model.transcribe(
            temp_path,
            language="de",  # Alemão
            fp16=torch.cuda.is_available(),  # Usar half-precision se GPU disponível
            task="transcribe",
            verbose=False
        )
        
        print(f"✅ Transcrição concluída: {result['text'][:50]}...")
        
        return JSONResponse({
            "text": result["text"].strip(),
            "language": result.get("language", "de"),
            "segments": [
                {
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"]
                }
                for seg in result.get("segments", [])
            ]
        })
    
    except Exception as e:
        print(f"❌ Erro ao transcrever áudio: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to transcribe audio: {str(e)}"
        )
    
    finally:
        # Limpar arquivo temporário
        if temp_path and Path(temp_path).exists():
            try:
                os.unlink(temp_path)
                print(f"🗑️ Arquivo temporário removido: {temp_path}")
            except Exception as e:
                print(f"⚠️ Não foi possível remover arquivo temporário: {e}")
        
        # Limpar cache CUDA
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

@app.post("/api/transcribe-audio-openai")
async def transcribe_audio_openai(file: UploadFile = File(...)):
    """
    Transcrever áudio usando o modelo da OpenAI.
    Depende das variáveis de ambiente:
    - OPENAI_API_KEY
    - MODELO_TRANSCRICAO_OPENAI
    """
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY não configurada."
        )

    if not MODELO_TRANSCRICAO_OPENAI:
        raise HTTPException(
            status_code=500,
            detail="MODELO_TRANSCRICAO_OPENAI não configurado."
        )

    try:
        audio_bytes = await file.read()

        # Enviar para transcrição usando o novo cliente OpenAI
        print("🎤 Enviando áudio para OpenAI (idioma: alemão)...")
        response = client_openai.audio.transcriptions.create(
            file=("audio.wav", audio_bytes, file.content_type),
            model=MODELO_TRANSCRICAO_OPENAI,
            language="de"  # Especificar idioma alemão
        )

        print("✅ Resposta recebida da OpenAI")

        # A resposta padrão da API OpenAI tem pelo menos: text
        text = response.text

        # Se houver segmentos (dependendo do modelo), formate
        segments = []
        if hasattr(response, "segments") and response.segments:
            segments = [
                {
                    "start": seg.get("start"),
                    "end": seg.get("end"),
                    "text": seg.get("text")
                }
                for seg in response.segments
            ]

        return JSONResponse({
            "text": text,
            "language": getattr(response, "language", None),
            "segments": segments
        })

    except Exception as e:
        print(f"❌ Erro no serviço OpenAI: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao transcrever via OpenAI: {str(e)}"
        )

# ============================================
# INICIALIZAÇÃO
# ============================================

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*50)
    print("🚀 Serviço TTS/STT Local e Remoto iniciado")
    print(f"📡 Host: {SERVICE_HOST}")
    print(f"🔌 Porta: {SERVICE_PORT}")
    print("📡 Endpoints disponíveis:")
    print("   - POST /api/generate-audio")
    print("   - POST /api/transcribe-audio (Whisper local)")
    print("   - POST /api/transcribe-audio-openai (OpenAI)")
    print("   - GET  /health")
    print(f"🌐 CORS permitido para: {', '.join(CORS_ORIGINS)}")
    if client_openai:
        print(f"✓ OpenAI: Configurado (Modelo: {MODELO_TRANSCRICAO_OPENAI})")
    else:
        print("⚠️  OpenAI: Não configurado (adicione OPENAI_API_KEY no .env)")
    print("="*50 + "\n")

    uvicorn.run(app, host=SERVICE_HOST, port=SERVICE_PORT)