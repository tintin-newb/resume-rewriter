import re
from pathlib import Path
from typing import Dict, List, Set, Any
from pypdf import PdfReader
from parsers.base import BaseDocumentParser


class ActionVerbPDFParser(BaseDocumentParser):
    """
    Parses action verb PDFs into categorized word lists 
    and a flat set for prompt injection.
    """

    def parse(self, file_path: Path | str) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Action verbs file not found: {path}")

        reader = PdfReader(path)
        combined_text = "\n".join(
            page.extract_text() for page in reader.pages if page.extract_text()
        )

        # Extract words (filter out common header lines and short artifacts)
        raw_lines = [line.strip() for line in combined_text.splitlines() if line.strip()]
        
        words: Set[str] = set()
        for line in raw_lines:
            # Match single verb words or hyphenated verbs (e.g. "Problem solved", "Co-authored")
            tokens = re.findall(r"\b[A-Za-z][A-Za-z\-]+[A-Za-z]\b|\b[A-Za-z]\b", line)
            for token in tokens:
                token_clean = token.capitalize()
                if len(token_clean) > 2 and token_clean.isalpha():
                    words.add(token_clean)

        return {
            "verb_set": sorted(list(words)),
            "count": len(words)
        }