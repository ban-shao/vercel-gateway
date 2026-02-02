// ============================================================
// 配置管理
// ============================================================

import dotenv from 'dotenv';
import { ProviderType } from './types.js';

dotenv.config();

export const config = {
  // 服务器配置
  port: parseInt(process.env.PORT || '3001', 10),
  host: process.env.HOST || '0.0.0.0',
  
  // 认证
  authKey: process.env.AUTH_KEY || '',
  
  // 密钥配置
  keysDir: process.env.KEYS_DIR || './data/keys',
  keysFile: process.env.KEYS_FILE || 'keys_high.txt',
  
  // 冷却时间（小时）
  cooldownHours: parseInt(process.env.COOLDOWN_HOURS || '24', 10),
  
  // 重试配置
  maxRetries: parseInt(process.env.MAX_RETRIES || '3', 10),
  
  // 上游 Vercel AI Gateway（用于获取模型列表）
  upstreamGateway: process.env.UPSTREAM_GATEWAY || 'https://ai-gateway.vercel.sh',
  
  // 模型列表缓存时间（秒）
  modelsCacheTTL: parseInt(process.env.MODELS_CACHE_TTL || '3600', 10),
  
  // 日志级别
  logLevel: process.env.LOG_LEVEL || 'info',
};

// 模型到 Provider 的映射
export const MODEL_PROVIDER_MAP: Record<string, ProviderType> = {
  // Anthropic
  'claude': 'anthropic',
  'claude-3': 'anthropic',
  'claude-4': 'anthropic',
  'claude-sonnet': 'anthropic',
  'claude-opus': 'anthropic',
  'claude-haiku': 'anthropic',
  
  // OpenAI
  'gpt': 'openai',
  'o1': 'openai',
  'o3': 'openai',
  'o4': 'openai',
  'chatgpt': 'openai',
  
  // Google
  'gemini': 'google',
  'gemma': 'google',
  
  // XAI
  'grok': 'xai',
};

// 支持思考/推理的模型
export const THINKING_MODELS: Record<string, { min: number; max: number }> = {
  // Anthropic Claude 4.x (Extended Thinking)
  'claude-sonnet-4': { min: 1024, max: 16000 },
  'claude-opus-4': { min: 1024, max: 32000 },
  'claude-3-7-sonnet': { min: 1024, max: 16000 },
  
  // OpenAI Reasoning Models
  'o1': { min: 1000, max: 100000 },
  'o1-mini': { min: 1000, max: 50000 },
  'o1-pro': { min: 1000, max: 200000 },
  'o3': { min: 1000, max: 100000 },
  'o3-mini': { min: 1000, max: 50000 },
  'o4-mini': { min: 1000, max: 50000 },
  
  // Google Gemini 2.x (Deep Think)
  'gemini-2.5-pro': { min: 1024, max: 16000 },
  'gemini-2.5-flash': { min: 1024, max: 8000 },
  'gemini-2.0-flash-thinking': { min: 1024, max: 8000 },
  
  // XAI Grok
  'grok-3': { min: 1024, max: 16000 },
  'grok-3-mini': { min: 1024, max: 8000 },
};

// 思考强度到 Token 预算的比例
export const EFFORT_RATIO: Record<string, number> = {
  'low': 0.25,
  'medium': 0.5,
  'high': 0.75,
  'auto': 0.5,
};
