"""
请求数据模式
"""
from pydantic import BaseModel, Field
from typing import Optional

class VolunteerRequest(BaseModel):
    """志愿填报请求"""
    district: str = Field(..., description="学籍区", example="越秀区")
    household_type: str = Field(..., description="户籍类型", example="户籍生")
    estimated_score: float = Field(..., description="预估分数", ge=0, le=800, example=720)
    consider_external_district: bool = Field(True, description="是否考虑外区学校（老三区视为一个区）", example=True)
    
    class Config:
        json_schema_extra = {
            "example": {
                "district": "越秀区",
                "household_type": "户籍生",
                "estimated_score": 720,
                "consider_external_district": True
            }
        }
