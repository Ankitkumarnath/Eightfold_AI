import csv
import uuid
from typing import Iterator
from parsers.base import BaseParser
from domain.models import RawRecord, Experience
from normalizers.email import normalize_email
from normalizers.phone import normalize_phone
from normalizers.text import normalize_text
from core.logger import logger

class RecruiterCsvParser(BaseParser):
    def __init__(self):
        super().__init__(source_name="recruiter_csv")

    def parse(self, file_path: str) -> Iterator[RawRecord]:
        try:
            with open(file_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=1):
                    try:
                        # Map Recruiter CSV export (name, email, phone, current_company, title)
                        row_lower = {k.lower().strip(): v for k, v in row.items() if k}
                        
                        original_id = str(uuid.uuid4())
                        name_parts = str(row_lower.get("name", "")).split()
                        first_name = normalize_text(name_parts[0]) if name_parts else None
                        last_name = normalize_text(" ".join(name_parts[1:])) if len(name_parts) > 1 else None
                        
                        company = normalize_text(row_lower.get("current_company"))
                        title = normalize_text(row_lower.get("title"))
                        
                        experience = []
                        if company or title:
                            experience.append(Experience(
                                company=company or "Unknown",
                                title=title or "Unknown"
                            ))
                            
                        yield RawRecord(
                            source_system=self.source_name,
                            original_id=original_id,
                            first_name=first_name,
                            last_name=last_name,
                            email=normalize_email(row_lower.get("email")),
                            phone=normalize_phone(row_lower.get("phone")),
                            experience=experience,
                            raw_data=row
                        )
                    except Exception as e:
                        logger.warning(f"Error parsing row {row_idx} in {file_path}: {e}")
                        continue
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            raise
