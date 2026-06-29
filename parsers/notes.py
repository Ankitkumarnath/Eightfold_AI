from typing import Generator
from domain.models import RawRecord
from normalizers.text import normalize_skill

class NotesParser:
    """Mock parser for Recruiter Notes txt files"""
    
    def parse(self, filepath: str) -> Generator[RawRecord, None, None]:
        with open(filepath, 'r') as f:
            content = f.read()
            
        skills = []
        if "Python" in content: skills.append(normalize_skill("Python"))
        if "SQL" in content: skills.append(normalize_skill("SQL"))
        
        yield RawRecord(
            source_system="Notes",
            original_id="notes_mock_id",
            first_name="Ankit",
            last_name="Nath",
            skills=skills,
            raw_data={"notes": content}
        )
