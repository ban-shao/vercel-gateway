"""
Vercel Gateway Proxy Server
支持密钥池管理、故障转移、参数转换等功能
"""

import os
import json
import time
import httpx
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from collections import defaultdict

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import StreamingResponse, JSONResponse
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ============== 配置 ==============
VERCEL_GATEWAY_URL = os.getenv("VERCEL_GATEWAY_URL", "https://ai-gateway.vercel.sh")
AUTH_KEY = os.getenv("AUTH_KEY", "")
COOLDOWN_HOURS = int(os.getenv("COOLDOWN_HOURS", "24"))
KEYS_FILE = os.getenv("KEYS_FILE", "data/keys/keys_high.txt")
COOLDOWN_FILE = os.getenv("COOLDOWN_FILE", "data/keys/cooldown_keys.json")
LOG_DIR = os.getenv("LOG_DIR", "logs")
PORT = int(os.getenv("PORT", "3001"))
ENABLE_PARAMS_CONVERSION = os.getenv("ENABLE_PARAMS_CONVERSION", "false").lower() == "true"

# 模型列表缓存配置
MODELS_CACHE_TTL = int(os.getenv("MODELS_CACHE_TTL", "3600"))  # 默认1小时

# ============== 参数转换模块（可选加载） ==============
params_converter = None
try:
    from .params import ParamsConverter
    params_converter = ParamsConverter()
except ImportError:
    try:
        from src.proxy.params import ParamsConverter
        params_converter = ParamsConverter()
    except ImportError:
        pass

# ============== 全局状态 ==============
api_keys: List[str] = []
cooldown_keys: Dict[str, str] = {}  # key -> cooldown_until (ISO format)
key_index = 0
key_lock = asyncio.Lock()

# 模型列表缓存
models_cache: Dict[str, Any] = {
    "data": None,
    "last_updated": None
}

# ============== 工具函数 ==============
def log(level: str, message: str):
    """统一日志格式"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level.upper()}] {message}")

def load_keys() -> List[str]:
    """从文件加载密钥"""
    keys_path = Path(KEYS_FILE)
    if not keys_path.exists():
        log("warn", f"密钥文件不存在: {KEYS_FILE}")
        return []
    
    with open(keys_path, "r") as f:
        keys = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    
    log("info", f"从 {keys_path.name} 加载了 {len(keys)} 个密钥")
    return keys

def load_cooldown_keys() -> Dict[str, str]:
    """加载冷却中的密钥"""
    cooldown_path = Path(COOLDOWN_FILE)
    if not cooldown_path.exists():
        return {}
    
    try:
        with open(cooldown_path, "r") as f:
            data = json.load(f)
        
        # 清理已过期的冷却密钥
        now = datetime.now()
        valid_keys = {}
        for key, until in data.items():
            if datetime.fromisoformat(until) > now:
                valid_keys[key] = until
        
        return valid_keys
    except Exception as e:
        log("error", f"加载冷却密钥失败: {e}")
        return {}

def save_cooldown_keys():
    """保存冷却中的密钥"""
    cooldown_path = Path(COOLDOWN_FILE)
    cooldown_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(cooldown_path, "w") as f:
        json.dump(cooldown_keys, f, indent=2)

def add_to_cooldown(key: str):
    """将密钥加入冷却"""
    until = datetime.now() + timedelta(hours=COOLDOWN_HOURS)
    cooldown_keys[key] = until.isoformat()
    save_cooldown_keys()
    
    masked_key = f"{key[:8]}****"
    log("warn", f"密钥 {masked_key} 已加入冷却，直到 {until.strftime('%Y-%m-%d %H:%M')}")

async def get_next_key() -> Optional[str]:
    """获取下一个可用密钥（轮询）"""
    global key_index
    
    async with key_lock:
        if not api_keys:
            return None
        
        # 尝试找到一个不在冷却中的密钥
        for _ in range(len(api_keys)):
            key = api_keys[key_index]
            key_index = (key_index + 1) % len(api_keys)
            
            # 检查是否在冷却中
            if key in cooldown_keys:
                until = datetime.fromisoformat(cooldown_keys[key])
                if datetime.now() < until:
                    continue
                else:
                    # 冷却已过期，移除
                    del cooldown_keys[key]
                    save_cooldown_keys()
            
            return key
        
        return None

def verify_auth(authorization: Optional[str]) -> bool:
    """验证请求授权"""
    if not AUTH_KEY:
        return True
    
    if not authorization:
        return False
    
    # 支持 "Bearer xxx" 或直接 "xxx"
    token = authorization.replace("Bearer ", "").strip()
    return token == AUTH_KEY

# ============== 模型列表获取 ==============
async def fetch_models_from_upstream(api_key: str) -> Optional[Dict[str, Any]]:
    """从上游 Vercel AI Gateway 获取模型列表"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{VERCEL_GATEWAY_URL}/v1/models",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                log("warn", f"获取模型列表失败: HTTP {response.status_code}")
                return None
    except Exception as e:
        log("error", f"获取模型列表异常: {e}")
        return None

async def get_models_list(force_refresh: bool = False) -> Dict[str, Any]:
    """获取模型列表（带缓存）"""
    global models_cache
    
    now = datetime.now()
    
    # 检查缓存是否有效
    if not force_refresh and models_cache["data"] is not None:
        if models_cache["last_updated"]:
            cache_age = (now - models_cache["last_updated"]).total_seconds()
            if cache_age < MODELS_CACHE_TTL:
                return models_cache["data"]
    
    # 从上游获取
    api_key = await get_next_key()
    if not api_key:
        log("error", "没有可用的 API 密钥来获取模型列表")
        # 如果有旧缓存，返回旧缓存
        if models_cache["data"]:
            return models_cache["data"]
        return {"object": "list", "data": []}
    
    result = await fetch_models_from_upstream(api_key)
    
    if result:
        models_cache["data"] = result
        models_cache["last_updated"] = now
        log("info", f"已从上游获取 {len(result.get('data', []))} 个模型")
        return result
    
    # 获取失败，返回旧缓存或空列表
    if models_cache["data"]:
        log("warn", "获取模型列表失败，使用缓存数据")
        return models_cache["data"]
    
    return {"object": "list", "data": []}

# ============== 请求处理 ==============
async def proxy_request(request: Request, path: str) -> StreamingResponse:
    """代理请求到 Vercel AI Gateway"""
    
    # 获取可用密钥
    api_key = await get_next_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="No available API keys")
    
    # 读取请求体
    body = await request.body()
    
    # 参数转换（如果启用）
    if ENABLE_PARAMS_CONVERSION and params_converter and body:
        try:
            body_json = json.loads(body)
            body_json = params_converter.convert(body_json)
            body = json.dumps(body_json).encode()
        except json.JSONDecodeError:
            pass
        except Exception as e:
            log("warn", f"参数转换失败: {e}")
    
    # 构建目标 URL
    target_url = f"{VERCEL_GATEWAY_URL}/{path}"
    if request.query_params:
        target_url += f"?{request.query_params}"
    
    # 构建请求头
    headers = dict(request.headers)
    headers["Authorization"] = f"Bearer {api_key}"
    headers.pop("host", None)
    headers.pop("content-length", None)
    
    # 发送请求
    async def stream_response():
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    content=body
                ) as response:
                    # 检查是否需要冷却
                    if response.status_code == 429:
                        add_to_cooldown(api_key)
                    
                    async for chunk in response.aiter_bytes():
                        yield chunk
        except Exception as e:
            log("error", f"代理请求失败: {e}")
            yield json.dumps({"error": str(e)}).encode()
    
    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream"
    )

# ============== 生命周期 ==============
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global api_keys, cooldown_keys
    
    # 启动时加载密钥
    api_keys = load_keys()
    cooldown_keys = load_cooldown_keys()
    
    log("info", "Vercel Gateway Proxy - v3.1.0 (Python/FastAPI)")
    log("info", "=" * 60)
    log("info", f"监听端口: {PORT}")
    log("info", f"已加载密钥: {len(api_keys)} 个")
    log("info", f"冷却时间: {COOLDOWN_HOURS} 小时")
    log("info", f"认证密钥: {AUTH_KEY[:4]}****" if AUTH_KEY else "认证密钥: 未设置")
    log("info", f"参数转换: {'启用' if ENABLE_PARAMS_CONVERSION and params_converter else '禁用'}")
    log("info", f"模型缓存: {MODELS_CACHE_TTL} 秒")
    log("info", "=" * 60)
    
    # 定时重新加载密钥
    async def reload_keys_periodically():
        while True:
            await asyncio.sleep(300)  # 每5分钟
            global api_keys
            api_keys = load_keys()
    
    task = asyncio.create_task(reload_keys_periodically())
    
    yield
    
    task.cancel()

# ============== FastAPI 应用 ==============
app = FastAPI(
    title="Vercel Gateway Proxy",
    version="3.1.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    """健康检查"""
    return {
        "status": "ok",
        "service": "vercel-gateway-proxy",
        "version": "3.1.0",
        "keys_loaded": len(api_keys),
        "keys_in_cooldown": len(cooldown_keys)
    }

@app.get("/health")
async def health():
    """健康检查端点"""
    return {"status": "healthy"}

@app.get("/v1/models")
async def list_models(
    authorization: Optional[str] = Header(None),
    provider: Optional[str] = None,
    refresh: Optional[bool] = False
):
    """获取模型列表（从上游 Vercel AI Gateway 自动获取）"""
    if not verify_auth(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # 获取模型列表
    models_response = await get_models_list(force_refresh=refresh)
    
    # 按 provider 过滤
    if provider and models_response.get("data"):
        filtered_data = [
            m for m in models_response["data"]
            if m.get("id", "").startswith(f"{provider}/") or 
               m.get("owned_by", "") == provider
        ]
        return {"object": "list", "data": filtered_data}
    
    return models_response

@app.get("/v1/models/{model_id:path}")
async def get_model(
    model_id: str,
    authorization: Optional[str] = Header(None)
):
    """获取单个模型详情"""
    if not verify_auth(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    models_response = await get_models_list()
    
    for model in models_response.get("data", []):
        if model.get("id") == model_id:
            return model
    
    raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_v1(
    request: Request,
    path: str,
    authorization: Optional[str] = Header(None)
):
    """代理 /v1/* 请求"""
    if not verify_auth(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return await proxy_request(request, f"v1/{path}")

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_all(
    request: Request,
    path: str,
    authorization: Optional[str] = Header(None)
):
    """代理其他请求"""
    if not verify_auth(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return await proxy_request(request, path)
