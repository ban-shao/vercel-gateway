# Vercel Gateway

Vercel AI Gateway 密钥池管理与代理服务 - 配合 NewAPI 使用

## 📋 功能特性

- ✅ **密钥池轮换** - 多个 Vercel API Key 自动轮换使用
- ✅ **故障转移** - 额度耗尽自动切换下一个密钥
- ✅ **余额检查** - 批量检查密钥余额，自动筛选有效密钥
- ✅ **定时刷新** - 每日自动触发密钥额度刷新
- ✅ **流式响应** - 完整支持 SSE 流式输出
- ✅ **systemd 服务** - 开机自启、崩溃自动重启

## 🏗️ 架构

```
客户端 → NewAPI → vercel-gateway (本项目) → ai-gateway.vercel.sh
                        ↑
                   密钥池轮换
                   故障转移
                   流式代理
```

## 📁 目录结构

```
/opt/vercel-gateway/
├── .env                          # 环境变量配置
├── requirements.txt              # Python 依赖
├── src/
│   ├── proxy/
│   │   └── server.py             # FastAPI 代理服务
│   ├── checker/
│   │   └── billing_checker.py    # 余额检查工具
│   └── refresher/
│       └── key_refresher.py      # 密钥刷新工具
├── data/
│   ├── keys/
│   │   ├── total_keys.txt        # 原始密钥（手动维护）
│   │   └── active_keys.txt       # 有效密钥（自动生成）
│   └── reports/
│       ├── billing_report.json
│       └── refresh_report.json
├── scripts/
│   ├── install.sh                # 一键安装脚本
│   ├── start.sh
│   ├── stop.sh
│   └── status.sh
├── logs/
└── systemd/
    ├── vercel-proxy.service
    └── vercel-refresh.timer
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

### 手动安装

```bash
# 1. 创建目录
sudo mkdir -p /opt/vercel-gateway
cd /opt/vercel-gateway

# 2. 安装依赖
pip3 install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
nano .env

# 4. 导入密钥
nano data/keys/total_keys.txt

# 5. 检查余额
python3 src/checker/billing_checker.py

# 6. 启动服务
sudo systemctl start vercel-proxy
sudo systemctl enable vercel-proxy
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
```

## 📡 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/admin/status` | GET | 查看密钥状态 |
| `/admin/reset` | POST | 重置所有密钥 |
| `/admin/reload` | POST | 重新加载密钥 |
| `/v1/*` | ALL | 代理到 Vercel |

## 🔗 NewAPI 渠道配置

| 配置项 | 值 |
|--------|-----|
| 类型 | OpenAI |
| Base URL | `http://127.0.0.1:3001` |
| API Key | `.env` 中的 `AUTH_KEY` |
| 模型 | `claude-sonnet-4`, `claude-3.5-sonnet` 等 |

## 📊 常用命令

```bash
# 查看服务状态
/opt/vercel-gateway/scripts/status.sh

# 检查密钥余额
/opt/vercel-gateway/scripts/check_balance.sh

# 手动刷新密钥
/opt/vercel-gateway/scripts/refresh_keys.sh

# 查看日志
tail -f /opt/vercel-gateway/logs/proxy.log

# 重启服务
sudo systemctl restart vercel-proxy
```

## 📝 License

MIT
