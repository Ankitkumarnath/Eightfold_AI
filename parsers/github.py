import json
from typing import Generator
from domain.models import RawRecord
from normalizers.text import normalize_text, normalize_skill

class GithubParser:
    """Mock parser for GitHub JSON profiles"""
    
    def parse(self, filepath: str) -> Generator[RawRecord, None, None]:
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        name_parts = str(data.get("Name", "")).split()
        first_name = name_parts[0] if name_parts else None
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else None
        
        # GitHub repos as skills
        skills = []
        for repo in data.get("Repositories", []):
            skill = normalize_skill(repo)
            if skill: skills.append(skill)
            
        links = {"github": "https://github.com/ankit"} # Hardcoded for demo
        
        yield RawRecord(
            source_system="GitHub",
            original_id="github_mock_id",
            first_name=first_name,
            last_name=last_name,
            skills=skills,
            links=links,
            raw_data=data
        )
