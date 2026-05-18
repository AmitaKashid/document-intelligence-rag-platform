from app.schemas.document import SearchResult
from app.services.llm.base import LLMProvider


class ExtractiveProvider(LLMProvider):
    """
    Safe fallback provider.

    It does not generate new claims.
    It formats retrieved chunks into an answer-like response.
    """

    def generate_answer(
        self,
        question: str,
        retrieved_chunks: list[SearchResult],
    ) -> str:
        if not retrieved_chunks:
            return (
                "I could not find relevant information in the indexed document context. "
                "Try uploading the document again or using a different retrieval strategy."
            )

        source_summaries = []

        for index, chunk in enumerate(retrieved_chunks, start=1):
            cleaned_text = self._clean_chunk_text(chunk.text)

            source_label = f"Source {index}"

            if chunk.document_name:
                source_label += f" - {chunk.document_name}"

            if chunk.section_title:
                source_label += f", section: {chunk.section_title}"

            source_summaries.append(
                f"{source_label}:\n{cleaned_text}"
            )

        joined_sources = "\n\n".join(source_summaries)

        return (
            "Based on the retrieved document context, the answer is grounded in the following evidence:\n\n"
            f"{joined_sources}\n\n"
            "This answer is limited to the retrieved chunks. If the retrieved context is incomplete, "
            "try increasing the retrieval limit or switching chunking strategy."
        )

    def _clean_chunk_text(self, text: str) -> str:
        text = text.strip()
        max_chars = 1200

        if len(text) > max_chars:
            return text[:max_chars].rstrip() + "..."

        return text