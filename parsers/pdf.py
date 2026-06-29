import re
import uuid
import pdfplumber
from typing import Iterator, List
from parsers.base import BaseParser
from domain.models import RawRecord
from normalizers.email import normalize_email
from normalizers.phone import normalize_phone
from normalizers.text import normalize_text
from core.logger import logger

# Basic regex for email and phone extraction from unstructured text
EMAIL_REGEX = re.compile(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")
PHONE_REGEX = re.compile(r"(\+?\d[\d\s\-\(\)]{8,}\d)")

# Common tech skills for heuristic matching
COMMON_SKILLS = {"python", "java", "c++", "c#", "ruby", "golang", "javascript", "react", "angular", "vue", "aws", "gcp", "azure", "sql", "nosql", "machine learning", "data science"}

class PdfParser(BaseParser):
    def __init__(self):
        super().__init__(source_name="resume_pdf")

    def _extract_text(self, file_path: str) -> str:
        text = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
        except Exception as e:
            logger.error(f"Failed to extract text from PDF {file_path}: {e}")
            raise
        return text

    def _extract_email(self, text: str) -> str | None:
        match = EMAIL_REGEX.search(text)
        if match:
            return normalize_email(match.group(1))
        return None

    def _extract_phone(self, text: str) -> str | None:
        matches = PHONE_REGEX.findall(text)
        for match in matches:
            # simple filter for weird matches
            clean_match = re.sub(r"[^\d+]", "", match)
            if 9 <= len(clean_match) <= 15:
                return normalize_phone(match)
        return None

    def _extract_name_heuristics(self, text: str) -> tuple[str | None, str | None]:
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines:
            return None, None
            
        # Heuristic: Name is usually the first non-empty line
        first_line = lines[0]
        # Ignore lines that look like "resume" or "cv"
        if first_line.lower() in ("resume", "cv", "curriculum vitae"):
            first_line = lines[1] if len(lines) > 1 else ""
            
        parts = first_line.split()
        if len(parts) == 1:
            return normalize_text(parts[0]), None
        elif len(parts) >= 2:
            return normalize_text(parts[0]), normalize_text(" ".join(parts[1:]))
            
        return None, None

    def _extract_skills(self, text: str) -> List[str]:
        text_lower = text.lower()
        found_skills = []
        for skill in COMMON_SKILLS:
            # using word boundaries
            if re.search(r"\b" + re.escape(skill) + r"\b", text_lower):
                # normalize skill casing
                title_skill = normalize_text(skill, titlecase=True)
                found_skills.append(title_skill)
        return found_skills

    def parse(self, file_path: str) -> Iterator[RawRecord]:
        logger.info(f"Parsing PDF: {file_path}")
        text = self._extract_text(file_path)
        
        email = self._extract_email(text)
        phone = self._extract_phone(text)
        first_name, last_name = self._extract_name_heuristics(text)
        skills = self._extract_skills(text)
        
        original_id = str(uuid.uuid4())
        
        yield RawRecord(
            source_system=self.source_name,
            original_id=original_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            skills=skills,
            raw_data={"extracted_text_preview": text[:200] + "..." if len(text) > 200 else text}
        )
