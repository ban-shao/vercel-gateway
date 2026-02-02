// ============================================================
// AI Provider - 使用 Vercel AI SDK
// ============================================================

import { streamText, generateText, CoreMessage, LanguageModel } from 'ai';
import { createAnthropic } from '@ai-sdk/anthropic';
import { createOpenAI } from '@ai-sdk/openai';
import { createGoogleGenerativeAI } from '@ai-sdk/google';
import { createXai } from '@ai-sdk/xai';
import { config, MODEL_PROVIDER_MAP, THINKING_MODELS, EFFORT_RATIO } from './config.js';
import { logger } from './logger.js';
import { OpenAIRequest, OpenAIMessage, ProviderType } from './types.js';

/**
 * 检测模型对应的 Provider
 */
export function detectProvider(modelId: string): ProviderType {
  const lowerModel = modelId.toLowerCase();
  
  for (const [prefix, provider] of Object.entries(MODEL_PROVIDER_MAP)) {
    if (lowerModel.includes(prefix)) {
      return provider;
    }
  }
  
  // 默认使用 OpenAI
  return 'openai';
}

/**
 * 检查模型是否支持思考/推理
 */
export function supportsThinking(modelId: string): boolean {
  const lowerModel = modelId.toLowerCase();
  return Object.keys(THINKING_MODELS).some(m => lowerModel.includes(m));
}

/**
 * 获取思考 Token 限制
 */
export function getThinkingLimits(modelId: string): { min: number; max: number } | null {
  const lowerModel = modelId.toLowerCase();
  for (const [model, limits] of Object.entries(THINKING_MODELS)) {
    if (lowerModel.includes(model)) {
      return limits;
    }
  }
  return null;
}

/**
 * 计算思考预算 Token
 */
export function calculateThinkingBudget(
  modelId: string,
  effort: 'low' | 'medium' | 'high' | 'auto' = 'medium'
): number {
  const limits = getThinkingLimits(modelId);
  if (!limits) return 8192; // 默认值
  
  const ratio = EFFORT_RATIO[effort] || 0.5;
  return Math.floor(limits.min + (limits.max - limits.min) * ratio);
}

/**
 * 创建 AI Provider 实例
 */
export function createProvider(provider: ProviderType, apiKey: string) {
  const baseURL = `${config.upstreamGateway}/v1`;
  
  switch (provider) {
    case 'anthropic':
      return createAnthropic({
        apiKey,
        baseURL: `${baseURL}/anthropic`,
      });
    case 'openai':
      return createOpenAI({
        apiKey,
        baseURL: `${baseURL}/openai`,
      });
    case 'google':
      return createGoogleGenerativeAI({
        apiKey,
        baseURL: `${baseURL}/google`,
      });
    case 'xai':
      return createXai({
        apiKey,
        baseURL: `${baseURL}/xai`,
      });
    default:
      return createOpenAI({
        apiKey,
        baseURL: `${baseURL}/openai`,
      });
  }
}

/**
 * 转换 OpenAI 消息格式为 AI SDK 格式
 */
export function convertMessages(messages: OpenAIMessage[]): CoreMessage[] {
  return messages.map(msg => {
    // 处理多模态内容
    if (Array.isArray(msg.content)) {
      const parts = msg.content.map(part => {
        if (part.type === 'text') {
          return { type: 'text' as const, text: part.text || '' };
        } else if (part.type === 'image_url' && part.image_url) {
          return { type: 'image' as const, image: part.image_url.url };
        }
        return { type: 'text' as const, text: '' };
      });
      
      return {
        role: msg.role as 'user' | 'assistant' | 'system',
        content: parts,
      };
    }
    
    return {
      role: msg.role as 'user' | 'assistant' | 'system',
      content: msg.content as string,
    };
  });
}

/**
 * 构建 Provider 特定选项
 */
export function buildProviderOptions(
  provider: ProviderType,
  modelId: string,
  request: OpenAIRequest
): Record<string, Record<string, unknown>> {
  const options: Record<string, Record<string, unknown>> = {};
  
  // 检查是否需要启用思考/推理
  const enableThinking = 
    request.thinking?.type === 'enabled' ||
    request.enable_thinking === true ||
    (request.reasoning_effort && supportsThinking(modelId));
  
  const effort = request.reasoning_effort || 
    (request.thinking?.type === 'enabled' ? 'high' : 'medium');
  
  const budgetTokens = request.thinking?.budget_tokens || 
    request.thinking_budget ||
    calculateThinkingBudget(modelId, effort);
  
  switch (provider) {
    case 'anthropic':
      if (enableThinking && supportsThinking(modelId)) {
        options['anthropic'] = {
          thinking: {
            type: 'enabled',
            budgetTokens: budgetTokens,
          },
        };
        logger.debug(`Anthropic thinking enabled: budgetTokens=${budgetTokens}`);
      }
      break;
      
    case 'openai':
      if (enableThinking && supportsThinking(modelId)) {
        options['openai'] = {
          reasoningEffort: effort,
        };
        logger.debug(`OpenAI reasoning enabled: effort=${effort}`);
      }
      break;
      
    case 'google':
      if (enableThinking && supportsThinking(modelId)) {
        options['google'] = {
          thinkingConfig: {
            thinkingBudget: budgetTokens,
            includeThoughts: true,
          },
        };
        logger.debug(`Google thinking enabled: budget=${budgetTokens}`);
      }
      break;
      
    case 'xai':
      if (enableThinking && supportsThinking(modelId)) {
        options['xai'] = {
          reasoningEffort: effort === 'low' ? 'low' : 'high',
        };
        logger.debug(`XAI reasoning enabled: effort=${effort}`);
      }
      break;
  }
  
  return options;
}

/**
 * 获取模型实例
 */
export function getModel(
  provider: ProviderType,
  modelId: string,
  apiKey: string
): LanguageModel {
  const aiProvider = createProvider(provider, apiKey);
  
  // 提取实际的模型名称（去掉 provider 前缀）
  let actualModelId = modelId;
  if (modelId.includes('/')) {
    actualModelId = modelId.split('/').pop() || modelId;
  }
  
  // 使用 AI SDK 创建模型
  switch (provider) {
    case 'anthropic':
      return (aiProvider as ReturnType<typeof createAnthropic>)(actualModelId);
    case 'openai':
      return (aiProvider as ReturnType<typeof createOpenAI>)(actualModelId);
    case 'google':
      return (aiProvider as ReturnType<typeof createGoogleGenerativeAI>)(actualModelId);
    case 'xai':
      return (aiProvider as ReturnType<typeof createXai>)(actualModelId);
    default:
      return (aiProvider as ReturnType<typeof createOpenAI>)(actualModelId);
  }
}

/**
 * 执行流式文本生成
 */
export async function executeStreamText(
  request: OpenAIRequest,
  apiKey: string
) {
  const provider = detectProvider(request.model);
  const model = getModel(provider, request.model, apiKey);
  const messages = convertMessages(request.messages);
  const providerOptions = buildProviderOptions(provider, request.model, request);
  
  logger.info(`执行流式请求: model=${request.model}, provider=${provider}`);
  
  const result = await streamText({
    model,
    messages,
    maxTokens: request.max_tokens,
    temperature: request.temperature,
    topP: request.top_p,
    presencePenalty: request.presence_penalty,
    frequencyPenalty: request.frequency_penalty,
    stopSequences: typeof request.stop === 'string' ? [request.stop] : request.stop,
    seed: request.seed,
    providerOptions,
  });
  
  return result;
}

/**
 * 执行非流式文本生成
 */
export async function executeGenerateText(
  request: OpenAIRequest,
  apiKey: string
) {
  const provider = detectProvider(request.model);
  const model = getModel(provider, request.model, apiKey);
  const messages = convertMessages(request.messages);
  const providerOptions = buildProviderOptions(provider, request.model, request);
  
  logger.info(`执行非流式请求: model=${request.model}, provider=${provider}`);
  
  const result = await generateText({
    model,
    messages,
    maxTokens: request.max_tokens,
    temperature: request.temperature,
    topP: request.top_p,
    presencePenalty: request.presence_penalty,
    frequencyPenalty: request.frequency_penalty,
    stopSequences: typeof request.stop === 'string' ? [request.stop] : request.stop,
    seed: request.seed,
    providerOptions,
  });
  
  return result;
}
