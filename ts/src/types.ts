// ============================================================
// 类型定义
// ============================================================

// OpenAI 兼容的消息格式
export interface OpenAIMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string | ContentPart[];
  name?: string;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
}

export interface ContentPart {
  type: 'text' | 'image_url';
  text?: string;
  image_url?: {
    url: string;
    detail?: 'auto' | 'low' | 'high';
  };
}

export interface ToolCall {
  id: string;
  type: 'function';
  function: {
    name: string;
    arguments: string;
  };
}

// OpenAI 兼容的请求格式
export interface OpenAIRequest {
  model: string;
  messages: OpenAIMessage[];
  stream?: boolean;
  temperature?: number;
  top_p?: number;
  max_tokens?: number;
  presence_penalty?: number;
  frequency_penalty?: number;
  stop?: string | string[];
  n?: number;
  seed?: number;
  
  // 扩展参数 - 思考/推理
  reasoning_effort?: 'low' | 'medium' | 'high';
  thinking?: {
    type: 'enabled' | 'disabled' | 'auto';
    budget_tokens?: number;
  };
  enable_thinking?: boolean;
  thinking_budget?: number;
  
  // 工具调用
  tools?: Tool[];
  tool_choice?: 'auto' | 'none' | 'required' | { type: 'function'; function: { name: string } };
  
  // 其他扩展
  response_format?: { type: 'text' | 'json_object' };
}

export interface Tool {
  type: 'function';
  function: {
    name: string;
    description?: string;
    parameters?: Record<string, unknown>;
  };
}

// Provider 类型
export type ProviderType = 'anthropic' | 'openai' | 'google' | 'xai';

// 密钥信息
export interface KeyInfo {
  key: string;
  provider: ProviderType;
  lastUsed?: Date;
  failCount: number;
  cooldownUntil?: Date;
}

// 模型映射
export interface ModelMapping {
  id: string;
  provider: ProviderType;
  aiSdkModel: string;
  displayName: string;
  supportsThinking?: boolean;
  supportsVision?: boolean;
  supportsTools?: boolean;
  maxTokens?: number;
  thinkingTokenLimits?: {
    min: number;
    max: number;
  };
}

// 响应格式
export interface OpenAIResponse {
  id: string;
  object: 'chat.completion';
  created: number;
  model: string;
  choices: {
    index: number;
    message: {
      role: 'assistant';
      content: string | null;
      tool_calls?: ToolCall[];
    };
    finish_reason: 'stop' | 'length' | 'tool_calls' | 'content_filter';
  }[];
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

// 流式响应块
export interface OpenAIStreamChunk {
  id: string;
  object: 'chat.completion.chunk';
  created: number;
  model: string;
  choices: {
    index: number;
    delta: {
      role?: 'assistant';
      content?: string;
      tool_calls?: Partial<ToolCall>[];
    };
    finish_reason: 'stop' | 'length' | 'tool_calls' | 'content_filter' | null;
  }[];
}
