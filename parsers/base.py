from abc import ABC, abstractmethod
from typing import Iterator, Dict, Any
from domain.models import RawRecord

class BaseParser(ABC):
    """
    Abstract base class for all data source parsers.
    Parsers are responsible for reading a file and yielding `RawRecord` instances.
    """
    
    def __init__(self, source_name: str):
        self.source_name = source_name
        
    @abstractmethod
    def parse(self, file_path: str) -> Iterator[RawRecord]:
        """
        Parses the given file and yields `RawRecord` objects.
        Should handle malformed records gracefully without crashing.
        """
        pass
