"""
应用启动脚本
"""
import uvicorn
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    print("="*60)
    print("🎓 广州中考志愿填报助手")
    print("="*60)
    print("🚀 正在启动服务...")
    print("📍 访问地址: http://localhost:8000")
    print("📊 API文档: http://localhost:8000/docs")
    print("="*60)
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
