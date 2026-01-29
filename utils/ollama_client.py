"""
Ollama client wrapper compatible avec l'interface Claude.
Permet d'utiliser des modèles locaux (Qwen3, etc.) via Ollama.
"""

import logging
import json
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class OllamaClient:
    """Wrapper for Ollama that mimics Anthropic Claude client interface."""
    
    def __init__(
        self,
        model: str = "qwen2.5:latest",
        base_url: str = "http://localhost:11434",
        timeout: int = 600,
        api_key: Optional[str] = None  # Not used but kept for compatibility
    ):
        """
        Initialize Ollama client.
        
        Args:
            model: Model name in Ollama (e.g., "qwen2.5:latest", "llama3:latest")
            base_url: Ollama API URL
            timeout: Request timeout in seconds (default: 600)
            api_key: Not used for Ollama but kept for interface compatibility
        """
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
        # Paramètres par défaut (peuvent être modifiés pour gridsearch)
        self.default_temperature = 0.7
        self.default_max_tokens = 4096
        self.default_top_p = 0.9
        self.default_repeat_penalty = 1.0
        
        logger.info(f"OllamaClient initialized with model: {model}, timeout: {timeout}s")
    
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
        Create a message with Ollama (compatible with Claude interface).
        
        Args:
            model: Model name (will be overridden by self.model)
            messages: List of message dicts with 'role' and 'content'
            system: System prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            Response object mimicking Claude's response format
        """
        try:
            import requests
        except ImportError:
            raise ImportError("requests library required. Install with: pip install requests")
        
        # Use the configured model
        model_to_use = self.model
        
        # Build prompt from messages
        prompt_parts = []
        
        if system:
            prompt_parts.append(f"System: {system}\n")
        
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            if role == 'user':
                prompt_parts.append(f"User: {content}\n")
            elif role == 'assistant':
                prompt_parts.append(f"Assistant: {content}\n")
        
        # Add final assistant prompt
        if messages and messages[-1].get('role') != 'assistant':
            prompt_parts.append("Assistant:")
        
        full_prompt = '\n'.join(prompt_parts)
        
        # Call Ollama API
        url = f"{self.base_url}/api/generate"
        
        # Utiliser les paramètres par défaut si non spécifiés
        actual_temperature = kwargs.get('temperature', temperature if temperature != 0.7 else self.default_temperature)
        actual_max_tokens = kwargs.get('max_tokens', max_tokens if max_tokens != 4096 else self.default_max_tokens)
        actual_top_p = kwargs.get('top_p', self.default_top_p)
        actual_repeat_penalty = kwargs.get('repeat_penalty', self.default_repeat_penalty)
        
        payload = {
            "model": model_to_use,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": actual_temperature,
                "num_predict": actual_max_tokens,
                "top_p": actual_top_p,
                "repeat_penalty": actual_repeat_penalty
            }
        }
        
        logger.info(f"Calling Ollama API with model: {model_to_use}")
        
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            
            result = response.json()
            
            # Transform response to mimic Claude's format
            class OllamaResponse:
                def __init__(self, text: str):
                    self.content = [type('obj', (object,), {'text': text})]
            
            generated_text = result.get('response', '')
            
            logger.info(f"Ollama response received ({len(generated_text)} chars)")
            
            return OllamaResponse(generated_text)
            
        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to Ollama at {self.base_url}. Is Ollama running?")
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Please ensure Ollama is running (ollama serve)"
            )
        except requests.exceptions.Timeout:
            logger.error(f"Ollama request timed out after {self.timeout}s")
            raise TimeoutError(f"Ollama request timed out after {self.timeout}s")
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            raise
    
    def create_message_stream(self, *args, **kwargs):
        """Streaming not implemented for simplified local testing."""
        raise NotImplementedError("Streaming not supported in OllamaClient yet")


class OllamaClientWrapper:
    """
    Wrapper that provides a 'client' attribute for compatibility with the existing architecture.
    """
    
    def __init__(
        self,
        model: str = "qwen2.5:latest",
        base_url: str = "http://localhost:11434",
        timeout: int = 600
    ):
        """
        Initialize wrapper.
        
        Args:
            model: Ollama model name
            base_url: Ollama API URL
            timeout: Request timeout in seconds (default: 600)
        """
        self.client = OllamaClient(model=model, base_url=base_url, timeout=timeout)
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        
        logger.info(f"OllamaClientWrapper initialized with {model}, timeout: {timeout}s")
    
    def create_message(self, *args, **kwargs):
        """Proxy to client.create_message"""
        return self.client.create_message(*args, **kwargs)
