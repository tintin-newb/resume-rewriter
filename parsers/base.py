from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseDocumentParser(ABC):
    """Abstract Base Class for all document parsers."""

    @abstractmethod
    def parse(self, file_path: Path | str) -> Any:
        """Parses the input file and returns structured or raw content."""
        pass