"""
响应数据模式
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class SchoolInfo(BaseModel):
    """学校信息"""
    school_id: int
    school_name: str
    district: str

class ScoreHistory(BaseModel):
    """分数线历史记录"""
    year: int = Field(..., description="年份")
    score: float = Field(..., description="录取分数线")
    last_volunteer_rank: Optional[int] = Field(None, description="末位志愿号")

class HistoricalData(BaseModel):
    """历史数据"""
    enrollment_2025: Optional[int] = Field(None, description="2025年招生人数")
    scores: List[ScoreHistory] = Field(default_factory=list, description="历年录取分数线")

class VolunteerItem(BaseModel):
    """志愿项"""
    volunteer_number: int = Field(..., description="志愿号")
    school_info: SchoolInfo
    risk_level: str = Field(..., description="风险等级：冲刺/稳妥/保底")
    admission_probability: float = Field(..., description="录取概率（0-1）")
    estimated_score_gap: float = Field(..., description="预估分数差")
    historical_data: Optional[HistoricalData] = Field(None, description="历史数据（招生人数和分数线）")

class VolunteerPlan(BaseModel):
    """志愿方案"""
    plan_name: str = Field(..., description="方案名称")
    overall_rating: str = Field(..., description="总体评估")
    volunteers: List[VolunteerItem] = Field(..., description="志愿列表")

class VolunteerResponse(BaseModel):
    """志愿填报响应"""
    success: bool = True
    message: str = "生成成功"
    plans: List[VolunteerPlan] = Field(..., description="志愿方案列表")