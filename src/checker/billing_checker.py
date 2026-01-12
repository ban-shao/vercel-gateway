#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel API Key 余额检查工具
检查所有密钥余额并按范围分类保存
"""

import requests
import json
import time
import os
import sys
import warnings
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

warnings.filterwarnings('ignore')

# 配置
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
KEYS_DIR = DATA_DIR / "keys"
REPORTS_DIR = DATA_DIR / "reports"

# 确保目录存在
KEYS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


class VercelBillingChecker:
    def __init__(self):
        self.base_url = "https://ai-gateway.vercel.sh/v1"
        self.headers_template = {
            "Content-Type": "application/json",
            "User-Agent": "vercel-billing-checker/2.0"
        }

    def check_single_key(self, api_key: str) -> dict:
        """检查单个密钥的余额"""
        headers = self.headers_template.copy()
        headers["Authorization"] = f"Bearer {api_key}"

        try:
            response = requests.get(
                f"{self.base_url}/credits",
                headers=headers,
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                balance = float(data.get("balance", 0))
                total_used = float(data.get("total_used", 0))
                total_limit = balance + total_used
                usage_percentage = round(total_used / total_limit * 100, 2) if total_limit > 0 else 0

                return {
                    "key": api_key,
                    "key_short": api_key[:16] + "..." + api_key[-4:],
                    "status": "success",
                    "balance": balance,
                    "total_used": total_used,
                    "total_limit": total_limit,
                    "usage_percentage": usage_percentage
                }
            else:
                return {
                    "key": api_key,
                    "key_short": api_key[:16] + "...",
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {response.text[:100]}"
                }

        except requests.exceptions.Timeout:
            return {
                "key": api_key,
                "key_short": api_key[:16] + "...",
                "status": "error",
                "error": "请求超时"
            }
        except Exception as e:
            return {
                "key": api_key,
                "key_short": api_key[:16] + "...",
                "status": "error",
                "error": str(e)
            }

    def check_multiple_keys(self, api_keys: list, max_workers: int = 5) -> list:
        """批量检查多个密钥"""
        results = []
        total = len(api_keys)

        print(f"\n{'='*60}")
        print(f"开始检查 {total} 个 Vercel API Key")
        print(f"并发数: {max_workers}")
        print(f"{'='*60}\n")

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_key = {
                executor.submit(self.check_single_key, key): key 
                for key in api_keys
            }
            
            completed = 0
            for future in as_completed(future_to_key):
                result = future.result()
                results.append(result)
                completed += 1
                
                # 显示进度
                progress = f"[{completed}/{total}]"
                if result["status"] == "success":
                    print(f"{progress} ✅ {result['key_short']} - 余额: ${result['balance']:.2f}")
                else:
                    print(f"{progress} ❌ {result['key_short']} - {result['error'][:50]}")

        elapsed = time.time() - start_time
        print(f"\n检查完成，耗时: {elapsed:.1f} 秒")

        return results

    def generate_report(self, results: list) -> dict:
        """生成报告并保存分类文件"""
        successful = [r for r in results if r["status"] == "success"]
        failed = [r for r in results if r["status"] == "error"]

        print(f"\n{'='*60}")
        print("📊 检查完成 - 统计报告")
        print(f"{'='*60}")
        print(f"总计: {len(results)} 个密钥")
        print(f"成功: {len(successful)} 个")
        print(f"失败: {len(failed)} 个")

        summary = {
            "total": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "total_balance": 0,
            "categories": {}
        }

        if successful:
            total_balance = sum(r["balance"] for r in successful)
            total_used = sum(r["total_used"] for r in successful)
            total_limit = sum(r["total_limit"] for r in successful)
            
            summary["total_balance"] = round(total_balance, 2)
            summary["total_used"] = round(total_used, 2)
            summary["total_limit"] = round(total_limit, 2)

            print(f"\n💰 余额统计:")
            print(f"   总余额: ${total_balance:.2f}")
            print(f"   总已用: ${total_used:.2f}")
            print(f"   总额度: ${total_limit:.2f}")

            # 按余额分类
            categories = {
                "high": {"name": "$3+", "min": 3, "max": float('inf'), "keys": []},
                "medium_high": {"name": "$2-3", "min": 2, "max": 3, "keys": []},
                "medium": {"name": "$1-2", "min": 1, "max": 2, "keys": []},
                "low": {"name": "$0-1", "min": 0.01, "max": 1, "keys": []},
                "zero": {"name": "$0", "min": -float('inf'), "max": 0.01, "keys": []}
            }

            # 按余额从高到低排序
            successful_sorted = sorted(successful, key=lambda x: x["balance"], reverse=True)

            for r in successful_sorted:
                balance = r["balance"]
                for cat_key, cat_info in categories.items():
                    if cat_info["min"] <= balance < cat_info["max"]:
                        cat_info["keys"].append(r["key"])
                        break

            print(f"\n📈 余额分布:")
            for cat_key, cat_info in categories.items():
                count = len(cat_info["keys"])
                if count > 0:
                    print(f"   {cat_info['name']}: {count} 个")
                summary["categories"][cat_key] = count

            # 保存有效密钥（余额>0）到 active_keys.txt
            active_keys = []
            for cat_key in ["high", "medium_high", "medium", "low"]:
                active_keys.extend(categories[cat_key]["keys"])

            if active_keys:
                active_file = KEYS_DIR / "active_keys.txt"
                active_file.write_text('\n'.join(active_keys))
                print(f"\n✅ 已保存 {len(active_keys)} 个有效密钥到: {active_file}")

            # 保存各分类
            for cat_key, cat_info in categories.items():
                if cat_info["keys"]:
                    cat_file = KEYS_DIR / f"keys_{cat_key}.txt"
                    cat_file.write_text('\n'.join(cat_info["keys"]))
                    print(f"   - {cat_info['name']}: {cat_file.name} ({len(cat_info['keys'])} 个)")

            # 显示 Top 10
            print(f"\n🏆 余额 Top 10:")
            for i, r in enumerate(successful_sorted[:10], 1):
                print(f"   {i:2d}. {r['key_short']} - ${r['balance']:.2f}")

        # 保存 JSON 报告
        report = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": summary,
            "successful": [
                {
                    "key_short": r["key_short"],
                    "balance": r["balance"],
                    "total_used": r["total_used"],
                    "total_limit": r["total_limit"],
                    "usage_percentage": r["usage_percentage"]
                }
                for r in sorted(successful, key=lambda x: x["balance"], reverse=True)
            ],
            "failed": [
                {"key_short": r["key_short"], "error": r["error"]}
                for r in failed
            ]
        }

        report_file = REPORTS_DIR / "billing_report.json"
        report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\n📊 详细报告: {report_file}")

        return summary


def main():
    """主函数"""
    keys_file = KEYS_DIR / "total_keys.txt"

    # 检查文件是否存在
    if not keys_file.exists():
        print(f"❌ 找不到密钥文件: {keys_file}")
        print(f"\n请创建文件并添加密钥，每行一个:")
        print(f"   nano {keys_file}")
        sys.exit(1)

    # 读取密钥
    content = keys_file.read_text()
    api_keys = [k.strip() for k in content.split('\n') if k.strip()]

    if not api_keys:
        print("❌ 密钥文件为空")
        sys.exit(1)

    print(f"✅ 读取到 {len(api_keys)} 个密钥")

    # 执行检查
    checker = VercelBillingChecker()
    results = checker.check_multiple_keys(api_keys, max_workers=5)
    summary = checker.generate_report(results)

    print(f"\n{'='*60}")
    print("✅ 检查完成！")
    print(f"{'='*60}")

    return summary


if __name__ == "__main__":
    main()
