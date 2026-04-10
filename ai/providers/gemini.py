import google.generativeai as genai
from ai.base import LLMProvider


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self._api_key = api_key

    @property
    def provider_name(self): 
        return "gemini"

    async def chat(self, messages: list[dict], system_prompt: str) -> str:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_prompt
        )
        # Convert to Gemini format
        history = []
        for m in messages[:-1]:
            role = "user" if m["role"] == "user" else "model"
            history.append({"role": role, "parts": [m["content"]]})

        chat = model.start_chat(history=history)
        response = await chat.send_message_async(messages[-1]["content"])
        return response.text
