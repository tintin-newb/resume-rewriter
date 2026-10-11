from pathlib import Path
from pypdf import PdfReader
from parsers.base import BaseDocumentParser


class ResumeParser(BaseDocumentParser):
    """Parses resumes from Markdown, plain text, or PDF files into raw text."""

    def parse(self, file_path: Path | str) -> str:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Resume file not found at: {path}")

        suffix = path.suffix.lower()

        if suffix in [".txt", ".md"]:
            return path.read_text(encoding="utf-8").strip()

        elif suffix == ".pdf":
            reader = PdfReader(path)
            extracted_pages = []
            for page_idx, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    extracted_pages.append(text)
            return "\n\n".join(extracted_pages).strip()

        else:
            raise ValueError(f"Unsupported resume file format: {suffix}. Supported: .pdf, .md, .txt")