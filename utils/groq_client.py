"""
Client wrapper pour Groq API compatible avec l'interface Claude SDK.
"""

import os
import json
import requests
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()


class GroqClient:
    """Client Groq compatible avec l'interface Claude."""
    
    # Modèles disponibles sur Groq
    AVAILABLE_MODELS = {
        "llama-3.1-70b": "llama-3.1-70b-versatile",
        "llama-3.1-8b": "llama-3.1-8b-instant",
        "llama-3.2-90b": "llama-3.2-90b-text-preview",
        "llama-3.3-70b": "llama-3.3-70b-versatile",
        "mixtral-8x7b": "mixtral-8x7b-32768",
        "gemma-7b": "gemma-7b-it",
        "gemma2-9b": "gemma2-9b-it",
    }
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        base_url: str = "https://api.groq.com/openai/v1",
        model: str = "llama-3.1-70b",
        timeout: int = 300
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY non trouvée dans .env")
        
        self.base_url = base_url
        self.model = self.AVAILABLE_MODELS.get(model, model)
        self.timeout = timeout
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def create(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        max_retries: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Appel API Groq avec retry automatique en cas de rate limit.
        
        Args:
            messages: Liste de messages [{"role": "user", "content": "..."}]
            model: Modèle à utiliser (optionnel)
            max_tokens: Nombre max de tokens
            temperature: Température (0-2)
            max_retries: Nombre de tentatives en cas de rate limit
            **kwargs: Paramètres additionnels
        
        Returns:
            Réponse formatée compatible Claude
        """
        import time
        
        used_model = self.AVAILABLE_MODELS.get(model, self.model) if model else self.model
        
        payload = {
            "model": used_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs
        }
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                groq_response = response.json()
                
                # Formater la réponse comme Claude
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": groq_response["choices"][0]["message"]["content"]
                        }
                    ],
                    "model": groq_response["model"],
                    "usage": {
                        "input_tokens": groq_response["usage"]["prompt_tokens"],
                        "output_tokens": groq_response["usage"]["completion_tokens"]
                    }
                }
            
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limit
                    last_error = e
                    if attempt < max_retries - 1:
                        # Backoff exponentiel : 2s, 4s, 8s, etc.
                        wait_time = 2 ** (attempt + 1)
                        print(f"⚠️  Rate limit atteint. Nouvelle tentative dans {wait_time}s (tentative {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"Rate limit Groq dépassé après {max_retries} tentatives. Attendez quelques minutes ou utilisez Ollama.")
                else:
                    raise Exception(f"Erreur HTTP Groq {e.response.status_code}: {str(e)}")
            
            except requests.exceptions.Timeout:
                raise TimeoutError(f"Groq API timeout après {self.timeout}s")
            
            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** (attempt + 1)
                    print(f"⚠️  Erreur réseau. Nouvelle tentative dans {wait_time}s (tentative {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Erreur Groq API après {max_retries} tentatives: {str(e)}")
        
        # Ne devrait pas arriver ici
        if last_error:
            raise last_error


class GroqClientWrapper:
    """Wrapper pour compatibilité totale avec l'architecture existante."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.1-70b", timeout: int = 300):
        self.client = GroqClient(api_key=api_key, model=model, timeout=timeout)
        self.messages = self.Messages(self.client)
        self.default_model = model
    
    def create_message(
        self,
        model: str,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> Any:
        """
        Méthode compatible avec ClaudeClient.create_message().
        
        Args:
            model: Modèle à utiliser
            messages: Liste de messages
            system: System prompt (non utilisé par Groq mais accepté pour compatibilité)
            temperature: Température
            max_tokens: Max tokens
            **kwargs: Paramètres additionnels
        
        Returns:
            Response object compatible avec Claude
        """
        # Créer une copie pour éviter de modifier la liste originale
        messages_copy = list(messages)
        
        # Si un system prompt est fourni, vérifier qu'il n'existe pas déjà
        if system:
            has_system = any(msg.get("role") == "system" for msg in messages_copy)
            if not has_system:
                messages_copy = [{"role": "system", "content": system}] + messages_copy
        
        response_data = self.client.create(
            messages=messages_copy,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
        
        return self.Response(response_data)
    
    class Messages:
        def __init__(self, client: GroqClient):
            self.client = client
        
        def create(self, messages: List[Dict[str, str]], **kwargs) -> Any:
            response = self.client.create(messages=messages, **kwargs)
            return GroqClientWrapper.Response(response)
    
    class Response:
        def __init__(self, response_data: Dict[str, Any]):
            self.content = [self.ContentBlock(response_data["content"][0]["text"])]
            self.model = response_data["model"]
            self.usage = response_data.get("usage", {})
        
        class ContentBlock:
            def __init__(self, text: str):
                self.text = text
                self.type = "text"


def get_available_groq_models() -> Dict[str, str]:
    """Retourne la liste des modèles Groq disponibles."""
    return GroqClient.AVAILABLE_MODELS


def test_groq_connection(api_key: Optional[str] = None, model: str = "llama-3.1-8b") -> bool:
    """
    Teste la connexion à Groq API.
    
    Args:
        api_key: Clé API (optionnel, utilise .env par défaut)
        model: Modèle à tester
    
    Returns:
        True si la connexion fonctionne
    """
    try:
        client = GroqClientWrapper(api_key=api_key, model=model)
        response = client.messages.create(
            messages=[{"role": "user", "content": "Bonjour"}],
            max_tokens=50,
            temperature=0.5
        )
        return bool(response.content[0].text)
    except Exception as e:
        print(f"❌ Erreur de connexion Groq: {e}")
        return False


if __name__ == "__main__":
    print("🔍 Test de connexion Groq API...")
    print("\nModèles disponibles:")
    for key, model_id in get_available_groq_models().items():
        print(f"  • {key}: {model_id}")
    
    print("\n🧪 Test de connexion...")
    if test_groq_connection():
        print("✅ Connexion Groq réussie!")
    else:
        print("❌ Échec de la connexion Groq")
