import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
# 向上一级目录: agentchat
parent_dir = os.path.dirname(os.path.abspath(__file__))
# 向上一级目录: backend
parent_dir = os.path.dirname(parent_dir)
# 向上一级目录: src
src_dir = os.path.dirname(parent_dir)
sys.path.insert(0, src_dir)
# 向上一级目录: 项目根目录
project_dir = os.path.dirname(src_dir)
sys.path.insert(0, project_dir)

# 添加backend目录到Python路径，确保agentchat模块可以被找到
backend_dir = os.path.join(src_dir, 'backend')
sys.path.insert(0, backend_dir)

# 导入股票API路由
from agentchat.api.v1.stock import router as stock_router

# 创建FastAPI应用
app = FastAPI(
    title="Stock API",
    description="为前端提供股票数据访问能力",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含股票API路由
app.include_router(stock_router)

# 健康检查端点
@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("stock_api:app", host="0.0.0.0", port=8000, reload=True)
