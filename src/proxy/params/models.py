#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型配置和定义
包含支持的模型列表、Token 限制、能力配置等
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class ProviderType(str, Enum):
    """Provider 类型枚举"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    XAI = "xai"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    DOUBAO = "doubao"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"
    BEDROCK = "bedrock"
    UNKNOWN = "unknown"


@dataclass
class TokenLimit:
    """Token 限制配置"""
    min_tokens: int = 1024
    max_tokens: int = 16384
    default_tokens: int = 4096


@dataclass
class ModelCapabilities:
    """模型能力配置"""
    supports_thinking: bool = False
    supports_vision: bool = False
    supports_tools: bool = True
    supports_streaming: bool = True
    supports_json_mode: bool = False
    supports_web_search: bool = False


@dataclass
class ModelConfig:
    """模型配置"""
    id: str
    name: str
    provider: ProviderType
    token_limit: TokenLimit = field(default_factory=TokenLimit)
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)
    description: str = ""
    context_window: int = 128000
    
    def to_openai_format(self) -> Dict[str, Any]:
        """转换为 OpenAI 兼容的模型格式"""
        return {
            "id": self.id,
            "object": "model",
            "created": 1700000000,
            "owned_by": self.provider.value,
            "permission": [],
            "root": self.id,
            "parent": None,
            # 额外信息
            "_extra": {
                "name": self.name,
                "description": self.description,
                "context_window": self.context_window,
                "capabilities": {
                    "thinking": self.capabilities.supports_thinking,
                    "vision": self.capabilities.supports_vision,
                    "tools": self.capabilities.supports_tools,
                    "streaming": self.capabilities.supports_streaming,
                    "json_mode": self.capabilities.supports_json_mode,
                    "web_search": self.capabilities.supports_web_search,
                },
                "token_limit": {
                    "min": self.token_limit.min_tokens,
                    "max": self.token_limit.max_tokens,
                    "default": self.token_limit.default_tokens,
                }
            }
        }


# ================================
# 支持的模型列表
# ================================

SUPPORTED_MODELS: Dict[str, ModelConfig] = {
    # ================================
    # Anthropic / Claude 模型
    # ================================
    "anthropic/claude-sonnet-4-20250514": ModelConfig(
        id="anthropic/claude-sonnet-4-20250514",
        name="Claude Sonnet 4",
        provider=ProviderType.ANTHROPIC,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=16384, default_tokens=8192),
        capabilities=ModelCapabilities(
            supports_thinking=True,
            supports_vision=True,
            supports_tools=True,
        ),
        description="Claude Sonnet 4 - 平衡性能与成本",
        context_window=200000,
    ),
    "anthropic/claude-opus-4-20250514": ModelConfig(
        id="anthropic/claude-opus-4-20250514",
        name="Claude Opus 4",
        provider=ProviderType.ANTHROPIC,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=32000, default_tokens=16384),
        capabilities=ModelCapabilities(
            supports_thinking=True,
            supports_vision=True,
            supports_tools=True,
        ),
        description="Claude Opus 4 - 最强大的 Claude 模型",
        context_window=200000,
    ),
    "anthropic/claude-3-5-sonnet-20241022": ModelConfig(
        id="anthropic/claude-3-5-sonnet-20241022",
        name="Claude 3.5 Sonnet",
        provider=ProviderType.ANTHROPIC,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=8192, default_tokens=4096),
        capabilities=ModelCapabilities(
            supports_thinking=False,
            supports_vision=True,
            supports_tools=True,
        ),
        description="Claude 3.5 Sonnet - 高性能通用模型",
        context_window=200000,
    ),
    "anthropic/claude-3-5-haiku-20241022": ModelConfig(
        id="anthropic/claude-3-5-haiku-20241022",
        name="Claude 3.5 Haiku",
        provider=ProviderType.ANTHROPIC,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=8192, default_tokens=4096),
        capabilities=ModelCapabilities(
            supports_thinking=False,
            supports_vision=True,
            supports_tools=True,
        ),
        description="Claude 3.5 Haiku - 快速响应模型",
        context_window=200000,
    ),
    "anthropic/claude-3-opus-20240229": ModelConfig(
        id="anthropic/claude-3-opus-20240229",
        name="Claude 3 Opus",
        provider=ProviderType.ANTHROPIC,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=4096, default_tokens=4096),
        capabilities=ModelCapabilities(
            supports_thinking=False,
            supports_vision=True,
            supports_tools=True,
        ),
        description="Claude 3 Opus - 前代旗舰模型",
        context_window=200000,
    ),
    
    # ================================
    # OpenAI 模型
    # ================================
    "openai/gpt-4o": ModelConfig(
        id="openai/gpt-4o",
        name="GPT-4o",
        provider=ProviderType.OPENAI,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=16384, default_tokens=4096),
        capabilities=ModelCapabilities(
            supports_thinking=False,
            supports_vision=True,
            supports_tools=True,
            supports_json_mode=True,
        ),
        description="GPT-4o - OpenAI 多模态旗舰",
        context_window=128000,
    ),
    "openai/gpt-4o-mini": ModelConfig(
        id="openai/gpt-4o-mini",
        name="GPT-4o Mini",
        provider=ProviderType.OPENAI,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=16384, default_tokens=4096),
        capabilities=ModelCapabilities(
            supports_thinking=False,
            supports_vision=True,
            supports_tools=True,
            supports_json_mode=True,
        ),
        description="GPT-4o Mini - 轻量快速版本",
        context_window=128000,
    ),
    "openai/o1": ModelConfig(
        id="openai/o1",
        name="o1",
        provider=ProviderType.OPENAI,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=100000, default_tokens=32768),
        capabilities=ModelCapabilities(
            supports_thinking=True,
            supports_vision=True,
            supports_tools=True,
        ),
        description="o1 - OpenAI 推理模型",
        context_window=200000,
    ),
    "openai/o1-mini": ModelConfig(
        id="openai/o1-mini",
        name="o1 Mini",
        provider=ProviderType.OPENAI,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=65536, default_tokens=16384),
        capabilities=ModelCapabilities(
            supports_thinking=True,
            supports_vision=False,
            supports_tools=True,
        ),
        description="o1 Mini - 轻量推理模型",
        context_window=128000,
    ),
    "openai/o1-pro": ModelConfig(
        id="openai/o1-pro",
        name="o1 Pro",
        provider=ProviderType.OPENAI,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=100000, default_tokens=32768),
        capabilities=ModelCapabilities(
            supports_thinking=True,
            supports_vision=True,
            supports_tools=True,
        ),
        description="o1 Pro - 增强推理模型",
        context_window=200000,
    ),
    "openai/o3": ModelConfig(
        id="openai/o3",
        name="o3",
        provider=ProviderType.OPENAI,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=100000, default_tokens=32768),
        capabilities=ModelCapabilities(
            supports_thinking=True,
            supports_vision=True,
            supports_tools=True,
        ),
        description="o3 - 最新推理模型",
        context_window=200000,
    ),
    "openai/o3-mini": ModelConfig(
        id="openai/o3-mini",
        name="o3 Mini",
        provider=ProviderType.OPENAI,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=65536, default_tokens=16384),
        capabilities=ModelCapabilities(
            supports_thinking=True,
            supports_vision=False,
            supports_tools=True,
        ),
        description="o3 Mini - 轻量版 o3",
        context_window=128000,
    ),
    "openai/o4-mini": ModelConfig(
        id="openai/o4-mini",
        name="o4 Mini",
        provider=ProviderType.OPENAI,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=100000, default_tokens=32768),
        capabilities=ModelCapabilities(
            supports_thinking=True,
            supports_vision=True,
            supports_tools=True,
        ),
        description="o4 Mini - 新一代推理模型",
        context_window=200000,
    ),
    "openai/gpt-4-turbo": ModelConfig(
        id="openai/gpt-4-turbo",
        name="GPT-4 Turbo",
        provider=ProviderType.OPENAI,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=4096, default_tokens=4096),
        capabilities=ModelCapabilities(
            supports_thinking=False,
            supports_vision=True,
            supports_tools=True,
            supports_json_mode=True,
        ),
        description="GPT-4 Turbo",
        context_window=128000,
    ),
    
    # ================================
    # Google / Gemini 模型
    # ================================
    "google/gemini-2.5-pro-preview-06-05": ModelConfig(
        id="google/gemini-2.5-pro-preview-06-05",
        name="Gemini 2.5 Pro",
        provider=ProviderType.GOOGLE,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=65536, default_tokens=8192),
        capabilities=ModelCapabilities(
            supports_thinking=True,
            supports_vision=True,
            supports_tools=True,
            supports_json_mode=True,
            supports_web_search=True,
        ),
        description="Gemini 2.5 Pro - Google 最强模型",
        context_window=1000000,
    ),
    "google/gemini-2.5-flash-preview-05-20": ModelConfig(
        id="google/gemini-2.5-flash-preview-05-20",
        name="Gemini 2.5 Flash",
        provider=ProviderType.GOOGLE,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=65536, default_tokens=8192),
        capabilities=ModelCapabilities(
            supports_thinking=True,
            supports_vision=True,
            supports_tools=True,
            supports_json_mode=True,
            supports_web_search=True,
        ),
        description="Gemini 2.5 Flash - 快速版本",
        context_window=1000000,
    ),
    "google/gemini-2.0-flash": ModelConfig(
        id="google/gemini-2.0-flash",
        name="Gemini 2.0 Flash",
        provider=ProviderType.GOOGLE,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=8192, default_tokens=4096),
        capabilities=ModelCapabilities(
            supports_thinking=False,
            supports_vision=True,
            supports_tools=True,
            supports_json_mode=True,
        ),
        description="Gemini 2.0 Flash",
        context_window=1000000,
    ),
    "google/gemini-1.5-pro": ModelConfig(
        id="google/gemini-1.5-pro",
        name="Gemini 1.5 Pro",
        provider=ProviderType.GOOGLE,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=8192, default_tokens=4096),
        capabilities=ModelCapabilities(
            supports_thinking=False,
            supports_vision=True,
            supports_tools=True,
            supports_json_mode=True,
        ),
        description="Gemini 1.5 Pro",
        context_window=2000000,
    ),
    
    # ================================
    # XAI / Grok 模型
    # ================================
    "xai/grok-3": ModelConfig(
        id="xai/grok-3",
        name="Grok 3",
        provider=ProviderType.XAI,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=16384, default_tokens=4096),
        capabilities=ModelCapabilities(
            supports_thinking=True,
            supports_vision=False,
            supports_tools=True,
        ),
        description="Grok 3 - xAI 旗舰模型",
        context_window=131072,
    ),
    "xai/grok-3-mini": ModelConfig(
        id="xai/grok-3-mini",
        name="Grok 3 Mini",
        provider=ProviderType.XAI,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=16384, default_tokens=4096),
        capabilities=ModelCapabilities(
            supports_thinking=True,
            supports_vision=False,
            supports_tools=True,
        ),
        description="Grok 3 Mini",
        context_window=131072,
    ),
    "xai/grok-2": ModelConfig(
        id="xai/grok-2",
        name="Grok 2",
        provider=ProviderType.XAI,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=8192, default_tokens=4096),
        capabilities=ModelCapabilities(
            supports_thinking=False,
            supports_vision=False,
            supports_tools=True,
        ),
        description="Grok 2",
        context_window=131072,
    ),
    
    # ================================
    # DeepSeek 模型
    # ================================
    "deepseek/deepseek-r1": ModelConfig(
        id="deepseek/deepseek-r1",
        name="DeepSeek R1",
        provider=ProviderType.DEEPSEEK,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=65536, default_tokens=8192),
        capabilities=ModelCapabilities(
            supports_thinking=True,
            supports_vision=False,
            supports_tools=True,
        ),
        description="DeepSeek R1 - 深度推理模型",
        context_window=128000,
    ),
    "deepseek/deepseek-chat": ModelConfig(
        id="deepseek/deepseek-chat",
        name="DeepSeek Chat",
        provider=ProviderType.DEEPSEEK,
        token_limit=TokenLimit(min_tokens=1024, max_tokens=8192, default_tokens=4096),
        capabilities=ModelCapabilities(
            supports_thinking=False,
            supports_vision=False,
            supports_tools=True,
        ),
        description="DeepSeek Chat - 通用对话模型",
        context_window=128000,
    ),
}

# 模型别名映射
MODEL_ALIASES: Dict[str, str] = {
    # Claude 别名
    "claude-sonnet-4": "anthropic/claude-sonnet-4-20250514",
    "claude-4-sonnet": "anthropic/claude-sonnet-4-20250514",
    "claude-opus-4": "anthropic/claude-opus-4-20250514",
    "claude-4-opus": "anthropic/claude-opus-4-20250514",
    "claude-3.5-sonnet": "anthropic/claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet": "anthropic/claude-3-5-sonnet-20241022",
    "claude-3.5-haiku": "anthropic/claude-3-5-haiku-20241022",
    "claude-3-5-haiku": "anthropic/claude-3-5-haiku-20241022",
    "claude-3-opus": "anthropic/claude-3-opus-20240229",
    
    # OpenAI 别名
    "gpt-4o": "openai/gpt-4o",
    "gpt-4o-mini": "openai/gpt-4o-mini",
    "o1": "openai/o1",
    "o1-mini": "openai/o1-mini",
    "o1-pro": "openai/o1-pro",
    "o3": "openai/o3",
    "o3-mini": "openai/o3-mini",
    "o4-mini": "openai/o4-mini",
    
    # Gemini 别名
    "gemini-2.5-pro": "google/gemini-2.5-pro-preview-06-05",
    "gemini-2.5-flash": "google/gemini-2.5-flash-preview-05-20",
    "gemini-2.0-flash": "google/gemini-2.0-flash",
    "gemini-1.5-pro": "google/gemini-1.5-pro",
    
    # Grok 别名
    "grok-3": "xai/grok-3",
    "grok-3-mini": "xai/grok-3-mini",
    "grok-2": "xai/grok-2",
    
    # DeepSeek 别名
    "deepseek-r1": "deepseek/deepseek-r1",
    "deepseek-chat": "deepseek/deepseek-chat",
}


def get_model_info(model_id: str) -> Optional[ModelConfig]:
    """获取模型配置信息"""
    # 直接匹配
    if model_id in SUPPORTED_MODELS:
        return SUPPORTED_MODELS[model_id]
    
    # 别名匹配
    if model_id in MODEL_ALIASES:
        return SUPPORTED_MODELS.get(MODEL_ALIASES[model_id])
    
    # 模糊匹配（不带 provider 前缀）
    for key, config in SUPPORTED_MODELS.items():
        if key.endswith(f"/{model_id}") or model_id in key:
            return config
    
    return None


def detect_provider(model_id: str) -> ProviderType:
    """根据模型 ID 检测 Provider 类型"""
    model_lower = model_id.lower()
    
    # 检查前缀
    if model_lower.startswith("anthropic/") or "claude" in model_lower:
        return ProviderType.ANTHROPIC
    if model_lower.startswith("openai/") or model_lower.startswith("gpt") or model_lower.startswith("o1") or model_lower.startswith("o3") or model_lower.startswith("o4"):
        return ProviderType.OPENAI
    if model_lower.startswith("google/") or "gemini" in model_lower:
        return ProviderType.GOOGLE
    if model_lower.startswith("xai/") or "grok" in model_lower:
        return ProviderType.XAI
    if model_lower.startswith("deepseek/") or "deepseek" in model_lower:
        return ProviderType.DEEPSEEK
    if model_lower.startswith("qwen/") or "qwen" in model_lower or "qwq" in model_lower:
        return ProviderType.QWEN
    if model_lower.startswith("doubao/") or "doubao" in model_lower:
        return ProviderType.DOUBAO
    if model_lower.startswith("openrouter/"):
        return ProviderType.OPENROUTER
    
    return ProviderType.UNKNOWN


def get_all_models() -> List[Dict[str, Any]]:
    """获取所有支持的模型列表（OpenAI 格式）"""
    return [config.to_openai_format() for config in SUPPORTED_MODELS.values()]


def get_models_by_provider(provider: ProviderType) -> List[Dict[str, Any]]:
    """获取指定 Provider 的模型列表"""
    return [
        config.to_openai_format()
        for config in SUPPORTED_MODELS.values()
        if config.provider == provider
    ]
