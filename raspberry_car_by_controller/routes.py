# app/routes.py
import json

from fastapi import APIRouter, WebSocket, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from .car_state import car_state
from .ws_manager import ConnectionManager
import os
import threading

# 获取当前文件所在目录的父目录，即项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_FILES_PATH = os.path.join(BASE_DIR, "static")

# 挂载静态文件
# FastAPI 不直接支持在 APIRouter 中挂载静态文件，通常在主应用中完成。
# 这里我们创建一个特殊的 APIRouter 并说明用法，在 main.py 中会用到。
# static_files_router = APIRouter()
# static_files_router.mount("/", StaticFiles(directory=STATIC_FILES_PATH, html=True), name="static")

# 创建 API 路由
api_router = APIRouter()
manager = ConnectionManager()

# 定义模板引擎，用于渲染 HTML 文件
templates = Jinja2Templates(directory=STATIC_FILES_PATH)

@api_router.get("/", response_class=HTMLResponse)
async def get_control_page(request: Request):
    """
    HTTP GET 路由，返回控制页面 index.html。
    """
    return templates.TemplateResponse("index.html", {"request": request})
@api_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 路由，处理客户端连接和断开。
    """
    await manager.connect(websocket)
    try:
        while True:
            # 等待接收客户端发送的控制消息
            message = await websocket.receive_text()
            print(f"Received control message from client: {message}")

            # 解析 JSON 消息
            try:
                data = json.loads(message)
                direction = data.get("direction", "stop")
                left_speed = float(data.get("leftSpeed", 0.0))
                right_speed = float(data.get("rightSpeed", 0.0))

                car_state.update_state(
                    direction=direction,
                    leftSpeed=left_speed,
                    rightSpeed=right_speed,
                    source="web"
                )
                print(f"[DEBUG] CarState updated: {car_state.get_state()}", flush=True)
            except (ValueError, json.JSONDecodeError) as e:
                print(f"Invalid message received: {message} - {e}")

    except Exception as e:
        print(f"WebSocket connection error: {e}")
    finally:
        manager.disconnect(websocket)
