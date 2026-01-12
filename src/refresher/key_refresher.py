#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel API Key 自动刷新工具
每天自动调用所有密钥，触发额度刷新机制
"""

import requests
import json
import time
import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# 配置
BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = BASE_DIR / "logs"
KEYS_DIR = BASE_DIR / "data/keys"
REPORTS_DIR = BASE_DIR / "data/reports"

# 确保目录存在
LOGS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'refresher.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class VercelKeyRefresher:
    """Vercel 密钥刷新器"""
    
    def __init__(self):
        self.base_url = "https://ai-gateway.vercel.sh/v1/chat/completions"
        # 使用最便宜的模型
        self.model = "anthropic/claude-3-haiku"
        self.interval = 2  # 每个密钥之间间隔秒数

    def refresh_single_key(self, api_key: str, index: int, total: int) -> dict:
        """刷新单个密钥"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        # 最小请求，减少消耗
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "1"}],
            "max_tokens": 1
        }

        key_display = f"{api_key[:12]}...{api_key[-4:]}"

        try:
            logger.info(f"[{index}/{total}] 正在刷新: {key_display}")

            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                logger.info(f"[{index}/{total}] ✅ {key_display} - 成功")
                return {
                    "key": key_display,
                    "status": "success",
                    "code": 200
                }
            else:
                # 即使失败也触发了刷新检查
                logger.info(f"[{index}/{total}] ⚠️  {key_display} - HTTP {response.status_code}")
                return {
                    "key": key_display,
                    "status": "triggered",
                    "code": response.status_code,
                    "message": response.text[:100]
                }

        except requests.exceptions.Timeout:
            logger.warning(f"[{index}/{total}] ⏱️  {key_display} - 超时")
            return {
                "key": key_display,
                "status": "timeout"
            }
        except Exception as e:
            logger.error(f"[{index}/{total}] ❌ {key_display} - {str(e)}")
            return {
                "key": key_display,
                "status": "error",
                "error": str(e)
            }

    def refresh_all_keys(self, api_keys: list) -> list:
        """刷新所有密钥"""
        total = len(api_keys)
        results = []

        logger.info("=" * 60)
        logger.info(f"Vercel Key 刷新任务启动")
        logger.info(f"密钥数量: {total}")
        logger.info(f"间隔时间: {self.interval} 秒")
        logger.info("=" * 60)

        start_time = time.time()

        for i, key in enumerate(api_keys, 1):
            result = self.refresh_single_key(key, i, total)
            results.append(result)
            
            # 最后一个不需要等待
            if i < total:
                time.sleep(self.interval)

        elapsed = time.time() - start_time

        # 统计
        success = len([r for r in results if r["status"] == "success"])
        triggered = len([r for r in results if r["status"] == "triggered"])
        timeout = len([r for r in results if r["status"] == "timeout"])
        error = len([r for r in results if r["status"] == "error"])

        logger.info("=" * 60)
        logger.info("刷新完成 - 统计报告")
        logger.info("=" * 60)
        logger.info(f"总计: {total}")
        logger.info(f"成功: {success}")
        logger.info(f"触发: {triggered}")
        logger.info(f"超时: {timeout}")
        logger.info(f"错误: {error}")
        logger.info(f"耗时: {elapsed:.1f} 秒")
        logger.info("=" * 60)

        # 保存报告
        report = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "total": total,
                "success": success,
                "triggered": triggered,
                "timeout": timeout,
                "error": error,
                "elapsed_seconds": round(elapsed, 2)
            },
            "details": results
        }

        report_file = REPORTS_DIR / "refresh_report.json"
        report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        logger.info(f"报告已保存: {report_file}")

        return results


def main():
    """主函数"""
    # 按优先级查找密钥文件
    key_files = [
        KEYS_DIR / "active_keys.txt",  # 优先使用有效密钥
        KEYS_DIR / "total_keys.txt"    # 备用：所有密钥
    ]

    api_keys = []
    used_file = None

    for key_file in key_files:
        if key_file.exists():
            content = key_file.read_text()
            keys = [k.strip() for k in content.split('\n') if k.strip()]
            if keys:
                api_keys = keys
                used_file = key_file
                break

    if not api_keys:
        logger.error("❌ 未找到密钥文件或文件为空")
        logger.error(f"   请确保以下文件之一存在且包含密钥:")
        for f in key_files:
            logger.error(f"   - {f}")
        sys.exit(1)

    logger.info(f"从 {used_file.name} 读取 {len(api_keys)} 个密钥")

    # 执行刷新
    refresher = VercelKeyRefresher()
    results = refresher.refresh_all_keys(api_keys)

    # 返回成功数量（用于脚本判断）
    success_count = len([r for r in results if r["status"] in ("success", "triggered")])
    return success_count


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success > 0 else 1)
