import json
from typing import Generator
from parsers.base import BaseParser
from domain.models import RawRecord, Experience, Location
from normalizers.text import normalize_text
from normalizers.email import normalize_email
from normalizers.phone import normalize_phone
from normalizers.location import normalize_location

class LinkedinParser(BaseParser):
    def __init__(self):
        super().__init__(source_name="linkedin")
        
    def parse(self, source_path: str) -> Generator[RawRecord, None, None]:
        with open(source_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        profile = data.get("profile", {})
        if not profile:
            return
            
        # Extract fields safely
        first_name = normalize_text(profile.get("firstName", ""))
        last_name = normalize_text(profile.get("lastName", ""))
        
        contact_info = profile.get("contactInfo", {})
        email = normalize_email(contact_info.get("emailAddress"))
        phone = normalize_phone(contact_info.get("phoneNumber"))
        
        headline = profile.get("headline")
        
        loc_data = profile.get("location", {}).get("basicLocation", {})
        city = loc_data.get("city")
        state = loc_data.get("state")
        country = loc_data.get("countryCode")
        
        loc_str = ", ".join(filter(None, [city, state, country]))
        location = normalize_location(loc_str)
        
        # Experience
        experience_list = []
        for pos in profile.get("positions", []):
            start = pos.get("startDate", {})
            end = pos.get("endDate")
            
            start_date = f"{start.get('year')}-{str(start.get('month')).zfill(2)}" if start else None
            end_date = f"{end.get('year')}-{str(end.get('month')).zfill(2)}" if end else None
            
            experience_list.append(Experience(
                company=pos.get("companyName", ""),
                title=pos.get("title", ""),
                start_date=start_date,
                end_date=end_date
            ))
            
        # Skills
        skills = [s.get("name", "") for s in profile.get("skills", [])]
        
        yield RawRecord(
            source_system="linkedin",
            original_id=profile.get("urn", "unknown"),
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            location=location,
            headline=headline,
            experience=experience_list,
            skills=skills,
            links={"linkedin": f"https://linkedin.com/in/{profile.get('urn', '').split(':')[-1]}"} if profile.get("urn") else {}
        )
