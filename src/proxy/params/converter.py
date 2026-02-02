#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
参数转换核心模块
处理 Cherry Studio 发送的请求参数并转换为 Vercel AI Gateway 格式
"""

import copy
from typing import Dict, Any, Optional, Tuple

from .models import (
    ProviderType,
    detect_provider,
    get_model_info,
    SUPPORTED_MODELS,
    MODEL_ALIASES,
)
from .reasoning import (
    ReasoningParams,
    get_reasoning_params,
    parse_reasoning_from_request,
)


class ParamsConverter:
    """
    参数转换器
    负责将 Cherry Studio 格式的请求参数转换为 Vercel AI Gateway 格式
    """
    
    def __init__(self):
        pass
    
    def normalize_model_id(self, model_id: str) -> str:
        """
        标准化模型 ID
        
        Examples:
            - "claude-sonnet-4" -> "anthropic/claude-sonnet-4-20250514"
            - "gpt-4o" -> "openai/gpt-4o"
            - "anthropic/claude-3-5-sonnet" -> "anthropic/claude-3-5-sonnet-20241022"
        """
        if not model_id:
            return model_id
        
        # 检查别名
        if model_id in MODEL_ALIASES:
            return MODEL_ALIASES[model_id]
        
        # 检查是否已经是完整格式
        if model_id in SUPPORTED_MODELS:
            return model_id
        
        # 尝试添加 provider 前缀
        provider = detect_provider(model_id)
        if provider != ProviderType.UNKNOWN and not "/" in model_id:
            full_id = f"{provider.value}/{model_id}"
            if full_id in SUPPORTED_MODELS:
                return full_id
        
        # 尝试模糊匹配
        for key in SUPPORTED_MODELS.keys():
            if model_id in key or key.endswith(f"/{model_id}"):
                return key
        
        # 如果没有前缀，尝试添加
        if "/" not in model_id:
            if model_id.startswith("claude"):
                return f"anthropic/{model_id}"
            if model_id.startswith("gpt") or model_id.startswith("o1") or model_id.startswith("o3") or model_id.startswith("o4"):
                return f"openai/{model_id}"
            if model_id.startswith("gemini"):
                return f"google/{model_id}"
            if model_id.startswith("grok"):
                return f"xai/{model_id}"
            if model_id.startswith("deepseek"):
                return f"deepseek/{model_id}"
        
        return model_id
    
    def extract_provider_options(self, body: Dict[str, Any], provider: ProviderType) -> Dict[str, Any]:
        """
        从请求体中提取 provider 特定的选项
        
        Cherry Studio 发送的格式:
        {
            "providerOptions": {
                "anthropic": { ... },
                "openai": { ... },
                "google": { ... }
            }
        }
        """
        provider_options = body.get("providerOptions", {})
        
        # 根据 provider 类型选择对应的选项
        provider_key_map = {
            ProviderType.ANTHROPIC: ["anthropic", "claude"],
            ProviderType.OPENAI: ["openai", "azure"],
            ProviderType.GOOGLE: ["google", "gemini"],
            ProviderType.XAI: ["xai", "grok"],
            ProviderType.DEEPSEEK: ["deepseek"],
            ProviderType.QWEN: ["qwen", "alibaba"],
            ProviderType.DOUBAO: ["doubao", "bytedance"],
            ProviderType.OPENROUTER: ["openrouter"],
            ProviderType.BEDROCK: ["bedrock", "aws"],
        }
        
        keys = provider_key_map.get(provider, [])
        for key in keys:
            if key in provider_options:
                return provider_options[key]
        
        return {}
    
    def convert_temperature(self, body: Dict[str, Any], provider: ProviderType) -> Optional[float]:
        """
        转换温度参数
        
        注意: Claude 模型的温度范围是 0-1
        """
        temp = body.get("temperature")
        if temp is None:
            return None
        
        # Claude 模型温度上限为 1
        if provider == ProviderType.ANTHROPIC:
            return min(float(temp), 1.0)
        
        return float(temp)
    
    def convert_max_tokens(self, body: Dict[str, Any], model_id: str) -> Optional[int]:
        """
        转换最大 Token 参数
        
        处理不同的参数名称:
        - max_tokens
        - maxTokens
        - max_output_tokens
        - maxOutputTokens
        """
        # 尝试多种参数名
        max_tokens = (
            body.get("max_tokens") or
            body.get("maxTokens") or
            body.get("max_output_tokens") or
            body.get("maxOutputTokens")
        )
        
        if max_tokens is None:
            # 使用模型默认值
            model_info = get_model_info(model_id)
            if model_info:
                return model_info.token_limit.default_tokens
            return None
        
        return int(max_tokens)
    
    def convert_standard_params(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换标准参数
        
        包括:
        - top_p / topP
        - top_k / topK
        - frequency_penalty / frequencyPenalty
        - presence_penalty / presencePenalty
        - stop / stopSequences
        - seed
        """
        result = {}
        
        # Top P
        top_p = body.get("top_p") or body.get("topP")
        if top_p is not None:
            result["top_p"] = float(top_p)
        
        # Top K
        top_k = body.get("top_k") or body.get("topK")
        if top_k is not None:
            result["top_k"] = int(top_k)
        
        # Frequency Penalty
        freq_penalty = body.get("frequency_penalty") or body.get("frequencyPenalty")
        if freq_penalty is not None:
            result["frequency_penalty"] = float(freq_penalty)
        
        # Presence Penalty
        pres_penalty = body.get("presence_penalty") or body.get("presencePenalty")
        if pres_penalty is not None:
            result["presence_penalty"] = float(pres_penalty)
        
        # Stop Sequences
        stop = body.get("stop") or body.get("stopSequences")
        if stop is not None:
            result["stop"] = stop if isinstance(stop, list) else [stop]
        
        # Seed
        seed = body.get("seed")
        if seed is not None:
            result["seed"] = int(seed)
        
        return result
    
    def convert_custom_parameters(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取自定义参数
        
        Cherry Studio 支持用户添加自定义参数:
        {
            "customParameters": [
                {"name": "top_k", "value": 10, "type": "number"},
                {"name": "extra_config", "value": "{\"key\": \"value\"}", "type": "json"}
            ]
        }
        """
        custom_params = body.get("customParameters", [])
        result = {}
        
        for param in custom_params:
            name = param.get("name", "").strip()
            if not name:
                continue
            
            value = param.get("value")
            param_type = param.get("type", "string")
            
            # 根据类型转换值
            if param_type == "json":
                if isinstance(value, str):
                    if value == "undefined":
                        continue
                    try:
                        import json
                        value = json.loads(value)
                    except:
                        pass
            elif param_type == "number":
                try:
                    value = float(value)
                    if value == int(value):
                        value = int(value)
                except:
                    pass
            elif param_type == "boolean":
                value = str(value).lower() in ("true", "1", "yes")
            
            result[name] = value
        
        return result
    
    def build_provider_options(
        self,
        body: Dict[str, Any],
        model_id: str,
        provider: ProviderType
    ) -> Dict[str, Any]:
        """
        构建 Provider 特定的选项
        
        这是核心转换函数，根据 Provider 类型构建不同格式的选项
        """
        result = {}
        
        # 1. 提取原有的 provider 选项
        existing_options = self.extract_provider_options(body, provider)
        result.update(existing_options)
        
        # 2. 解析并转换推理参数
        reasoning = parse_reasoning_from_request(body, model_id)
        reasoning_params = get_reasoning_params(provider, reasoning, model_id)
        
        # 3. 合并推理参数
        if reasoning_params:
            # 对于某些 provider，参数需要放在特定位置
            if provider == ProviderType.ANTHROPIC:
                result.update(reasoning_params)
            elif provider == ProviderType.OPENAI:
                result.update(reasoning_params)
            elif provider == ProviderType.GOOGLE:
                result.update(reasoning_params)
            else:
                result.update(reasoning_params)
        
        return result
    
    def convert(
        self,
        body: Dict[str, Any],
        preserve_original: bool = False
    ) -> Tuple[Dict[str, Any], ProviderType]:
        """
        主转换函数
        
        将 Cherry Studio 格式的请求体转换为 Vercel AI Gateway 格式
        
        Args:
            body: 原始请求体
            preserve_original: 是否保留原始参数
        
        Returns:
            (转换后的请求体, 检测到的 Provider 类型)
        """
        if preserve_original:
            result = copy.deepcopy(body)
        else:
            result = {}
        
        # 1. 标准化模型 ID
        model_id = body.get("model", "")
        normalized_model = self.normalize_model_id(model_id)
        result["model"] = normalized_model
        
        # 2. 检测 Provider
        provider = detect_provider(normalized_model)
        
        # 3. 复制必要的基础参数
        result["messages"] = body.get("messages", [])
        result["stream"] = body.get("stream", False)
        
        # 4. 转换温度
        temperature = self.convert_temperature(body, provider)
        if temperature is not None:
            result["temperature"] = temperature
        
        # 5. 转换最大 Token
        max_tokens = self.convert_max_tokens(body, normalized_model)
        if max_tokens is not None:
            result["max_tokens"] = max_tokens
        
        # 6. 转换标准参数
        standard_params = self.convert_standard_params(body)
        result.update(standard_params)
        
        # 7. 构建 Provider 特定选项
        provider_options = self.build_provider_options(body, normalized_model, provider)
        if provider_options:
            # 将 provider 选项放入对应的命名空间
            provider_key = provider.value
            if provider_key not in result.get("providerOptions", {}):
                if "providerOptions" not in result:
                    result["providerOptions"] = {}
                result["providerOptions"][provider_key] = provider_options
        
        # 8. 处理自定义参数
        custom_params = self.convert_custom_parameters(body)
        if custom_params:
            result.update(custom_params)
        
        # 9. 清理不需要传递的参数
        keys_to_remove = [
            "customParameters",  # 已处理
        ]
        for key in keys_to_remove:
            result.pop(key, None)
        
        return result, provider
    
    def convert_for_vercel_gateway(
        self,
        body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        专门为 Vercel AI Gateway 转换请求
        
        Vercel AI Gateway 需要特定的格式，这个函数处理所有必要的转换
        """
        converted, provider = self.convert(body, preserve_original=True)
        
        # Vercel AI Gateway 特殊处理
        # 1. 确保模型 ID 格式正确
        model_id = converted.get("model", "")
        
        # 2. 将 providerOptions 中的参数提升到顶层（如果 Vercel Gateway 需要）
        provider_options = converted.get("providerOptions", {})
        provider_key = provider.value
        
        if provider_key in provider_options:
            opts = provider_options[provider_key]
            
            # 对于 Anthropic，thinking 参数需要在顶层
            if provider == ProviderType.ANTHROPIC and "thinking" in opts:
                # Vercel AI Gateway 可能期望 thinking 在顶层
                # 保持在 providerOptions 中，让 Gateway 自己处理
                pass
            
            # 对于 OpenAI，reasoningEffort 需要在顶层
            if provider == ProviderType.OPENAI and "reasoningEffort" in opts:
                # 同样保持在 providerOptions 中
                pass
        
        return converted


# 全局转换器实例
converter = ParamsConverter()


def convert_request(body: Dict[str, Any]) -> Dict[str, Any]:
    """便捷函数：转换请求体"""
    return converter.convert_for_vercel_gateway(body)


def normalize_model(model_id: str) -> str:
    """便捷函数：标准化模型 ID"""
    return converter.normalize_model_id(model_id)
