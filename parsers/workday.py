import csv
import json
import uuid
from typing import Iterator, Dict, Any
from parsers.base import BaseParser
from domain.models import RawRecord, Location, Experience, Education
from normalizers.email import normalize_email
from normalizers.phone import normalize_phone
from normalizers.location import normalize_location
from normalizers.text import normalize_skill, normalize_text
from normalizers.date import normalize_date
from core.logger import logger

class WorkdayParser(BaseParser):
    def __init__(self):
        super().__init__(source_name="workday")

    def _parse_skills(self, skills_str: str) -> list[str]:
        if not skills_str:
            return []
        # Try to parse if it's a JSON array string
        if skills_str.strip().startswith("["):
            try:
                skills_list = json.loads(skills_str)
                if isinstance(skills_list, list):
                    return [normalize_skill(s) for s in skills_list if normalize_skill(s)]
            except json.JSONDecodeError:
                pass
        
        # Fallback to comma separated
        return [normalize_skill(s) for s in skills_str.split(",") if normalize_skill(s)]

    def _parse_experience(self, exp_str: str) -> list[Experience]:
        if not exp_str:
            return []
        try:
            # Assume experience might be a JSON string of list of dicts
            exp_list = json.loads(exp_str)
            if not isinstance(exp_list, list):
                return []
            
            parsed_exps = []
            for exp in exp_list:
                if not isinstance(exp, dict):
                    continue
                company = exp.get("Company") or exp.get("company")
                title = exp.get("Title") or exp.get("title")
                
                if company and title:
                    parsed_exps.append(Experience(
                        company=normalize_text(company),
                        title=normalize_text(title),
                        start=exp.get("start"),
                        end=exp.get("end")
                    ))
            return parsed_exps
        except json.JSONDecodeError:
            # Not JSON, maybe just a plain string? We'll log and ignore complex parsing for plain text 
            # in this mock implementation unless requested.
            logger.debug(f"Failed to parse experience JSON: {exp_str[:50]}...")
            return []

    def _parse_education(self, edu_str: str) -> list[Education]:
        if not edu_str:
            return []
        try:
            edu_list = json.loads(edu_str)
            if not isinstance(edu_list, list):
                return []
                
            parsed_edus = []
            for edu in edu_list:
                if not isinstance(edu, dict):
                    continue
                school = edu.get("School") or edu.get("school")
                if school:
                    parsed_edus.append(Education(
                        institution=normalize_text(school),
                        degree=normalize_text(edu.get("Degree") or edu.get("degree")),
                        field=normalize_text(edu.get("Field of Study") or edu.get("field_of_study")),
                        end_year=int(str(edu.get("End Date") or edu.get("end_date")).split("-")[0]) if edu.get("End Date") or edu.get("end_date") else None
                    ))
            return parsed_edus
        except json.JSONDecodeError:
            logger.debug(f"Failed to parse education JSON: {edu_str[:50]}...")
            return []

    def parse(self, file_path: str) -> Iterator[RawRecord]:
        try:
            with open(file_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=1):
                    try:
                        # Map Workday CSV columns to canonical schema
                        # Use lowercased/standardized keys for resilience
                        row_lower = {k.lower().strip(): v for k, v in row.items() if k}
                        
                        original_id = row_lower.get("applicant_id") or row_lower.get("id") or str(uuid.uuid4())
                        
                        yield RawRecord(
                            source_system=self.source_name,
                            original_id=original_id,
                            first_name=normalize_text(row_lower.get("first_name") or row_lower.get("first name")),
                            last_name=normalize_text(row_lower.get("last_name") or row_lower.get("last name")),
                            email=normalize_email(row_lower.get("email")),
                            phone=normalize_phone(row_lower.get("phone")),
                            location=normalize_location(row_lower.get("location")),
                            skills=self._parse_skills(row_lower.get("skills", "")),
                            experience=self._parse_experience(row_lower.get("experience", "")),
                            education=self._parse_education(row_lower.get("education", "")),
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
