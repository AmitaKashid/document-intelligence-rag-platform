from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import fitz


class DocumentProfiler:
    """
    Builds a lightweight document profile used for automatic retrieval-policy selection.

    This does not run LLM evaluation.
    It only inspects document structure:
    - page count
    - heading count
    - table density
    - average text length
    """

    def profile_document(
        self,
        document_id: str,
        document_name: str,
        pdf_path: str,
        markdown_path: str,
        chunking_results: list[dict] | None = None,
    ) -> dict[str, Any]:
        markdown = Path(markdown_path).read_text(encoding="utf-8")

        page_count = self._count_pdf_pages(pdf_path)
        heading_count = self._count_markdown_headings(markdown)
        table_count = self._count_markdown_tables(markdown)
        avg_page_chars = self._average_page_chars(pdf_path)

        chunking_results = chunking_results or []

        chunk_counts = {
            result.get("strategy"): result.get("chunks_created", 0)
            for result in chunking_results
            if result.get("strategy")
        }

        detected_structure = self._detect_structure(
            page_count=page_count,
            heading_count=heading_count,
            table_count=table_count,
            avg_page_chars=avg_page_chars,
        )

        policy = self.choose_retrieval_policy(
            page_count=page_count,
            heading_count=heading_count,
            table_count=table_count,
            detected_structure=detected_structure,
        )

        return {
            "document_id": document_id,
            "document_name": document_name,
            "page_count": page_count,
            "heading_count": heading_count,
            "table_count": table_count,
            "avg_page_chars": avg_page_chars,
            "chunk_counts": chunk_counts,
            "detected_structure": detected_structure,
            "recommended_strategy": policy["strategy"],
            "recommended_top_k": policy["top_k"],
            "reason": policy["reason"],
        }

    def choose_retrieval_policy(
        self,
        page_count: int,
        heading_count: int,
        table_count: int,
        detected_structure: str,
    ) -> dict[str, Any]:
        """
        Lightweight rule-based retrieval policy.

        This is intentionally simple and fast.
        Full benchmarking stays available as a separate diagnostic workflow.
        """
        if table_count >= 3:
            return {
                "strategy": "table_preserving",
                "top_k": 3,
                "reason": (
                    "The document contains multiple tables, so table-preserving "
                    "chunks reduce the risk of splitting tabular evidence."
                ),
            }

        if heading_count >= 5:
            return {
                "strategy": "section_aware",
                "top_k": 3,
                "reason": (
                    "The document contains clear headings, so section-aware chunks "
                    "preserve topic boundaries and support page-level citations."
                ),
            }

        if page_count >= 20:
            return {
                "strategy": "parent_child",
                "top_k": 3,
                "reason": (
                    "The document is long, so parent-child retrieval can preserve "
                    "broader context while retrieving focused child chunks."
                ),
            }

        return {
            "strategy": "recursive",
            "top_k": 3,
            "reason": (
                "The document has limited explicit structure, so recursive chunking "
                "provides a robust fallback."
            ),
        }

    def save_profile(self, profile: dict[str, Any], output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{profile['document_id']}_profile.json"

        output_path.write_text(
            json.dumps(profile, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return output_path

    def load_profile(self, document_id: str, profile_dir: Path) -> dict[str, Any] | None:
        profile_path = profile_dir / f"{document_id}_profile.json"

        if not profile_path.exists():
            return None

        return json.loads(profile_path.read_text(encoding="utf-8"))

    def _count_pdf_pages(self, pdf_path: str) -> int:
        path = Path(pdf_path)

        if not path.exists():
            return 0

        with fitz.open(str(path)) as doc:
            return len(doc)

    def _average_page_chars(self, pdf_path: str) -> int:
        path = Path(pdf_path)

        if not path.exists():
            return 0

        page_lengths: list[int] = []

        with fitz.open(str(path)) as doc:
            for page in doc:
                text = page.get_text("text") or ""
                page_lengths.append(len(text.strip()))

        if not page_lengths:
            return 0

        return round(sum(page_lengths) / len(page_lengths))

    def _count_markdown_headings(self, markdown: str) -> int:
        return len(re.findall(r"^#{1,6}\s+", markdown, flags=re.MULTILINE))

    def _count_markdown_tables(self, markdown: str) -> int:
        table_blocks = 0
        inside_table = False

        for line in markdown.splitlines():
            stripped = line.strip()
            is_table_line = stripped.count("|") >= 2

            if is_table_line and not inside_table:
                table_blocks += 1
                inside_table = True
            elif not is_table_line:
                inside_table = False

        return table_blocks

    def _detect_structure(
        self,
        page_count: int,
        heading_count: int,
        table_count: int,
        avg_page_chars: int,
    ) -> str:
        if table_count >= 3:
            return "table_heavy_pdf"

        if heading_count >= 5:
            return "structured_heading_based_pdf"

        if page_count >= 20:
            return "long_document"

        if avg_page_chars < 400:
            return "sparse_or_scan_like_pdf"

        return "general_text_pdf"