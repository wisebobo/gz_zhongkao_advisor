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
