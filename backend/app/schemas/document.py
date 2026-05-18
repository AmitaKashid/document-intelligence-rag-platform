from typing import Any

from pydantic import BaseModel


class ParsedDocumentMetadata(BaseModel):
    parser_name: str
    parsed_markdown_filename: str
    parsed_markdown_path: str
    markdown_char_count: int
    markdown_preview: str


class ChunkingResult(BaseModel):
    strategy: str
    chunks_created: int
    output_filename: str
    output_path: str
    chunk_type_counts: dict[str, int]
    average_chunk_chars: float
    min_chunk_chars: int
    max_chunk_chars: int


class EmbeddingResult(BaseModel):
    strategy: str
    embedding_model: str
    vectors_created: int
    vector_dimension: int
    output_filename: str
    output_path: str


class IndexingResult(BaseModel):
    strategy: str
    collection_name: str
    points_indexed: int
    vector_dimension: int
    status: str


class UploadedDocument(BaseModel):
    document_id: str
    original_filename: str
    stored_filename: str
    stored_path: str
    content_type: str | None
    size_bytes: int
    status: str
    parsing: ParsedDocumentMetadata | None = None
    chunking_results: list[ChunkingResult] = []
    embedding_results: list[EmbeddingResult] = []
    indexing_results: list[IndexingResult] = []


class UploadDocumentsResponse(BaseModel):
    status: str
    uploaded_count: int
    failed_count: int
    documents: list[UploadedDocument]
    errors: list[dict[str, Any]]


class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    strategy: str
    chunk_type: str
    text: str

    chunk_index: int
    parent_id: str | None = None

    section_title: str | None = None
    page_number: int | None = None

    metadata: dict[str, Any] = {}


class EmbeddedChunk(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    strategy: str
    chunk_type: str
    text: str

    chunk_index: int
    parent_id: str | None = None

    section_title: str | None = None
    page_number: int | None = None

    embedding_model: str
    vector_dimension: int
    embedding: list[float]

    metadata: dict[str, Any] = {}


class SearchRequest(BaseModel):
    query: str
    document_id: str | None = None
    strategy: str | None = "section_aware"
    limit: int = 5


class SearchResult(BaseModel):
    score: float
    chunk_id: str
    document_id: str
    document_name: str
    strategy: str
    chunk_type: str
    text: str
    chunk_index: int
    parent_id: str | None = None
    section_title: str | None = None
    page_number: int | None = None
    metadata: dict[str, Any] = {}


class SearchResponse(BaseModel):
    query: str
    strategy: str | None
    document_id: str | None
    limit: int
    results: list[SearchResult]


class ChatRequest(BaseModel):
    question: str
    document_id: str | None = None
    strategy: str = "section_aware"
    limit: int = 5
    provider: str = "extractive"


class ChatSource(BaseModel):
    score: float
    chunk_id: str
    document_id: str
    document_name: str
    strategy: str
    chunk_type: str
    section_title: str | None = None
    page_number: int | None = None
    chunk_index: int
    text: str


class ChatResponse(BaseModel):
    question: str
    answer: str
    strategy: str
    provider: str
    document_id: str | None = None
    sources: list[ChatSource]


class EvaluationTestCase(BaseModel):
    question_id: str
    question: str
    expected_answer: str
    expected_keywords: list[str]


class EvaluationRequest(BaseModel):
    document_id: str | None = None
    strategies: list[str] = [
        "recursive",
        "section_aware",
        "table_preserving",
        "parent_child",
    ]
    limit: int = 5


class EvaluationQuestionResult(BaseModel):
    question_id: str
    question: str
    expected_answer: str
    expected_keywords: list[str]
    retrieved_text_preview: str
    matched_keywords: list[str]
    missing_keywords: list[str]
    keyword_recall: float
    top_score: float | None = None
    passed: bool


class EvaluationStrategyResult(BaseModel):
    strategy: str
    questions_evaluated: int
    average_keyword_recall: float
    average_top_score: float | None = None
    pass_rate: float
    overall_score: float
    strengths: list[str]
    weaknesses: list[str]
    recommendation: str
    results: list[EvaluationQuestionResult]


class EvaluationResponse(BaseModel):
    document_id: str | None = None
    limit: int
    strategies_evaluated: list[str]
    best_strategy: str | None = None
    best_strategy_reason: str | None = None
    strategy_results: list[EvaluationStrategyResult]

class IndexedDocument(BaseModel):
    document_id: str
    document_name: str
    strategies: list[str]
    chunk_count: int


class ListDocumentsResponse(BaseModel):
    documents: list[IndexedDocument]