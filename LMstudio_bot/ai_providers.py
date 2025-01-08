import os
import aiohttp
import openai
import json
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import XAI_API_KEY, XAI_MODEL

class AIProvider(ABC):
    @abstractmethod
    async def generate_response(self, prompt: str, temperature: float = 0.7) -> str:
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        pass

class LMStudioProvider(AIProvider):
    def __init__(self):
        self.host = os.getenv("LMSTUDIO_HOST", "localhost")
        self.port = os.getenv("LMSTUDIO_PORT", "1234")
        self.base_url = f"http://{self.host}:{self.port}/v1"
        self.model = os.getenv("LMSTUDIO_MODEL", "default-model")  # Optional model environment variable

    async def test_connection(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/models", timeout=5) as response:
                    return response.status == 200
        except Exception as e:
            print(f"LMStudio connection test failed: {str(e)}")
            return False

    async def generate_response(self, prompt: str, temperature: float = 0.7) -> str:
        try:
            headers = {
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. "
                            "Your goal is to enhance the user's input to create vivid and precise prompts that guide the AI to produce stunning and accurate visuals."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": temperature,
                "max_tokens": 2000
            }
            print(f"Payload: {payload}")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"HTTP {response.status}: {error_text}")

                    data = await response.json()
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"LMStudio API error: {str(e)}")
            raise Exception(f"LMStudio API error: {str(e)}")


class OpenAIProvider(AIProvider):
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        openai.api_key = api_key
        self.model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    async def test_connection(self) -> bool:
        try:
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            return True
        except Exception as e:
            print(f"OpenAI connection test failed: {str(e)}")
            return False

    async def generate_response(self, prompt: str, temperature: float = 0.7) -> str:
        try:
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI API error: {str(e)}")
            raise Exception(f"OpenAI API error: {str(e)}")

class XAIProvider(AIProvider):
    def __init__(self):
        # Debug: Print all relevant environment variables
        print("\nDebug: Environment variables:")
        print(f"XAI_API_KEY exists: {XAI_API_KEY is not None}")
        print(f"XAI_MODEL: {XAI_MODEL}")
        
        self.api_key = XAI_API_KEY
        if not self.api_key:
            raise ValueError("XAI_API_KEY is not set in config")
        
        print(f"Initializing X.AI provider with API key: {self.api_key[:8]}...")
        self.base_url = "https://api.x.ai"
        self.model = XAI_MODEL or "grok-2-latest"
        print(f"Using model: {self.model}")
        print(f"Base URL: {self.base_url}")

    async def test_connection(self) -> bool:
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}/v1/chat/completions"
            print("\nDebug: Making test connection")
            print(f"URL: {url}")
            print(f"Headers: {headers}")
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You're an assistant"
                    },
                    {
                        "role": "user",
                        "content": "test"
                    }
                ]
            }
            print(f"Payload: {payload}")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=10
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"X.AI test failed with status {response.status}")
                        print(f"Error response: {error_text}")
                        return False
                    print("X.AI connection test successful!")
                    return True
        except Exception as e:
            print(f"X.AI connection test failed with exception: {str(e)}")
            return False

    async def generate_response(self, prompt: str, temperature: float = 0.7) -> str:
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}/v1/chat/completions"
            print("\nDebug: Generating response")
            print(f"URL: {url}")
            print(f"Headers: {headers}")
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. "
                            "Your goal is to enhance the user's input to create vivid and precise prompts that guide the AI to produce stunning and accurate visuals."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": temperature
            }
            print(f"Payload: {payload}")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=30
                ) as response:
                    response_text = await response.text()
                    print(f"X.AI API response status: {response.status}")
                    print(f"X.AI API response text: {response_text}")
                    
                    if response.status != 200:
                        print(f"X.AI API error response: {response_text}")
                        raise Exception(f"HTTP {response.status}: {response_text}")
                    
                    try:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"]
                    except Exception as e:
                        print(f"Failed to parse X.AI response: {response_text}")
                        raise Exception(f"Failed to parse X.AI response: {str(e)}")
        except Exception as e:
            print(f"X.AI API error: {str(e)}")
            raise Exception(f"X.AI API error: {str(e)}")

class GeminiProvider(AIProvider):
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    async def test_connection(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
                payload = {
                    "contents": [{
                        "parts": [{"text": "test"}]
                    }]
                }
                async with session.post(url, json=payload, timeout=5) as response:
                    return response.status == 200
        except Exception as e:
            print(f"Gemini connection test failed: {str(e)}")
            return False

    async def generate_response(self, prompt: str, temperature: float = 0.7) -> str:
        try:
            url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
            headers = {
                "Content-Type": "application/json"
            }
            
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": temperature
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=30) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"HTTP {response.status}: {error_text}")

                    data = await response.json()
                    if "candidates" in data and len(data["candidates"]) > 0:
                        return data["candidates"][0]["content"]["parts"][0]["text"]
                    raise Exception("No valid response received from Gemini API")
        except Exception as e:
            print(f"Gemini API error: {str(e)}")
            raise Exception(f"Gemini API error: {str(e)}")

class AIProviderFactory:
    @staticmethod
    def get_provider(provider_name: str) -> AIProvider:
        providers = {
            "lmstudio": LMStudioProvider,
            "openai": OpenAIProvider,
            "xai": XAIProvider,
            "gemini": GeminiProvider
        }
        
        provider_name = provider_name.lower() if provider_name else ""
        if provider_name not in providers:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        return providers[provider_name]()
