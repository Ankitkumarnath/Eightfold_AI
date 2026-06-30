from typing import List, Dict, Any, Tuple
from rapidfuzz import fuzz
from domain.models import RawRecord, CandidateProfile, FieldProvenance, Experience, Education, Skill, Links
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
        def get_confidence_weight(source: str) -> float:
            # Look up base confidence; default to 0.1 for unknown sources
            return settings.CONFIDENCE_BASE_WEIGHTS.get(source.lower(), 0.1)
        # Sort descending by confidence so highest confidence is first
        return sorted(records, key=lambda r: get_confidence_weight(r.source_system), reverse=True)

    def _merge_scalar_field(self, field_name: str, sorted_records: List[RawRecord], method="priority") -> Tuple[Any, FieldProvenance]:
        for record in sorted_records:
            val = getattr(record, field_name, None)
            if val is not None:
                provenance = FieldProvenance(
                    field=field_name,
                    source=record.source_system,
                    method=method
                )
                return val, provenance
        return None, None

    def _merge_list_field(self, field_name: str, sorted_records: List[RawRecord], method="deduplication") -> Tuple[List[Any], List[FieldProvenance]]:
        merged = []
        provs = []
        seen = set()
        for record in sorted_records:
            val = getattr(record, field_name, None)
            if val:
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
                        provs.append(FieldProvenance(field=field_name, source=record.source_system, method=method))
        return merged, provs

    def _merge_skills(self, sorted_records: List[RawRecord]) -> Tuple[List[Skill], List[FieldProvenance]]:
        skill_map: Dict[str, Skill] = {}
        provs = []
        for record in sorted_records:
            for skill_name in record.skills:
                if not skill_name: continue
                s_key = skill_name.lower().strip()
                if s_key not in skill_map:
                    # Initialize with the properly cased name from the first source we see
                    skill_map[s_key] = Skill(name=skill_name.strip().title(), confidence=1.0, sources=[record.source_system])
                    provs.append(FieldProvenance(field="skills", source=record.source_system, method="deduplication"))
                else:
                    if record.source_system not in skill_map[s_key].sources:
                        skill_map[s_key].sources.append(record.source_system)
                        skill_map[s_key].confidence = min(1.0, skill_map[s_key].confidence + 0.1)
        return list(skill_map.values()), provs

    def _merge_dict_field(self, field_name: str, sorted_records: List[RawRecord], method="priority") -> Tuple[Dict[str, Any], List[FieldProvenance]]:
        merged = {}
        provs = []
        # Lower priority to higher priority so higher overwrites
        for record in reversed(sorted_records):
            val = getattr(record, field_name, None)
            if val and isinstance(val, dict):
                for k, v in val.items():
                    if v:
                        merged[k] = v
                        provs = [p for p in provs if not (p.field == f"{field_name}.{k}")]
                        provs.append(FieldProvenance(field=f"{field_name}.{k}", source=record.source_system, method=method))
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
                    provs.append(FieldProvenance(field="experience", source=record.source_system, method="deduplication"))
        return merged_exp, provs

    def _is_same_education(self, edu1: Education, edu2: Education) -> bool:
        school_match = fuzz.token_sort_ratio(edu1.institution.lower(), edu2.institution.lower()) > 85
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
                    provs.append(FieldProvenance(field="education", source=record.source_system, method="deduplication"))
        return merged_edu, provs
        
    def _calculate_years_experience(self, experiences: List[Experience]) -> float:
        # Simplistic calculation based on start and end years (assuming YYYY-MM)
        from datetime import datetime
        now = datetime.now()
        total_months = 0
        for exp in experiences:
            if exp.start:
                try:
                    s_y, s_m = int(exp.start.split("-")[0]), int(exp.start.split("-")[1]) if "-" in exp.start else 1
                    
                    if exp.end:
                        e_y, e_m = int(exp.end.split("-")[0]), int(exp.end.split("-")[1]) if "-" in exp.end else 1
                    else:
                        e_y, e_m = now.year, now.month
                        
                    months = (e_y - s_y) * 12 + (e_m - s_m)
                    if months > 0:
                        total_months += months
                except:
                    pass
        return round(total_months / 12.0, 1) if total_months > 0 else None

    def merge(self, group: List[RawRecord]) -> CandidateProfile:
        if not group:
            raise ValueError("Cannot merge an empty group of records.")
            
        sorted_records = self._sort_records_by_priority(group)
        sources = list(set(r.source_system for r in group))
        
        candidate = CandidateProfile(source_system=sources)
        all_provs = []
        
        # 1. Full Name
        name_val = None
        for record in sorted_records:
            if record.first_name or record.last_name:
                name_val = f"{record.first_name or ''} {record.last_name or ''}".strip()
                all_provs.append(FieldProvenance(field="full_name", source=record.source_system, method="priority"))
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
        skills, provs = self._merge_skills(sorted_records)
        candidate.skills = skills
        all_provs.extend(provs)
        
        # 6. Experience & Education
        exp, provs = self._merge_experience(sorted_records)
        candidate.experience = exp
        # years_experience: prefer explicitly extracted value, fall back to computed
        yoe = None
        for record in sorted_records:
            if record.years_experience and record.years_experience > 0:
                yoe = record.years_experience
                all_provs.append(FieldProvenance(field="years_experience", source=record.source_system, method="extracted"))
                break
        if yoe is None and exp:
            yoe = self._calculate_years_experience(exp)
            if yoe:
                all_provs.append(FieldProvenance(field="years_experience", source="computed", method="derived"))
        candidate.years_experience = yoe
        all_provs.extend(provs)
        
        edu, provs = self._merge_education(sorted_records)
        candidate.education = edu
        all_provs.extend(provs)
        
        # 7. Location
        location_val, loc_prov = self._merge_scalar_field("location", sorted_records)
        if location_val:
            candidate.location = location_val
            if loc_prov:
                all_provs.append(loc_prov)
        raw_links, provs = self._merge_dict_field("links", sorted_records)
        links_obj = Links()
        for k, v in raw_links.items():
            k_lower = k.lower()
            if "linkedin" in k_lower:
                links_obj.linkedin = v
            elif "github" in k_lower:
                links_obj.github = v
            elif "portfolio" in k_lower:
                links_obj.portfolio = v
            else:
                links_obj.other.append(v)
        candidate.links = links_obj
        all_provs.extend(provs)
        
        # Combine Provenance
        candidate.provenance = all_provs
        
        # Confidence Score
        candidate.overall_confidence = self.confidence_calc.calculate(
            primary_source=sorted_records[0].source_system,
            source_count=len(sources),
            conflict_count=0
        )
        
        return candidate
