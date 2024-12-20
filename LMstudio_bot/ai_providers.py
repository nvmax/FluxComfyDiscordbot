import os
import aiohttp
import openai
from abc import ABC, abstractmethod
from typing import Optional

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
        self.api_key = os.getenv("XAI_API_KEY")
        if not self.api_key:
            raise ValueError("XAI_API_KEY environment variable is not set")
        print(f"Initializing X.AI provider with API key: {self.api_key[:8]}...")
        self.base_url = "https://api.x.ai/v1"
        self.model = os.getenv("XAI_MODEL", "grok-beta")
        print(f"Using model: {self.model}")

    async def test_connection(self) -> bool:
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            print("\nTesting X.AI connection...")
            print(f"URL: {self.base_url}/chat/completions")
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
                        "content": "test"
                    }
                ],
                "max_tokens": 1,
                "stream": False
            }
            print(f"Payload: {payload}")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
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
                "stream": False
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                ) as response:
                    response_text = await response.text()
                    print(f"X.AI API response status: {response.status}")
                    
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

class AIProviderFactory:
    @staticmethod
    def get_provider(provider_name: str) -> AIProvider:
        providers = {
            "lmstudio": LMStudioProvider,
            "openai": OpenAIProvider,
            "xai": XAIProvider
        }
        
        if provider_name not in providers:
            raise ValueError(f"Unknown provider: {provider_name}. Available providers: {', '.join(providers.keys())}")
        
        return providers[provider_name]()
