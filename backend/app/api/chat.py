from fastapi import APIRouter, HTTPException

from app.schemas.document import (
    ChatRequest,
    ChatResponse,
    ChatSource,
    SearchResult,
)
from app.services.embeddings import EmbeddingService
from app.services.llm.factory import LLMProviderFactory
from app.services.vector_store import QdrantVectorStore


router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)

embedding_service = EmbeddingService()
vector_store = QdrantVectorStore()


@router.post("", response_model=ChatResponse)
async def chat_with_documents(request: ChatRequest):
    try:
        query_vector = embedding_service.embed_query(request.question)

        hits = vector_store.search(
            query_vector=query_vector,
            document_id=request.document_id,
            strategy=request.strategy,
            limit=request.limit,
        )

        search_results: list[SearchResult] = []

        for hit in hits:
            payload = hit.payload or {}

            search_results.append(
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
        
        llm_provider = LLMProviderFactory.create(request.provider)
        
        answer = llm_provider.generate_answer(
            question=request.question,
            retrieved_chunks=search_results,
        )

        sources = [
            ChatSource(
                score=result.score,
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                document_name=result.document_name,
                strategy=result.strategy,
                chunk_type=result.chunk_type,
                section_title=result.section_title,
                page_number=result.page_number,
                chunk_index=result.chunk_index,
                text=result.text,
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
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )