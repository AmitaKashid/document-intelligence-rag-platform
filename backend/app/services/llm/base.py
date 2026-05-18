from abc import ABC, abstractmethod

from app.schemas.document import SearchResult


class LLMProvider(ABC):
    @abstractmethod
    def generate_answer(
        self,
        question: str,
        retrieved_chunks: list[SearchResult],
    ) -> str:
        raise NotImplementedError