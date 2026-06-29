import json
import os
from typing import Dict, Any, List
from domain.models import CandidateProfile
from core.logger import logger

class ProjectionEngine:
    """
    Dynamically projects the CandidateProfile into a final dictionary representation
    based on the configuration in config/schema.json.
    This allows changing the output structure without changing code.
    """
    
    def __init__(self, config_path: str = "config/schema.json"):
        self.config_path = config_path
        self.allowed_fields = self._load_config()
        
    def _load_config(self) -> List[str]:
        if not os.path.exists(self.config_path):
            logger.warning(f"Schema config not found at {self.config_path}, defaulting to full profile.")
            return []
            
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
                active_profile = config.get("active_profile", "full")
                fields = config.get("profiles", {}).get(active_profile, [])
                return fields
        except Exception as e:
            logger.error(f"Failed to load schema config: {e}")
            return []

    def project(self, candidate: CandidateProfile, include_provenance: bool = True) -> Dict[str, Any]:
        data = candidate.model_dump(exclude_none=True)
        
        # Strip provenance if requested
        if not include_provenance and "provenance" in data:
            del data["provenance"]
            
        # If no fields specified, return everything
        if not self.allowed_fields:
            return data
            
        # Dynamically filter based on config
        projected = {}
        for field in self.allowed_fields:
            if field in data:
                projected[field] = data[field]
                
        return projected
