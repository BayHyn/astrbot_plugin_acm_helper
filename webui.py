# 文件路径: acm-helper-plugin/webui.py

import asyncio
from quart import Quart, send_from_directory
from hypercorn.config import Config
import hypercorn.asyncio
from pathlib import Path

# 从我们的 backend 包导入 api 蓝图
from .backend.api import api

# --- Quart App 设置 ---
app = Quart(__name__, static_folder='public')
app.register_blueprint(api, url_prefix="/api")

# --- 根路由和静态文件服务 ---
@app.route('/')
async def index():
    public_dir = Path(__file__).parent / 'public'
    return await send_from_directory(public_dir, 'index.html')

@app.route('/<path:filename>')
async def serve_static(filename):
    public_dir = Path(__file__).parent / 'public'
    return await send_from_directory(public_dir, filename)

# --- 服务器启动逻辑 ---
async def start_server(port):
    hypercorn_config = Config()
    hypercorn_config.bind = [f"0.0.0.0:{port}"]
    print(f"[ACM Helper WebUI] Server is running on http://0.0.0.0:{port}")
    await hypercorn.asyncio.serve(app, hypercorn_config)

def run_server(db_path, port):
    print(f"[ACM Helper WebUI] Process started. DB path: {db_path}, Port: {port}")
    try:
        asyncio.run(start_server(port))
    except KeyboardInterrupt:
        print("[ACM Helper WebUI] Server stopped by KeyboardInterrupt.")
    except Exception as e:
        print(f"[ACM Helper WebUI] An error occurred: {e}")
