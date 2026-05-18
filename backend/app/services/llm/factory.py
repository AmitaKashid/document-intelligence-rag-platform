from app.services.llm.base import LLMProvider
from app.services.llm.extractive_provider import ExtractiveProvider
from app.services.llm.openai_compatible_provider import OpenAICompatibleProvider


class LLMProviderFactory:
    @staticmethod
    def create(provider_name: str) -> LLMProvider:
        normalized = provider_name.strip().lower()

        if normalized == "extractive":
            return ExtractiveProvider()

        if normalized in {"compatible", "openai_compatible", "groq"}:
            return OpenAICompatibleProvider()

        raise ValueError(
            f"Unsupported LLM provider: {provider_name}. "
            "Supported providers are: extractive, compatible."
        )