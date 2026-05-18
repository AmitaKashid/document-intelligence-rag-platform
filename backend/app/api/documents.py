from fastapi import APIRouter, File, UploadFile, HTTPException

from app.schemas.document import UploadedDocument, UploadDocumentsResponse
from app.services.chunking.chunking_service import ChunkingService
from app.services.embeddings import EmbeddingService
from app.services.parsing.docling_parser import DoclingParser
from app.services.vector_store import QdrantVectorStore
from app.utils.file_utils import save_upload_file
from app.schemas.document import ListDocumentsResponse, IndexedDocument


router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)

docling_parser = DoclingParser()
chunking_service = ChunkingService()
embedding_service = EmbeddingService()
vector_store = QdrantVectorStore()

@router.get("", response_model=ListDocumentsResponse)
async def list_documents():
    documents = vector_store.list_documents()

    return ListDocumentsResponse(
        documents=[
            IndexedDocument(**document)
            for document in documents
        ]
    )

@router.post("/upload", response_model=UploadDocumentsResponse)
async def upload_documents(
    files: list[UploadFile] = File(..., description="One or more PDF files"),
):
    documents: list[UploadedDocument] = []
    errors: list[dict] = []

    for file in files:
        try:
            saved_file = save_upload_file(file)

            parsing_result = docling_parser.parse_to_markdown(
                document_id=saved_file["document_id"],
                original_filename=saved_file["original_filename"],
                stored_path=saved_file["stored_path"],
            )

            chunking_results = chunking_service.create_all_strategy_chunks(
                document_id=saved_file["document_id"],
                document_name=saved_file["original_filename"],
                markdown_path=parsing_result["parsed_markdown_path"],
            )

            embedding_results = embedding_service.embed_chunking_results(
                document_id=saved_file["document_id"],
                document_name=saved_file["original_filename"],
                chunking_results=chunking_results,
            )

            indexing_results = vector_store.index_embedding_results(
                embedding_results=embedding_results,
            )

            saved_file["parsing"] = parsing_result
            saved_file["chunking_results"] = chunking_results
            saved_file["embedding_results"] = embedding_results
            saved_file["indexing_results"] = indexing_results

            documents.append(UploadedDocument(**saved_file))

        except Exception as exc:
            errors.append(
                {
                    "filename": file.filename,
                    "error": str(exc),
                }
            )

    if not documents:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "No files were successfully uploaded, parsed, chunked, embedded, and indexed.",
                "errors": errors,
            },
        )

    return UploadDocumentsResponse(
        status="completed",
        uploaded_count=len(documents),
        failed_count=len(errors),
        documents=documents,
        errors=errors,
    )   