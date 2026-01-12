#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel Gateway Proxy - FastAPI 版本
支持流式响应、密钥轮换、自动故障转移
"""

import os
import re
import time
import json
import asyncio
from pathlib import Path
from typing import Optional, AsyncGenerator
from datetime import datetime
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# ================================
# 配置加载
# ================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

PROXY_PORT = int(os.getenv("PROXY_PORT", "3001"))
AUTH_KEY = os.getenv("AUTH_KEY", "changeme")
KEY_COOLDOWN_HOURS = int(os.getenv("KEY_COOLDOWN_HOURS", "24"))
KEY_COOLDOWN_SECONDS = KEY_COOLDOWN_HOURS * 3600
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

TARGET_HOST = "ai-gateway.vercel.sh"
TARGET_BASE = f"https://{TARGET_HOST}"

# ================================
# 日志工具
# ================================

def log(level: str, message: str):
    """简单日志输出"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level.upper()}] {message}", flush=True)


# ================================
# 密钥管理
# ================================

class KeyManager:
    def __init__(self):
        self.keys: list[str] = []
        self.current_index: int = 0
        self.key_states: dict[str, dict] = {}
        self.lock = asyncio.Lock()
        self.load_keys()
    
    def load_keys(self) -> list[str]:
        """从文件加载密钥，优先使用高余额密钥"""
        key_files = [
            BASE_DIR / "data/keys/keys_high.txt",
            BASE_DIR / "data/keys/keys_medium_high.txt",
            BASE_DIR / "data/keys/keys_medium.txt",
            BASE_DIR / "data/keys/active_keys.txt",
            BASE_DIR / "data/keys/total_keys.txt"
        ]
        
        for key_file in key_files:
            if key_file.exists():
                content = key_file.read_text()
                keys = [k.strip() for k in re.split(r'[,\n]', content) if k.strip()]
                if keys:
                    self.keys = keys
                    log("info", f"从 {key_file.name} 加载了 {len(keys)} 个密钥")
                    return keys
        
        log("warn", "未找到密钥文件")
        return []
    
    def reload_keys(self):
        """重新加载密钥"""
        old_count = len(self.keys)
        self.load_keys()
        new_count = len(self.keys)
        if old_count != new_count:
            log("info", f"密钥数量变化: {old_count} -> {new_count}")
    
    def get_key_state(self, key: str) -> dict:
        """获取密钥状态"""
        if key not in self.key_states:
            self.key_states[key] = {
                "disabled": False,
                "disabled_until": 0,
                "error_count": 0,
                "last_used": 0,
                "success_count": 0
            }
        return self.key_states[key]
    
    async def select_key(self) -> Optional[str]:
        """选择一个可用的密钥（轮询）"""
        async with self.lock:
            if not self.keys:
                return None
            
            now = time.time()
            start_index = self.current_index
            
            for i in range(len(self.keys)):
                index = (start_index + i) % len(self.keys)
                key = self.keys[index]
                state = self.get_key_state(key)
                
                if state["disabled"] and now >= state["disabled_until"]:
                    state["disabled"] = False
                    log("info", f"密钥 {key[:8]}... 冷却结束，已恢复")
                
                if not state["disabled"]:
                    self.current_index = (index + 1) % len(self.keys)
                    state["last_used"] = now
                    return key
            
            best_key = self.keys[0]
            min_wait = float('inf')
            for key in self.keys:
                state = self.get_key_state(key)
                wait = state["disabled_until"] - now
                if wait < min_wait:
                    min_wait = wait
                    best_key = key
            
            log("warn", f"所有密钥都在冷却中，使用等待时间最短的: {best_key[:8]}...")
            return best_key
    
    def mark_success(self, key: str):
        """标记密钥使用成功"""
        state = self.get_key_state(key)
        state["success_count"] += 1
    
    def mark_exhausted(self, key: str):
        """标记密钥为不可用"""
        state = self.get_key_state(key)
        state["disabled"] = True
        state["disabled_until"] = time.time() + KEY_COOLDOWN_SECONDS
        state["error_count"] += 1
        log("warn", f"密钥 {key[:8]}... 标记为不可用，冷却 {KEY_COOLDOWN_HOURS} 小时")
    
    def get_status(self) -> dict:
        """获取所有密钥状态"""
        now = time.time()
        keys_status = []
        available_count = 0
        
        for i, key in enumerate(self.keys):
            state = self.get_key_state(key)
            is_available = not state["disabled"] or now >= state["disabled_until"]
            if is_available:
                available_count += 1
            
            keys_status.append({
                "index": i,
                "key": f"{key[:8]}...{key[-4:]}",
                "available": is_available,
                "disabled": state["disabled"],
                "cooldown_minutes": max(0, int((state["disabled_until"] - now) / 60)) if state["disabled"] else 0,
                "error_count": state["error_count"],
                "success_count": state["success_count"]
            })
        
        return {
            "total": len(self.keys),
            "available": available_count,
            "current_index": self.current_index,
            "keys": keys_status
        }
    
    def reset_all(self):
        """重置所有密钥状态"""
        self.key_states.clear()
        self.current_index = 0
        log("info", "所有密钥状态已重置")
    
    def reset_key(self, index: int) -> bool:
        """重置单个密钥"""
        if 0 <= index < len(self.keys):
            key = self.keys[index]
            self.key_states[key] = {
                "disabled": False,
                "disabled_until": 0,
                "error_count": 0,
                "last_used": 0,
                "success_count": 0
            }
            log("info", f"密钥 {key[:8]}... 已重置")
            return True
        return False


# 全局密钥管理器
key_manager = KeyManager()

# 全局 HTTP 客户端
http_client: Optional[httpx.AsyncClient] = None

# ================================
# 辅助函数
# ================================

def is_quota_error(status_code: int, body: str) -> bool:
    """检测是否为额度错误"""
    if status_code in (402, 429, 403):
        patterns = [
            r'insufficient', r'quota', r'exceeded', r'credits',
            r'balance', r'billing', r'limit.*reached', r'rate.*limit',
            r'overloaded', r'capacity'
        ]
        body_lower = body.lower()
        return any(re.search(p, body_lower) for p in patterns)
    return False


def normalize_model(model: str) -> str:
    """标准化模型名称"""
    if not model:
        return model
    if model.startswith("anthropic/"):
        return model
    if model.startswith("claude-"):
        return f"anthropic/{model}"
    return model


def check_auth(request: Request) -> bool:
    """验证请求授权"""
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "").strip()
    return token == AUTH_KEY


# ================================
# FastAPI 应用
# ================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global http_client
    
    log("info", "=" * 60)
    log("info", "Vercel Gateway Proxy - v2.1.0 (Python/FastAPI)")
    log("info", "=" * 60)
    log("info", f"监听端口: {PROXY_PORT}")
    log("info", f"已加载密钥: {len(key_manager.keys)} 个")
    log("info", f"冷却时间: {KEY_COOLDOWN_HOURS} 小时")
    log("info", f"认证密钥: {AUTH_KEY[:4]}****")
    log("info", "=" * 60)
    
    if not key_manager.keys:
        log("warn", "警告: 未加载任何密钥！请检查 data/keys/ 目录")
    
    # 创建全局 HTTP 客户端
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=30.0))
    
    # 启动定时重载密钥任务
    async def reload_task():
        while True:
            await asyncio.sleep(300)
            key_manager.reload_keys()
    
    task = asyncio.create_task(reload_task())
    
    yield
    
    task.cancel()
    await http_client.aclose()
    log("info", "服务已停止")


app = FastAPI(
    title="Vercel Gateway Proxy",
    description="Vercel AI Gateway 密钥池代理服务",
    version="2.1.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================================
# 路由 - 健康检查
# ================================

@app.get("/")
@app.get("/health")
async def health():
    """健康检查"""
    status = key_manager.get_status()
    return {
        "ok": True,
        "service": "Vercel Gateway Proxy",
        "version": "2.1.0",
        "keys": {
            "total": status["total"],
            "available": status["available"]
        },
        "timestamp": datetime.now().isoformat()
    }


# ================================
# 路由 - 管理接口
# ================================

@app.get("/admin/status")
async def admin_status(request: Request):
    """管理接口 - 查看状态"""
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return key_manager.get_status()


@app.post("/admin/reset")
async def admin_reset(request: Request):
    """管理接口 - 重置所有密钥"""
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    key_manager.reset_all()
    return {"success": True, "message": "All keys reset"}


@app.post("/admin/reset/{index}")
async def admin_reset_key(request: Request, index: int):
    """管理接口 - 重置单个密钥"""
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if key_manager.reset_key(index):
        return {"success": True, "message": f"Key {index} reset"}
    raise HTTPException(status_code=404, detail="Key not found")


@app.post("/admin/reload")
async def admin_reload(request: Request):
    """管理接口 - 重新加载密钥"""
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    key_manager.reload_keys()
    return {"success": True, "message": f"Reloaded {len(key_manager.keys)} keys"}


# ================================
# 流式响应生成器
# ================================

async def stream_response(
    method: str,
    url: str,
    headers: dict,
    content: bytes,
    gateway_key: str
) -> AsyncGenerator[bytes, None]:
    """流式响应生成器 - 保持连接直到完成"""
    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=30.0)) as client:
        async with client.stream(method, url, headers=headers, content=content) as response:
            if response.status_code != 200:
                # 读取错误响应
                error_body = await response.aread()
                error_text = error_body.decode('utf-8', errors='ignore')
                
                if is_quota_error(response.status_code, error_text):
                    log("warn", f"流式响应检测到额度错误: {error_text[:200]}")
                    key_manager.mark_exhausted(gateway_key)
                
                # 返回错误信息
                yield f"data: {json.dumps({'error': {'message': error_text, 'code': response.status_code}})}\n\n".encode()
                yield b"data: [DONE]\n\n"
                return
            
            # 标记成功
            key_manager.mark_success(gateway_key)
            
            # 流式传输响应
            async for chunk in response.aiter_bytes():
                yield chunk


# ================================
# 路由 - 代理
# ================================

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy(request: Request, path: str):
    """代理所有请求到 Vercel AI Gateway"""
    
    # 处理 CORS 预检请求
    if request.method == "OPTIONS":
        return Response(
            content="",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Max-Age": "86400",
            }
        )
    
    # 验证授权
    if not check_auth(request):
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "message": "Incorrect API key provided",
                    "type": "invalid_request_error",
                    "code": "invalid_api_key"
                }
            }
        )
    
    # 读取请求体
    body = await request.body()
    body_json = None
    is_stream = False
    
    if body:
        try:
            body_json = json.loads(body)
            # 标准化模型名称
            if "model" in body_json:
                original_model = body_json["model"]
                body_json["model"] = normalize_model(original_model)
                if original_model != body_json["model"]:
                    log("info", f"模型标准化: {original_model} -> {body_json['model']}")
            # 检查是否为流式请求
            is_stream = body_json.get("stream", False)
        except json.JSONDecodeError:
            pass
    
    # 最多重试次数
    max_retries = min(len(key_manager.keys), 5) if key_manager.keys else 1
    
    for attempt in range(max_retries):
        gateway_key = await key_manager.select_key()
        
        if not gateway_key:
            return JSONResponse(
                status_code=500,
                content={"error": {"message": "No API keys configured", "type": "configuration_error"}}
            )
        
        log("info", f"尝试 {attempt + 1}/{max_retries}，使用密钥: {gateway_key[:8]}...")
        
        # 构建目标 URL
        target_url = f"{TARGET_BASE}/{path}"
        if request.url.query:
            target_url += f"?{request.url.query}"
        
        # 构建请求头
        headers = {
            "Authorization": f"Bearer {gateway_key}",
            "Host": TARGET_HOST,
            "Content-Type": request.headers.get("Content-Type", "application/json"),
        }
        
        # 传递其他必要的头
        for key in ["Accept", "User-Agent", "X-Request-ID"]:
            if key in request.headers:
                headers[key] = request.headers[key]
        
        # 准备请求内容
        request_content = json.dumps(body_json).encode() if body_json else body
        
        try:
            if is_stream:
                # 流式请求 - 使用生成器
                return StreamingResponse(
                    stream_response(
                        method=request.method,
                        url=target_url,
                        headers=headers,
                        content=request_content,
                        gateway_key=gateway_key
                    ),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "Access-Control-Allow-Origin": "*",
                        "X-Accel-Buffering": "no",
                    }
                )
            else:
                # 非流式请求
                response = await http_client.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    content=request_content,
                )
                
                response_body = response.text
                
                # 检查额度错误
                if is_quota_error(response.status_code, response_body):
                    log("warn", f"检测到额度错误: {response_body[:200]}")
                    key_manager.mark_exhausted(gateway_key)
                    continue
                
                # 成功
                if response.status_code == 200:
                    key_manager.mark_success(gateway_key)
                
                # 构建响应头
                response_headers = {
                    "Access-Control-Allow-Origin": "*",
                    "Content-Type": response.headers.get("Content-Type", "application/json"),
                }
                
                try:
                    return JSONResponse(
                        status_code=response.status_code,
                        content=json.loads(response_body),
                        headers=response_headers
                    )
                except json.JSONDecodeError:
                    return Response(
                        status_code=response.status_code,
                        content=response_body,
                        headers=response_headers
                    )
                    
        except httpx.TimeoutException:
            log("error", f"请求超时，密钥: {gateway_key[:8]}...")
            key_manager.mark_exhausted(gateway_key)
            if attempt == max_retries - 1:
                return JSONResponse(
                    status_code=504,
                    content={"error": {"message": "Gateway timeout", "type": "timeout_error"}}
                )
        except Exception as e:
            log("error", f"请求失败: {str(e)}")
            key_manager.mark_exhausted(gateway_key)
            if attempt == max_retries - 1:
                return JSONResponse(
                    status_code=502,
                    content={"error": {"message": f"Proxy error: {str(e)}", "type": "proxy_error"}}
                )
    
    return JSONResponse(
        status_code=503,
        content={"error": {"message": "All API keys exhausted", "type": "all_keys_exhausted"}}
    )


# ================================
# 启动入口
# ================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=PROXY_PORT,
        log_level=LOG_LEVEL,
        access_log=True
    )
