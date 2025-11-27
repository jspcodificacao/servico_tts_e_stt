"""
Script de Teste do Serviço TTS/STT
Testa o fluxo completo: TTS -> STT -> Validação com LLM
"""

import os
import sys
import json
import base64
import requests
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from colorama import init, Fore, Style

# Inicializar colorama para cores no terminal Windows
init(autoreset=True)

# Carregar variáveis de ambiente
load_dotenv()

# Configurações
SERVICE_HOST = os.getenv("SERVICE_HOST", "127.0.0.1")
SERVICE_PORT = os.getenv("SERVICE_PORT", "3015")
LLM_SERVICE_PORT = os.getenv("LLM_SERVICE_PORT", "11434")
LLM_MODEL = os.getenv("LLM_MODEL", "gemma-3-1b-it-Q5_K_M:latest")
FRASE_TTS_ALEMAO = os.getenv("FRASE_TTS_ALEMAO", "Guten Morgen")

# URLs dos serviços
TTS_STT_BASE_URL = f"http://{SERVICE_HOST}:{SERVICE_PORT}"
LLM_BASE_URL = f"http://localhost:{LLM_SERVICE_PORT}"

# Remover aspas da frase se existirem
FRASE_TTS_ALEMAO = FRASE_TTS_ALEMAO.strip('"').strip("'")


def print_header(text):
    """Imprime cabeçalho formatado"""
    print("\n" + "=" * 70)
    print(f"{Fore.CYAN}{Style.BRIGHT}{text}")
    print("=" * 70)


def print_success(text):
    """Imprime mensagem de sucesso"""
    print(f"{Fore.GREEN}✓ {text}")


def print_error(text):
    """Imprime mensagem de erro"""
    print(f"{Fore.RED}✗ {text}")


def print_info(text):
    """Imprime mensagem informativa"""
    print(f"{Fore.YELLOW}ℹ {text}")


def print_result(label, value):
    """Imprime resultado formatado"""
    print(f"{Fore.MAGENTA}{label}:{Style.RESET_ALL} {value}")


def verificar_servico_tts_stt():
    """Verifica se o serviço TTS/STT está rodando"""
    try:
        response = requests.get(f"{TTS_STT_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print_success(f"Serviço TTS/STT disponível em {TTS_STT_BASE_URL}")
            data = response.json()
            print_info(f"GPU: {data.get('gpu', False)}")
            print_info(f"Piper disponível: {data.get('piper_available', False)}")
            return True
        else:
            print_error(f"Serviço TTS/STT retornou status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print_error(f"Serviço TTS/STT não está disponível: {e}")
        print_info(f"Certifique-se de que o serviço está rodando na porta {SERVICE_PORT}")
        return False


def verificar_servico_llm():
    """Verifica se o serviço LLM (Ollama) está rodando"""
    try:
        response = requests.get(f"{LLM_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            print_success(f"Serviço LLM (Ollama) disponível em {LLM_BASE_URL}")
            data = response.json()
            models = [m['name'] for m in data.get('models', [])]
            print_info(f"Modelos disponíveis: {', '.join(models)}")
            if LLM_MODEL in models:
                print_success(f"Modelo {LLM_MODEL} encontrado")
            else:
                print_error(f"Modelo {LLM_MODEL} não encontrado")
            return True
        else:
            print_error(f"Serviço LLM retornou status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print_error(f"Serviço LLM não está disponível: {e}")
        print_info(f"Certifique-se de que o Ollama está rodando na porta {LLM_SERVICE_PORT}")
        return False


def gerar_audio(texto, velocidade=1.0):
    """Gera áudio a partir de texto usando TTS"""
    print_header("ETAPA 1: Geração de Áudio (TTS)")
    print_result("Texto original", texto)
    print_result("Velocidade", f"{velocidade}x")

    try:
        response = requests.post(
            f"{TTS_STT_BASE_URL}/api/generate-audio",
            json={"text": texto, "speed": velocidade},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            audio_base64 = data.get("audio", "")

            # Decodificar base64 para bytes
            audio_bytes = base64.b64decode(audio_base64)

            print_success(f"Áudio gerado com sucesso ({len(audio_bytes)} bytes)")
            print_info(f"Metadados: {data.get('metadata', {})}")

            return audio_bytes
        else:
            print_error(f"Erro ao gerar áudio: {response.status_code}")
            print_error(response.text)
            return None

    except Exception as e:
        print_error(f"Erro ao gerar áudio: {e}")
        return None


def transcrever_audio(audio_bytes):
    """Transcreve áudio para texto usando STT"""
    print_header("ETAPA 2: Transcrição de Áudio (STT)")

    try:
        # Salvar áudio em arquivo temporário
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name

        print_info(f"Áudio salvo temporariamente em: {temp_path}")

        # Enviar para transcrição
        with open(temp_path, "rb") as audio_file:
            files = {"file": ("audio.wav", audio_file, "audio/wav")}
            response = requests.post(
                f"{TTS_STT_BASE_URL}/api/transcribe-audio",
                files=files,
                timeout=120
            )

        # Remover arquivo temporário
        os.unlink(temp_path)

        if response.status_code == 200:
            data = response.json()
            transcricao = data.get("text", "").strip()

            print_success("Áudio transcrito com sucesso")
            print_result("Transcrição", transcricao)
            print_info(f"Idioma detectado: {data.get('language', 'N/A')}")

            return transcricao
        else:
            print_error(f"Erro ao transcrever áudio: {response.status_code}")
            print_error(response.text)
            return None

    except Exception as e:
        print_error(f"Erro ao transcrever áudio: {e}")
        return None


def validar_com_llm(texto_original, transcricao):
    """Valida se a transcrição é equivalente ao texto original usando LLM"""
    print_header("ETAPA 3: Validação com LLM (Ollama)")

    prompt = f"""Compare these two German texts and determine if they are semantically equivalent.

Original text: {texto_original}
Transcribed text: {transcricao}

Consider:
- Minor spelling variations
- Punctuation differences
- Case differences (uppercase/lowercase)
- Common transcription errors

Respond ONLY with a JSON object in this exact format:
{{"equivalent": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}

Do not include any other text or explanation outside the JSON."""

    print_info("Enviando para Ollama...")
    print_result("Modelo", LLM_MODEL)

    try:
        response = requests.post(
            f"{LLM_BASE_URL}/api/generate",
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "format": "json",
                "stream": False
            },
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()
            response_text = data.get("response", "{}")

            # Parse do JSON retornado
            try:
                result = json.loads(response_text)
                equivalent = result.get("equivalent", False)
                confidence = result.get("confidence", 0.0)
                reason = result.get("reason", "N/A")

                print_success("Análise LLM concluída")

                if equivalent:
                    print(f"\n{Fore.GREEN}{Style.BRIGHT}✓ TEXTOS EQUIVALENTES")
                else:
                    print(f"\n{Fore.RED}{Style.BRIGHT}✗ TEXTOS NÃO EQUIVALENTES")

                print_result("Confiança", f"{confidence:.2%}")
                print_result("Razão", reason)

                return equivalent, confidence, reason

            except json.JSONDecodeError as e:
                print_error(f"Erro ao parsear resposta do LLM: {e}")
                print_info(f"Resposta recebida: {response_text}")
                return False, 0.0, "Erro ao parsear resposta"
        else:
            print_error(f"Erro ao consultar LLM: {response.status_code}")
            print_error(response.text)
            return False, 0.0, "Erro na requisição"

    except Exception as e:
        print_error(f"Erro ao validar com LLM: {e}")
        return False, 0.0, str(e)


def executar_teste_completo():
    """Executa o teste completo do serviço"""
    print_header("TESTE DO SERVIÇO TTS/STT")
    print_info(f"Frase de teste: {FRASE_TTS_ALEMAO}")
    print_info(f"URL TTS/STT: {TTS_STT_BASE_URL}")
    print_info(f"URL LLM: {LLM_BASE_URL}")

    # Verificar serviços
    print_header("Verificação de Serviços")
    tts_stt_ok = verificar_servico_tts_stt()
    llm_ok = verificar_servico_llm()

    if not tts_stt_ok:
        print_error("\n❌ Serviço TTS/STT não está disponível. Abortando teste.")
        return False

    if not llm_ok:
        print_error("\n❌ Serviço LLM não está disponível. Abortando teste.")
        return False

    # Etapa 1: Gerar áudio
    audio_bytes = gerar_audio(FRASE_TTS_ALEMAO, velocidade=1.0)
    if not audio_bytes:
        print_error("\n❌ Falha na geração de áudio. Abortando teste.")
        return False

    # Etapa 2: Transcrever áudio
    transcricao = transcrever_audio(audio_bytes)
    if not transcricao:
        print_error("\n❌ Falha na transcrição de áudio. Abortando teste.")
        return False

    # Etapa 3: Validar com LLM
    equivalent, confidence, reason = validar_com_llm(FRASE_TTS_ALEMAO, transcricao)

    # Resultado final
    print_header("RESULTADO FINAL")
    print_result("Texto original", FRASE_TTS_ALEMAO)
    print_result("Transcrição", transcricao)
    print_result("Equivalentes", "SIM" if equivalent else "NÃO")
    print_result("Confiança", f"{confidence:.2%}")
    print_result("Observação", reason)

    if equivalent and confidence >= 0.7:
        print(f"\n{Fore.GREEN}{Style.BRIGHT}{'='*70}")
        print(f"{Fore.GREEN}{Style.BRIGHT}✓ TESTE PASSOU - Serviço TTS/STT funcionando corretamente!")
        print(f"{Fore.GREEN}{Style.BRIGHT}{'='*70}\n")
        return True
    else:
        print(f"\n{Fore.RED}{Style.BRIGHT}{'='*70}")
        print(f"{Fore.RED}{Style.BRIGHT}✗ TESTE FALHOU - Verifique os resultados acima")
        print(f"{Fore.RED}{Style.BRIGHT}{'='*70}\n")
        return False


if __name__ == "__main__":
    print(f"\n{Fore.CYAN}{Style.BRIGHT}╔═══════════════════════════════════════════════════════════════════╗")
    print(f"{Fore.CYAN}{Style.BRIGHT}║         TESTE DO SERVIÇO TTS/STT COM VALIDAÇÃO LLM              ║")
    print(f"{Fore.CYAN}{Style.BRIGHT}╚═══════════════════════════════════════════════════════════════════╝\n")

    try:
        sucesso = executar_teste_completo()
        sys.exit(0 if sucesso else 1)
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}⚠ Teste interrompido pelo usuário")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n{Fore.RED}✗ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
