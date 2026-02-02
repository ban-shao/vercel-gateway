#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
思考/推理参数处理
处理不同 Provider 的思考强度参数转换
"""

from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass
from enum import Enum

from .models import ProviderType, get_model_info, detect_provider


class ReasoningEffort(str, Enum):
    """思考强度级别"""
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    AUTO = "auto"


# 思考强度到比例的映射
EFFORT_RATIO: Dict[str, float] = {
    "minimal": 0.1,
    "low": 0.25,
    "medium": 0.5,
    "high": 0.75,
    "xhigh": 1.0,
    "auto": 0.5,
}


@dataclass
class ReasoningParams:
    """推理参数"""
    enabled: bool = False
    effort: str = "medium"
    budget_tokens: Optional[int] = None
    include_thoughts: bool = True


def calculate_budget_tokens(
    effort: str,
    min_tokens: int = 1024,
    max_tokens: int = 16384,
    output_max_tokens: Optional[int] = None
) -> int:
    """
    计算思考 Token 预算
    
    Args:
        effort: 思考强度级别
        min_tokens: 最小 Token 数
        max_tokens: 最大 Token 数
        output_max_tokens: 用户设置的最大输出 Token
    
    Returns:
        计算后的 Token 预算
    """
    ratio = EFFORT_RATIO.get(effort, 0.5)
    budget = int((max_tokens - min_tokens) * ratio + min_tokens)
    
    # 确保最小值
    budget = max(1024, budget)
    
    # 如果设置了输出限制，按比例调整
    if output_max_tokens:
        budget = min(budget, int(output_max_tokens * ratio))
        budget = max(1024, budget)
    
    return budget


def get_anthropic_reasoning_params(
    reasoning: ReasoningParams,
    model_id: str
) -> Dict[str, Any]:
    """
    获取 Anthropic/Claude 的推理参数
    
    格式:
    {
        "thinking": {
            "type": "enabled" | "disabled",
            "budget_tokens": number
        }
    }
    """
    if not reasoning.enabled:
        return {}
    
    # 获取模型的 Token 限制
    model_info = get_model_info(model_id)
    if model_info:
        min_tokens = model_info.token_limit.min_tokens
        max_tokens = model_info.token_limit.max_tokens
    else:
        min_tokens = 1024
        max_tokens = 16384
    
    budget = reasoning.budget_tokens or calculate_budget_tokens(
        reasoning.effort, min_tokens, max_tokens
    )
    
    return {
        "thinking": {
            "type": "enabled",
            "budget_tokens": budget
        }
    }


def get_openai_reasoning_params(
    reasoning: ReasoningParams,
    model_id: str
) -> Dict[str, Any]:
    """
    获取 OpenAI 的推理参数（用于 o1, o3, o4 系列）
    
    格式:
    {
        "reasoningEffort": "low" | "medium" | "high",
        "reasoningSummary": "auto" | "concise" | "detailed"  # 可选
    }
    """
    if not reasoning.enabled:
        return {}
    
    # OpenAI 只支持 low, medium, high
    effort_map = {
        "minimal": "low",
        "low": "low",
        "medium": "medium",
        "high": "high",
        "xhigh": "high",
        "auto": "medium",
    }
    
    effort = effort_map.get(reasoning.effort, "medium")
    
    result = {
        "reasoningEffort": effort
    }
    
    # 如果需要包含思考过程摘要
    if reasoning.include_thoughts:
        result["reasoningSummary"] = "auto"
    
    return result


def get_gemini_reasoning_params(
    reasoning: ReasoningParams,
    model_id: str
) -> Dict[str, Any]:
    """
    获取 Google/Gemini 的推理参数
    
    格式:
    {
        "thinkingConfig": {
            "thinkingBudget": number,  # 或 -1 表示自动
            "includeThoughts": boolean,
            "thinkingLevel": "minimal" | "low" | "medium" | "high"  # Gemini 3
        }
    }
    """
    if not reasoning.enabled:
        return {}
    
    # 获取模型的 Token 限制
    model_info = get_model_info(model_id)
    if model_info:
        min_tokens = model_info.token_limit.min_tokens
        max_tokens = model_info.token_limit.max_tokens
    else:
        min_tokens = 1024
        max_tokens = 65536
    
    budget = reasoning.budget_tokens or calculate_budget_tokens(
        reasoning.effort, min_tokens, max_tokens
    )
    
    result = {
        "thinkingConfig": {
            "thinkingBudget": budget,
            "includeThoughts": reasoning.include_thoughts,
        }
    }
    
    # 如果是 auto，使用 -1
    if reasoning.effort == "auto":
        result["thinkingConfig"]["thinkingBudget"] = -1
    
    return result


def get_xai_reasoning_params(
    reasoning: ReasoningParams,
    model_id: str
) -> Dict[str, Any]:
    """
    获取 xAI/Grok 的推理参数
    
    格式:
    {
        "reasoningEffort": "low" | "high"
    }
    """
    if not reasoning.enabled:
        return {}
    
    # Grok 只支持 low 和 high
    effort = "high" if reasoning.effort in ("high", "xhigh") else "low"
    
    return {
        "reasoningEffort": effort
    }


def get_deepseek_reasoning_params(
    reasoning: ReasoningParams,
    model_id: str
) -> Dict[str, Any]:
    """
    获取 DeepSeek 的推理参数
    
    格式:
    {
        "thinking": {
            "type": "enabled"
        }
    }
    或者:
    {
        "enable_thinking": true,
        "thinking_budget": number
    }
    """
    if not reasoning.enabled:
        return {}
    
    # DeepSeek R1 使用 thinking 格式
    if "r1" in model_id.lower():
        return {
            "thinking": {
                "type": "enabled"
            }
        }
    
    # 其他 DeepSeek 模型使用 enable_thinking 格式
    result = {
        "enable_thinking": True
    }
    
    if reasoning.budget_tokens:
        result["thinking_budget"] = reasoning.budget_tokens
    
    return result


def get_qwen_reasoning_params(
    reasoning: ReasoningParams,
    model_id: str
) -> Dict[str, Any]:
    """
    获取 Qwen 的推理参数
    
    格式:
    {
        "enable_thinking": true,
        "thinking_budget": number
    }
    """
    if not reasoning.enabled:
        return {}
    
    result = {
        "enable_thinking": True
    }
    
    if reasoning.budget_tokens:
        result["thinking_budget"] = reasoning.budget_tokens
    else:
        # 计算默认预算
        budget = calculate_budget_tokens(reasoning.effort, 1024, 32768)
        result["thinking_budget"] = budget
    
    return result


def get_openrouter_reasoning_params(
    reasoning: ReasoningParams,
    model_id: str
) -> Dict[str, Any]:
    """
    获取 OpenRouter 的推理参数
    
    格式:
    {
        "reasoning": {
            "effort": "low" | "medium" | "high"
        }
    }
    或者:
    {
        "reasoning": {
            "enabled": true
        }
    }
    """
    if not reasoning.enabled:
        return {}
    
    # 尝试使用 effort
    effort_map = {
        "minimal": "low",
        "low": "low",
        "medium": "medium",
        "high": "high",
        "xhigh": "high",
        "auto": "medium",
    }
    
    return {
        "reasoning": {
            "effort": effort_map.get(reasoning.effort, "medium")
        }
    }


def get_reasoning_params(
    provider: ProviderType,
    reasoning: ReasoningParams,
    model_id: str
) -> Dict[str, Any]:
    """
    获取指定 Provider 的推理参数
    
    Args:
        provider: Provider 类型
        reasoning: 推理参数
        model_id: 模型 ID
    
    Returns:
        转换后的推理参数字典
    """
    if not reasoning.enabled:
        return {}
    
    handlers = {
        ProviderType.ANTHROPIC: get_anthropic_reasoning_params,
        ProviderType.OPENAI: get_openai_reasoning_params,
        ProviderType.GOOGLE: get_gemini_reasoning_params,
        ProviderType.XAI: get_xai_reasoning_params,
        ProviderType.DEEPSEEK: get_deepseek_reasoning_params,
        ProviderType.QWEN: get_qwen_reasoning_params,
        ProviderType.OPENROUTER: get_openrouter_reasoning_params,
    }
    
    handler = handlers.get(provider)
    if handler:
        return handler(reasoning, model_id)
    
    # 默认使用 OpenAI 格式
    return get_openai_reasoning_params(reasoning, model_id)


def parse_reasoning_from_request(body: Dict[str, Any], model_id: str) -> ReasoningParams:
    """
    从请求体中解析推理参数
    
    支持多种格式:
    1. Cherry Studio 格式: providerOptions.xxx.thinking / reasoningEffort
    2. 直接格式: reasoning_effort, enable_thinking, thinking
    """
    reasoning = ReasoningParams()
    
    # 1. 检查 providerOptions
    provider_options = body.get("providerOptions", {})
    
    # Anthropic 格式
    anthropic_opts = provider_options.get("anthropic", {})
    if "thinking" in anthropic_opts:
        thinking = anthropic_opts["thinking"]
        if isinstance(thinking, dict):
            reasoning.enabled = thinking.get("type") == "enabled"
            reasoning.budget_tokens = thinking.get("budget_tokens") or thinking.get("budgetTokens")
    
    # OpenAI 格式
    openai_opts = provider_options.get("openai", {})
    if "reasoningEffort" in openai_opts:
        reasoning.enabled = True
        reasoning.effort = openai_opts["reasoningEffort"]
    
    # Google 格式
    google_opts = provider_options.get("google", {})
    if "thinkingConfig" in google_opts:
        thinking_config = google_opts["thinkingConfig"]
        reasoning.enabled = True
        reasoning.budget_tokens = thinking_config.get("thinkingBudget")
        reasoning.include_thoughts = thinking_config.get("includeThoughts", True)
    
    # 2. 检查直接参数
    if "reasoning_effort" in body:
        reasoning.enabled = True
        reasoning.effort = body["reasoning_effort"]
    
    if "enable_thinking" in body:
        reasoning.enabled = body["enable_thinking"]
    
    if "thinking" in body:
        thinking = body["thinking"]
        if isinstance(thinking, dict):
            reasoning.enabled = thinking.get("type") == "enabled" or thinking.get("enabled", False)
            reasoning.budget_tokens = thinking.get("budget_tokens") or thinking.get("budgetTokens")
        elif isinstance(thinking, bool):
            reasoning.enabled = thinking
    
    if "thinking_budget" in body:
        reasoning.budget_tokens = body["thinking_budget"]
    
    return reasoning
