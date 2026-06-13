#!/usr/bin/env python3
"""
mhh1.com 自动签到 - 定时调度器
可作为守护进程运行，每天自动签到
"""

import time
import random
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 导入签到模块
from signin import load_config, create_scraper, login, do_sign_in

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "scheduler.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def run_sign_in():
    """执行一次签到"""
    logger.info("=" * 50)
    logger.info(f"开始签到 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    try:
        config = load_config()
        scraper = create_scraper(config)

        if login(scraper, config):
            time.sleep(random.uniform(2, 5))
            success = do_sign_in(scraper, config)
            if success:
                logger.info("签到成功！")
            else:
                logger.warning("签到结果不确定，请手动验证")
            return success
        else:
            logger.error("登录失败")
            return False
    except Exception as e:
        logger.error(f"签到异常: {e}")
        return False


def calculate_next_run(hour=8, minute=0):
    """计算下一次运行时间"""
    now = datetime.now()
    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if next_run <= now:
        next_run += timedelta(days=1)

    return next_run


def main():
    """主循环"""
    run_hour = 8
    run_minute = 0

    if len(sys.argv) > 1:
        try:
            parts = sys.argv[1].split(":")
            run_hour = int(parts[0])
            run_minute = int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            print("用法: python scheduler.py [HH:MM]")
            print("示例: python scheduler.py 08:30")
            sys.exit(1)

    logger.info(f"签到调度器启动，计划时间: 每天 {run_hour:02d}:{run_minute:02d}")

    while True:
        next_run = calculate_next_run(run_hour, run_minute)
        wait_seconds = (next_run - datetime.now()).total_seconds()

        logger.info(f"下次签到时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"等待 {wait_seconds / 3600:.1f} 小时")

        time.sleep(wait_seconds)

        # 添加随机延迟 (0-30分钟)
        jitter = random.uniform(0, 1800)
        logger.info(f"随机延迟 {jitter / 60:.1f} 分钟")
        time.sleep(jitter)

        run_sign_in()

        # 签到后等待到明天
        time.sleep(3600)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("调度器已停止")
        sys.exit(0)
