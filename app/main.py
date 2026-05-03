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
from .models import Batch3Public, Batch3Private, Batch4Public, Batch2QuotaAllocation, Batch2Quota, School

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

@app.get("/api/v1/historical/batch3-aggregated")
async def get_batch3_historical_data_aggregated(
    district: Optional[str] = Query(None, description="区域"),
    school_name: Optional[str] = Query(None, description="学校名称"),
    db: Session = Depends(get_db)
):
    """
    获取第三批次历年录取数据（按学校聚合）
    
    返回格式：每个学校一行，包含多年的分数线数据
    """
    # 查询所有有数据的学校
    query = db.query(School).join(
        Batch3Public, School.school_id == Batch3Public.school_id
    ).distinct()
    
    if district:
        query = query.filter(School.district == district)
    
    if school_name:
        query = query.filter(School.school_name.like(f"%{school_name}%"))
    
    schools = query.all()
    
    # 为每个学校聚合多年数据
    aggregated_data = []
    for school in schools:
        school_record = {
            "school_id": school.school_id,
            "school_name": school.school_name,
            "district": school.district,
            "years": {}
        }
        
        # 查询该学校的所有年份数据
        records = db.query(Batch3Public).filter(
            Batch3Public.school_id == school.school_id
        ).all()
        
        for record in records:
            year_key = str(record.year)
            if year_key not in school_record["years"]:
                school_record["years"][year_key] = {}
            
            # 存储不同学生类型的数据
            student_type = record.student_type
            school_record["years"][year_key][student_type] = {
                "min_score": record.min_score,
                "last_volunteer_rank": record.last_volunteer_rank
            }
        
        aggregated_data.append(school_record)
    
    # 按学校名称排序
    aggregated_data.sort(key=lambda x: x["school_name"])
    
    return {"success": True, "data": aggregated_data, "count": len(aggregated_data)}

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
    if batch == "batch3":
        # 第三批次：合并公办和民办
        school_ids_1 = db.query(Batch3Public.school_id).distinct().all()
        school_ids_2 = db.query(Batch3Private.school_id).distinct().all()
        
        school_ids = set([s[0] for s in school_ids_1] + [s[0] for s in school_ids_2])
        
        query = db.query(School).filter(School.school_id.in_(school_ids))
    else:
        # 第四批次
        query = db.query(School).join(
            Batch4Public, School.school_id == Batch4Public.school_id
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

@app.get("/api/v1/historical/batch3-unified")
async def get_batch3_unified_data(
    district: Optional[str] = Query(None, description="区域"),
    school_id: Optional[int] = Query(None, description="学校ID"),
    db: Session = Depends(get_db)
):
    """
    获取第三批次历年录取数据（统一版本，合并公办和民办）
    
    返回格式：每个学校一行，包含多年的分数线数据
    """
    # 查询所有有数据的学校（包括公办和民办）
    query = db.query(School).join(
        Batch3Public, School.school_id == Batch3Public.school_id
    ).distinct()
    
    if district:
        query = query.filter(School.district == district)
    
    schools_public = query.all()
    
    # 查询民办学校
    query_private = db.query(School).join(
        Batch3Private, School.school_id == Batch3Private.school_id
    ).distinct()
    
    if district:
        query_private = query_private.filter(School.district == district)
    
    schools_private = query_private.all()
    
    # 合并学校列表并去重
    all_schools = {school.school_id: school for school in schools_public}
    for school in schools_private:
        all_schools[school.school_id] = school
    
    schools = list(all_schools.values())
    
    # 如果指定了学校ID，过滤
    if school_id:
        schools = [s for s in schools if s.school_id == school_id]
    
    # 为每个学校聚合多年数据
    aggregated_data = []
    for school in schools:
        school_record = {
            "school_id": school.school_id,
            "school_name": school.school_name,
            "district": school.district,
            "years": {}
        }
        
        # 查询该学校的公办数据
        public_records = db.query(Batch3Public).filter(
            Batch3Public.school_id == school.school_id
        ).all()
        
        for record in public_records:
            year_key = str(record.year)
            if year_key not in school_record["years"]:
                school_record["years"][year_key] = {}
            
            student_type = record.student_type
            school_record["years"][year_key][student_type] = {
                "min_score": record.min_score,
                "last_volunteer_rank": record.last_volunteer_rank,
                "type": "公办"
            }
        
        # 查询该学校的民办数据
        private_records = db.query(Batch3Private).filter(
            Batch3Private.school_id == school.school_id
        ).all()
        
        for record in private_records:
            year_key = str(record.year)
            if year_key not in school_record["years"]:
                school_record["years"][year_key] = {}
            
            # 民办学校数据：将分数复制到所有学生类型字段
            # 因为民办学校的分数线对户籍生、非户籍生、外区生都是一样的
            score_data = {
                "min_score": record.min_score,
                "last_volunteer_rank": record.last_volunteer_rank,
                "type": "民办",
                "admission_scope": record.admission_scope,
                "is_admitted": record.is_admitted,
                "sub_type": record.sub_type or "普通高中"
            }
            
            # 根据招生范围决定复制到哪些学生类型
            admission_scope = record.admission_scope or ""
            
            # 如果招生范围包含“全市”或没有明确限制，复制到所有类型
            if "全市" in admission_scope or not admission_scope:
                school_record["years"][year_key]["户籍生"] = score_data.copy()
                school_record["years"][year_key]["非户籍生"] = score_data.copy()
                school_record["years"][year_key]["外区生"] = score_data.copy()
            else:
                # 如果有明确的区域限制，只复制到对应的类型
                # 这里简化处理：默认复制到户籍生和非户籍生
                school_record["years"][year_key]["户籍生"] = score_data.copy()
                school_record["years"][year_key]["非户籍生"] = score_data.copy()
        
        aggregated_data.append(school_record)
    
    # 按学校名称排序
    aggregated_data.sort(key=lambda x: x["school_name"])
    
    return {"success": True, "data": aggregated_data, "count": len(aggregated_data)}

@app.get("/api/v1/historical/batch4-unified")
async def get_batch4_unified_data(
    district: Optional[str] = Query(None, description="区域"),
    school_id: Optional[int] = Query(None, description="学校ID"),
    db: Session = Depends(get_db)
):
    """
    获取第四批次历年录取数据（统一版本）
    
    返回格式：每个学校一行，包含多年的分数线数据
    """
    # 查询所有有数据的学校
    query = db.query(School).join(
        Batch4Public, School.school_id == Batch4Public.school_id
    ).distinct()
    
    if district:
        query = query.filter(School.district == district)
    
    if school_id:
        query = query.filter(School.school_id == school_id)
    
    schools = query.all()
    
    # 为每个学校聚合多年数据
    aggregated_data = []
    for school in schools:
        school_record = {
            "school_id": school.school_id,
            "school_name": school.school_name,
            "district": school.district,
            "years": {}
        }
        
        # 查询该学校的所有年份数据
        records = db.query(Batch4Public).filter(
            Batch4Public.school_id == school.school_id
        ).all()
        
        for record in records:
            year_key = str(record.year)
            if year_key not in school_record["years"]:
                school_record["years"][year_key] = {}
            
            # 存储不同学生类型的数据
            student_type = record.student_type
            school_record["years"][year_key][student_type] = {
                "min_score": record.min_score,
                "last_volunteer_rank": record.last_volunteer_rank
            }
        
        aggregated_data.append(school_record)
    
    # 按学校名称排序
    aggregated_data.sort(key=lambda x: x["school_name"])
    
    return {"success": True, "data": aggregated_data, "count": len(aggregated_data)}

@app.get("/api/v1/config/districts-with-data")
async def get_districts_with_data(
    batch: str = Query("batch3", description="批次：batch3或batch4"),
    db: Session = Depends(get_db)
):
    """
    获取有录取数据的区域列表（从数据库动态获取）
    """
    # 根据批次选择数据表
    if batch == "batch3":
        # 第三批次：合并公办和民办
        Model1 = Batch3Public
        Model2 = Batch3Private
        
        # 查询有数据的学校ID
        school_ids_1 = db.query(Model1.school_id).distinct().all()
        school_ids_2 = db.query(Model2.school_id).distinct().all()
        
        school_ids = set([s[0] for s in school_ids_1] + [s[0] for s in school_ids_2])
        
        # 查询这些学校对应的区域
        districts = db.query(School.district).filter(
            School.school_id.in_(school_ids)
        ).distinct().all()
    else:
        # 第四批次
        districts = db.query(School.district).join(
            Batch4Public, School.school_id == Batch4Public.school_id
        ).distinct().all()
    
    # 提取区域名称并排序
    district_list = sorted([d[0] for d in districts if d[0]])
    
    return {"success": True, "districts": district_list}

@app.get("/api/v1/config/batch2-districts")
async def get_batch2_districts(
    db: Session = Depends(get_db)
):
    """
    获取 batch2_quota_allocation 表中所有唯一的行政区列表
    """
    # 从 batch2_quota_allocation 表中提取所有唯一的行政区
    districts = db.query(
        Batch2QuotaAllocation.junior_school_district
    ).distinct().all()
    
    # 提取、过滤空值并排序
    district_list = sorted([d[0] for d in districts if d[0]])
    
    return {
        "success": True,
        "districts": district_list,
        "count": len(district_list)
    }

@app.get("/api/v1/config/junior-schools")
async def get_junior_schools(
    district: Optional[str] = Query(None, description="行政区（可选）"),
    db: Session = Depends(get_db)
):
    """
    获取初中学校列表（从 batch2_quota_allocation 表中提取）
    
    可以按行政区筛选
    """
    query = db.query(
        Batch2QuotaAllocation.junior_school_name
    ).distinct()
    
    # 如果指定了行政区，添加过滤条件
    if district:
        query = query.filter(Batch2QuotaAllocation.junior_school_district == district)
    
    schools = query.all()
    
    # 提取并排序
    school_list = sorted([s[0] for s in schools if s[0]])
    
    return {
        "success": True,
        "schools": school_list,
        "count": len(school_list)
    }

@app.get("/api/v1/historical/batch2-quota")
async def get_batch2_quota_data(
    junior_school_name: str = Query(..., description="初中学校名称"),
    db: Session = Depends(get_db)
):
    """
    获取指定初中的名额分配数据（按高中聚合，多年份对比）
    
    返回格式：每个高中一行，包含多年的名额、分数线、排名、第三批次分数
    """
    # 步骤1: 获取该初中的所有高中目标（只保留名额>0的记录）
    senior_schools = db.query(
        Batch2QuotaAllocation.senior_school_id
    ).filter(
        Batch2QuotaAllocation.junior_school_name == junior_school_name,
        Batch2QuotaAllocation.quota_count > 0  # 只保留有名额的学校
    ).distinct().all()
    
    if not senior_schools:
        return {"success": True, "data": [], "count": 0}
    
    # 步骤2: 对每个高中，按年份聚合数据
    aggregated_data = []
    for school_tuple in senior_schools:
        senior_school_id = school_tuple[0]
        
        # 获取高中学校信息
        school_info = db.query(School).filter(
            School.school_id == senior_school_id
        ).first()
        
        if not school_info:
            continue
        
        school_record = {
            "senior_school_id": senior_school_id,
            "senior_school_name": school_info.school_name,
            "district": school_info.district,
            "years": {}
        }
        
        # 获取该高中的所有年份数据
        quota_records = db.query(Batch2QuotaAllocation).filter(
            Batch2QuotaAllocation.junior_school_name == junior_school_name,
            Batch2QuotaAllocation.senior_school_id == senior_school_id
        ).all()
        
        for quota_rec in quota_records:
            year_key = str(quota_rec.year)
            if year_key not in school_record["years"]:
                school_record["years"][year_key] = {}
            
            # 名额数量
            school_record["years"][year_key]["quota_count"] = quota_rec.quota_count
            
            # 只有当名额 > 0 时，才查询录取分数线
            if quota_rec.quota_count > 0:
                # 第二批次录取数据（取户籍生的数据，如果没有则取不限）
                batch2_rec = db.query(Batch2Quota).filter(
                    Batch2Quota.senior_school_id == senior_school_id,
                    Batch2Quota.junior_school_name == junior_school_name,  # 添加初中学校过滤
                    Batch2Quota.year == quota_rec.year,
                    Batch2Quota.student_type.in_(['户籍生', '不限'])
                ).order_by(
                    Batch2Quota.student_type.desc()  # 优先取户籍生
                ).first()
                
                if batch2_rec:
                    school_record["years"][year_key]["batch2_min_score"] = batch2_rec.min_score
                    school_record["years"][year_key]["last_volunteer_rank"] = batch2_rec.last_volunteer_rank
                
                # 第三批次录取分数线（户籍生）
                batch3_rec = db.query(Batch3Public).filter(
                    Batch3Public.school_id == senior_school_id,
                    Batch3Public.year == quota_rec.year,
                    Batch3Public.student_type == '户籍生'
                ).first()
                
                if batch3_rec:
                    school_record["years"][year_key]["batch3_min_score"] = batch3_rec.min_score
            else:
                # 名额为0时，不显示分数线
                school_record["years"][year_key]["batch2_min_score"] = None
                school_record["years"][year_key]["last_volunteer_rank"] = None
                school_record["years"][year_key]["batch3_min_score"] = None
        
        aggregated_data.append(school_record)
    
    # 按高中学校名称排序
    aggregated_data.sort(key=lambda x: x["senior_school_name"])
    
    return {
        "success": True,
        "junior_school_name": junior_school_name,
        "data": aggregated_data,
        "count": len(aggregated_data)
    }

@app.get("/quota-allocation", response_class=HTMLResponse)
async def quota_allocation_page():
    """返回名额分配查询页面"""
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    quota_path = os.path.join(frontend_dir, "quota_allocation.html")
    if os.path.exists(quota_path):
        with open(quota_path, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse(content="<h1>名额分配查询页面未找到</h1>")

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "version": APP_VERSION}
