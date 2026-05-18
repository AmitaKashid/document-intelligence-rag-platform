from fastapi import APIRouter, HTTPException

from app.schemas.document import SearchRequest, SearchResponse, SearchResult
from app.services.embeddings import EmbeddingService
from app.services.vector_store import QdrantVectorStore


router = APIRouter(
    prefix="/search",
    tags=["search"],
)

embedding_service = EmbeddingService()
vector_store = QdrantVectorStore()


@router.post("", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    try:
        query_vector = embedding_service.embed_query(request.query)

        hits = vector_store.search(
            query_vector=query_vector,
            document_id=request.document_id,
            strategy=request.strategy,
            limit=request.limit,
        )

        results: list[SearchResult] = []

        for hit in hits:
            payload = hit.payload or {}

            results.append(
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

        return SearchResponse(
            query=request.query,
            strategy=request.strategy,
            document_id=request.document_id,
            limit=request.limit,
            results=results,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )