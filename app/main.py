"""
广州中考志愿填报助手 - FastAPI应用
"""
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import os

# 导入配置
from .config import APP_TITLE, APP_VERSION, APP_DESCRIPTION, DISTRICTS, HOUSEHOLD_TYPES, DATABASE_URL

# 导入数据库
from .database import get_db, engine, Base

# 导入模型
from .models import Batch3Public, Batch4Public, School

# 导入Schema
from .schemas.request import VolunteerRequest
from .schemas.response import VolunteerResponse

# 导入服务
from .services.advisor_service import AdvisorService

# 创建FastAPI应用
app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description=APP_DESCRIPTION
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
static_dir = os.path.join(frontend_dir, "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """返回前端页面"""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse(content="<h1>前端页面未找到</h1>")

@app.get("/historical-data", response_class=HTMLResponse)
async def historical_data_page():
    """返回历年数据查询页面"""
    historical_path = os.path.join(frontend_dir, "historical_data.html")
    if os.path.exists(historical_path):
        with open(historical_path, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse(content="<h1>历年数据页面未找到</h1>")

@app.post("/api/v1/volunteer/generate", response_model=VolunteerResponse)
async def generate_volunteer_plans(
    request: VolunteerRequest,
    db: Session = Depends(get_db)
):
    """
    生成志愿方案
    
    - **district**: 学籍区（行政区）
    - **household_type**: 户籍类型（户籍生/非户籍生）
    - **estimated_score**: 预估分数（0-800）
    - **consider_external_district**: 是否考虑外区学校（老三区视为一个区）
    """
    try:
        service = AdvisorService(db)
        result = service.generate_volunteer_plans(
            district=request.district,
            household_type=request.household_type,
            estimated_score=request.estimated_score,
            consider_external_district=request.consider_external_district
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成方案失败: {str(e)}")

@app.get("/api/v1/config/districts")
async def get_districts():
    """获取学籍区列表（只包含行政区）"""
    return {"districts": DISTRICTS}

@app.get("/api/v1/config/historical-districts")
async def get_historical_districts(db: Session = Depends(get_db)):
    """
    获取历史数据查询可用的区域列表（包含省市属）
    
    从数据库中动态获取所有存在的区域值，包括：
    - 11个行政区
    - 省市属
    """
    # 从School表中查询所有不同的区域值
    districts = db.query(School.district).distinct().all()
    district_list = sorted([d[0] for d in districts if d[0]])
    
    return {
        "districts": district_list,
        "total": len(district_list)
    }

@app.get("/api/v1/config/household_types")
async def get_household_types():
    """获取户籍类型列表"""
    return {"household_types": HOUSEHOLD_TYPES}

@app.get("/api/v1/historical/batch3")
async def get_batch3_historical_data(
    school_id: Optional[int] = Query(None, description="学校ID"),
    district: Optional[str] = Query(None, description="区域"),
    year: Optional[int] = Query(None, description="年份"),
    student_type: Optional[str] = Query("户籍生", description="学生类型"),
    db: Session = Depends(get_db)
):
    """
    获取第三批次历年录取数据（包含分数线和招生计划）
    
    可以按学校、区域、年份筛选
    """
    query = db.query(Batch3Public).filter(
        Batch3Public.student_type == student_type
    )
    
    if school_id:
        query = query.filter(Batch3Public.school_id == school_id)
    
    if year:
        query = query.filter(Batch3Public.year == year)
    
    results = query.all()
    
    # 如果指定了区域，需要关联学校表过滤
    if district:
        filtered = []
        for record in results:
            school = db.query(School).filter(
                School.school_id == record.school_id
            ).first()
            if school and school.district == district:
                filtered.append(record)
        results = filtered
    
    # 构建响应数据
    data = []
    for record in results:
        school = db.query(School).filter(
            School.school_id == record.school_id
        ).first()
        
        if school:
            item = {
                "year": record.year,
                "school_id": record.school_id,
                "school_name": school.school_name,
                "district": school.district,
                "min_score": record.min_score,
                "last_volunteer_rank": record.last_volunteer_rank,
                "student_type": record.student_type,
                "enrollment_plan": None  # 招生计划数据暂不可用
            }
            
            data.append(item)
    
    # 按年份和学校排序
    data.sort(key=lambda x: (x["school_name"], x["year"]))
    
    return {"success": True, "data": data, "count": len(data)}

@app.get("/api/v1/historical/batch4")
async def get_batch4_historical_data(
    school_id: Optional[int] = Query(None, description="学校ID"),
    district: Optional[str] = Query(None, description="区域"),
    year: Optional[int] = Query(None, description="年份"),
    student_type: Optional[str] = Query("户籍生", description="学生类型"),
    db: Session = Depends(get_db)
):
    """
    获取第四批次历年录取数据
    
    可以按学校、区域、年份筛选
    """
    query = db.query(Batch4Public).filter(
        Batch4Public.student_type == student_type
    )
    
    if school_id:
        query = query.filter(Batch4Public.school_id == school_id)
    
    if year:
        query = query.filter(Batch4Public.year == year)
    
    results = query.all()
    
    # 如果指定了区域，需要关联学校表过滤
    if district:
        filtered = []
        for record in results:
            school = db.query(School).filter(
                School.school_id == record.school_id
            ).first()
            if school and school.district == district:
                filtered.append(record)
        results = filtered
    
    # 构建响应数据
    data = []
    for record in results:
        school = db.query(School).filter(
            School.school_id == record.school_id
        ).first()
        
        if school:
            data.append({
                "year": record.year,
                "school_id": record.school_id,
                "school_name": school.school_name,
                "district": school.district,
                "min_score": record.min_score,
                "last_volunteer_rank": record.last_volunteer_rank,
                "student_type": record.student_type
            })
    
    # 按年份和学校排序
    data.sort(key=lambda x: (x["school_name"], x["year"]))
    
    return {"success": True, "data": data, "count": len(data)}

@app.get("/api/v1/historical/schools")
async def get_schools_with_data(
    batch: str = Query("batch3", description="批次：batch3或batch4"),
    district: Optional[str] = Query(None, description="区域"),
    db: Session = Depends(get_db)
):
    """
    获取有历年数据的学校列表
    
    优化：使用JOIN替代子查询，提升查询性能
    """
    # 根据批次选择数据表
    Model = Batch3Public if batch == "batch3" else Batch4Public
    
    # 使用JOIN直接关联查询，避免子查询的性能问题
    query = db.query(School).join(
        Model, School.school_id == Model.school_id
    ).distinct()
    
    # 如果指定了区域，添加过滤条件
    if district:
        query = query.filter(School.district == district)
    
    # 执行查询
    schools = query.all()
    
    # 构建响应数据
    return {
        "success": True,
        "schools": [
            {
                "school_id": s.school_id,
                "school_name": s.school_name,
                "district": s.district
            }
            for s in schools
        ]
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "version": APP_VERSION}
