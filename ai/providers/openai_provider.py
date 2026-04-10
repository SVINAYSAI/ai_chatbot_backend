from openai import AsyncOpenAI
from ai.base import LLMProvider


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    @property
    def provider_name(self): 
        return "openai"

    async def chat(self, messages: list[dict], system_prompt: str) -> str:
        full_messages = [{"role": "system", "content": system_prompt}, *messages]
        resp = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=full_messages,
            max_tokens=1000
        )
        return resp.choices[0].message.content
