import uuid
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, EmailStr

class Location(BaseModel):
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

class Experience(BaseModel):
    company: str
    title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class Education(BaseModel):
    school: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class FieldProvenance(BaseModel):
    field: str
    source: str

class CandidateProfile(BaseModel):
    """
    Canonical representation of a resolved candidate.
    """
    candidate_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    full_name: Optional[str] = None
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    headline: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    links: Dict[str, str] = Field(default_factory=dict)
    
    overall_confidence: float = 0.0
    provenance: List[FieldProvenance] = Field(default_factory=list)
    
    source_system: List[str] = Field(default_factory=list, exclude=True)

class RawRecord(BaseModel):
    """
    Intermediate schema for data extracted by parsers before merging.
    Allows standardizing the interface regardless of input format.
    """
    source_system: str
    original_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[Location] = None
    skills: List[str] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    links: Dict[str, str] = Field(default_factory=dict)
    raw_data: Dict[str, Any] = Field(default_factory=dict)
