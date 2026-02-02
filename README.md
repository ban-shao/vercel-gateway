# Vercel Gateway

Vercel AI Gateway 密钥池管理与代理服务 - 配合 NewAPI / Cherry Studio 使用

## 📋 功能特性

- ✅ **密钥池轮换** - 多个 Vercel API Key 自动轮换使用
- ✅ **故障转移** - 额度耗尽自动切换下一个密钥
- ✅ **余额检查** - 批量检查密钥余额，自动筛选有效密钥
- ✅ **每日定时任务** - 自动刷新额度 → 检查余额 → 更新密钥列表
- ✅ **高余额优先** - 自动使用 $3+ 高余额密钥
- ✅ **流式响应** - 完整支持 SSE 流式输出
- ✅ **systemd 服务** - 开机自启、崩溃自动重启
- ✅ **Cherry Studio 参数转换** - 自动处理 providerOptions 参数
- ✅ **模型列表 API** - 兼容 OpenAI /v1/models 端点

## 🏗️ 架构

```
客户端 → NewAPI/Cherry Studio → vercel-gateway (本项目) → ai-gateway.vercel.sh
                                        ↑
                                   密钥池轮换
                                   参数转换
                                   故障转移
                                   流式代理
```

## 🎯 Cherry Studio 参数转换

本项目支持自动转换 Cherry Studio 发送的参数格式，让各种模型的特殊参数（如思考强度）能够正确传递到 Vercel AI Gateway。

### 支持的参数类型

| Provider | 参数格式 | 说明 |
|----------|----------|------|
| **Anthropic/Claude** | `thinking: { type, budgetTokens }` | Claude 4.x 思考模式 |
| **OpenAI** | `reasoningEffort: low/medium/high` | o1/o3/o4 推理强度 |
| **Google/Gemini** | `thinkingConfig: { thinkingBudget, includeThoughts }` | Gemini 2.5 思考配置 |
| **XAI/Grok** | `reasoningEffort: low/high` | Grok 推理强度 |
| **DeepSeek** | `thinking: { type }` 或 `enable_thinking` | DeepSeek R1 |
| **Qwen** | `enable_thinking, thinking_budget` | QwQ/Qwen3 |

### 参数转换示例

**Cherry Studio 发送的请求：**
```json
{
  "model": "claude-sonnet-4",
  "messages": [...],
  "providerOptions": {
    "anthropic": {
      "thinking": {
        "type": "enabled",
        "budgetTokens": 8192
      }
    }
  }
}
```

**转换后发送到 Vercel AI Gateway：**
```json
{
  "model": "anthropic/claude-sonnet-4-20250514",
  "messages": [...],
  "providerOptions": {
    "anthropic": {
      "thinking": {
        "type": "enabled",
        "budget_tokens": 8192
      }
    }
  }
}
```

## ⏰ 每日定时任务

每天凌晨 00:00 自动执行完整流程：

```
┌─────────────────────────────────────────────────────────────────┐
│                      每日定时任务流程                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  00:00  ┌──────────────────┐                                    │
│    │    │ 1. 刷新所有密钥   │  对 total_keys.txt 中每个密钥      │
│    │    │    (key_refresher)│  发送最小请求，触发额度刷新        │
│    ▼    └────────┬─────────┘                                    │
│                  │                                               │
│  等待30秒        │ 让刷新生效                                    │
│                  │                                               │
│    │    ┌────────▼─────────┐                                    │
│    │    │ 2. 检查所有余额   │  检查每个密钥的当前余额            │
│    │    │    (billing_check)│  按余额分类保存                    │
│    ▼    └────────┬─────────┘                                    │
│                  │                                               │
│         ┌────────▼─────────┐                                    │
│         │ 生成分类文件:     │                                    │
│         │ • keys_high.txt   │  $3+ 高余额 ← 代理服务优先使用     │
│         │ • keys_medium_*.txt│  $1-3 中余额                      │
│         │ • active_keys.txt │  所有有效密钥                      │
│         └────────┬─────────┘                                    │
│                  │                                               │
│    │    ┌────────▼─────────┐                                    │
│    │    │ 3. 通知代理热加载 │  调用 /admin/reload                │
│    ▼    │    (proxy reload) │  代理服务重新加载 keys_high.txt    │
│         └──────────────────┘                                    │
│                                                                  │
│  ✅ 完成！代理服务现在使用最新的高余额密钥                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 目录结构

```
/opt/vercel-gateway/
├── .env                          # 环境变量配置
├── requirements.txt              # Python 依赖
├── src/
│   ├── proxy/
│   │   ├── server.py             # FastAPI 代理服务
│   │   └── params/               # 参数转换模块
│   │       ├── __init__.py
│   │       ├── converter.py      # 核心转换逻辑
│   │       ├── models.py         # 模型配置
│   │       └── reasoning.py      # 推理参数处理
│   ├── checker/
│   │   └── billing_checker.py    # 余额检查工具
│   ├── refresher/
│   │   └── key_refresher.py      # 密钥刷新工具
│   └── daily_task.py             # 每日定时任务（完整流程）
├── data/
│   ├── keys/
│   │   ├── total_keys.txt        # 原始密钥（手动维护）
│   │   ├── active_keys.txt       # 有效密钥（自动生成）
│   │   ├── keys_high.txt         # $3+ 高余额（代理优先使用）
│   │   ├── keys_medium_high.txt  # $2-3
│   │   └── keys_medium.txt       # $1-2
│   └── reports/
│       ├── billing_report.json
│       └── refresh_report.json
├── scripts/
│   ├── install.sh                # 一键安装脚本
│   ├── start.sh
│   ├── stop.sh
│   ├── status.sh
│   ├── check.sh                  # 检查余额
│   ├── refresh.sh                # 刷新密钥
│   └── daily.sh                  # 手动执行每日任务
└── logs/
    ├── daily_task.log            # 每日任务日志
    └── refresher.log
```

## 🚀 快速部署

### 一键安装

```bash
# 克隆仓库
git clone https://github.com/ban-shao/vercel-gateway.git /opt/vercel-gateway

# 执行安装脚本
cd /opt/vercel-gateway
chmod +x scripts/install.sh
sudo ./scripts/install.sh
```

### 部署后配置

```bash
# 1. 添加密钥（每行一个）
nano /opt/vercel-gateway/data/keys/total_keys.txt

# 2. 检查余额，生成分类文件
/opt/vercel-gateway/scripts/check.sh

# 3. 启动服务
/opt/vercel-gateway/scripts/start.sh

# 4. 查看状态
/opt/vercel-gateway/scripts/status.sh
```

## ⚙️ 配置说明

### .env 文件

```bash
# 代理服务端口
PROXY_PORT=3001

# 访问密钥（NewAPI 渠道中使用）
AUTH_KEY=your_secure_password

# 密钥冷却时间（小时）
KEY_COOLDOWN_HOURS=24

# 日志级别
LOG_LEVEL=info

# 是否启用参数转换（默认启用）
ENABLE_PARAMS_CONVERSION=true
```

## 📡 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/v1/models` | GET | 获取支持的模型列表 |
| `/v1/models/{model_id}` | GET | 获取单个模型信息 |
| `/admin/status` | GET | 查看密钥状态 |
| `/admin/reset` | POST | 重置所有密钥 |
| `/admin/reload` | POST | 重新加载密钥文件 |
| `/v1/*` | ALL | 代理到 Vercel |

### 模型列表 API

```bash
# 获取所有模型
curl -H "Authorization: Bearer YOUR_AUTH_KEY" \
  http://127.0.0.1:3001/v1/models

# 按 Provider 过滤
curl -H "Authorization: Bearer YOUR_AUTH_KEY" \
  "http://127.0.0.1:3001/v1/models?provider=anthropic"
```

返回格式（OpenAI 兼容）：
```json
{
  "object": "list",
  "data": [
    {
      "id": "anthropic/claude-sonnet-4-20250514",
      "object": "model",
      "created": 1700000000,
      "owned_by": "anthropic",
      "_extra": {
        "name": "Claude Sonnet 4",
        "capabilities": {
          "thinking": true,
          "vision": true,
          "tools": true
        }
      }
    }
  ]
}
```

## 🔗 NewAPI 渠道配置

| 配置项 | 值 |
|--------|-----|
| 类型 | OpenAI |
| Base URL | `http://127.0.0.1:3001` |
| API Key | `.env` 中的 `AUTH_KEY` |
| 模型 | `claude-sonnet-4`, `claude-3.5-sonnet` 等 |

## 🍒 Cherry Studio 配置

| 配置项 | 值 |
|--------|-----|
| API 地址 | `http://127.0.0.1:3001/v1/ai#` |
| API 密钥 | `.env` 中的 `AUTH_KEY` |
| 模型 | 从模型列表中选择或手动添加 |

### 支持的模型

**Anthropic:**
- `claude-sonnet-4` / `anthropic/claude-sonnet-4-20250514`
- `claude-opus-4` / `anthropic/claude-opus-4-20250514`
- `claude-3.5-sonnet` / `anthropic/claude-3-5-sonnet-20241022`
- `claude-3.5-haiku` / `anthropic/claude-3-5-haiku-20241022`

**OpenAI:**
- `gpt-4o` / `openai/gpt-4o`
- `gpt-4o-mini` / `openai/gpt-4o-mini`
- `o1` / `openai/o1`
- `o3` / `openai/o3`
- `o4-mini` / `openai/o4-mini`

**Google:**
- `gemini-2.5-pro` / `google/gemini-2.5-pro-preview-06-05`
- `gemini-2.5-flash` / `google/gemini-2.5-flash-preview-05-20`

**XAI:**
- `grok-3` / `xai/grok-3`
- `grok-3-mini` / `xai/grok-3-mini`

**DeepSeek:**
- `deepseek-r1` / `deepseek/deepseek-r1`
- `deepseek-chat` / `deepseek/deepseek-chat`

## 📊 常用命令

```bash
# 查看服务状态
/opt/vercel-gateway/scripts/status.sh

# 检查密钥余额
/opt/vercel-gateway/scripts/check.sh

# 手动刷新密钥
/opt/vercel-gateway/scripts/refresh.sh

# 手动执行每日完整任务（刷新 + 检查 + 热加载）
/opt/vercel-gateway/scripts/daily.sh

# 查看每日任务日志
tail -f /opt/vercel-gateway/logs/daily_task.log

# 查看代理服务日志
journalctl -u vercel-proxy -f

# 查看定时任务状态
systemctl list-timers vercel-daily.timer

# 重启服务
sudo systemctl restart vercel-proxy
```

## 📝 License

MIT
