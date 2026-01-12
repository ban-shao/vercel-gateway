#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel Gateway 每日定时任务
完整流程：刷新密钥 -> 检查余额 -> 更新有效密钥 -> 通知代理服务热加载
"""

import os
import sys
import time
import logging
import subprocess
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# 配置
BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
KEYS_DIR = BASE_DIR / "data/keys"

# 加载环境变量
load_dotenv(BASE_DIR / ".env")
PROXY_PORT = os.getenv("PROXY_PORT", "3001")
AUTH_KEY = os.getenv("AUTH_KEY", "")

# 确保目录存在
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'daily_task.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def run_refresh():
    """步骤1: 刷新所有密钥"""
    logger.info("=" * 60)
    logger.info("📍 步骤 1/3: 刷新所有密钥额度")
    logger.info("=" * 60)
    
    try:
        from src.refresher.key_refresher import VercelKeyRefresher
        
        # 始终使用 total_keys.txt（所有密钥）
        keys_file = KEYS_DIR / "total_keys.txt"
        if not keys_file.exists():
            logger.error(f"❌ 密钥文件不存在: {keys_file}")
            return False
        
        content = keys_file.read_text()
        api_keys = [k.strip() for k in content.split('\n') if k.strip() and not k.startswith('#')]
        
        if not api_keys:
            logger.error("❌ 密钥文件为空")
            return False
        
        logger.info(f"读取到 {len(api_keys)} 个密钥")
        
        refresher = VercelKeyRefresher()
        results = refresher.refresh_all_keys(api_keys)
        
        success = len([r for r in results if r["status"] in ("success", "triggered")])
        logger.info(f"✅ 刷新完成: {success}/{len(api_keys)} 个密钥已触发")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 刷新失败: {e}")
        return False


def run_check():
    """步骤2: 检查所有密钥余额"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("📍 步骤 2/3: 检查所有密钥余额")
    logger.info("=" * 60)
    
    try:
        from src.checker.billing_checker import VercelBillingChecker
        
        # 始终使用 total_keys.txt
        keys_file = KEYS_DIR / "total_keys.txt"
        content = keys_file.read_text()
        api_keys = [k.strip() for k in content.split('\n') if k.strip() and not k.startswith('#')]
        
        if not api_keys:
            logger.error("❌ 密钥文件为空")
            return False
        
        checker = VercelBillingChecker()
        results = checker.check_multiple_keys(api_keys, max_workers=10)
        checker.generate_report(results)
        
        # 统计
        successful = [r for r in results if r["status"] == "success"]
        high_balance = len([r for r in successful if r.get("balance", 0) >= 3])
        
        logger.info(f"✅ 检查完成: {len(successful)}/{len(api_keys)} 个有效")
        logger.info(f"   高余额密钥($3+): {high_balance} 个")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 检查失败: {e}")
        return False


def notify_proxy_reload():
    """步骤3: 通知代理服务重新加载密钥"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("📍 步骤 3/3: 通知代理服务热加载密钥")
    logger.info("=" * 60)
    
    if not AUTH_KEY:
        logger.warning("⚠️ 未配置 AUTH_KEY，跳过热加载通知")
        logger.info("   请手动重启服务: /opt/vercel-gateway/scripts/restart.sh")
        return True
    
    try:
        url = f"http://127.0.0.1:{PROXY_PORT}/admin/reload"
        headers = {"Authorization": f"Bearer {AUTH_KEY}"}
        
        response = requests.post(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ 代理服务已重新加载密钥: {data.get('message', 'OK')}")
            return True
        else:
            logger.warning(f"⚠️ 热加载请求失败: HTTP {response.status_code}")
            logger.info("   请手动重启服务: /opt/vercel-gateway/scripts/restart.sh")
            return True
            
    except requests.exceptions.ConnectionError:
        logger.warning("⚠️ 代理服务未运行，跳过热加载")
        return True
    except Exception as e:
        logger.warning(f"⚠️ 热加载失败: {e}")
        return True


def main():
    """主函数 - 执行完整的每日任务"""
    start_time = time.time()
    
    logger.info("")
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + "  Vercel Gateway 每日定时任务".center(56) + "║")
    logger.info("║" + f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(56) + "║")
    logger.info("╚" + "═" * 58 + "╝")
    logger.info("")
    
    # 步骤1: 刷新密钥
    refresh_ok = run_refresh()
    
    if not refresh_ok:
        logger.error("刷新失败，但继续执行检查...")
    
    # 等待一会，让刷新生效
    logger.info("\n⏳ 等待 30 秒让额度刷新生效...")
    time.sleep(30)
    
    # 步骤2: 检查余额
    check_ok = run_check()
    
    if not check_ok:
        logger.error("检查失败")
        sys.exit(1)
    
    # 步骤3: 通知代理热加载
    notify_proxy_reload()
    
    # 完成
    elapsed = time.time() - start_time
    
    logger.info("")
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + "  ✅ 每日任务完成！".center(54) + "║")
    logger.info("║" + f"  总耗时: {elapsed:.1f} 秒".center(54) + "║")
    logger.info("╚" + "═" * 58 + "╝")
    
    # 显示当前密钥状态
    keys_high = KEYS_DIR / "keys_high.txt"
    if keys_high.exists():
        count = len([k for k in keys_high.read_text().split('\n') if k.strip()])
        logger.info(f"\n📊 当前高余额密钥: {count} 个")
        logger.info(f"   文件: {keys_high}")


if __name__ == "__main__":
    main()
