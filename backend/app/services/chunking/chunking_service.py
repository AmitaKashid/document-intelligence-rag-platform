import json
import re
import uuid
from pathlib import Path
from statistics import mean
import fitz
from app.core.config import settings
from app.schemas.document import DocumentChunk


class ChunkingService:
    """
    Creates multiple chunking strategies from parsed Markdown.

    Strategies:
    - recursive: fixed-size recursive-style chunks with overlap
    - section_aware: split by Markdown headings first
    - table_preserving: keeps Markdown tables together where possible
    - parent_child: creates parent section chunks and smaller child chunks
    """

    def create_all_strategy_chunks(
        self,
        document_id: str,
        document_name: str,
        markdown_path: str,
        pdf_path: str | None = None,
    ) -> list[dict]:
        markdown = Path(markdown_path).read_text(encoding="utf-8")

        page_texts = self._extract_pdf_pages(pdf_path) if pdf_path else []

        strategy_to_chunks = {
            "recursive": self.create_recursive_chunks(
                document_id=document_id,
                document_name=document_name,
                markdown=markdown,
                page_texts=page_texts,
            ),
            "section_aware": self.create_section_aware_chunks(
                document_id=document_id,
                document_name=document_name,
                markdown=markdown,
                page_texts=page_texts,
            ),
            "table_preserving": self.create_table_preserving_chunks(
                document_id=document_id,
                document_name=document_name,
                markdown=markdown,
                page_texts=page_texts,
            ),
            "parent_child": self.create_parent_child_chunks(
                document_id=document_id,
                document_name=document_name,
                markdown=markdown,
                page_texts=page_texts,
            ),
        }

        results: list[dict] = []

        for strategy, chunks in strategy_to_chunks.items():
            output_path = self._write_chunks_jsonl(
                document_id=document_id,
                document_name=document_name,
                strategy=strategy,
                chunks=chunks,
            )

            results.append(
                self._build_chunking_result(
                    strategy=strategy,
                    chunks=chunks,
                    output_path=output_path,
                )
            )

        return results

    def create_recursive_chunks(
    self,
    document_id: str,
    document_name: str,
    markdown: str,
    page_texts: list[dict] | None = None,
    ) -> list[DocumentChunk]:
        text = self._normalize_text(markdown)

        raw_chunks = self._split_with_overlap(
            text=text,
            chunk_size=settings.DEFAULT_CHUNK_SIZE,
            chunk_overlap=settings.DEFAULT_CHUNK_OVERLAP,
        )

        raw_chunks = [
            chunk
            for chunk in raw_chunks
            if self._is_useful_chunk(chunk)
        ]

        return [
            self._build_chunk(
                document_id=document_id,
                document_name=document_name,
                strategy="recursive",
                chunk_type="text",
                text=chunk_text,
                chunk_index=index,
                page_number=self._infer_page_number(chunk_text, page_texts or []),
            )
            for index, chunk_text in enumerate(raw_chunks)
        ]

    def create_section_aware_chunks(
        self,
        document_id: str,
        document_name: str,
        markdown: str,
        page_texts: list[dict] | None = None,
    ) -> list[DocumentChunk]:
        sections = self._split_markdown_sections(markdown)
        chunks: list[DocumentChunk] = []

        for section_title, section_text in sections:
            section_text = self._normalize_text(section_text)

            if not self._is_useful_chunk(section_text):
                continue

            if len(section_text) <= settings.DEFAULT_CHUNK_SIZE:
                chunks.append(
                    self._build_chunk(
                        document_id=document_id,
                        document_name=document_name,
                        strategy="section_aware",
                        chunk_type="text",
                        text=section_text,
                        chunk_index=len(chunks),
                        section_title=section_title,
                        page_number=self._infer_page_number(section_text, page_texts or []),
                    )
                )
            else:
                split_chunks = self._split_with_overlap(
                    text=section_text,
                    chunk_size=settings.DEFAULT_CHUNK_SIZE,
                    chunk_overlap=settings.DEFAULT_CHUNK_OVERLAP,
                )

                split_chunks = [
                    chunk for chunk in split_chunks
                    if self._is_useful_chunk(chunk)
                ]

                for chunk_text in split_chunks:
                    chunks.append(
                        self._build_chunk(
                            document_id=document_id,
                            document_name=document_name,
                            strategy="section_aware",
                            chunk_type="text",
                            text=chunk_text,
                            chunk_index=len(chunks),
                            section_title=section_title,
                            page_number=self._infer_page_number(chunk_text, page_texts or []),
                        )
                    )

        return chunks
    def create_table_preserving_chunks(
        self,
        document_id: str,
        document_name: str,
        markdown: str,
        page_texts: list[dict] | None = None,
        ) -> list[DocumentChunk]:
        blocks = self._split_markdown_preserving_tables(markdown)
        chunks: list[DocumentChunk] = []

        text_buffer = ""

        for block_type, block_text in blocks:
            block_text = block_text.strip()

            if not block_text:
                continue

            if block_type == "table":
                if text_buffer.strip():
                    for text_chunk in self._split_with_overlap(
                        text=self._normalize_text(text_buffer),
                        chunk_size=settings.DEFAULT_CHUNK_SIZE,
                        chunk_overlap=settings.DEFAULT_CHUNK_OVERLAP,
                    ):
                        if self._is_useful_chunk(text_chunk):
                            chunks.append(
                                self._build_chunk(
                                    document_id=document_id,
                                    document_name=document_name,
                                    strategy="table_preserving",
                                    chunk_type="text",
                                    text=text_chunk,
                                    chunk_index=len(chunks),
                                    page_number=self._infer_page_number(text_chunk, page_texts or []),
                                )
                            )

                    text_buffer = ""

                chunks.append(
                    self._build_chunk(
                        document_id=document_id,
                        document_name=document_name,
                        strategy="table_preserving",
                        chunk_type="table",
                        text=block_text,
                        chunk_index=len(chunks),
                        page_number=self._infer_page_number(block_text, page_texts or []),
                    )
                )
            else:
                text_buffer += "\n\n" + block_text

        if text_buffer.strip():
            for text_chunk in self._split_with_overlap(
                text=self._normalize_text(text_buffer),
                chunk_size=settings.DEFAULT_CHUNK_SIZE,
                chunk_overlap=settings.DEFAULT_CHUNK_OVERLAP,
            ):
                if self._is_useful_chunk(text_chunk):
                    chunks.append(
                        self._build_chunk(
                            document_id=document_id,
                            document_name=document_name,
                            strategy="table_preserving",
                            chunk_type="text",
                            text=text_chunk,
                            chunk_index=len(chunks),
                            page_number=self._infer_page_number(text_chunk, page_texts or []),
                        )
                    )

        return chunks
    def create_parent_child_chunks(
        self,
        document_id: str,
        document_name: str,
        markdown: str,
        page_texts: list[dict] | None = None,
    ) -> list[DocumentChunk]:
        sections = self._split_markdown_sections(markdown)
        chunks: list[DocumentChunk] = []

        for section_title, section_text in sections:
            section_text = self._normalize_text(section_text)

            if not self._is_useful_chunk(section_text):
                continue

            parent_id = str(uuid.uuid4())
            parent_page_number = self._infer_page_number(section_text, page_texts or [])
            parent_chunk = DocumentChunk(
                chunk_id=parent_id,
                document_id=document_id,
                document_name=document_name,
                strategy="parent_child",
                chunk_type="parent",
                text=section_text,
                chunk_index=len(chunks),
                parent_id=None,
                section_title=section_title,
                page_number=parent_page_number,
                metadata={
                    "role": "parent_context",
                    "child_chunk_size": 450,
                    "child_chunk_overlap": 75,
                },
            )
            chunks.append(parent_chunk)

            child_texts = self._split_with_overlap(
                text=section_text,
                chunk_size=450,
                chunk_overlap=75,
            )

            child_texts = [
                child_text
                for child_text in child_texts
                if self._is_useful_chunk(child_text)
            ]

            for child_text in child_texts:
                chunks.append(
                    self._build_chunk(
                        document_id=document_id,
                        document_name=document_name,
                        strategy="parent_child",
                        chunk_type="child",
                        text=child_text,
                        chunk_index=len(chunks),
                        parent_id=parent_id,
                        section_title=section_title,
                        page_number=self._infer_page_number(child_text, page_texts or []),
                        metadata={
                            "role": "retrieval_child",
                        },
                    )
                )

        return chunks

    def _is_heading_only_chunk(self, text: str) -> bool:
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        if len(lines) == 1 and lines[0].startswith("#"):
            return True

        return False

    def _is_useful_chunk(self, text: str) -> bool:
        cleaned = text.strip()

        if not cleaned:
            return False

        if self._is_heading_only_chunk(cleaned):
            return False

        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]

        non_heading_lines = [
            line
            for line in lines
            if not line.startswith("#")
        ]

        if not non_heading_lines:
            return False

        content_text = " ".join(non_heading_lines).strip()

        if len(content_text) < 80:
            return False

        return True

    def _build_chunk(
        self,
        document_id: str,
        document_name: str,
        strategy: str,
        chunk_type: str,
        text: str,
        chunk_index: int,
        parent_id: str | None = None,
        section_title: str | None = None,
        page_number: int | None = None,
        metadata: dict | None = None,
    ) -> DocumentChunk:
        return DocumentChunk(
            chunk_id=str(uuid.uuid4()),
            document_id=document_id,
            document_name=document_name,
            strategy=strategy,
            chunk_type=chunk_type,
            text=text,
            chunk_index=chunk_index,
            parent_id=parent_id,
            section_title=section_title,
            page_number=page_number,
            metadata=metadata or {},
        )

    def _split_with_overlap(
        self,
        text: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[str]:
        if not text:
            return []

        separators = ["\n\n", "\n", ". ", " ", ""]
        chunks = self._recursive_split(text, chunk_size, separators)

        merged_chunks: list[str] = []
        current = ""

        for chunk in chunks:
            if len(current) + len(chunk) <= chunk_size:
                current = f"{current} {chunk}".strip()
            else:
                if current:
                    merged_chunks.append(current.strip())
                current = chunk

        if current:
            merged_chunks.append(current.strip())

        if chunk_overlap <= 0 or len(merged_chunks) <= 1:
            return merged_chunks

        overlapped_chunks: list[str] = []

        for index, chunk in enumerate(merged_chunks):
            if index == 0:
                overlapped_chunks.append(chunk)
                continue

            previous = merged_chunks[index - 1]
            overlap_text = self._get_word_boundary_overlap(
                previous,
                chunk_overlap,
            )
            overlapped_chunks.append(f"{overlap_text} {chunk}".strip())

        return overlapped_chunks

    def _recursive_split(
        self,
        text: str,
        chunk_size: int,
        separators: list[str],
    ) -> list[str]:
        text = text.strip()

        if len(text) <= chunk_size:
            return [text]

        separator = separators[0]

        if separator == "":
            return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

        parts = text.split(separator)

        if len(parts) == 1:
            return self._recursive_split(text, chunk_size, separators[1:])

        result = []

        for part in parts:
            part = part.strip()

            if not part:
                continue

            if len(part) <= chunk_size:
                result.append(part)
            else:
                result.extend(
                    self._recursive_split(part, chunk_size, separators[1:])
                )

        return result

    def _get_word_boundary_overlap(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text

        overlap = text[-max_chars:]
        first_space = overlap.find(" ")

        if first_space == -1:
            return overlap

        return overlap[first_space + 1 :].strip()

    def _split_markdown_sections(self, markdown: str) -> list[tuple[str | None, str]]:
        pattern = r"(?=^#{1,6}\s+)"
        raw_sections = re.split(pattern, markdown, flags=re.MULTILINE)

        sections: list[tuple[str | None, str]] = []

        for raw_section in raw_sections:
            raw_section = raw_section.strip()

            if not raw_section:
                continue

            lines = raw_section.splitlines()
            first_line = lines[0].strip() if lines else ""

            section_title = None

            if first_line.startswith("#"):
                section_title = first_line.lstrip("#").strip()

            sections.append((section_title, raw_section))

        if not sections and markdown.strip():
            sections.append((None, markdown.strip()))

        return sections

    def _split_markdown_preserving_tables(self, markdown: str) -> list[tuple[str, str]]:
        lines = markdown.splitlines()

        blocks: list[tuple[str, str]] = []
        current_text_lines: list[str] = []
        current_table_lines: list[str] = []
        inside_table = False

        for line in lines:
            if self._is_markdown_table_line(line):
                if current_text_lines:
                    blocks.append(("text", "\n".join(current_text_lines)))
                    current_text_lines = []

                current_table_lines.append(line)
                inside_table = True
            else:
                if inside_table:
                    blocks.append(("table", "\n".join(current_table_lines)))
                    current_table_lines = []
                    inside_table = False

                current_text_lines.append(line)

        if current_table_lines:
            blocks.append(("table", "\n".join(current_table_lines)))

        if current_text_lines:
            blocks.append(("text", "\n".join(current_text_lines)))

        return blocks

    def _is_markdown_table_line(self, line: str) -> bool:
        stripped = line.strip()

        if not stripped:
            return False

        has_pipes = stripped.count("|") >= 2
        is_separator = bool(
            re.match(
                r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$",
                stripped,
            )
        )

        return has_pipes or is_separator

    def _normalize_text(self, text: str) -> str:
        text = text.replace("\r\n", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    def _extract_pdf_pages(self, pdf_path: str | None) -> list[dict]:
        if not pdf_path:
            return []

        path = Path(pdf_path)

        if not path.exists():
            return []

        pages: list[dict] = []

        with fitz.open(str(path)) as doc:
            for page_index, page in enumerate(doc):
                text = page.get_text("text")
                text = self._normalize_text(text)

                if not text:
                    continue

                pages.append(
                    {
                        "page_number": page_index + 1,
                        "text": text,
                        "normalized_text": self._normalize_for_page_match(text),
                        "tokens": set(self._tokenize_for_page_match(text)),
                    }
                )

        return pages


    def _normalize_for_page_match(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^a-z0-9äöüß]+", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


    def _tokenize_for_page_match(self, text: str) -> list[str]:
        text = self._normalize_for_page_match(text)

        stopwords = {
            "this", "that", "with", "from", "into", "than", "then",
            "they", "them", "their", "there", "what", "when", "where",
            "which", "would", "could", "should", "about", "using",
            "used", "also", "more", "less", "such", "only", "very",
            "page", "section"
        }

        return [
            token
            for token in text.split()
            if len(token) >= 4 and token not in stopwords
        ]
    def _infer_page_number(
        self,
        chunk_text: str,
        page_texts: list[dict],
    ) -> int | None:
        """
        Infer page number for a chunk.

        Priority:
        1. Match heading/section title exactly or nearly exactly.
        2. Match first meaningful sentence.
        3. Fall back to token overlap only if strong enough.
        """
        if not chunk_text or not page_texts:
            return None

        normalized_chunk = self._normalize_for_page_match(chunk_text)
        chunk_tokens = set(self._tokenize_for_page_match(chunk_text))

        if not chunk_tokens:
            return None

        lines = [
            line.strip().strip("#").strip()
            for line in chunk_text.splitlines()
            if line.strip()
        ]

        heading_candidates = []
        first_sentence_candidates = []

        for line in lines[:5]:
            normalized_line = self._normalize_for_page_match(line)

            if not normalized_line:
                continue

            # Headings are the strongest signal.
            if len(normalized_line) >= 8 and len(normalized_line) <= 120:
                heading_candidates.append(normalized_line)

            if len(normalized_line) >= 30:
                first_sentence_candidates.append(normalized_line)

        # 1. Exact / near-exact heading match.
        for phrase in heading_candidates:
            for page in page_texts:
                page_text = page.get("normalized_text", "")

                if phrase in page_text:
                    return page["page_number"]

        # 2. First sentence / phrase match.
        for phrase in first_sentence_candidates:
            phrase_probe = phrase[:160]

            for page in page_texts:
                page_text = page.get("normalized_text", "")

                if phrase_probe in page_text:
                    return page["page_number"]

        # 3. Token-overlap fallback with stronger threshold.
        best_page_number: int | None = None
        best_score = 0.0

        for page in page_texts:
            page_tokens = page.get("tokens", set())

            if not page_tokens:
                continue

            overlap = chunk_tokens.intersection(page_tokens)
            score = len(overlap) / max(len(chunk_tokens), 1)

            # Penalize page 1 fallback unless the score is very strong.
            if page["page_number"] == 1 and score < 0.45:
                score *= 0.35

            if score > best_score:
                best_score = score
                best_page_number = page["page_number"]

        if best_score < 0.30:
            return None

        return best_page_number

    def _normalize_for_page_match(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^a-z0-9äöüß]+", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _tokenize_for_page_match(self, text: str) -> list[str]:
        text = self._normalize_for_page_match(text)

        stopwords = {
            "this", "that", "with", "from", "into", "than", "then",
            "they", "them", "their", "there", "what", "when", "where",
            "which", "would", "could", "should", "about", "using",
            "used", "also", "more", "less", "such", "only", "very",
            "page", "section"
        }

        return [
            token
            for token in text.split()
            if len(token) >= 4 and token not in stopwords
        ]


    def _write_chunks_jsonl(
        self,
        document_id: str,
        document_name: str,
        strategy: str,
        chunks: list[DocumentChunk],
    ) -> Path:
        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", Path(document_name).stem)
        output_filename = f"{safe_name}_{document_id}_{strategy}_chunks.jsonl"
        output_path = settings.CHUNKS_DIR / output_filename

        with output_path.open("w", encoding="utf-8") as file:
            for chunk in chunks:
                file.write(chunk.model_dump_json() + "\n")

        return output_path

    def _build_chunking_result(
        self,
        strategy: str,
        chunks: list[DocumentChunk],
        output_path: Path,
    ) -> dict:
        chunk_lengths = [len(chunk.text) for chunk in chunks]
        chunk_type_counts: dict[str, int] = {}

        for chunk in chunks:
            chunk_type_counts[chunk.chunk_type] = (
                chunk_type_counts.get(chunk.chunk_type, 0) + 1
            )

        return {
            "strategy": strategy,
            "chunks_created": len(chunks),
            "output_filename": output_path.name,
            "output_path": str(output_path),
            "chunk_type_counts": chunk_type_counts,
            "average_chunk_chars": round(mean(chunk_lengths), 2) if chunk_lengths else 0,
            "min_chunk_chars": min(chunk_lengths) if chunk_lengths else 0,
            "max_chunk_chars": max(chunk_lengths) if chunk_lengths else 0,
        }