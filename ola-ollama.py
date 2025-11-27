import requests
import json



response = requests.post('http://localhost:11434/api/chat', 
    json={
        'model': 'gemma-3-1b-it-Q5_K_M:latest',
        'messages': [{'role': 'user', 'content': 'Olá'}],
        'stream': False
    }
)

# A resposta completa tem esta estrutura:
print(response.json()["message"]["content"])
