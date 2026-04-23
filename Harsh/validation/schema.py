from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, Dict

class Location(BaseModel):
    """Strict validation for GPS coordinates"""
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)

class SignDetection(BaseModel):
    detection_id: str
    # Using default_factory ensures the time is captured at the moment of detection
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    sign_type: str  # e.g., "Stop", "Speed Limit 80"
    
    # Ensuring Contrast Ratio stays within a realistic range
    contrast_ratio: float = Field(..., ge=0, le=5.0) 
    
    status: str  # Must be "Pass", "Fail", or "Warning"
    
    # Use the nested Location model for strictness
    location: Location 
    
    image_url: Optional[str] = None

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        allowed = ["Pass", "Fail", "Warning"]
        if v not in allowed:
            raise ValueError(f"Status must be one of {allowed}")
        return v