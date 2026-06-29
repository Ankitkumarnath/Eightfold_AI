from typing import Optional
from dateutil import parser
from core.logger import logger

def normalize_date(date_str: Optional[str]) -> Optional[str]:
    """
    Parses a raw date string into an ISO 8601 formatted date string (YYYY-MM-DD).
    Returns None if parsing fails.
    """
    if not date_str or not str(date_str).strip():
        return None
        
    try:
        parsed = parser.parse(str(date_str), fuzzy=True)
        return parsed.date().isoformat()
    except (ValueError, TypeError) as e:
        logger.debug(f"Failed to parse date: '{date_str}'. Error: {e}")
        return None
