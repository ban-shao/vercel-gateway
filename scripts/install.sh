#!/bin/bash
# Vercel Gateway 一键安装脚本
# 适用于 Ubuntu 22.04+

set -e

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
INSTALL_DIR="/opt/vercel-gateway"
SERVICE_USER="root"

echo -e "${BLUE}"
echo "=============================================="
echo "   Vercel Gateway 安装脚本"
echo "=============================================="
echo -e "${NC}"

# 检查是否为 root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 sudo 运行此脚本${NC}"
    exit 1
fi

# 1. 检查 Python
echo -e "\n${YELLOW}[1/6] 检查 Python 环境...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}正在安装 Python3...${NC}"
    apt-get update
    apt-get install -y python3 python3-pip python3-venv
fi
PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✓ $PYTHON_VERSION${NC}"

# 2. 创建目录结构
echo -e "\n${YELLOW}[2/6] 创建目录结构...${NC}"
mkdir -p $INSTALL_DIR/{src/{proxy,checker,refresher},scripts,data/{keys,reports},logs,systemd}
echo -e "${GREEN}✓ 目录结构已创建${NC}"

# 3. 安装 Python 依赖
echo -e "\n${YELLOW}[3/6] 安装 Python 依赖...${NC}"
cd $INSTALL_DIR
pip3 install -q fastapi uvicorn httpx python-dotenv requests
echo -e "${GREEN}✓ 依赖安装完成${NC}"

# 4. 创建配置文件
echo -e "\n${YELLOW}[4/6] 创建配置文件...${NC}"
if [ ! -f "$INSTALL_DIR/.env" ]; then
    # 生成随机 AUTH_KEY
    AUTH_KEY=$(openssl rand -hex 16)
    
    cat > $INSTALL_DIR/.env << EOF
# Vercel Gateway 配置
PROXY_PORT=3001
AUTH_KEY=$AUTH_KEY
KEY_COOLDOWN_HOURS=24
LOG_LEVEL=info
EOF
    echo -e "${GREEN}✓ 配置文件已创建${NC}"
    echo -e "${YELLOW}  AUTH_KEY: ${GREEN}$AUTH_KEY${NC}"
else
    echo -e "${GREEN}✓ 配置文件已存在，跳过${NC}"
    AUTH_KEY=$(grep AUTH_KEY $INSTALL_DIR/.env | cut -d'=' -f2)
fi

# 5. 安装 systemd 服务
echo -e "\n${YELLOW}[5/6] 配置 systemd 服务...${NC}"

# 代理服务
cat > /etc/systemd/system/vercel-proxy.service << EOF
[Unit]
Description=Vercel Gateway Proxy Service
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 -m uvicorn src.proxy.server:app --host 0.0.0.0 --port 3001 --log-level info
Restart=always
RestartSec=5
Environment="PYTHONPATH=$INSTALL_DIR"

[Install]
WantedBy=multi-user.target
EOF

# 每日定时任务服务（完整流程：刷新 -> 检查 -> 热加载）
cat > /etc/systemd/system/vercel-daily.service << EOF
[Unit]
Description=Vercel Gateway Daily Task (Refresh + Check + Reload)

[Service]
Type=oneshot
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/src/daily_task.py
Environment="PYTHONPATH=$INSTALL_DIR"
# 超时设置：最多运行 2 小时
TimeoutStartSec=7200
EOF

# 定时器（每天凌晨 0 点执行）
cat > /etc/systemd/system/vercel-daily.timer << EOF
[Unit]
Description=Daily Vercel Gateway Task (Refresh + Check)

[Timer]
# 每天凌晨 00:00 执行
OnCalendar=*-*-* 00:00:00
# 如果错过了执行时间（如服务器关机），开机后立即补执行
Persistent=true
# 随机延迟 0-5 分钟，避免并发
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
EOF

# 删除旧的服务文件（如果存在）
rm -f /etc/systemd/system/vercel-refresh.service
rm -f /etc/systemd/system/vercel-refresh.timer

# 重载 systemd
systemctl daemon-reload
systemctl enable vercel-proxy
systemctl enable vercel-daily.timer

echo -e "${GREEN}✓ systemd 服务已配置${NC}"
echo -e "${YELLOW}  每日定时任务: 凌晨 00:00 自动执行${NC}"

# 6. 创建快捷脚本
echo -e "\n${YELLOW}[6/6] 创建管理脚本...${NC}"

# start.sh
cat > $INSTALL_DIR/scripts/start.sh << 'EOF'
#!/bin/bash
echo "启动 Vercel Gateway..."
sudo systemctl start vercel-proxy
sudo systemctl start vercel-daily.timer
sleep 2
sudo systemctl status vercel-proxy --no-pager -l
echo ""
echo "定时任务状态:"
sudo systemctl status vercel-daily.timer --no-pager
EOF

# stop.sh
cat > $INSTALL_DIR/scripts/stop.sh << 'EOF'
#!/bin/bash
echo "停止 Vercel Gateway..."
sudo systemctl stop vercel-proxy
echo "✓ 已停止"
EOF

# restart.sh
cat > $INSTALL_DIR/scripts/restart.sh << 'EOF'
#!/bin/bash
echo "重启 Vercel Gateway..."
sudo systemctl restart vercel-proxy
sleep 2
sudo systemctl status vercel-proxy --no-pager -l
EOF

# status.sh
cat > $INSTALL_DIR/scripts/status.sh << 'EOF'
#!/bin/bash
echo "=========================================="
echo "   Vercel Gateway 状态"
echo "=========================================="
echo ""
echo "📡 服务状态:"
systemctl is-active vercel-proxy &>/dev/null && echo "  代理服务: ✅ 运行中" || echo "  代理服务: ❌ 未运行"
systemctl is-active vercel-daily.timer &>/dev/null && echo "  每日任务: ✅ 已启用" || echo "  每日任务: ❌ 未启用"
echo ""
echo "⏰ 下次定时任务执行时间:"
systemctl list-timers vercel-daily.timer --no-pager 2>/dev/null | grep vercel || echo "  未设置"
echo ""
echo "🔑 密钥统计:"
TOTAL=$(wc -l < /opt/vercel-gateway/data/keys/total_keys.txt 2>/dev/null || echo "0")
ACTIVE=$(wc -l < /opt/vercel-gateway/data/keys/active_keys.txt 2>/dev/null || echo "0")
HIGH=$(wc -l < /opt/vercel-gateway/data/keys/keys_high.txt 2>/dev/null || echo "0")
echo "  总密钥数: $TOTAL"
echo "  有效密钥: $ACTIVE"
echo "  高余额($3+): $HIGH"
echo ""
echo "🌐 端口监听:"
ss -tlnp | grep 3001 || echo "  端口 3001 未监听"
echo ""
echo "📋 最近日志 (最后5行):"
echo "----------------------------------------"
tail -5 /opt/vercel-gateway/logs/daily_task.log 2>/dev/null || journalctl -u vercel-proxy -n 5 --no-pager 2>/dev/null || echo "  无日志"
echo "=========================================="
EOF

# check.sh (检查余额)
cat > $INSTALL_DIR/scripts/check.sh << 'EOF'
#!/bin/bash
cd /opt/vercel-gateway
python3 -m src.checker.billing_checker
EOF

# refresh.sh (手动刷新)
cat > $INSTALL_DIR/scripts/refresh.sh << 'EOF'
#!/bin/bash
cd /opt/vercel-gateway
python3 -m src.refresher.key_refresher
EOF

# daily.sh (手动执行每日任务 - 完整流程)
cat > $INSTALL_DIR/scripts/daily.sh << 'EOF'
#!/bin/bash
echo "手动执行每日任务（刷新 + 检查 + 热加载）..."
cd /opt/vercel-gateway
python3 -m src.daily_task
EOF

# logs.sh (查看日志)
cat > $INSTALL_DIR/scripts/logs.sh << 'EOF'
#!/bin/bash
echo "查看代理服务日志 (Ctrl+C 退出)..."
journalctl -u vercel-proxy -f
EOF

# daily-logs.sh (查看每日任务日志)
cat > $INSTALL_DIR/scripts/daily-logs.sh << 'EOF'
#!/bin/bash
echo "查看每日任务日志..."
echo "=========================================="
tail -100 /opt/vercel-gateway/logs/daily_task.log
EOF

chmod +x $INSTALL_DIR/scripts/*.sh

echo -e "${GREEN}✓ 管理脚本已创建${NC}"

# 创建示例密钥文件
if [ ! -f "$INSTALL_DIR/data/keys/total_keys.txt" ]; then
    echo "# 每行一个 Vercel API Key" > $INSTALL_DIR/data/keys/total_keys.txt
    echo "# 示例: vcel_xxxxxxxxxxxxxxxx" >> $INSTALL_DIR/data/keys/total_keys.txt
fi

# 完成
echo -e "\n${GREEN}"
echo "=============================================="
echo "   安装完成！"
echo "=============================================="
echo -e "${NC}"

echo -e "${YELLOW}重要信息:${NC}"
echo -e "  安装目录: ${GREEN}$INSTALL_DIR${NC}"
echo -e "  代理端口: ${GREEN}3001${NC}"
echo -e "  AUTH_KEY: ${GREEN}$AUTH_KEY${NC}"
echo ""

echo -e "${YELLOW}每日定时任务:${NC}"
echo -e "  执行时间: ${GREEN}每天凌晨 00:00${NC}"
echo -e "  任务内容: ${GREEN}刷新所有密钥 → 检查余额 → 更新高余额列表 → 热加载代理${NC}"
echo ""

echo -e "${YELLOW}下一步:${NC}"
echo -e "  1. 添加密钥: ${GREEN}nano $INSTALL_DIR/data/keys/total_keys.txt${NC}"
echo -e "  2. 检查余额: ${GREEN}$INSTALL_DIR/scripts/check.sh${NC}"
echo -e "  3. 启动服务: ${GREEN}$INSTALL_DIR/scripts/start.sh${NC}"
echo -e "  4. 查看状态: ${GREEN}$INSTALL_DIR/scripts/status.sh${NC}"
echo ""

echo -e "${YELLOW}NewAPI 渠道配置:${NC}"
echo -e "  类型:     ${GREEN}OpenAI${NC}"
echo -e "  Base URL: ${GREEN}http://127.0.0.1:3001${NC}"
echo -e "  API Key:  ${GREEN}$AUTH_KEY${NC}"
echo ""

echo -e "${YELLOW}常用命令:${NC}"
echo -e "  启动: ${GREEN}$INSTALL_DIR/scripts/start.sh${NC}"
echo -e "  停止: ${GREEN}$INSTALL_DIR/scripts/stop.sh${NC}"
echo -e "  重启: ${GREEN}$INSTALL_DIR/scripts/restart.sh${NC}"
echo -e "  状态: ${GREEN}$INSTALL_DIR/scripts/status.sh${NC}"
echo -e "  日志: ${GREEN}$INSTALL_DIR/scripts/logs.sh${NC}"
echo -e "  手动执行每日任务: ${GREEN}$INSTALL_DIR/scripts/daily.sh${NC}"
echo ""
