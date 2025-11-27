"""
Gravador de Áudio com Transcrição Local e Remota (OpenAI)
Interface gráfica para gravar áudio em alemão e comparar transcrições automaticamente
Com verificação de instalação integrada
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, Toplevel, filedialog
import pyaudio
import wave
import threading
import requests
from datetime import datetime
from pathlib import Path
import os
import sys
import time
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configurações
SERVICE_URL = f"http://{os.getenv('SERVICE_HOST', '127.0.0.1')}:{os.getenv('SERVICE_PORT', '3015')}"
AUDIOS_DIR = Path("audios")
AUDIOS_DIR.mkdir(exist_ok=True)

# Configurações de áudio
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

# ============================================
# VERIFICAÇÃO DE INSTALAÇÃO
# ============================================

def verificar_dependencias():
    """Verificar dependências essenciais"""
    erros = []

    # Verificar bibliotecas críticas
    libs_criticas = [
        ("pyaudio", "PyAudio"),
        ("requests", "Requests"),
        ("dotenv", "python-dotenv"),
    ]

    for modulo, nome in libs_criticas:
        try:
            __import__(modulo)
        except ImportError:
            erros.append(f"Biblioteca {nome} não instalada")

    # Verificar serviço
    try:
        response = requests.get(f"{SERVICE_URL}/health", timeout=5)
        if response.status_code != 200:
            erros.append(f"Serviço não está respondendo corretamente em {SERVICE_URL}")
    except:
        erros.append(f"Serviço não está acessível em {SERVICE_URL}\nCertifique-se de que servico_tts_e_stt.py está rodando")

    return erros

# ============================================
# CLASSE PRINCIPAL
# ============================================

class GravadorTranscricao:
    def __init__(self, root):
        self.root = root
        self.root.title("Gravador de Áudio - Transcrição Automática (Alemão)")
        self.root.geometry("950x750")
        self.root.resizable(False, False)

        # Estado da gravação
        self.gravando = False
        self.frames = []
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.ultimo_arquivo = None

        # Tempos de transcrição
        self.tempo_local = 0
        self.tempo_openai = 0

        self.criar_interface()

    def criar_interface(self):
        """Criar todos os elementos da interface"""

        # Título
        titulo = tk.Label(
            self.root,
            text="🎤 Gravador de Áudio - Transcrição Automática (DE)",
            font=("Arial", 18, "bold"),
            bg="#2196F3",
            fg="white",
            pady=15
        )
        titulo.pack(fill=tk.X)

        # Frame principal
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Seção de Gravação ---
        gravacao_frame = tk.LabelFrame(
            main_frame,
            text="📹 Gravação e Transcrição Automática",
            font=("Arial", 12, "bold"),
            padx=10,
            pady=10
        )
        gravacao_frame.pack(fill=tk.X, pady=(0, 15))

        # Botão de gravar
        self.btn_gravar = tk.Button(
            gravacao_frame,
            text="🔴 Iniciar Gravação",
            font=("Arial", 14, "bold"),
            bg="#f44336",
            fg="white",
            command=self.toggle_gravacao,
            height=2,
            cursor="hand2"
        )
        self.btn_gravar.pack(fill=tk.X, pady=5)

        # Frame para botão adicional
        btns_extras = tk.Frame(gravacao_frame)
        btns_extras.pack(fill=tk.X, pady=5)

        # Botão carregar áudio
        self.btn_carregar = tk.Button(
            btns_extras,
            text="📁 Carregar Áudio",
            font=("Arial", 10),
            bg="#2196F3",
            fg="white",
            command=self.carregar_audio,
            cursor="hand2"
        )
        self.btn_carregar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # Botão modo individual
        self.btn_individual = tk.Button(
            btns_extras,
            text="🎯 Transcrição Individual",
            font=("Arial", 10),
            bg="#9C27B0",
            fg="white",
            command=self.abrir_modo_individual,
            cursor="hand2"
        )
        self.btn_individual.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # Label de status
        self.label_status = tk.Label(
            gravacao_frame,
            text="Pronto para gravar",
            font=("Arial", 10),
            fg="#666"
        )
        self.label_status.pack(pady=5)

        # Label do último arquivo
        self.label_arquivo = tk.Label(
            gravacao_frame,
            text="",
            font=("Arial", 9),
            fg="#999"
        )
        self.label_arquivo.pack()

        # Barra de progresso
        self.progress = ttk.Progressbar(
            gravacao_frame,
            mode='indeterminate',
            length=300
        )
        self.progress.pack(pady=5)

        # --- Resultados ---
        resultados_frame = tk.Frame(main_frame)
        resultados_frame.pack(fill=tk.BOTH, expand=True)

        # Coluna Esquerda - Transcrição Local
        coluna_esquerda = tk.Frame(resultados_frame)
        coluna_esquerda.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Header com tempo
        header_local_frame = tk.Frame(coluna_esquerda, bg="#4CAF50")
        header_local_frame.pack(fill=tk.X)

        label_local = tk.Label(
            header_local_frame,
            text="🖥️ Transcrição Local (Whisper)",
            font=("Arial", 11, "bold"),
            bg="#4CAF50",
            fg="white",
            pady=8
        )
        label_local.pack(side=tk.LEFT, padx=10)

        self.label_tempo_local = tk.Label(
            header_local_frame,
            text="",
            font=("Arial", 9),
            bg="#4CAF50",
            fg="white"
        )
        self.label_tempo_local.pack(side=tk.RIGHT, padx=10)

        self.texto_local = scrolledtext.ScrolledText(
            coluna_esquerda,
            wrap=tk.WORD,
            font=("Arial", 10),
            height=18,
            state=tk.DISABLED
        )
        self.texto_local.pack(fill=tk.BOTH, expand=True)

        # Coluna Direita - Transcrição OpenAI
        coluna_direita = tk.Frame(resultados_frame)
        coluna_direita.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # Header com tempo
        header_openai_frame = tk.Frame(coluna_direita, bg="#FF9800")
        header_openai_frame.pack(fill=tk.X)

        label_openai = tk.Label(
            header_openai_frame,
            text="☁️ Transcrição OpenAI",
            font=("Arial", 11, "bold"),
            bg="#FF9800",
            fg="white",
            pady=8
        )
        label_openai.pack(side=tk.LEFT, padx=10)

        self.label_tempo_openai = tk.Label(
            header_openai_frame,
            text="",
            font=("Arial", 9),
            bg="#FF9800",
            fg="white"
        )
        self.label_tempo_openai.pack(side=tk.RIGHT, padx=10)

        self.texto_openai = scrolledtext.ScrolledText(
            coluna_direita,
            wrap=tk.WORD,
            font=("Arial", 10),
            height=18,
            state=tk.DISABLED
        )
        self.texto_openai.pack(fill=tk.BOTH, expand=True)

        # --- Rodapé ---
        rodape = tk.Label(
            self.root,
            text=f"Serviço: {SERVICE_URL} | Áudios: {AUDIOS_DIR.absolute()} | Idioma: Alemão (DE)",
            font=("Arial", 8),
            fg="#999",
            pady=5
        )
        rodape.pack(fill=tk.X)

    def toggle_gravacao(self):
        """Alternar entre iniciar e parar gravação"""
        if not self.gravando:
            self.iniciar_gravacao()
        else:
            self.parar_gravacao()

    def carregar_audio(self):
        """Carregar arquivo de áudio do HD e iniciar transcrição automática"""
        # Tipos de arquivo suportados
        filetypes = (
            ('Arquivos de Áudio', '*.wav *.mp3 *.m4a *.flac *.ogg'),
            ('Todos os arquivos', '*.*')
        )

        # Abrir diálogo de seleção de arquivo
        filepath = filedialog.askopenfilename(
            title='Selecione um arquivo de áudio',
            initialdir=AUDIOS_DIR,
            filetypes=filetypes
        )

        if not filepath:
            return  # Usuário cancelou

        try:
            # Converter para Path e verificar se existe
            filepath = Path(filepath)
            if not filepath.exists():
                messagebox.showerror("Erro", "Arquivo não encontrado!")
                return

            # Limpar resultados anteriores
            self.atualizar_texto(self.texto_local, "")
            self.atualizar_texto(self.texto_openai, "")
            self.label_tempo_local.config(text="")
            self.label_tempo_openai.config(text="")

            # Armazenar arquivo
            self.ultimo_arquivo = filepath

            # Atualizar interface
            self.label_status.config(
                text="⏳ Transcrevendo arquivo carregado...",
                fg="blue",
                font=("Arial", 10, "bold")
            )
            self.label_arquivo.config(
                text=f"Arquivo: {filepath.name}"
            )

            # Desabilitar botões durante transcrição
            self.btn_carregar.config(state=tk.DISABLED)
            self.btn_individual.config(state=tk.DISABLED)
            self.btn_gravar.config(state=tk.DISABLED)

            # Iniciar barra de progresso
            self.progress.start(10)

            # Iniciar transcrição automática
            self.transcrever_automatico()

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar áudio:\n{str(e)}")

    def iniciar_gravacao(self):
        """Iniciar gravação de áudio"""
        try:
            self.gravando = True
            self.frames = []

            # Limpar resultados anteriores
            self.atualizar_texto(self.texto_local, "")
            self.atualizar_texto(self.texto_openai, "")
            self.label_tempo_local.config(text="")
            self.label_tempo_openai.config(text="")

            # Atualizar interface
            self.btn_gravar.config(
                text="⏹️ Parar Gravação",
                bg="#ff5722"
            )
            self.label_status.config(
                text="🔴 GRAVANDO...",
                fg="red",
                font=("Arial", 10, "bold")
            )
            self.btn_individual.config(state=tk.DISABLED)

            # Iniciar stream de áudio
            self.stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
                stream_callback=self.audio_callback
            )

            self.stream.start_stream()

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao iniciar gravação:\n{str(e)}")
            self.gravando = False
            self.restaurar_interface()

    def audio_callback(self, in_data, frame_count, time_info, status):
        """Callback para capturar áudio"""
        if self.gravando:
            self.frames.append(in_data)
        return (in_data, pyaudio.paContinue)

    def parar_gravacao(self):
        """Parar gravação, salvar arquivo e iniciar transcrição automática"""
        try:
            self.gravando = False

            # Parar stream
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()

            # Salvar arquivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"audio_{timestamp}.wav"
            filepath = AUDIOS_DIR / filename

            wf = wave.open(str(filepath), 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(self.frames))
            wf.close()

            self.ultimo_arquivo = filepath

            # Atualizar interface
            self.label_status.config(
                text="⏳ Transcrevendo automaticamente...",
                fg="blue",
                font=("Arial", 10, "bold")
            )
            self.label_arquivo.config(
                text=f"Arquivo: {filename}"
            )

            self.restaurar_interface()

            # Iniciar barra de progresso
            self.progress.start(10)

            # Iniciar transcrição automática
            self.transcrever_automatico()

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao salvar áudio:\n{str(e)}")
            self.restaurar_interface()

    def restaurar_interface(self):
        """Restaurar botão de gravação ao estado inicial"""
        self.btn_gravar.config(
            text="🔴 Iniciar Gravação",
            bg="#f44336"
        )

    def transcrever_automatico(self):
        """Iniciar transcrição automática nos dois serviços"""
        if not self.ultimo_arquivo:
            return

        # Atualizar textos iniciais
        self.atualizar_texto(self.texto_local, "⏳ Transcrevendo com Whisper local...\n")
        self.atualizar_texto(self.texto_openai, "⏳ Transcrevendo com OpenAI...\n")

        # Iniciar threads em sequência
        thread_local = threading.Thread(target=self._transcrever_local_auto)
        thread_openai = threading.Thread(target=self._transcrever_openai_auto)

        thread_local.start()
        thread_openai.start()

    def _transcrever_local_auto(self):
        """Thread para transcrição local automática"""
        inicio = time.time()

        try:
            with open(self.ultimo_arquivo, 'rb') as f:
                files = {'file': (self.ultimo_arquivo.name, f, 'audio/wav')}
                # Especificar idioma alemão via parâmetro
                response = requests.post(
                    f"{SERVICE_URL}/api/transcribe-audio",
                    files=files,
                    timeout=120
                )

            tempo_decorrido = time.time() - inicio
            self.tempo_local = tempo_decorrido

            if response.status_code == 200:
                resultado = response.json()
                texto = resultado.get('text', '')

                output = f"✅ Transcrição Local Concluída\n\n"
                output += f"Texto:\n{texto}\n\n"

                if resultado.get('segments'):
                    output += "Segmentos com timestamp:\n"
                    for seg in resultado['segments']:
                        output += f"[{seg['start']:.2f}s - {seg['end']:.2f}s] {seg['text']}\n"

                self.atualizar_texto(self.texto_local, output)
                self.root.after(0, lambda: self.label_tempo_local.config(text=f"⏱️ {tempo_decorrido:.2f}s"))
            else:
                self.atualizar_texto(
                    self.texto_local,
                    f"❌ Erro na transcrição local:\n{response.status_code} - {response.text}"
                )

        except Exception as e:
            self.atualizar_texto(
                self.texto_local,
                f"❌ Erro na transcrição local:\n{str(e)}"
            )

        finally:
            self.verificar_conclusao()

    def _transcrever_openai_auto(self):
        """Thread para transcrição OpenAI automática"""
        inicio = time.time()

        try:
            with open(self.ultimo_arquivo, 'rb') as f:
                files = {'file': (self.ultimo_arquivo.name, f, 'audio/wav')}
                # Especificar idioma alemão via parâmetro (se a API suportar)
                response = requests.post(
                    f"{SERVICE_URL}/api/transcribe-audio-openai",
                    files=files,
                    timeout=120
                )

            tempo_decorrido = time.time() - inicio
            self.tempo_openai = tempo_decorrido

            if response.status_code == 200:
                resultado = response.json()
                texto = resultado.get('text', '')

                output = f"✅ Transcrição OpenAI Concluída\n\n"
                output += f"Texto:\n{texto}\n\n"

                if resultado.get('segments'):
                    output += "Segmentos com timestamp:\n"
                    for seg in resultado['segments']:
                        output += f"[{seg['start']:.2f}s - {seg['end']:.2f}s] {seg['text']}\n"

                self.atualizar_texto(self.texto_openai, output)
                self.root.after(0, lambda: self.label_tempo_openai.config(text=f"⏱️ {tempo_decorrido:.2f}s"))
            else:
                self.atualizar_texto(
                    self.texto_openai,
                    f"❌ Erro na transcrição OpenAI:\n{response.status_code} - {response.text}"
                )

        except Exception as e:
            self.atualizar_texto(
                self.texto_openai,
                f"❌ Erro na transcrição OpenAI:\n{str(e)}"
            )

        finally:
            self.verificar_conclusao()

    def verificar_conclusao(self):
        """Verificar se ambas as transcrições terminaram"""
        # Esta função será chamada por ambas as threads
        # Usar um contador seria melhor, mas vamos simplificar
        def parar_progress():
            self.progress.stop()
            self.label_status.config(
                text="✅ Transcrições concluídas!",
                fg="green",
                font=("Arial", 10, "bold")
            )
            self.btn_individual.config(state=tk.NORMAL)
            self.btn_carregar.config(state=tk.NORMAL)
            self.btn_gravar.config(state=tk.NORMAL)

        # Aguardar um pouco para garantir que ambas terminaram
        self.root.after(1000, parar_progress)

    def atualizar_texto(self, widget, texto):
        """Atualizar texto em um widget ScrolledText"""
        def update():
            widget.config(state=tk.NORMAL)
            widget.delete(1.0, tk.END)
            widget.insert(1.0, texto)
            widget.config(state=tk.DISABLED)

        self.root.after(0, update)

    def abrir_modo_individual(self):
        """Abrir janela de modo individual"""
        ModoIndividual(self.root, self.ultimo_arquivo)

    def on_closing(self):
        """Limpar recursos ao fechar"""
        if self.gravando:
            self.parar_gravacao()

        # Fechar stream com tratamento de erro
        if self.stream:
            try:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
            except:
                pass  # Stream já foi fechado

        try:
            self.audio.terminate()
        except:
            pass

        self.root.destroy()


# ============================================
# JANELA MODO INDIVIDUAL
# ============================================

class ModoIndividual:
    def __init__(self, parent, arquivo_inicial=None):
        self.janela = Toplevel(parent)
        self.janela.title("Modo Transcrição Individual")
        self.janela.geometry("800x600")
        self.janela.resizable(False, False)

        self.audio = pyaudio.PyAudio()
        self.gravando = False
        self.frames = []
        self.stream = None
        self.ultimo_arquivo = arquivo_inicial

        self.criar_interface()

        # Configurar evento de fechamento
        self.janela.protocol("WM_DELETE_WINDOW", self.on_closing)

    def criar_interface(self):
        """Criar interface do modo individual"""

        # Título
        titulo = tk.Label(
            self.janela,
            text="🎯 Modo Transcrição Individual",
            font=("Arial", 16, "bold"),
            bg="#9C27B0",
            fg="white",
            pady=12
        )
        titulo.pack(fill=tk.X)

        # Frame principal
        main_frame = tk.Frame(self.janela, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Seção de gravação
        gravacao_frame = tk.LabelFrame(
            main_frame,
            text="Gravação",
            font=("Arial", 11, "bold"),
            padx=10,
            pady=10
        )
        gravacao_frame.pack(fill=tk.X, pady=(0, 15))

        # Frame para botões de gravação e carregar
        btns_grav_frame = tk.Frame(gravacao_frame)
        btns_grav_frame.pack(fill=tk.X, pady=5)

        self.btn_gravar = tk.Button(
            btns_grav_frame,
            text="🔴 Gravar",
            font=("Arial", 12, "bold"),
            bg="#f44336",
            fg="white",
            command=self.toggle_gravacao,
            height=2
        )
        self.btn_gravar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.btn_carregar = tk.Button(
            btns_grav_frame,
            text="📁 Carregar",
            font=("Arial", 12, "bold"),
            bg="#2196F3",
            fg="white",
            command=self.carregar_audio,
            height=2
        )
        self.btn_carregar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        self.label_status = tk.Label(
            gravacao_frame,
            text="Pronto" if not self.ultimo_arquivo else f"Arquivo carregado: {self.ultimo_arquivo.name}",
            font=("Arial", 9),
            fg="#666"
        )
        self.label_status.pack()

        # Botões de transcrição
        btns_frame = tk.Frame(main_frame)
        btns_frame.pack(fill=tk.X, pady=(0, 15))

        self.btn_local = tk.Button(
            btns_frame,
            text="🖥️ Transcrever Local",
            font=("Arial", 11, "bold"),
            bg="#4CAF50",
            fg="white",
            command=self.transcrever_local,
            height=2,
            state=tk.NORMAL if self.ultimo_arquivo else tk.DISABLED
        )
        self.btn_local.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.btn_openai = tk.Button(
            btns_frame,
            text="☁️ Transcrever OpenAI",
            font=("Arial", 11, "bold"),
            bg="#FF9800",
            fg="white",
            command=self.transcrever_openai,
            height=2,
            state=tk.NORMAL if self.ultimo_arquivo else tk.DISABLED
        )
        self.btn_openai.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # Área de resultado
        resultado_frame = tk.LabelFrame(
            main_frame,
            text="Resultado",
            font=("Arial", 11, "bold"),
            padx=10,
            pady=10
        )
        resultado_frame.pack(fill=tk.BOTH, expand=True)

        self.texto_resultado = scrolledtext.ScrolledText(
            resultado_frame,
            wrap=tk.WORD,
            font=("Arial", 10),
            state=tk.DISABLED
        )
        self.texto_resultado.pack(fill=tk.BOTH, expand=True)

    def toggle_gravacao(self):
        if not self.gravando:
            self.iniciar_gravacao()
        else:
            self.parar_gravacao()

    def iniciar_gravacao(self):
        try:
            self.gravando = True
            self.frames = []

            self.btn_gravar.config(text="⏹️ Parar", bg="#ff5722")
            self.label_status.config(text="🔴 GRAVANDO...", fg="red")

            self.stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
                stream_callback=self.audio_callback
            )
            self.stream.start_stream()

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao gravar:\n{str(e)}")
            self.gravando = False

    def audio_callback(self, in_data, frame_count, time_info, status):
        if self.gravando:
            self.frames.append(in_data)
        return (in_data, pyaudio.paContinue)

    def parar_gravacao(self):
        try:
            self.gravando = False

            if self.stream:
                self.stream.stop_stream()
                self.stream.close()

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"audio_individual_{timestamp}.wav"
            filepath = AUDIOS_DIR / filename

            wf = wave.open(str(filepath), 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(self.frames))
            wf.close()

            self.ultimo_arquivo = filepath

            self.btn_gravar.config(text="🔴 Gravar", bg="#f44336")
            self.label_status.config(text=f"Salvo: {filename}", fg="green")
            self.btn_local.config(state=tk.NORMAL)
            self.btn_openai.config(state=tk.NORMAL)

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao salvar:\n{str(e)}")

    def carregar_audio(self):
        """Carregar arquivo de áudio do HD"""
        # Tipos de arquivo suportados
        filetypes = (
            ('Arquivos de Áudio', '*.wav *.mp3 *.m4a *.flac *.ogg'),
            ('Todos os arquivos', '*.*')
        )

        # Abrir diálogo de seleção de arquivo
        filepath = filedialog.askopenfilename(
            title='Selecione um arquivo de áudio',
            initialdir=AUDIOS_DIR,
            filetypes=filetypes
        )

        if not filepath:
            return  # Usuário cancelou

        try:
            # Converter para Path e verificar se existe
            filepath = Path(filepath)
            if not filepath.exists():
                messagebox.showerror("Erro", "Arquivo não encontrado!")
                return

            # Armazenar arquivo
            self.ultimo_arquivo = filepath

            # Atualizar interface
            self.label_status.config(
                text=f"Arquivo carregado: {filepath.name}",
                fg="green"
            )

            # Habilitar botões de transcrição
            self.btn_local.config(state=tk.NORMAL)
            self.btn_openai.config(state=tk.NORMAL)

            # Limpar texto anterior
            self.atualizar_texto("")

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar áudio:\n{str(e)}")

    def transcrever_local(self):
        if not self.ultimo_arquivo:
            return

        self.atualizar_texto("⏳ Transcrevendo com Whisper local...\n")
        thread = threading.Thread(target=self._transcrever_local_thread)
        thread.start()

    def _transcrever_local_thread(self):
        inicio = time.time()

        try:
            with open(self.ultimo_arquivo, 'rb') as f:
                files = {'file': (self.ultimo_arquivo.name, f, 'audio/wav')}
                response = requests.post(
                    f"{SERVICE_URL}/api/transcribe-audio",
                    files=files,
                    timeout=120
                )

            tempo = time.time() - inicio

            if response.status_code == 200:
                resultado = response.json()
                output = f"✅ Transcrição Local ({tempo:.2f}s)\n\n{resultado.get('text', '')}"
                self.atualizar_texto(output)
            else:
                self.atualizar_texto(f"❌ Erro: {response.status_code}")

        except Exception as e:
            self.atualizar_texto(f"❌ Erro: {str(e)}")

    def transcrever_openai(self):
        if not self.ultimo_arquivo:
            return

        self.atualizar_texto("⏳ Transcrevendo com OpenAI...\n")
        thread = threading.Thread(target=self._transcrever_openai_thread)
        thread.start()

    def _transcrever_openai_thread(self):
        inicio = time.time()

        try:
            with open(self.ultimo_arquivo, 'rb') as f:
                files = {'file': (self.ultimo_arquivo.name, f, 'audio/wav')}
                response = requests.post(
                    f"{SERVICE_URL}/api/transcribe-audio-openai",
                    files=files,
                    timeout=120
                )

            tempo = time.time() - inicio

            if response.status_code == 200:
                resultado = response.json()
                output = f"✅ Transcrição OpenAI ({tempo:.2f}s)\n\n{resultado.get('text', '')}"
                self.atualizar_texto(output)
            else:
                self.atualizar_texto(f"❌ Erro: {response.status_code}")

        except Exception as e:
            self.atualizar_texto(f"❌ Erro: {str(e)}")

    def atualizar_texto(self, texto):
        def update():
            self.texto_resultado.config(state=tk.NORMAL)
            self.texto_resultado.delete(1.0, tk.END)
            self.texto_resultado.insert(1.0, texto)
            self.texto_resultado.config(state=tk.DISABLED)
        self.janela.after(0, update)

    def on_closing(self):
        """Limpar recursos ao fechar a janela individual"""
        if self.gravando:
            try:
                self.gravando = False
                if self.stream:
                    self.stream.stop_stream()
                    self.stream.close()
            except:
                pass

        # Fechar stream se existir
        if self.stream:
            try:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
            except:
                pass

        try:
            self.audio.terminate()
        except:
            pass

        self.janela.destroy()


# ============================================
# FUNÇÃO PRINCIPAL
# ============================================

def main():
    """Função principal"""

    # Verificar dependências
    print("🔍 Verificando instalação...")
    erros = verificar_dependencias()

    if erros:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Erro de Instalação",
            "Problemas encontrados:\n\n" + "\n".join(f"• {erro}" for erro in erros) +
            "\n\nCertifique-se de que:\n1. pip install -r requirements.txt foi executado\n2. servico_tts_e_stt.py está rodando"
        )
        root.destroy()
        sys.exit(1)

    print("✅ Verificação concluída!")

    # Iniciar aplicação
    root = tk.Tk()
    app = GravadorTranscricao(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
