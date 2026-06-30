import json
import uuid
from typing import Generator
from domain.models import RawRecord
from normalizers.text import normalize_text, normalize_skill
from normalizers.location import normalize_location
from core.logger import logger

class GithubParser:
    """Parser for GitHub JSON profiles"""
    def __init__(self):
        self.source_name = "github"
    
    def parse(self, filepath: str) -> Generator[RawRecord, None, None]:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if not isinstance(data, list):
                # Ensure it's a list for iteration, even if single object
                data = [data]
                
            for record in data:
                if not isinstance(record, dict):
                    continue
                    
                name_parts = str(record.get("Name", "")).split()
                first_name = normalize_text(name_parts[0]) if name_parts else None
                last_name = normalize_text(" ".join(name_parts[1:])) if len(name_parts) > 1 else None
                
                email = record.get("Email")
                location_str = record.get("Location")
                location = normalize_location(location_str) if location_str else None
                
                # GitHub repos as skills
                skills = []
                seen_skills = set()
                for repo in record.get("Repositories", []):
                    skill = normalize_skill(repo)
                    if skill and skill.lower() not in seen_skills:
                        seen_skills.add(skill.lower())
                        skills.append(skill)
                        
                # Extract github link if present, else fallback to a constructed one
                github_link = record.get("Url") or record.get("url") or record.get("html_url")
                if not github_link and record.get("login"):
                    github_link = f"https://github.com/{record.get('login')}"
                
                links = {}
                if github_link:
                    links["github"] = github_link
                    
                original_id = str(record.get("id") or record.get("login") or uuid.uuid4())
                
                yield RawRecord(
                    source_system=self.source_name,
                    original_id=original_id,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    location=location,
                    skills=skills,
                    links=links,
                    raw_data=record
                )
        except Exception as e:
            logger.error(f"Failed to parse GitHub JSON {filepath}: {e}")
