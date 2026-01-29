"""
Claude SDK client wrapper with retry and error handling.
"""

import os
import time
import logging
from typing import Dict, Any, Optional, List
from anthropic import Anthropic, AuthenticationError, RateLimitError, APIError

logger = logging.getLogger(__name__)


class ClaudeClient:
    """Wrapper for Anthropic Claude SDK with retry logic."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_retries: int = 3,
        base_delay: float = 2.0
    ):
        """
        Initialize Claude client.
        
        Args:
            api_key: Anthropic API key (defaults to env ANTHROPIC_API_KEY)
            base_url: API base URL for OpenRouter support
            max_retries: Maximum number of retry attempts
            base_delay: Base delay for exponential backoff (seconds)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = base_url or os.getenv("ANTHROPIC_BASE_URL")
        self.max_retries = max_retries
        self.base_delay = base_delay
        
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY must be set in environment or passed as argument")
        
        # Initialize client
        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
            
        self.client = Anthropic(**client_kwargs)
        logger.info(f"Claude client initialized (base_url: {self.base_url or 'default'})")
    
    def create_message(
        self,
        model: str,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a message with Claude, with retry logic.
        
        Args:
            model: Model name (e.g., 'claude-sonnet-4-5')
            messages: List of message dicts with 'role' and 'content'
            system: System prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            Response dict from Claude API
            
        Raises:
            AuthenticationError: Invalid API key
            APIError: Unrecoverable API error
        """
        attempt = 0
        last_error = None
        
        while attempt < self.max_retries:
            try:
                params = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    **kwargs
                }
                
                if system:
                    params["system"] = system
                
                response = self.client.messages.create(**params)
                
                logger.info(f"Claude API call successful (model: {model}, attempt: {attempt + 1})")
                return response
                
            except RateLimitError as e:
                attempt += 1
                last_error = e
                if attempt < self.max_retries:
                    delay = self.base_delay ** attempt
                    logger.warning(
                        f"Rate limit hit. Retrying in {delay}s (attempt {attempt}/{self.max_retries})"
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"Rate limit exceeded after {self.max_retries} attempts")
                    raise
                    
            except AuthenticationError as e:
                logger.error(f"Authentication error: {e}")
                raise
                
            except APIError as e:
                attempt += 1
                last_error = e
                if attempt < self.max_retries:
                    delay = self.base_delay ** attempt
                    logger.warning(
                        f"API error: {e}. Retrying in {delay}s (attempt {attempt}/{self.max_retries})"
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"API error after {self.max_retries} attempts: {e}")
                    raise
                    
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                raise
        
        # Should not reach here, but for safety
        if last_error:
            raise last_error
    
    def create_message_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ):
        """
        Create a streaming message with Claude.
        
        Args:
            model: Model name
            messages: List of messages
            system: System prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Yields:
            Stream chunks from Claude API
        """
        params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs
        }
        
        if system:
            params["system"] = system
        
        with self.client.messages.stream(**params) as stream:
            for chunk in stream:
                yield chunk
