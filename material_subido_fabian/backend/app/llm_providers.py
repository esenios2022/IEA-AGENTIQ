"""
LLM Provider Factory
Soporta múltiples proveedores de LLM
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()

class LLMProvider(ABC):
    """Interfaz base para proveedores de LLM"""
    
    @abstractmethod
    def complete(self, prompt: str, **kwargs) -> str:
        """Completar un prompt"""
        pass
    
    @abstractmethod
    def validate_credentials(self) -> bool:
        """Validar que las credenciales sean correctas"""
        pass

# ==================== OPENAI ====================

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4-turbo"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = None
        
        if self.api_key:
            try:
                import openai
                openai.api_key = self.api_key
                self.client = openai
            except ImportError:
                print("⚠️ OpenAI no instalado. Instalar: pip install openai")
    
    def validate_credentials(self) -> bool:
        return bool(self.api_key and self.client)
    
    def complete(self, prompt: str, **kwargs) -> str:
        if not self.validate_credentials():
            return "❌ OpenAI API key no configurada"
        
        try:
            response = self.client.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 1024)
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"❌ Error OpenAI: {str(e)}"

# ==================== ANTHROPIC (CLAUDE) ====================

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-sonnet-20240229"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.client = None
        
        if self.api_key:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                print("⚠️ Anthropic no instalado. Instalar: pip install anthropic")
    
    def validate_credentials(self) -> bool:
        return bool(self.api_key and self.client)
    
    def complete(self, prompt: str, **kwargs) -> str:
        if not self.validate_credentials():
            return "❌ Anthropic API key no configurada"
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=kwargs.get("max_tokens", 1024),
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            return f"❌ Error Anthropic: {str(e)}"

# ==================== OLLAMA (LOCAL) ====================

class OllamaProvider(LLMProvider):
    def __init__(self, model: str = "llama2", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.client = None
        
        try:
            import requests
            self.requests = requests
            # Validar conexión
            self.validate_credentials()
        except ImportError:
            print("⚠️ Requests no instalado. Instalar: pip install requests")
    
    def validate_credentials(self) -> bool:
        try:
            response = self.requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def complete(self, prompt: str, **kwargs) -> str:
        if not self.validate_credentials():
            return f"❌ Ollama no disponible en {self.base_url}"
        
        try:
            response = self.requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            if response.status_code == 200:
                return response.json()["response"]
            else:
                return f"❌ Error Ollama: {response.status_code}"
        except Exception as e:
            return f"❌ Error Ollama: {str(e)}"

# ==================== MISTRAL ====================

class MistralProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "mistral-medium"):
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        self.model = model
        self.client = None
        
        if self.api_key:
            try:
                from mistralai.client import MistralClient
                self.client = MistralClient(api_key=self.api_key)
            except ImportError:
                print("⚠️ Mistral no instalado. Instalar: pip install mistral-ai")
    
    def validate_credentials(self) -> bool:
        return bool(self.api_key and self.client)
    
    def complete(self, prompt: str, **kwargs) -> str:
        if not self.validate_credentials():
            return "❌ Mistral API key no configurada"
        
        try:
            message = self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.choices[0].message.content
        except Exception as e:
            return f"❌ Error Mistral: {str(e)}"

# ==================== GOOGLE GEMINI ====================

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-pro"):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model = model
        self.client = None
        
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.client = genai
            except ImportError:
                print("⚠️ Google AI no instalado. Instalar: pip install google-generativeai")
    
    def validate_credentials(self) -> bool:
        return bool(self.api_key and self.client)
    
    def complete(self, prompt: str, **kwargs) -> str:
        if not self.validate_credentials():
            return "❌ Google API key no configurada"
        
        try:
            model = self.client.GenerativeModel(self.model)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"❌ Error Gemini: {str(e)}"

# ==================== HUGGINGFACE ====================

class HuggingFaceProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "meta-llama/Llama-2-7b-chat-hf"):
        self.api_key = api_key or os.getenv("HUGGINGFACE_API_KEY")
        self.model = model
        self.client = None
        
        if self.api_key:
            try:
                from huggingface_hub import InferenceClient
                self.client = InferenceClient(api_key=self.api_key)
            except ImportError:
                print("⚠️ HuggingFace no instalado. Instalar: pip install huggingface-hub")
    
    def validate_credentials(self) -> bool:
        return bool(self.api_key and self.client)
    
    def complete(self, prompt: str, **kwargs) -> str:
        if not self.validate_credentials():
            return "❌ HuggingFace API key no configurada"
        
        try:
            response = self.client.text_generation(
                prompt,
                model=self.model
            )
            return response
        except Exception as e:
            return f"❌ Error HuggingFace: {str(e)}"

# ==================== LLM FACTORY ====================

class LLMFactory:
    """Factory para crear y gestionar proveedores de LLM"""
    
    PROVIDERS = {
        "openai": OpenAIProvider,
        "claude": AnthropicProvider,
        "anthropic": AnthropicProvider,
        "ollama": OllamaProvider,
        "mistral": MistralProvider,
        "gemini": GeminiProvider,
        "google": GeminiProvider,
        "huggingface": HuggingFaceProvider,
        "hf": HuggingFaceProvider,
    }
    
    @staticmethod
    def create(provider: str, **kwargs) -> LLMProvider:
        """Crear un proveedor de LLM"""
        provider = provider.lower()
        
        if provider not in LLMFactory.PROVIDERS:
            raise ValueError(f"Provider {provider} no soportado. Opciones: {list(LLMFactory.PROVIDERS.keys())}")
        
        return LLMFactory.PROVIDERS[provider](**kwargs)
    
    @staticmethod
    def get_available_providers() -> Dict[str, bool]:
        """Obtener proveedores disponibles y su estado"""
        available = {}
        for name, provider_class in LLMFactory.PROVIDERS.items():
            try:
                provider = provider_class()
                available[name] = provider.validate_credentials()
            except:
                available[name] = False
        return available
    
    @staticmethod
    def get_default_provider() -> LLMProvider:
        """Obtener el proveedor por defecto disponible"""
        providers = LLMFactory.PROVIDERS
        
        # Orden de preferencia
        for name in ["openai", "anthropic", "mistral", "ollama"]:
            if name in providers:
                try:
                    provider = providers[name]()
                    if provider.validate_credentials():
                        return provider
                except:
                    pass
        
        # Si nada está disponible, devolver Ollama como fallback
        return OllamaProvider()

# Instancia global
default_llm = LLMFactory.get_default_provider()
