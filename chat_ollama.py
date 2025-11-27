import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import ollama
import time
import threading


class OllamaGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Ollama Client")
        self.root.geometry("800x600")
        
        # Variáveis
        self.models = []
        self.is_processing = False
        
        # Frame superior - Seleção de modelo
        top_frame = ttk.Frame(root, padding="10")
        top_frame.pack(fill=tk.X)
        
        ttk.Label(top_frame, text="Modelo:").pack(side=tk.LEFT, padx=5)
        
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(top_frame, textvariable=self.model_var, 
                                        state="readonly", width=30)
        self.model_combo.pack(side=tk.LEFT, padx=5)
        
        self.refresh_btn = ttk.Button(top_frame, text="Atualizar", 
                                      command=self.load_models)
        self.refresh_btn.pack(side=tk.LEFT, padx=5)
        
        # Frame de entrada
        input_frame = ttk.LabelFrame(root, text="Pergunta", padding="10")
        input_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)
        
        self.input_text = scrolledtext.ScrolledText(input_frame, height=4, 
                                                     wrap=tk.WORD)
        self.input_text.pack(fill=tk.BOTH, expand=True)
        
        # Botão enviar
        btn_frame = ttk.Frame(root, padding="5")
        btn_frame.pack(fill=tk.X)
        
        self.send_btn = ttk.Button(btn_frame, text="Enviar", 
                                   command=self.send_query)
        self.send_btn.pack(side=tk.LEFT, padx=10)
        
        self.stop_btn = ttk.Button(btn_frame, text="Parar", 
                                   command=self.stop_generation, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=10)
        
        # Frame de estatísticas
        stats_frame = ttk.Frame(root, padding="5")
        stats_frame.pack(fill=tk.X)
        
        self.stats_label = ttk.Label(stats_frame, text="Pronto", 
                                     foreground="blue")
        self.stats_label.pack(side=tk.LEFT, padx=10)
        
        # Frame de resposta
        output_frame = ttk.LabelFrame(root, text="Resposta", padding="10")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.output_text = scrolledtext.ScrolledText(output_frame, height=15, 
                                                      wrap=tk.WORD, 
                                                      state=tk.DISABLED)
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # Carregar modelos ao iniciar
        self.load_models()
        
    def load_models(self):
        """Carrega lista de modelos disponíveis no Ollama"""
        try:
            models_response = ollama.list()
            
            # A resposta é um objeto com atributo 'models'
            # Cada modelo tem atributo 'model' (não 'name')
            if hasattr(models_response, 'models'):
                self.models = [model.model for model in models_response.models]
            elif isinstance(models_response, dict) and 'models' in models_response:
                self.models = [model['model'] for model in models_response['models']]
            else:
                self.models = []
            
            self.model_combo['values'] = self.models
            
            if self.models:
                self.model_combo.current(0)
            else:
                messagebox.showwarning("Aviso", 
                    "Nenhum modelo encontrado. Execute 'ollama pull <modelo>' primeiro.")
                
        except Exception as e:
            messagebox.showerror("Erro", 
                f"Erro ao conectar com Ollama: {str(e)}\n\n"
                "Certifique-se de que o Ollama está em execução.")
    
    def send_query(self):
        """Envia a pergunta para o modelo"""
        if self.is_processing:
            return
            
        model = self.model_var.get()
        question = self.input_text.get("1.0", tk.END).strip()
        
        if not model:
            messagebox.showwarning("Aviso", "Selecione um modelo.")
            return
            
        if not question:
            messagebox.showwarning("Aviso", "Digite uma pergunta.")
            return
        
        # Limpar resposta anterior
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.config(state=tk.DISABLED)
        
        # Desabilitar controles
        self.is_processing = True
        self.send_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.stats_label.config(text="Processando...", foreground="orange")
        
        # Executar em thread separada
        thread = threading.Thread(target=self.process_query, 
                                  args=(model, question))
        thread.daemon = True
        thread.start()
    
    def process_query(self, model, question):
        """Processa a query em thread separada"""
        try:
            start_time = time.time()
            total_tokens = 0
            response_text = ""
            
            stream = ollama.chat(
                model=model,
                messages=[{'role': 'user', 'content': question}],
                stream=True
            )
            
            for chunk in stream:
                if not self.is_processing:
                    break
                
                content = chunk['message']['content']
                response_text += content
                
                # Atualizar UI na thread principal
                self.root.after(0, self.update_output, content)
                
                # Contar tokens (aproximação: split por espaços)
                total_tokens += len(content.split())
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            if self.is_processing:
                tokens_per_sec = total_tokens / elapsed_time if elapsed_time > 0 else 0
                stats_text = (f"Tempo: {elapsed_time:.2f}s | "
                            f"Tokens: ~{total_tokens} | "
                            f"Velocidade: ~{tokens_per_sec:.1f} tokens/s")
                
                self.root.after(0, self.update_stats, stats_text, "green")
            
        except Exception as e:
            error_msg = f"Erro: {str(e)}"
            self.root.after(0, self.update_stats, error_msg, "red")
            self.root.after(0, self.update_output, f"\n\n{error_msg}")
        
        finally:
            self.root.after(0, self.reset_controls)
    
    def update_output(self, text):
        """Atualiza o texto de saída"""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)
    
    def update_stats(self, text, color):
        """Atualiza as estatísticas"""
        self.stats_label.config(text=text, foreground=color)
    
    def stop_generation(self):
        """Para a geração de texto"""
        self.is_processing = False
        self.update_stats("Geração interrompida", "red")
    
    def reset_controls(self):
        """Reabilita os controles"""
        self.is_processing = False
        self.send_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)


if __name__ == "__main__":
    root = tk.Tk()
    app = OllamaGUI(root)
    root.mainloop()