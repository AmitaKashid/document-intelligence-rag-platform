import json
import re
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.schemas.document import EmbeddedChunk


class EmbeddingService:
    """
    Generates dense embeddings for chunk JSONL files.

    Current behavior:
    - Reads chunk JSONL files
    - Embeds chunk text using BGE-M3 through sentence-transformers
    - Saves embedding records as JSONL
    """

    def __init__(self) -> None:
        self.model_name = settings.EMBEDDING_MODEL_NAME
        self.model = SentenceTransformer(self.model_name)

    def embed_chunking_results(
        self,
        document_id: str,
        document_name: str,
        chunking_results: list[dict],
    ) -> list[dict]:
        results: list[dict] = []

        for chunking_result in chunking_results:
            strategy = chunking_result["strategy"]
            chunk_file_path = chunking_result["output_path"]

            embedded_chunks = self.embed_chunk_file(
                chunk_file_path=chunk_file_path,
                strategy=strategy,
            )

            output_path = self._write_embeddings_jsonl(
                document_id=document_id,
                document_name=document_name,
                strategy=strategy,
                embedded_chunks=embedded_chunks,
            )

            results.append(
                {
                    "strategy": strategy,
                    "embedding_model": self.model_name,
                    "vectors_created": len(embedded_chunks),
                    "vector_dimension": (
                        embedded_chunks[0].vector_dimension if embedded_chunks else 0
                    ),
                    "output_filename": output_path.name,
                    "output_path": str(output_path),
                }
            )

        return results

    def embed_chunk_file(
        self,
        chunk_file_path: str,
        strategy: str,
    ) -> list[EmbeddedChunk]:
        chunks = self._read_jsonl(Path(chunk_file_path))

        texts = [chunk["text"] for chunk in chunks]

        if not texts:
            return []

        vectors = self._embed_texts(texts)

        embedded_chunks: list[EmbeddedChunk] = []

        for chunk, vector in zip(chunks, vectors):
            embedded_chunks.append(
                EmbeddedChunk(
                    chunk_id=chunk["chunk_id"],
                    document_id=chunk["document_id"],
                    document_name=chunk["document_name"],
                    strategy=strategy,
                    chunk_type=chunk["chunk_type"],
                    text=chunk["text"],
                    chunk_index=chunk["chunk_index"],
                    parent_id=chunk.get("parent_id"),
                    section_title=chunk.get("section_title"),
                    page_number=chunk.get("page_number"),
                    embedding_model=self.model_name,
                    vector_dimension=len(vector),
                    embedding=vector,
                    metadata=chunk.get("metadata", {}),
                )
            )

        return embedded_chunks

    def embed_query(self, query: str) -> list[float]:
        query = query.strip()

        if not query:
            raise ValueError("Query must not be empty.")

        vectors = self._embed_texts([query])
        return vectors[0]

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
            normalize_embeddings=settings.NORMALIZE_EMBEDDINGS,
            show_progress_bar=False,
        )

        if isinstance(vectors, np.ndarray):
            return vectors.astype(float).tolist()

        return [list(vector) for vector in vectors]

    def _read_jsonl(self, path: Path) -> list[dict]:
        records: list[dict] = []

        with path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue

                records.append(json.loads(line))

        return records

    def _write_embeddings_jsonl(
        self,
        document_id: str,
        document_name: str,
        strategy: str,
        embedded_chunks: list[EmbeddedChunk],
    ) -> Path:
        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", Path(document_name).stem)
        output_filename = f"{safe_name}_{document_id}_{strategy}_embeddings.jsonl"
        output_path = settings.EMBEDDINGS_DIR / output_filename

        with output_path.open("w", encoding="utf-8") as file:
            for embedded_chunk in embedded_chunks:
                file.write(embedded_chunk.model_dump_json() + "\n")

        return output_path