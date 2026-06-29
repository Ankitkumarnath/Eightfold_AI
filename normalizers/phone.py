import phonenumbers
from typing import Optional
from core.logger import logger

def normalize_phone(phone_str: Optional[str], default_region: str = "IN") -> Optional[str]:
    """
    Normalizes a phone number to E.164 format.
    Gracefully handles parsing errors by returning None and logging a warning.
    
    Args:
        phone_str: The raw phone number string.
        default_region: Default country code if not provided (e.g., "IN").
        
    Returns:
        The normalized E.164 phone string, or None if invalid.
    """
    if not phone_str or not phone_str.strip():
        return None
        
    try:
        parsed_num = phonenumbers.parse(phone_str, default_region)
        if phonenumbers.is_valid_number(parsed_num):
            return phonenumbers.format_number(
                parsed_num, phonenumbers.PhoneNumberFormat.E164
            )
        else:
            logger.debug(f"Parsed phone number is invalid: {phone_str}")
            return None
    except phonenumbers.NumberParseException as e:
        logger.debug(f"Failed to parse phone number: '{phone_str}'. Error: {e}")
        return None
