import json
import os
import re
from typing import Dict, Any, List, Optional
from domain.models import CandidateProfile
from core.logger import logger

class ProjectionError(Exception):
    pass

class ProjectionEngine:
    """
    Dynamically projects the CandidateProfile into a final dictionary representation
    based on the configuration in config/schema.json.
    Supports complex mapping, extraction, and type handling.
    """
    
    def __init__(self, config_path: str = "config/schema.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.fields = self.config.get("fields", [])
        self.include_confidence = self.config.get("include_confidence", True)
        self.on_missing = self.config.get("on_missing", "null") # "null", "omit", "error"
        
        # Load normalizers map
        from normalizers.phone import normalize_phone
        from normalizers.text import normalize_skill
        self.normalizers = {
            "E164": normalize_phone,
            "canonical": normalize_skill
        }
        
    def _load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            logger.warning(f"Schema config not found at {self.config_path}, using empty config.")
            return {}
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load schema config: {e}")
            return {}

    def _extract_value(self, data: Any, path: str) -> Any:
        """
        Simple extractor for paths like 'emails[0]', 'skills[].name', 'location.city'
        """
        if not path:
            return data
            
        parts = path.replace("[]", "[*]").split(".")
        current = data
        
        for part in parts:
            if current is None:
                return None
                
            # Check for array indexing like key[0] or key[*]
            match = re.match(r"([a-zA-Z0-9_]+)\[(.*?)\]", part)
            if match:
                key, index = match.groups()
                if isinstance(current, dict):
                    current = current.get(key)
                else:
                    return None
                    
                if not isinstance(current, list):
                    return None
                    
                if index == "*":
                    # For skills[].name, we will return a special indicator or 
                    # we must handle the rest of the path on each element.
                    # Simplified: if it's [*], we apply the remaining path to all elements.
                    remaining_path = ".".join(parts[parts.index(part)+1:])
                    if not remaining_path:
                        return current
                    return [self._extract_value(item, remaining_path) for item in current]
                else:
                    try:
                        idx = int(index)
                        if idx < len(current):
                            current = current[idx]
                        else:
                            return None
                    except ValueError:
                        return None
            else:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None
                    
        return current

    def _apply_normalization(self, val: Any, norm_key: str) -> Any:
        if norm_key not in self.normalizers:
            logger.warning(f"Unknown normalizer: {norm_key}")
            return val
            
        func = self.normalizers[norm_key]
        if isinstance(val, list):
            return [func(v) for v in val if v]
        return func(val)

    def project(self, candidate: CandidateProfile, include_provenance: bool = True) -> Dict[str, Any]:
        data = candidate.model_dump(exclude_none=True)
        
        if not self.fields:
            # Fallback if config is old or missing: just return everything
            if not include_provenance and "provenance" in data:
                del data["provenance"]
            if not self.include_confidence and "overall_confidence" in data:
                del data["overall_confidence"]
            return data
            
        projected = {}
        
        # Always include candidate_id
        projected["candidate_id"] = data.get("candidate_id")
        
        for field_def in self.fields:
            target_path = field_def.get("path")
            source_path = field_def.get("from", target_path)
            is_required = field_def.get("required", False)
            norm_key = field_def.get("normalize")
            field_type = field_def.get("type", "string")
            
            # For simple flat keys with no array/dot notation, do a direct dict lookup
            if "[" not in source_path and "." not in source_path:
                val = data.get(source_path)
            else:
                val = self._extract_value(data, source_path)
            
            # Normalization
            if val is not None and norm_key:
                val = self._apply_normalization(val, norm_key)
                
            # Missing check
            is_missing = val is None or (isinstance(val, list) and len(val) == 0)
            
            if is_missing:
                if is_required and self.on_missing == "error":
                    raise ProjectionError(f"Required field missing: {target_path}")
                elif self.on_missing == "omit":
                    continue
                else:
                    projected[target_path] = None
            else:
                projected[target_path] = val
                
        if self.include_confidence:
            projected["overall_confidence"] = data.get("overall_confidence")
            
        if include_provenance:
            projected["provenance"] = data.get("provenance", [])
            
        return projected
