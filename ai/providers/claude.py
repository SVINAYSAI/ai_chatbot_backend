import anthropic
from ai.base import LLMProvider


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    @property
    def provider_name(self): 
        return "claude"

    async def chat(self, messages: list[dict], system_prompt: str) -> str:
        resp = await self.client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1000,
            system=system_prompt,
            messages=messages
        )
        return resp.content[0].text
