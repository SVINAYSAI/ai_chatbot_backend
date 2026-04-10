from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], system_prompt: str) -> str:
        """
        messages: list of {"role": "user"|"assistant", "content": "..."}
        Returns the assistant reply as a plain string.
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass
