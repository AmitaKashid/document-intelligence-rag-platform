from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Document Intelligence RAG Platform"

    BASE_DIR: Path = BASE_DIR
    STORAGE_DIR: Path = BASE_DIR / "storage"
    UPLOAD_DIR: Path = STORAGE_DIR / "uploads"
    PARSED_DIR: Path = STORAGE_DIR / "parsed"
    CHUNKS_DIR: Path = STORAGE_DIR / "chunks"
    EMBEDDINGS_DIR: Path = STORAGE_DIR / "embeddings"

    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: set[str] = {".pdf"}
    ALLOWED_CONTENT_TYPES: set[str] = {
        "application/pdf",
        "application/x-pdf",
    }

    DEFAULT_CHUNK_SIZE: int = 900
    DEFAULT_CHUNK_OVERLAP: int = 150

    EMBEDDING_MODEL_NAME: str = "BAAI/bge-m3"
    EMBEDDING_BATCH_SIZE: int = 8
    NORMALIZE_EMBEDDINGS: bool = True

    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION_NAME: str = "document_chunks"

    LLM_PROVIDER: str = "extractive"

    OPENAI_COMPATIBLE_BASE_URL: str | None = None
    OPENAI_COMPATIBLE_API_KEY: str | None = None
    OPENAI_COMPATIBLE_MODEL: str = "llama-3.1-8b-instant"


settings = Settings()

settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.PARSED_DIR.mkdir(parents=True, exist_ok=True)
settings.CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
settings.EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)