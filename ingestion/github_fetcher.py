import requests
import json
from core.logger import logger

class GitHubFetcher:
    """Fetches user data from the GitHub API and converts it to our internal github.json format."""
    
    BASE_URL = "https://api.github.com/users"

    @classmethod
    def fetch(cls, username: str) -> dict:
        logger.info(f"Fetching GitHub data for {username}...")
        
        # Fetch user profile
        user_resp = requests.get(f"{cls.BASE_URL}/{username}")
        if user_resp.status_code != 200:
            raise Exception(f"Failed to fetch user {username} from GitHub: {user_resp.status_code}")
            
        user_data = user_resp.json()
        
        # Fetch repos
        repos_resp = requests.get(f"{cls.BASE_URL}/{username}/repos")
        if repos_resp.status_code != 200:
            raise Exception(f"Failed to fetch repos for {username} from GitHub")
            
        repos_data = repos_resp.json()
        
        # We only take the top 5 repos for simplicity
        repo_names = [repo.get("language") or repo.get("name") for repo in repos_data if not repo.get("fork")][:5]
        # Filter out Nones and get unique values
        repo_names = list(set([r for r in repo_names if r]))
        
        # Construct the JSON as expected by our github.json parser
        formatted_data = {
            "Name": user_data.get("name") or user_data.get("login"),
            "Bio": user_data.get("bio") or "",
            "Email": user_data.get("email"),
            "Location": user_data.get("location"),
            "Repositories": repo_names
        }
        
        return formatted_data
