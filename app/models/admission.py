"""
数据模型定义
"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base

class School(Base):
    """学校信息表"""
    __tablename__ = "schools"
    
    school_id = Column(Integer, primary_key=True, index=True)
    school_name = Column(String(100), nullable=False, index=True)
    base_name = Column(String(100))  # 学校基础名称
    campus_name = Column(String(100))  # 校区名称
    district = Column(String(50), nullable=False, index=True)  # 学校所属区域（包括省市属）
    school_type = Column(String(50))  # 学校类型（公办/民办）
    is_vocational = Column(Integer, default=0)  # 是否职业学校

class Batch3Public(Base):
    """第三批次公办高中录取数据表"""
    __tablename__ = "batch3_public"
    
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.school_id"), nullable=False, index=True)
    min_score = Column(Float, nullable=False)  # 最低录取分数线
    last_volunteer_rank = Column(Integer)  # 末位志愿排名
    student_type = Column(String(20), nullable=False, index=True)  # 户籍生/非户籍生
    
    # 关联学校
    school = relationship("School", backref="batch3_records")

class Batch3Private(Base):
    """第三批次民办高中录取数据表（包含公费班和普通班）"""
    __tablename__ = "batch3_private"
    
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.school_id"), nullable=False, index=True)
    admission_scope = Column(String(50))  # 招生范围（全市/本区等）
    sub_type = Column(String(50))  # 子类型（公费班/普通高中等）
    min_score = Column(Float, nullable=False)  # 最低录取分数线
    min_score_rank = Column(Integer)  # 最低分位次
    last_volunteer_rank = Column(Integer)  # 末位志愿排名
    last_score = Column(Float)  # 末位分数
    last_score_rank = Column(Integer)  # 末位分位次
    is_admitted = Column(Integer)  # 是否录取
    
    # 关联学校
    school = relationship("School", backref="batch3_private_records")

class Batch4Public(Base):
    """第四批次录取数据表（包含公办和民办）"""
    __tablename__ = "batch4_public"
    
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.school_id"), nullable=False, index=True)
    min_score = Column(Float, nullable=False)  # 最低录取分数线
    last_volunteer_rank = Column(Integer)  # 末位志愿排名
    student_type = Column(String(20), nullable=False, index=True)  # 户籍生/非户籍生
    
    # 关联学校
    school = relationship("School", backref="batch4_records")

class Batch2QuotaAllocation(Base):
    """第二批次名额分配表（初中→高中的名额数量）"""
    __tablename__ = "batch2_quota_allocation"
    
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False, index=True)
    junior_school_code = Column(String(50))  # 初中学校代码
    junior_school_name = Column(String(100), nullable=False, index=True)  # 初中学校名称
    junior_school_district = Column(String(50), index=True)  # 初中学校所属行政区
    senior_school_id = Column(Integer, ForeignKey("schools.school_id"), index=True)  # 高中学校ID
    senior_school_name = Column(String(100))  # 高中学校名称（冗余字段，便于查询）
    quota_count = Column(Integer)  # 名额数量
    
    # 不建立relationship，因为junior_school不在schools表中

class Batch2Quota(Base):
    """第二批次录取数据表（分数线、排名等）"""
    __tablename__ = "batch2_quota"
    
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False, index=True)
    senior_school_id = Column(Integer, ForeignKey("schools.school_id"), nullable=False, index=True)  # 高中学校ID
    junior_school_name = Column(String(100), nullable=False, index=True)  # 初中学校名称
    student_type = Column(String(20), nullable=False)  # 户籍生/非户籍生/不限
    min_score = Column(Integer)  # 最低录取分数线
    min_score_rank = Column(Integer)  # 最低分位次
    last_volunteer_rank = Column(Integer)  # 末位志愿排名
    last_score = Column(Integer)  # 末位分数
    last_score_rank = Column(Integer)  # 末位分位次
    data_source = Column(String(50), default='PDF')  # 数据来源
    is_admitted = Column(Integer, default=1)  # 是否录取
    
    # 关联高中学校
    senior_school = relationship("School", foreign_keys=[senior_school_id], backref="batch2_quota_records")

class EnrollmentPlan(Base):
    """招生计划表"""
    __tablename__ = "enrollment_plan"
    
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False, index=True)
    batch = Column(String(50))  # 批次
    school_name = Column(String(100), nullable=False, index=True)
    school_type = Column(String(50))  # 学校类型（公办/民办）
    school_level = Column(String(100))  # 学校等级
    district = Column(String(50), nullable=False, index=True)
    plan_total = Column(Integer)  # 总计划
    plan_suqian = Column(Integer)  # 随迁子女计划
    plan_waiqu = Column(Integer)  # 外区计划
    scope_huji = Column(String(50))  # 户籍生招生范围
    scope_suqian = Column(String(50))  # 随迁子女招生范围
