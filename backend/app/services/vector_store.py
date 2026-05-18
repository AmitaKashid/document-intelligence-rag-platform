import json
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.core.config import settings


class QdrantVectorStore:
    """
    Handles vector indexing in Qdrant.

    Current responsibility:
    - Create collection if needed
    - Read embedding JSONL files
    - Upsert vectors with metadata payload
    """

    def __init__(self) -> None:
        self.client = QdrantClient(url=settings.QDRANT_URL)
        self.collection_name = settings.QDRANT_COLLECTION_NAME

    def index_embedding_results(self, embedding_results: list[dict]) -> list[dict]:
        indexing_results: list[dict] = []

        for embedding_result in embedding_results:
            records = self._read_jsonl(Path(embedding_result["output_path"]))

            if not records:
                indexing_results.append(
                    {
                        "strategy": embedding_result["strategy"],
                        "collection_name": self.collection_name,
                        "points_indexed": 0,
                        "vector_dimension": 0,
                        "status": "skipped_empty_embedding_file",
                    }
                )
                continue

            vector_dimension = records[0]["vector_dimension"]

            self._ensure_collection(vector_dimension=vector_dimension)

            points = self._build_points(records)

            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )

            indexing_results.append(
                {
                    "strategy": embedding_result["strategy"],
                    "collection_name": self.collection_name,
                    "points_indexed": len(points),
                    "vector_dimension": vector_dimension,
                    "status": "indexed",
                }
            )

        return indexing_results

    def _ensure_collection(self, vector_dimension: int) -> None:
        collections = self.client.get_collections().collections
        existing_names = {collection.name for collection in collections}

        if self.collection_name in existing_names:
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=vector_dimension,
                distance=Distance.COSINE,
            ),
        )

    def _build_points(self, records: list[dict]) -> list[PointStruct]:
        points: list[PointStruct] = []

        for record in records:
            payload = {
                "chunk_id": record["chunk_id"],
                "document_id": record["document_id"],
                "document_name": record["document_name"],
                "strategy": record["strategy"],
                "chunk_type": record["chunk_type"],
                "text": record["text"],
                "chunk_index": record["chunk_index"],
                "parent_id": record.get("parent_id"),
                "section_title": record.get("section_title"),
                "page_number": record.get("page_number"),
                "embedding_model": record["embedding_model"],
                "vector_dimension": record["vector_dimension"],
                "metadata": record.get("metadata", {}),
            }

            points.append(
                PointStruct(
                    id=record["chunk_id"],
                    vector=record["embedding"],
                    payload=payload,
                )
            )

        return points

    def search(
        self,
        query_vector: list[float],
        document_id: str | None = None,
        strategy: str | None = None,
        limit: int = 5,
    ) -> list:
        query_filter = self._build_filter(
            document_id=document_id,
            strategy=strategy,
        )

        if not self.client.collection_exists(collection_name=self.collection_name):
            raise ValueError(
                f"Qdrant collection '{self.collection_name}' does not exist. "
                "Upload and index a document first."
            )

        try:
            result = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )

            return result.points

        except AttributeError:
            return self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
            )

    def _build_filter(
        self,
        document_id: str | None = None,
        strategy: str | None = None,
    ) -> Filter | None:
        conditions = []

        if document_id:
            conditions.append(
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=document_id),
                )
            )

        if strategy:
            conditions.append(
                FieldCondition(
                    key="strategy",
                    match=MatchValue(value=strategy),
                )
            )

        if not conditions:
            return None

        return Filter(must=conditions)

    def _read_jsonl(self, path: Path) -> list[dict]:
        records: list[dict] = []

        with path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))

        return records
    
    def list_documents(self) -> list[dict]:
        points, _ = self.client.scroll(
            collection_name=self.collection_name,
            limit=10000,
            with_payload=True,
            with_vectors=False,
        )

        documents: dict[str, dict] = {}

        for point in points:
            payload = point.payload or {}

            document_id = payload.get("document_id")
            document_name = payload.get("document_name")
            strategy = payload.get("strategy")

            if not document_id or not document_name:
                continue

            if document_id not in documents:
                documents[document_id] = {
                    "document_id": document_id,
                    "document_name": document_name,
                    "strategies": set(),
                    "chunk_count": 0,
                }

            if strategy:
                documents[document_id]["strategies"].add(strategy)

            documents[document_id]["chunk_count"] += 1

        return [
            {
                "document_id": item["document_id"],
                "document_name": item["document_name"],
                "strategies": sorted(item["strategies"]),
                "chunk_count": item["chunk_count"],
            }
            for item in documents.values()
        ]