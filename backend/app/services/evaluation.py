import re

from app.schemas.document import SearchResult


class RetrievalEvaluationService:
    """
    Evaluates retrieval quality using transparent keyword recall.

    This is intentionally simple and explainable:
    - Expected answer is represented by expected keywords.
    - Retrieved chunks are concatenated.
    - Score = matched expected keywords / total expected keywords.
    """

    def evaluate_question(
        self,
        question_id: str,
        question: str,
        expected_answer: str,
        expected_keywords: list[str],
        retrieved_chunks: list[SearchResult],
    ) -> dict:
        retrieved_text = "\n\n".join(
            chunk.text for chunk in retrieved_chunks
        )

        normalized_text = self._normalize(retrieved_text)

        matched_keywords = []
        missing_keywords = []

        for keyword in expected_keywords:
            normalized_keyword = self._normalize(keyword)

            if normalized_keyword in normalized_text:
                matched_keywords.append(keyword)
            else:
                missing_keywords.append(keyword)

        keyword_recall = (
            len(matched_keywords) / len(expected_keywords)
            if expected_keywords
            else 0.0
        )

        top_score = retrieved_chunks[0].score if retrieved_chunks else None

        return {
            "question_id": question_id,
            "question": question,
            "expected_answer": expected_answer,
            "expected_keywords": expected_keywords,
            "retrieved_text_preview": retrieved_text[:1200],
            "matched_keywords": matched_keywords,
            "missing_keywords": missing_keywords,
            "keyword_recall": round(keyword_recall, 3),
            "top_score": top_score,
            "passed": keyword_recall >= 0.6,
        }

    def _normalize(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^a-z0-9äöüß\s-]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()