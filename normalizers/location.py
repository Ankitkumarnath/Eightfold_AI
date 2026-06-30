from typing import Optional, Union, Dict
from domain.models import Location
from normalizers.text import normalize_text
from core.logger import logger

def parse_location_string(loc_str: str) -> Location:
    """
    Parses a simple location string like 'City, State, Country'
    or 'City, State' into a Location object.
    """
    parts = [normalize_text(p) for p in loc_str.split(",")]
    parts = [p for p in parts if p] # Remove empty
    
    loc = Location()
    if len(parts) == 1:
        loc.city = parts[0]
    elif len(parts) == 2:
        loc.city = parts[0]
        loc.region = parts[1]
    elif len(parts) == 3:
        loc.city = parts[0]
        loc.region = parts[1]
        loc.country = parts[2]
        
    return loc

def normalize_location(raw_loc: Optional[Union[str, Dict[str, str]]]) -> Optional[Location]:
    """
    Normalizes location input (string or dict) into a canonical Location object.
    """
    if not raw_loc:
        return None
        
    if isinstance(raw_loc, str):
        if not raw_loc.strip():
            return None
        return parse_location_string(raw_loc)
        
    if isinstance(raw_loc, dict):
        city = normalize_text(raw_loc.get("city") or raw_loc.get("City"))
        region = normalize_text(raw_loc.get("state") or raw_loc.get("region") or raw_loc.get("State") or raw_loc.get("Region"))
        country = normalize_text(raw_loc.get("country") or raw_loc.get("Country"))
        
        if not (city or region or country):
            return None
            
        return Location(city=city, region=region, country=country)
        
    logger.debug(f"Unrecognized location format: {type(raw_loc)}")
    return None
