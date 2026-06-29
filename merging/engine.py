from typing import List, Dict, Any, Tuple
from rapidfuzz import fuzz
from domain.models import RawRecord, CandidateProfile, FieldProvenance, Experience, Education
from core.config import settings
from confidence.calculator import ConfidenceCalculator

class MergeEngine:
    """
    Consolidates data from multiple sources into a single canonical candidate profile.
    Applies priority-based conflict resolution and tracks data provenance.
    """
    
    def __init__(self):
        self.priority_list = settings.SOURCE_PRIORITY
        self.confidence_calc = ConfidenceCalculator()
        
    def _sort_records_by_priority(self, records: List[RawRecord]) -> List[RawRecord]:
        def get_priority_index(source: str) -> int:
            try:
                return self.priority_list.index(source.lower())
            except ValueError:
                return len(self.priority_list)
        return sorted(records, key=lambda r: get_priority_index(r.source_system))

    def _merge_scalar_field(self, field_name: str, sorted_records: List[RawRecord]) -> Tuple[Any, FieldProvenance]:
        for record in sorted_records:
            val = getattr(record, field_name, None)
            if val is not None:
                provenance = FieldProvenance(
                    field=field_name,
                    source=record.source_system
                )
                return val, provenance
        return None, None

    def _merge_list_field(self, field_name: str, sorted_records: List[RawRecord]) -> Tuple[List[Any], List[FieldProvenance]]:
        merged = []
        provs = []
        seen = set()
        for record in sorted_records:
            val = getattr(record, field_name, None)
            if val:
                # Could be string or list
                if isinstance(val, list):
                    items = val
                else:
                    items = [val]
                
                for item in items:
                    if not item: continue
                    item_key = str(item).lower().strip()
                    if item_key not in seen:
                        seen.add(item_key)
                        merged.append(item)
                        provs.append(FieldProvenance(field=field_name, source=record.source_system))
        return merged, provs

    def _merge_dict_field(self, field_name: str, sorted_records: List[RawRecord]) -> Tuple[Dict[str, Any], List[FieldProvenance]]:
        merged = {}
        provs = []
        # Lower priority to higher priority so higher overwrites
        for record in reversed(sorted_records):
            val = getattr(record, field_name, None)
            if val and isinstance(val, dict):
                for k, v in val.items():
                    if v:
                        merged[k] = v
                        # Remove existing prov for this dict key to avoid dupes in provenance output
                        provs = [p for p in provs if not (p.field == f"{field_name}.{k}")]
                        provs.append(FieldProvenance(field=f"{field_name}.{k}", source=record.source_system))
        return merged, provs

    def _is_same_experience(self, exp1: Experience, exp2: Experience) -> bool:
        company_match = fuzz.token_sort_ratio(exp1.company.lower(), exp2.company.lower()) >= 60
        title_match = fuzz.token_sort_ratio(exp1.title.lower(), exp2.title.lower()) >= 60
        return company_match and title_match

    def _merge_experience(self, sorted_records: List[RawRecord]) -> Tuple[List[Experience], List[FieldProvenance]]:
        merged_exp = []
        provs = []
        for record in sorted_records:
            for exp in record.experience:
                if not any(self._is_same_experience(exp, existing) for existing in merged_exp):
                    merged_exp.append(exp)
                    provs.append(FieldProvenance(field="experience", source=record.source_system))
        return merged_exp, provs

    def _is_same_education(self, edu1: Education, edu2: Education) -> bool:
        school_match = fuzz.token_sort_ratio(edu1.school.lower(), edu2.school.lower()) > 85
        deg1 = edu1.degree or ""
        deg2 = edu2.degree or ""
        if deg1 and deg2:
            return school_match and fuzz.token_sort_ratio(deg1.lower(), deg2.lower()) > 80
        return school_match

    def _merge_education(self, sorted_records: List[RawRecord]) -> Tuple[List[Education], List[FieldProvenance]]:
        merged_edu = []
        provs = []
        for record in sorted_records:
            for edu in record.education:
                if not any(self._is_same_education(edu, existing) for existing in merged_edu):
                    merged_edu.append(edu)
                    provs.append(FieldProvenance(field="education", source=record.source_system))
        return merged_edu, provs

    def merge(self, group: List[RawRecord]) -> CandidateProfile:
        if not group:
            raise ValueError("Cannot merge an empty group of records.")
            
        sorted_records = self._sort_records_by_priority(group)
        sources = list(set(r.source_system for r in group))
        
        candidate = CandidateProfile(source_system=sources)
        all_provs = []
        
        # 1. Full Name (from first_name/last_name or full_name)
        # Try to get full_name from raw_data if we stored it there, or just build it.
        name_val = None
        for record in sorted_records:
            if record.first_name or record.last_name:
                name_val = f"{record.first_name or ''} {record.last_name or ''}".strip()
                all_provs.append(FieldProvenance(field="full_name", source=record.source_system))
                break
        candidate.full_name = name_val
        
        # 2. Headline
        headline, prov = self._merge_scalar_field("headline", sorted_records)
        if headline:
            candidate.headline = headline
            all_provs.append(prov)
            
        # 3. Emails
        emails, provs = self._merge_list_field("email", sorted_records)
        candidate.emails = emails
        all_provs.extend(provs)
        
        # 4. Phones
        phones, provs = self._merge_list_field("phone", sorted_records)
        candidate.phones = phones
        all_provs.extend(provs)
        
        # 5. Skills
        skills, provs = self._merge_list_field("skills", sorted_records)
        candidate.skills = skills
        all_provs.extend(provs)
        
        # 6. Experience & Education
        exp, provs = self._merge_experience(sorted_records)
        candidate.experience = exp
        all_provs.extend(provs)
        
        edu, provs = self._merge_education(sorted_records)
        candidate.education = edu
        all_provs.extend(provs)
        
        # 7. Links
        links, provs = self._merge_dict_field("links", sorted_records)
        candidate.links = links
        all_provs.extend(provs)
        
        # Combine Provenance
        candidate.provenance = all_provs
        
        # Confidence Score (simplified based on number of sources matching)
        candidate.overall_confidence = self.confidence_calc.calculate(
            primary_source=sorted_records[0].source_system,
            source_count=len(sources),
            conflict_count=0
        )
        
        return candidate
