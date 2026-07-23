from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExtractedPDF:
    markdown: str
    method: str
    summary: dict[str, object]


class PDFProcessingService:
    def __init__(self, *, ocr_languages: list[str]):
        self.ocr_languages = ocr_languages

    async def extract(self, *, file_bytes: bytes, filename: str) -> ExtractedPDF:
        return await asyncio.to_thread(
            self._extract_sync,
            file_bytes=file_bytes,
            filename=filename,
        )

    def _extract_sync(self, *, file_bytes: bytes, filename: str) -> ExtractedPDF:
        import pymupdf4llm

        suffix = Path(filename).suffix or ".pdf"
        with tempfile.TemporaryDirectory(prefix="shiloh-pdf-") as temp_dir:
            working_dir = Path(temp_dir)
            original_path = working_dir / f"input{suffix}"
            original_path.write_bytes(file_bytes)

            markdown = pymupdf4llm.to_markdown(
                str(original_path),
                header=False,
                footer=False,
            )
            if self._needs_ocr_fallback(markdown):
                import ocrmypdf

                ocr_path = working_dir / f"ocr{suffix}"
                ocrmypdf.ocr(
                    str(original_path),
                    str(ocr_path),
                    language=self.ocr_languages,
                    skip_text=True,
                    rotate_pages=True,
                    deskew=True,
                    clean=True,
                    force_ocr=False,
                )
                ocr_markdown = pymupdf4llm.to_markdown(
                    str(ocr_path),
                    header=False,
                    footer=False,
                )
                if len(ocr_markdown.strip()) >= len(markdown.strip()):
                    markdown = ocr_markdown
                    method = "ocrmypdf+pymupdf4llm"
                else:
                    method = "pymupdf4llm"
            else:
                method = "pymupdf4llm"

        summary = {
            "character_count": len(markdown),
            "line_count": len([line for line in markdown.splitlines() if line.strip()]),
            "used_ocr_fallback": method == "ocrmypdf+pymupdf4llm",
        }
        return ExtractedPDF(markdown=markdown, method=method, summary=summary)

    def _needs_ocr_fallback(self, markdown: str) -> bool:
        stripped = markdown.strip()
        if len(stripped) < 100:
            return True
        non_whitespace = len("".join(stripped.split()))
        return non_whitespace < 150
