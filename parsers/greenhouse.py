import json
import uuid
from typing import Iterator, Dict, Any, List
from parsers.base import BaseParser
from domain.models import RawRecord, Location, Experience, Education
from normalizers.email import normalize_email
from normalizers.phone import normalize_phone
from normalizers.location import normalize_location
from normalizers.text import normalize_skill, normalize_text
from normalizers.date import normalize_date
from core.logger import logger

class GreenhouseParser(BaseParser):
    def __init__(self):
        super().__init__(source_name="greenhouse")
        
    def _parse_skills(self, skills_raw: Any) -> List[str]:
        if not skills_raw:
            return []
        if isinstance(skills_raw, list):
            return [normalize_skill(s) for s in skills_raw if normalize_skill(s)]
        if isinstance(skills_raw, str):
            return [normalize_skill(s) for s in skills_raw.split(",") if normalize_skill(s)]
        return []

    def _parse_experience(self, exp_list: Any) -> List[Experience]:
        if not isinstance(exp_list, list):
            return []
            
        parsed_exps = []
        for exp in exp_list:
            if not isinstance(exp, dict):
                continue
            company = exp.get("company") or exp.get("employer")
            title = exp.get("title") or exp.get("role")
            
            if company and title:
                parsed_exps.append(Experience(
                    company=normalize_text(company),
                    title=normalize_text(title),
                    start=normalize_date(exp.get("start_date") or exp.get("startDate")),
                    end=normalize_date(exp.get("end_date") or exp.get("endDate"))
                ))
        return parsed_exps

    def _parse_education(self, edu_list: Any) -> List[Education]:
        if not isinstance(edu_list, list):
            return []
            
        parsed_edus = []
        for edu in edu_list:
            if not isinstance(edu, dict):
                continue
            school = edu.get("school") or edu.get("institution")
            if school:
                end_dt = str(normalize_date(edu.get("end_date") or edu.get("endDate")))
                parsed_edus.append(Education(
                    institution=normalize_text(school),
                    degree=normalize_text(edu.get("degree")),
                    field=normalize_text(edu.get("field_of_study") or edu.get("major")),
                    end_year=int(end_dt.split("-")[0]) if "-" in end_dt else None
                ))
        return parsed_edus

    def parse(self, file_path: str) -> Iterator[RawRecord]:
        try:
            with open(file_path, mode='r', encoding='utf-8') as f:
                data = json.load(f)
                
                if not isinstance(data, list):
                    # Sometimes the array is nested inside a 'candidates' key
                    if isinstance(data, dict) and "candidates" in data:
                        data = data["candidates"]
                    else:
                        logger.error(f"Expected a list of candidates in {file_path}")
                        return
                        
                for idx, record in enumerate(data):
                    try:
                        if not isinstance(record, dict):
                            continue
                            
                        # Extract first and last name (sometimes provided as a single 'name' field)
                        first_name = record.get("first_name")
                        last_name = record.get("last_name")
                        if not first_name and not last_name and record.get("name"):
                            parts = str(record.get("name")).split(" ", 1)
                            first_name = parts[0]
                            last_name = parts[1] if len(parts) > 1 else None
                            
                        first_name = normalize_text(first_name)
                        last_name = normalize_text(last_name)
                            
                        original_id = str(record.get("id") or uuid.uuid4())
                            
                        yield RawRecord(
                            source_system=self.source_name,
                            original_id=original_id,
                            first_name=normalize_text(first_name),
                            last_name=normalize_text(last_name),
                            email=normalize_email(record.get("email")),
                            phone=normalize_phone(record.get("phone")),
                            location=normalize_location(record.get("location")),
                            skills=self._parse_skills(record.get("skills")),
                            experience=self._parse_experience(record.get("experience")),
                            education=self._parse_education(record.get("education")),
                            raw_data=record
                        )
                    except Exception as e:
                        logger.warning(f"Error parsing record index {idx} in {file_path}: {e}")
                        continue
                        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format in {file_path}: {e}")
            raise
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            raise
