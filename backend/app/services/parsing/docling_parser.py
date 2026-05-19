from pathlib import Path

from docling.document_converter import DocumentConverter

from app.core.config import settings


class DoclingParser:
    """
    Structure-aware PDF parser using Docling.

    Current responsibility:
    - Convert PDF into DoclingDocument
    - Export parsed result to Markdown
    - Save Markdown artifact for inspection/debugging
    """

    def __init__(self) -> None:
        self.converter = DocumentConverter()

    def parse_to_markdown(
        self,
        document_id: str,
        original_filename: str,
        stored_path: str,
    ) -> dict:
        pdf_path = Path(stored_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {stored_path}")

        result = self.converter.convert(str(pdf_path))
        doc = result.document

        markdown = doc.export_to_markdown()

        parsed_filename = f"{document_id}_{Path(original_filename).stem}.md"
        parsed_path = settings.PARSED_DIR / parsed_filename
        parsed_path.write_text(markdown, encoding="utf-8")

        return {
            "parser_name": "docling",
            "parsed_markdown_filename": parsed_filename,
            "parsed_markdown_path": str(parsed_path),
            "source_pdf_path": str(pdf_path),
            "markdown_char_count": len(markdown),
            "markdown_preview": markdown[:1000],
        }