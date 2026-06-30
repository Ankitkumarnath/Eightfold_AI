import json
from typing import Dict, Any

class LinkedInFetcher:
    """
    Mock fetcher for LinkedIn. Real LinkedIn scraping is notoriously difficult 
    and requires authentication/headless browsers. This returns a mock payload 
    simulating a successful GraphQL/API response for demonstration purposes.
    """
    @staticmethod
    def fetch(url: str) -> Dict[str, Any]:
        username = url.rstrip('/').split('/')[-1]
        # Generate a mock structured JSON response representing LinkedIn profile data
        return {
            "profile": {
                "urn": f"urn:li:member:{username}",
                "firstName": "Jonathan",
                "lastName": "Doe",
                "headline": "Software Engineer at TechCorp",
                "location": {
                    "basicLocation": {
                        "countryCode": "us",
                        "city": "San Francisco",
                        "state": "California"
                    }
                },
                "contactInfo": {
                    "emailAddress": "john.doe@email.com",
                    "phoneNumber": "415-555-0198"
                },
                "positions": [
                    {
                        "companyName": "TechCorp",
                        "title": "Software Engineer",
                        "startDate": {"year": 2021, "month": 6},
                        "endDate": None
                    },
                    {
                        "companyName": "PreviousInc",
                        "title": "Junior Developer",
                        "startDate": {"year": 2019, "month": 8},
                        "endDate": {"year": 2021, "month": 5}
                    }
                ],
                "skills": [
                    {"name": "Python"},
                    {"name": "System Architecture"},
                    {"name": "Machine Learning"}
                ]
            }
        }
