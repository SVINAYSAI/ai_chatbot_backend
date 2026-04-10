from ai.base import LLMProvider
from ai.providers.gemini import GeminiProvider
from ai.providers.openai_provider import OpenAIProvider
from ai.providers.grok import GrokProvider
from ai.providers.claude import ClaudeProvider
from config import settings


def get_provider() -> LLMProvider:
    """
    Priority: GEMINI → OPENAI → GROK → CLAUDE
    Uses pydantic settings so values from .env are always loaded correctly.
    """
    if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip():
        print("[AI Router] Using Gemini")
        return GeminiProvider(settings.GEMINI_API_KEY)
    if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip():
        print("[AI Router] Using OpenAI")
        return OpenAIProvider(settings.OPENAI_API_KEY)
    if settings.GROK_API_KEY and settings.GROK_API_KEY.strip():
        print("[AI Router] Using Grok")
        return GrokProvider(settings.GROK_API_KEY)
    if settings.CLAUDE_API_KEY and settings.CLAUDE_API_KEY.strip():
        print("[AI Router] Using Claude")
        return ClaudeProvider(settings.CLAUDE_API_KEY)

    raise RuntimeError(
        "No AI provider configured. Set at least one of: "
        "GEMINI_API_KEY, OPENAI_API_KEY, GROK_API_KEY, CLAUDE_API_KEY"
    )
