# app/main.py
import uvicorn
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .routes import router  # 从 .routes 模块导入路由

# 获取项目根目录，用于挂载静态文件
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# 初始化 FastAPI 应用
app = FastAPI(
    title="智能遥控小车",
    description="基于 FastAPI 和 WebSocket 的遥控小车控制系统",
    version="1.0.0"
)

# 挂载静态文件目录
# 用户访问 / 路径时，会自动查找 static/index.html
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 引入所有路由
app.include_router(router)

if __name__ == "__main__":
    # 启动 uvicorn 服务器，使用标准配置以获得更好的性能
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
