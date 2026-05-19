from __future__ import annotations

from typing import Any

from sentence_transformers import CrossEncoder


class RerankingService:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model: CrossEncoder | None = None

    def _load_model(self) -> CrossEncoder:
        if self.model is None:
            self.model = CrossEncoder(self.model_name)
        return self.model

    def rerank(
        self,
        question: str,
        candidates: list[dict[str, Any]],
        final_top_k: int,
    ) -> list[dict[str, Any]]:
        if not question.strip() or not candidates:
            return candidates[:final_top_k]

        model = self._load_model()

        pairs = [[question, str(candidate.get("text", ""))] for candidate in candidates]
        scores = model.predict(pairs)

        reranked = []

        for original_rank, (candidate, score) in enumerate(
            zip(candidates, scores),
            start=1,
        ):
            updated_candidate = dict(candidate)
            updated_candidate["original_rank"] = original_rank
            updated_candidate["rerank_score"] = float(score)
            updated_candidate["similarity_score"] = float(candidate.get("score", 0.0))
            reranked.append(updated_candidate)

        reranked.sort(
            key=lambda item: item.get("rerank_score", 0.0),
            reverse=True,
        )

        return reranked[:final_top_k]