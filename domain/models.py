import uuid
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, EmailStr

class Location(BaseModel):
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None

class Experience(BaseModel):
    company: str
    title: str
    start: Optional[str] = None
    end: Optional[str] = None
    summary: Optional[str] = None

class Education(BaseModel):
    institution: str
    degree: Optional[str] = None
    field: Optional[str] = None
    end_year: Optional[int] = None

class FieldProvenance(BaseModel):
    field: str
    source: str
    method: str

class Skill(BaseModel):
    name: str
    confidence: float = 1.0
    sources: List[str] = Field(default_factory=list)

class Links(BaseModel):
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    other: List[str] = Field(default_factory=list)

class CandidateProfile(BaseModel):
    """
    Canonical representation of a resolved candidate.
    """
    candidate_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    full_name: Optional[str] = None
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    location: Optional[Location] = None
    headline: Optional[str] = None
    years_experience: Optional[float] = None
    skills: List[Skill] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    links: Links = Field(default_factory=Links)
    
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
    headline: Optional[str] = None
    years_experience: Optional[float] = None
    location: Optional[Location] = None
    skills: List[str] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    links: Dict[str, str] = Field(default_factory=dict)
    raw_data: Dict[str, Any] = Field(default_factory=dict)
