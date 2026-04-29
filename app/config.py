"""
配置管理模块
"""
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 数据库配置
# 使用现有的完整数据库 guangzhou_admission.db
DATABASE_URL = f"sqlite:///{BASE_DIR}/guangzhou_admission.db"

# 应用配置
APP_NAME = "广州中考志愿填报助手"
APP_VERSION = "2.0.0"
APP_TITLE = APP_NAME
APP_DESCRIPTION = "基于广州市招考办官方数据的智能志愿填报系统"
DEBUG = True

# API配置
API_V1_PREFIX = "/api/v1"

# CORS配置
ALLOWED_ORIGINS = ["*"]

# 分页配置
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# 志愿配置
VOLUNTEER_COUNT = 6  # 可填报的志愿数量

# 风险等级
RISK_LEVELS = {
    "冲刺": {"min_prob": 0.2, "max_prob": 0.5, "color": "#ff4757"},
    "稳妥": {"min_prob": 0.5, "max_prob": 0.85, "color": "#ffa502"},
    "保守": {"min_prob": 0.85, "max_prob": 1.0, "color": "#2ed573"}
}

# 学籍区列表（只包含行政区，不包含省市属）
DISTRICTS = [
    "越秀区", "海珠区", "荔湾区", "天河区", "白云区", 
    "黄埔区", "花都区", "番禺区", "南沙区", "从化区", "增城区"
]

# 户籍类型
HOUSEHOLD_TYPES = ["户籍生", "非户籍生"]
