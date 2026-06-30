import json
from typing import List, Dict, Any
from core.logger import logger

class GreenhouseFetcher:
    """
    Mock fetcher for Greenhouse ATS. 
    In a real-world scenario, this would use `requests` with a Harvest API key 
    to fetch live candidate data. Here, we simulate an API call and return mock data.
    """
    
    @classmethod
    def fetch_mock_data(cls) -> List[Dict[str, Any]]:
        logger.info("Simulating fetch from Greenhouse Harvest API...")
        
        # Simulated payload matching the structure expected by our greenhouse.py parser
        return [
            {
                "id": 1001,
                "first_name": "Charlie",
                "last_name": "Brown",
                "email_addresses": [
                    {"value": "charlie@email.com", "type": "personal"}
                ],
                "phone_numbers": [
                    {"value": "555-0100", "type": "mobile"}
                ],
                "location": {
                    "name": "San Francisco, CA"
                },
                "tags": ["Ruby", "Rails"],
                "educations": [
                    {
                        "school": "Stanford",
                        "degree": "BS",
                        "major": "Computer Science",
                        "end_date": "2020-05-01"
                    }
                ],
                "employments": [
                    {
                        "company_name": "Tech Corp",
                        "title": "Software Engineer",
                        "start_date": "2020-06-01"
                    }
                ]
            }
        ]
