# Vercel Gateway - TypeScript + AI SDK

使用官方 Vercel AI SDK 实现的智能代理服务，确保参数转换 100% 正确。

## ✨ 特性

- 🔄 **官方 AI SDK** - 使用 `@ai-sdk/*` 确保参数格式正确
- 🎯 **OpenAI 兼容** - 输入使用标准 OpenAI 格式
- 🧠 **智能转换** - 自动将思考参数转换为各 Provider 格式
- 🔑 **密钥池** - 内置密钥池管理和轮换
- ⚡ **故障转移** - 自动切换到备用密钥

## 🚀 快速开始

```bash
# 安装依赖
cd ts
npm install

# 配置环境变量
cp .env.example .env
nano .env

# 开发模式
npm run dev

# 生产模式
npm run build
npm start
```

## 📋 API 端点

### Chat Completions

```bash
POST /v1/chat/completions
```

**请求格式（OpenAI 兼容 + 扩展）：**

```json
{
  "model": "claude-sonnet-4",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "stream": true,
  "temperature": 0.7,
  "max_tokens": 4096,
  
  // 思考/推理参数（任选其一）
  "reasoning_effort": "high",
  // 或
  "thinking": {
    "type": "enabled",
    "budget_tokens": 8192
  },
  // 或
  "enable_thinking": true,
  "thinking_budget": 8192
}
```

### 参数转换说明

| 输入参数 | Anthropic | OpenAI | Google | XAI |
|---------|-----------|--------|--------|-----|
| `reasoning_effort: "high"` | `thinking.budgetTokens=12000` | `reasoningEffort="high"` | `thinkingConfig.thinkingBudget=12000` | `reasoningEffort="high"` |
| `thinking.type: "enabled"` | `thinking.type="enabled"` | `reasoningEffort="high"` | `thinkingConfig` | `reasoningEffort="high"` |
| `enable_thinking: true` | `thinking.type="enabled"` | `reasoningEffort="medium"` | `thinkingConfig` | `reasoningEffort="high"` |

### 模型列表

```bash
GET /v1/models
GET /v1/models?provider=anthropic
GET /v1/models?refresh=true
```

## 🔧 配置说明

| 变量 | 说明 | 默认值 |
|-----|------|-------|
| `PORT` | 服务端口 | 3001 |
| `AUTH_KEY` | API 认证密钥 | - |
| `KEYS_DIR` | 密钥文件目录 | ./data/keys |
| `KEYS_FILE` | 密钥文件名 | keys_high.txt |
| `COOLDOWN_HOURS` | 失败冷却时间 | 24 |
| `UPSTREAM_GATEWAY` | 上游地址 | https://ai-gateway.vercel.sh |

## 📦 技术栈

- **运行时**: Node.js 18+
- **框架**: Express
- **AI SDK**: @ai-sdk/anthropic, @ai-sdk/openai, @ai-sdk/google, @ai-sdk/xai
- **语言**: TypeScript

## 🔗 架构

```
用户（OpenAI 格式）
        ↓
    NewAPI
        ↓
Vercel Gateway TS（@ai-sdk 转换）
        ↓
Vercel AI Gateway
        ↓
各 AI Provider
```
