from __future__ import annotations

import json
import os
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient


TEXT_KEYS = [
    "text",
    "content",
    "page_content",
    "chunk_text",
    "document_text",
]

DOCUMENT_KEYS = [
    "document",
    "document_name",
    "filename",
    "file_name",
    "source",
    "pdf_name",
]

PAGE_KEYS = [
    "page",
    "page_number",
    "page_index",
    "pageIndex",
    "page_no",
    "page_num",
]

SECTION_KEYS = [
    "section",
    "heading",
    "title",
    "section_title",
]

STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "are", "was", "were",
    "you", "your", "have", "has", "had", "not", "but", "can", "will", "would",
    "should", "could", "into", "than", "then", "they", "them", "their", "there",
    "about", "also", "using", "used", "use", "our", "out", "all", "any", "each",
    "such", "these", "those", "when", "where", "which", "what", "how", "why",
    "its", "it", "is", "in", "on", "of", "to", "a", "an", "as", "by", "or",
    "be", "we", "if", "at", "more", "one", "two", "may", "do", "does"
}


def read_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_nested_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flattens Qdrant payload and metadata.

    Important:
    Some fields may exist both at the top level and inside payload["metadata"].
    We keep non-empty values and avoid overwriting useful metadata with None.
    """
    merged: Dict[str, Any] = {}

    metadata = payload.get("metadata")

    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if value not in [None, ""]:
                merged[key] = value

    for key, value in payload.items():
        if key == "metadata":
            continue

        if value not in [None, ""]:
            merged[key] = value
        elif key not in merged:
            merged[key] = value

    return merged


def first_available(payload: Dict[str, Any], keys: List[str]) -> Optional[Any]:
    """
    Reads field from flattened payload first, then from nested metadata.
    """
    for key in keys:
        value = payload.get(key)
        if value not in [None, ""]:
            return value

    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for key in keys:
            value = metadata.get(key)
            if value not in [None, ""]:
                return value

    return None



def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_topic_word(word: str) -> str:
    word = word.lower()
    word = re.sub(r"[^a-zA-Z0-9\-]", "", word)
    return word.strip()


def extract_topic(text: str, max_words: int = 4) -> str:
    """
    Creates a small topic phrase from the chunk.
    This gives better dynamic questions than generic 'this part of the document'.
    """
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", text)
    normalized = [normalize_topic_word(w) for w in words]

    candidates = [
        w for w in normalized
        if w and w not in STOPWORDS and len(w) >= 4
    ]

    if not candidates:
        return "this topic"

    counts = Counter(candidates)
    top_words = [word for word, _ in counts.most_common(max_words)]

    return " ".join(top_words)


def first_sentences(text: str, max_sentences: int = 2, max_chars: int = 600) -> str:
    text = clean_text(text)

    sentences = re.split(r"(?<=[.!?])\s+", text)
    selected = []

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 35:
            continue

        selected.append(sentence)

        if len(selected) >= max_sentences:
            break

    answer = " ".join(selected)

    if not answer:
        answer = text[:max_chars]

    return answer[:max_chars].strip()


def get_qdrant_client() -> QdrantClient:
    backend_dir = Path(__file__).resolve().parents[1]
    read_env_file(backend_dir / ".env")

    qdrant_url = (
        os.environ.get("QDRANT_URL")
        or os.environ.get("VECTOR_DB_URL")
        or "http://127.0.0.1:6333"
    )

    return QdrantClient(url=qdrant_url)


def get_collection_name(client: QdrantClient) -> str:
    explicit = (
        os.environ.get("QDRANT_COLLECTION")
        or os.environ.get("QDRANT_COLLECTION_NAME")
        or os.environ.get("COLLECTION_NAME")
    )

    if explicit:
        return explicit

    collections = client.get_collections().collections
    names = [collection.name for collection in collections]

    if not names:
        raise RuntimeError("No Qdrant collections found. Upload and index a PDF first.")

    preferred_names = [
        "documents",
        "document_chunks",
        "rag_documents",
        "chunks",
    ]

    for name in preferred_names:
        if name in names:
            return name

    return names[0]


def debug_payload_keys(payload: Dict[str, Any]) -> None:
    """
    Helpful when page is None. Shows which metadata keys actually exist.
    """
    print("\nAvailable Qdrant payload keys:")
    print(sorted(payload.keys()))


def load_indexed_chunks(
    max_points: int = 500,
    target_document: Optional[str] = None,
    debug_first_payload: bool = False,
) -> List[Dict[str, Any]]:
    client = get_qdrant_client()
    collection_name = get_collection_name(client)

    chunks: List[Dict[str, Any]] = []
    offset = None
    first_payload_printed = False

    while len(chunks) < max_points:
        points, next_offset = client.scroll(
            collection_name=collection_name,
            limit=min(100, max_points - len(chunks)),
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        if not points:
            break

        for point in points:
            payload = get_nested_payload(point.payload or {})

            if debug_first_payload and not first_payload_printed:
                debug_payload_keys(payload)
                first_payload_printed = True

            text = first_available(payload, TEXT_KEYS)

            if not text:
                continue

            text = clean_text(str(text))

            if len(text) < 180:
                continue

            document = str(first_available(payload, DOCUMENT_KEYS) or "")
            page = first_available(payload, PAGE_KEYS)
            section = str(first_available(payload, SECTION_KEYS) or "")

            if target_document:
                if target_document.lower() not in document.lower():
                    continue

            chunks.append(
                {
                    "id": str(point.id),
                    "text": text,
                    "document": document,
                    "page": page,
                    "section": section,
                    "topic": extract_topic(text),
                }
            )

        if next_offset is None:
            break

        offset = next_offset

    if not chunks:
        raise RuntimeError(
            "No usable chunks found in Qdrant. Make sure a PDF is uploaded/indexed "
            "and that Qdrant payload contains text/content/page_content."
        )

    return chunks


def select_diverse_chunks(
    chunks: List[Dict[str, Any]],
    num_questions: int,
) -> List[Dict[str, Any]]:
    """
    Select chunks from different documents/pages/sections/topics where possible.
    """
    seen_keys = set()
    diverse = []

    random.shuffle(chunks)

    for chunk in chunks:
        key = (
            chunk.get("document"),
            chunk.get("page"),
            chunk.get("section"),
            chunk.get("topic"),
        )

        if key in seen_keys:
            continue

        seen_keys.add(key)
        diverse.append(chunk)

        if len(diverse) >= num_questions:
            return diverse

    return diverse[:num_questions]


def make_question_from_chunk(chunk: Dict[str, Any], index: int) -> Dict[str, Any]:
    document = chunk.get("document") or ""
    page = chunk.get("page")
    section = chunk.get("section") or ""
    text = chunk["text"]
    topic = chunk.get("topic") or "this topic"

    expected_answer = first_sentences(text)

    if section:
        question = f"What does the document explain in the section '{section}' about {topic}?"
    elif topic and topic != "this topic":
        question = f"What does the document explain about {topic}?"
    elif page not in [None, ""]:
        question = f"What information is provided on page {page} of the document?"
    else:
        question = "What is the main information in this part of the document?"

    return {
        "id": f"dynamic_q{index}",
        "question": question,
        "expected_answer": expected_answer,
        "expected_sources": [
            {
                "document": document,
                "page": page,
                "section": section,
            }
        ],
        "source_chunk_id": chunk["id"],
        "source_preview": text[:700],
    }


def generate_dynamic_eval_dataset(
    output_path: str | Path,
    num_questions: int = 5,
    max_points: int = 500,
    target_document: Optional[str] = None,
    debug_first_payload: bool = False,
) -> List[Dict[str, Any]]:
    chunks = load_indexed_chunks(
        max_points=max_points,
        target_document=target_document,
        debug_first_payload=debug_first_payload,
    )

    selected_chunks = select_diverse_chunks(chunks, num_questions=num_questions)

    dataset = [
        make_question_from_chunk(chunk, index=i + 1)
        for i, chunk in enumerate(selected_chunks)
    ]

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    return dataset


if __name__ == "__main__":
    backend_dir = Path(__file__).resolve().parents[1]
    output_file = backend_dir / "data" / "eval_questions_dynamic.json"

    # Optional: restrict evaluation to one document.
    # Example:
    # target_document = "RAG.pdf"
    target_document = None

    dataset = generate_dynamic_eval_dataset(
        output_path=output_file,
        num_questions=5,
        target_document=target_document,
        debug_first_payload=True,
    )

    print(f"\nGenerated {len(dataset)} dynamic evaluation questions.")
    print(f"Saved to: {output_file}")

    for item in dataset:
        print()
        print(f"{item['id']}: {item['question']}")
        print(f"Expected source: {item['expected_sources']}")