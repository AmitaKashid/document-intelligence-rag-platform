from fastapi import APIRouter, HTTPException
from app.services.reranking_service import RerankingService

from app.schemas.document import (
    ChatRequest,
    ChatResponse,
    ChatSource,
    SearchResult,
)
from app.services.embeddings import EmbeddingService
from app.services.llm.factory import LLMProviderFactory
from app.services.vector_store import QdrantVectorStore
from app.services.document_profiler import DocumentProfiler
from app.core.config import settings

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)

embedding_service = EmbeddingService()
vector_store = QdrantVectorStore()
document_profiler = DocumentProfiler()
reranking_service = RerankingService(settings.RERANKER_MODEL)

@router.post("", response_model=ChatResponse)
async def chat_with_documents(request: ChatRequest):
    try:
        query_vector = embedding_service.embed_query(request.question)

        strategy = request.strategy
        limit = request.limit

        if strategy in [None, "", "auto"]:
            profile = None

            if request.document_id:
                profile = document_profiler.load_profile(
                    document_id=request.document_id,
                    profile_dir=settings.PARSED_DIR,
                )

            if profile:
                strategy = profile.get("recommended_strategy", "section_aware")
                limit = limit or profile.get("recommended_top_k", 3)
            else:
                strategy = "section_aware"
                limit = limit or 3

        use_reranking = (
            request.rerank
            if request.rerank is not None
            else settings.ENABLE_RERANKING
        )

        final_top_k = limit or settings.RERANKER_FINAL_TOP_K

        candidate_limit = (
            request.rerank_candidate_limit
            or settings.RERANKER_CANDIDATE_LIMIT
        )

        retrieval_limit = candidate_limit if use_reranking else final_top_k

        hits = vector_store.search(
            query_vector=query_vector,
            document_id=request.document_id,
            strategy=strategy,
            limit=retrieval_limit,
        )

        search_results: list[dict] = []

        for hit in hits:
            payload = hit.payload or {}

            search_results.append(
                {
                    "score": float(hit.score),
                    "similarity_score": float(hit.score),
                    "chunk_id": payload.get("chunk_id", ""),
                    "document_id": payload.get("document_id", ""),
                    "document_name": payload.get("document_name", ""),
                    "strategy": payload.get("strategy", ""),
                    "chunk_type": payload.get("chunk_type", ""),
                    "text": payload.get("text", ""),
                    "chunk_index": payload.get("chunk_index", -1),
                    "parent_id": payload.get("parent_id"),
                    "section_title": payload.get("section_title"),
                    "page_number": payload.get("page_number"),
                    "metadata": payload.get("metadata", {}),
                }
            )
        if use_reranking and search_results:
            search_results = reranking_service.rerank(
                question=request.question,
                candidates=search_results,
                final_top_k=final_top_k,
            )
        else:
            search_results = search_results[:final_top_k]

        if not search_results:
            return ChatResponse(
                question=request.question,
                answer="I could not find relevant information in the indexed document context.",
                strategy=request.strategy,
                provider=request.provider,
                document_id=request.document_id,
                sources=[],
                used_strategy=strategy,
                used_top_k=final_top_k,
                used_reranking=use_reranking,
                rerank_candidate_limit=retrieval_limit,
            )
        llm_provider = LLMProviderFactory.create(request.provider)

        llm_chunks = [
            SearchResult(
                score=result.get("score", 0.0),
                chunk_id=result.get("chunk_id", ""),
                document_id=result.get("document_id", ""),
                document_name=result.get("document_name", ""),
                strategy=result.get("strategy", ""),
                chunk_type=result.get("chunk_type", ""),
                text=result.get("text", ""),
                chunk_index=result.get("chunk_index", -1),
                parent_id=result.get("parent_id"),
                section_title=result.get("section_title"),
                page_number=result.get("page_number"),
                metadata=result.get("metadata", {}),
            )
            for result in search_results
        ]

        answer = llm_provider.generate_answer(
            question=request.question,
            retrieved_chunks=llm_chunks,
        )

        sources = [
            ChatSource(
                score=result.get("score", 0.0),
                similarity_score=result.get("similarity_score"),
                rerank_score=result.get("rerank_score"),
                original_rank=result.get("original_rank"),
                chunk_id=result.get("chunk_id", ""),
                document_id=result.get("document_id", ""),
                document_name=result.get("document_name", ""),
                strategy=result.get("strategy", ""),
                chunk_type=result.get("chunk_type", ""),
                section_title=result.get("section_title"),
                page_number=result.get("page_number"),
                chunk_index=result.get("chunk_index"),
                text=result.get("text", ""),
            )
            for result in search_results
        ]

        return ChatResponse(
            question=request.question,
            answer=answer,
            strategy=request.strategy,
            provider=request.provider,
            document_id=request.document_id,
            sources=sources,
            used_strategy=strategy,
            used_top_k=final_top_k,
            used_reranking=use_reranking,
            rerank_candidate_limit=retrieval_limit,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )