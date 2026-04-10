from openai import AsyncOpenAI
from ai.base import LLMProvider


class GrokProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1"
        )

    @property
    def provider_name(self): 
        return "grok"

    async def chat(self, messages: list[dict], system_prompt: str) -> str:
        full_messages = [{"role": "system", "content": system_prompt}, *messages]
        resp = await self.client.chat.completions.create(
            model="grok-2",
            messages=full_messages
        )
        return resp.choices[0].message.content
