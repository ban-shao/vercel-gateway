// ============================================================
// Express 服务器
// ============================================================

import express, { Request, Response, NextFunction } from 'express';
import { config } from './config.js';
import { logger } from './logger.js';
import { keyManager } from './key-manager.js';
import { 
  executeStreamText, 
  executeGenerateText,
  detectProvider,
  supportsThinking
} from './ai-provider.js';
import { OpenAIRequest, OpenAIResponse, OpenAIStreamChunk } from './types.js';

const app = express();

// 中间件
app.use(express.json({ limit: '50mb' }));

// 认证中间件
function authMiddleware(req: Request, res: Response, next: NextFunction): void {
  // 健康检查不需要认证
  if (req.path === '/health' || req.path === '/') {
    next();
    return;
  }
  
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith('Bearer ')) {
    res.status(401).json({ error: 'Unauthorized' });
    return;
  }
  
  const token = authHeader.slice(7);
  if (config.authKey && token !== config.authKey) {
    res.status(401).json({ error: 'Invalid API key' });
    return;
  }
  
  next();
}

app.use(authMiddleware);

// 健康检查
app.get('/health', (_req, res) => {
  const stats = keyManager.getStats();
  res.json({
    status: 'ok',
    version: '4.0.0',
    keys: stats,
  });
});

app.get('/', (_req, res) => {
  res.json({
    service: 'Vercel Gateway',
    version: '4.0.0',
    description: '使用 Vercel AI SDK 的智能代理服务',
  });
});

// 模型列表缓存
let modelsCache: { data: unknown; timestamp: number } | null = null;

// 获取模型列表
app.get('/v1/models', async (req, res) => {
  try {
    const refresh = req.query.refresh === 'true';
    const provider = req.query.provider as string | undefined;
    
    // 检查缓存
    const now = Date.now();
    if (!refresh && modelsCache && (now - modelsCache.timestamp) < config.modelsCacheTTL * 1000) {
      let data = modelsCache.data as { object: string; data: { id: string }[] };
      
      // Provider 过滤
      if (provider) {
        data = {
          ...data,
          data: data.data.filter(m => m.id.toLowerCase().includes(provider.toLowerCase()))
        };
      }
      
      res.json(data);
      return;
    }
    
    // 从上游获取模型列表
    const apiKey = keyManager.getNextKey();
    if (!apiKey) {
      res.status(503).json({ error: 'No available API keys' });
      return;
    }
    
    const response = await fetch(`${config.upstreamGateway}/v1/models`, {
      headers: {
        'Authorization': `Bearer ${apiKey}`,
      },
    });
    
    if (!response.ok) {
      throw new Error(`上游返回错误: ${response.status}`);
    }
    
    const data = await response.json();
    
    // 更新缓存
    modelsCache = { data, timestamp: now };
    
    // Provider 过滤
    if (provider) {
      const filtered = {
        ...(data as { object: string; data: { id: string }[] }),
        data: (data as { data: { id: string }[] }).data.filter((m: { id: string }) => 
          m.id.toLowerCase().includes(provider.toLowerCase())
        )
      };
      res.json(filtered);
      return;
    }
    
    res.json(data);
  } catch (error) {
    logger.error(`获取模型列表失败: ${error}`);
    res.status(500).json({ error: 'Failed to fetch models' });
  }
});

// 获取单个模型
app.get('/v1/models/:modelId', async (req, res) => {
  try {
    const { modelId } = req.params;
    const provider = detectProvider(modelId);
    const hasThinking = supportsThinking(modelId);
    
    res.json({
      id: modelId,
      object: 'model',
      owned_by: provider,
      capabilities: {
        thinking: hasThinking,
        vision: true,
        tools: true,
      }
    });
  } catch (error) {
    logger.error(`获取模型详情失败: ${error}`);
    res.status(500).json({ error: 'Failed to fetch model' });
  }
});

// Chat Completions API
app.post('/v1/chat/completions', async (req: Request, res: Response) => {
  const request = req.body as OpenAIRequest;
  const startTime = Date.now();
  
  logger.info(`收到请求: model=${request.model}, stream=${request.stream}`);
  
  // 获取 API 密钥
  const apiKey = keyManager.getNextKey();
  if (!apiKey) {
    res.status(503).json({ error: 'No available API keys' });
    return;
  }
  
  try {
    if (request.stream) {
      // 流式响应
      res.setHeader('Content-Type', 'text/event-stream');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');
      
      const result = await executeStreamText(request, apiKey);
      
      const responseId = `chatcmpl-${Date.now()}`;
      const created = Math.floor(Date.now() / 1000);
      
      // 发送初始 chunk
      const initialChunk: OpenAIStreamChunk = {
        id: responseId,
        object: 'chat.completion.chunk',
        created,
        model: request.model,
        choices: [{
          index: 0,
          delta: { role: 'assistant' },
          finish_reason: null,
        }],
      };
      res.write(`data: ${JSON.stringify(initialChunk)}\n\n`);
      
      // 流式输出内容
      for await (const chunk of result.textStream) {
        const contentChunk: OpenAIStreamChunk = {
          id: responseId,
          object: 'chat.completion.chunk',
          created,
          model: request.model,
          choices: [{
            index: 0,
            delta: { content: chunk },
            finish_reason: null,
          }],
        };
        res.write(`data: ${JSON.stringify(contentChunk)}\n\n`);
      }
      
      // 发送结束 chunk
      const finalChunk: OpenAIStreamChunk = {
        id: responseId,
        object: 'chat.completion.chunk',
        created,
        model: request.model,
        choices: [{
          index: 0,
          delta: {},
          finish_reason: 'stop',
        }],
      };
      res.write(`data: ${JSON.stringify(finalChunk)}\n\n`);
      res.write('data: [DONE]\n\n');
      res.end();
      
      keyManager.markKeySuccess(apiKey);
      logger.info(`流式请求完成: ${Date.now() - startTime}ms`);
      
    } else {
      // 非流式响应
      const result = await executeGenerateText(request, apiKey);
      
      const response: OpenAIResponse = {
        id: `chatcmpl-${Date.now()}`,
        object: 'chat.completion',
        created: Math.floor(Date.now() / 1000),
        model: request.model,
        choices: [{
          index: 0,
          message: {
            role: 'assistant',
            content: result.text,
          },
          finish_reason: 'stop',
        }],
        usage: {
          prompt_tokens: result.usage?.promptTokens || 0,
          completion_tokens: result.usage?.completionTokens || 0,
          total_tokens: result.usage?.totalTokens || 0,
        },
      };
      
      res.json(response);
      
      keyManager.markKeySuccess(apiKey);
      logger.info(`非流式请求完成: ${Date.now() - startTime}ms`);
    }
  } catch (error: unknown) {
    logger.error(`请求失败: ${error}`);
    keyManager.markKeyFailed(apiKey);
    
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    
    // 检查是否需要重试
    if (errorMessage.includes('rate limit') || errorMessage.includes('quota')) {
      // 尝试使用另一个密钥重试
      const newApiKey = keyManager.getNextKey();
      if (newApiKey && newApiKey !== apiKey) {
        logger.info('尝试使用备用密钥重试...');
        // 递归重试（简化处理）
        req.headers.authorization = `Bearer ${newApiKey}`;
        return app.handle(req, res);
      }
    }
    
    res.status(500).json({
      error: {
        message: errorMessage,
        type: 'api_error',
        code: 'internal_error',
      },
    });
  }
});

// 兼容路由：/v1/ai/language-model
app.post('/v1/ai/language-model', (req, res) => {
  // 重定向到 chat/completions
  req.url = '/v1/chat/completions';
  app.handle(req, res);
});

// 启动服务器
export function startServer(): void {
  const stats = keyManager.getStats();
  
  console.log('');
  console.log('============================================================');
  console.log('   Vercel Gateway - TypeScript + AI SDK Edition');
  console.log('   版本: 4.0.0');
  console.log('============================================================');
  console.log(`   监听端口: ${config.port}`);
  console.log(`   已加载密钥: ${stats.total} 个`);
  console.log(`   冷却时间: ${config.cooldownHours} 小时`);
  console.log(`   认证密钥: ${config.authKey ? config.authKey.substring(0, 4) + '****' : '未设置'}`);
  console.log('============================================================');
  console.log('');
  console.log('   支持的参数转换:');
  console.log('   • Anthropic: thinking.budgetTokens');
  console.log('   • OpenAI: reasoningEffort');
  console.log('   • Google: thinkingConfig.thinkingBudget');
  console.log('   • XAI: reasoningEffort');
  console.log('');
  console.log('   输入格式: OpenAI 兼容');
  console.log('   • reasoning_effort: low | medium | high');
  console.log('   • thinking: { type, budget_tokens }');
  console.log('   • enable_thinking: boolean');
  console.log('============================================================');
  console.log('');
  
  app.listen(config.port, config.host, () => {
    logger.info(`服务器启动成功: http://${config.host}:${config.port}`);
  });
}
