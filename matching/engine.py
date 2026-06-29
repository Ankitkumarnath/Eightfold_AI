from typing import List
from domain.models import RawRecord
from matching.graph import build_connected_components

class EntityResolutionEngine:
    """
    Orchestrates the entity resolution process.
    Groups raw records into sets of records that belong to the same candidate.
    """
    
    def resolve(self, records: List[RawRecord]) -> List[List[RawRecord]]:
        """
        Takes a list of raw records from all sources and returns a list of candidate groups.
        Each group is a list of RawRecords that represent the same candidate.
        """
        return build_connected_components(records)
