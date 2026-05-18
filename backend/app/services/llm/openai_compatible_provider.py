from openai import OpenAI

from app.core.config import settings
from app.schemas.document import SearchResult
from app.services.llm.base import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self) -> None:

        if not settings.OPENAI_COMPATIBLE_API_KEY:
            raise ValueError(
                "DEBUG-NEW-PROVIDER-2026: OPENAI_COMPATIBLE_API_KEY is not configured. "
                f"base_url={settings.OPENAI_COMPATIBLE_BASE_URL}, "
                f"model={settings.OPENAI_COMPATIBLE_MODEL}, "
                f"key_exists={bool(settings.OPENAI_COMPATIBLE_API_KEY)}"
            )

        if not settings.OPENAI_COMPATIBLE_BASE_URL:
            raise ValueError(
                "OPENAI_COMPATIBLE_BASE_URL is not configured. "
                "Example: https://api.groq.com/openai/v1"
            )

        self.client = OpenAI(
            api_key=settings.OPENAI_COMPATIBLE_API_KEY,
            base_url=settings.OPENAI_COMPATIBLE_BASE_URL,
        )
        self.model = settings.OPENAI_COMPATIBLE_MODEL

    def generate_answer(
        self,
        question: str,
        retrieved_chunks: list[SearchResult],
    ) -> str:
        if not retrieved_chunks:
            return "I could not find relevant information in the indexed document context."

        context = self._build_context(retrieved_chunks)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a careful RAG answer generator. "
                        "Answer only using the provided retrieved context. "
                        "Do not use outside knowledge. "
                        "If the answer is not present in the context, say that the document context does not contain enough information. "
                        "Keep the answer concise and cite sources inline using [Source 1], [Source 2], etc."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question:\n{question}\n\n"
                        f"Retrieved context:\n{context}\n\n"
                        "Write a grounded answer using only the retrieved context."
                    ),
                },
            ],
            temperature=0.2,
        )

        return response.choices[0].message.content or ""

    def _build_context(self, chunks: list[SearchResult]) -> str:
        blocks = []

        for index, chunk in enumerate(chunks, start=1):
            metadata = (
                f"Source {index} | "
                f"document={chunk.document_name} | "
                f"section={chunk.section_title or 'unknown'} | "
                f"chunk_type={chunk.chunk_type} | "
                f"score={chunk.score:.4f}"
            )

            blocks.append(f"{metadata}\n{chunk.text.strip()}")

        return "\n\n---\n\n".join(blocks)