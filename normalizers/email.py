import re
from typing import Optional
from core.logger import logger

# Basic regex for email validation fallback
EMAIL_REGEX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")

def normalize_email(email_str: Optional[str]) -> Optional[str]:
    """
    Normalizes an email address to lowercase and strips whitespace.
    Validates the email format.
    
    Args:
        email_str: The raw email string.
        
    Returns:
        Normalized email string or None if invalid.
    """
    if not email_str or not str(email_str).strip():
        return None
        
    cleaned = str(email_str).strip().lower()
    
    # Basic validation
    if not EMAIL_REGEX.match(cleaned):
        logger.debug(f"Invalid email format detected: '{email_str}'")
        return None
        
    return cleaned
