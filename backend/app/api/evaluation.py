from fastapi import APIRouter, HTTPException

from app.schemas.document import (
    EvaluationRequest,
    EvaluationResponse,
    EvaluationStrategyResult,
    SearchResult,
)
from app.services.embeddings import EmbeddingService
from app.services.evaluation import RetrievalEvaluationService
from app.services.evaluation_testset import DEFAULT_EVALUATION_TESTSET
from app.services.vector_store import QdrantVectorStore


router = APIRouter(
    prefix="/evaluation",
    tags=["evaluation"],
)

embedding_service = EmbeddingService()
vector_store = QdrantVectorStore()
evaluation_service = RetrievalEvaluationService()


@router.post("/run", response_model=EvaluationResponse)
async def run_evaluation(request: EvaluationRequest):
    try:
        strategy_results = []

        for strategy in request.strategies:
            question_results = []

            for test_case in DEFAULT_EVALUATION_TESTSET:
                query_vector = embedding_service.embed_query(test_case.question)

                hits = vector_store.search(
                    query_vector=query_vector,
                    document_id=request.document_id,
                    strategy=strategy,
                    limit=request.limit,
                )

                retrieved_chunks: list[SearchResult] = []

                for hit in hits:
                    payload = hit.payload or {}

                    retrieved_chunks.append(
                        SearchResult(
                            score=float(hit.score),
                            chunk_id=payload.get("chunk_id", ""),
                            document_id=payload.get("document_id", ""),
                            document_name=payload.get("document_name", ""),
                            strategy=payload.get("strategy", ""),
                            chunk_type=payload.get("chunk_type", ""),
                            text=payload.get("text", ""),
                            chunk_index=payload.get("chunk_index", -1),
                            parent_id=payload.get("parent_id"),
                            section_title=payload.get("section_title"),
                            page_number=payload.get("page_number"),
                            metadata=payload.get("metadata", {}),
                        )
                    )

                result = evaluation_service.evaluate_question(
                    question_id=test_case.question_id,
                    question=test_case.question,
                    expected_answer=test_case.expected_answer,
                    expected_keywords=test_case.expected_keywords,
                    retrieved_chunks=retrieved_chunks,
                )

                question_results.append(result)

            average_keyword_recall = (
                sum(result["keyword_recall"] for result in question_results)
                / len(question_results)
                if question_results
                else 0.0
            )

            top_scores = [
                result["top_score"]
                for result in question_results
                if result["top_score"] is not None
            ]

            average_top_score = (
                sum(top_scores) / len(top_scores)
                if top_scores
                else None
            )

            passed_count = sum(
                1 for result in question_results if result["passed"]
            )

            pass_rate = (
                passed_count / len(question_results)
                if question_results
                else 0.0
            )

            normalized_top_score = min(average_top_score or 0.0, 1.0)

            overall_score = (
                0.65 * average_keyword_recall
                + 0.25 * pass_rate
                + 0.10 * normalized_top_score
            )

            strengths = []
            weaknesses = []

            if average_keyword_recall >= 0.75:
                strengths.append("Retrieved most expected answer concepts across the test questions.")
            elif average_keyword_recall >= 0.5:
                strengths.append("Retrieved a reasonable portion of the expected answer concepts.")
            else:
                weaknesses.append("Missed many expected answer concepts in the retrieved chunks.")

            if pass_rate >= 0.8:
                strengths.append("Passed most of the hard-coded evaluation questions.")
            elif pass_rate < 0.5:
                weaknesses.append("Passed fewer than half of the evaluation questions.")

            if average_top_score is not None and average_top_score >= 0.55:
                strengths.append("Returned high-scoring nearest-neighbor chunks for the test queries.")
            elif average_top_score is not None:
                weaknesses.append("Top retrieved chunks had relatively weak similarity scores.")

            if not weaknesses:
                weaknesses.append("No major weakness detected in this small evaluation set.")

            if overall_score >= 0.75:
                recommendation = "Recommended for chat by default."
            elif overall_score >= 0.55:
                recommendation = "Usable, but compare against the best-performing strategy."
            else:
                recommendation = "Not recommended as the default strategy for this document."

            strategy_results.append(
                EvaluationStrategyResult(
                    strategy=strategy,
                    questions_evaluated=len(question_results),
                    average_keyword_recall=round(average_keyword_recall, 3),
                    average_top_score=round(average_top_score, 3)
                    if average_top_score is not None
                    else None,
                    pass_rate=round(pass_rate, 3),
                    overall_score=round(overall_score, 3),
                    strengths=strengths,
                    weaknesses=weaknesses,
                    recommendation=recommendation,
                    results=question_results,
                )
            )

        best_strategy_result = None

        if strategy_results:
            best_strategy_result = max(
                strategy_results,
                key=lambda result: result.overall_score,
            )

        best_strategy = (
            best_strategy_result.strategy
            if best_strategy_result
            else None
        )

        best_strategy_reason = None

        if best_strategy_result:
            best_strategy_reason = (
                f"{best_strategy_result.strategy} achieved the highest overall score "
                f"({best_strategy_result.overall_score}) based on keyword recall, pass rate, "
                f"and average top retrieval score."
            )
        return EvaluationResponse(
            document_id=request.document_id,
            limit=request.limit,
            strategies_evaluated=request.strategies,
            best_strategy=best_strategy,
            best_strategy_reason=best_strategy_reason,
            strategy_results=strategy_results,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )