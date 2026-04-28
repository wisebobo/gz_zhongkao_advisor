"""
Response Data Schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class SchoolInfo(BaseModel):
    """School Information"""
    school_id: int
    school_name: str
    district: str

class ScoreHistory(BaseModel):
    """Score History Record"""
    year: int = Field(..., description="Year")
    score: float = Field(..., description="Admission Score")
    last_volunteer_rank: Optional[int] = Field(None, description="Last Volunteer Rank")

class HistoricalData(BaseModel):
    """Historical Data"""
    enrollment_2025: Optional[int] = Field(None, description="2025 Enrollment Count")
    scores: List[ScoreHistory] = Field(default_factory=list, description="Historical Admission Scores")

class VolunteerItem(BaseModel):
    """Volunteer Item (Single School)"""
    volunteer_number: int = Field(..., description="Volunteer Position Number")
    school_info: SchoolInfo
    risk_level: str = Field(..., description="Risk Level: 冲刺/稳妥/保底")
    admission_probability: float = Field(..., description="Admission Probability (0-1)")
    estimated_score_gap: float = Field(..., description="Estimated Score Gap")
    historical_data: Optional[HistoricalData] = Field(None, description="Historical Data")

class VolunteerPosition(BaseModel):
    """Volunteer Position with Multiple Candidate Schools"""
    position_number: int = Field(..., description="Position Number (1-6)")
    recommended_school: VolunteerItem = Field(..., description="Primary Recommended School")
    alternative_schools: List[VolunteerItem] = Field(default_factory=list, description="Alternative Candidate Schools")
    position_strategy: str = Field(..., description="Position Strategy: 冲刺/稳妥/保底")

class VolunteerPlan(BaseModel):
    """Volunteer Plan"""
    plan_name: str = Field(..., description="Plan Name")
    overall_rating: str = Field(..., description="Overall Rating")
    volunteers: List[VolunteerItem] = Field(..., description="Selected Volunteers (Final Choice)")
    all_candidates: List[VolunteerPosition] = Field(default_factory=list, description="All Candidates for Each Position")

class VolunteerResponse(BaseModel):
    """Volunteer Recommendation Response"""
    success: bool = True
    message: str = "Generation Successful"
    plans: List[VolunteerPlan] = Field(..., description="Volunteer Plans List")
