#!/usr/bin/env python3
"""
mhh1.com 自动签到脚本 (Playwright + ddddocr)
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright
import ddddocr

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "signin.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

ocr = ddddocr.DdddOcr(show_ad=False)


def recognize_captcha(img_bytes: bytes) -> str:
    result = ocr.classification(img_bytes)
    return ''.join(c for c in result if c.isdigit())


def load_config():
    config_path = Path(__file__).parent / "config.json"
    if not config_path.exists():
        logger.error("配置文件 config.json 不存在")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    if config["username"] == "你的邮箱" or config["password"] == "你的密码":
        logger.error("请先在 config.json 中填写用户名和密码")
        sys.exit(1)
    return config


JS_REFRESH_CAPTCHA = '''() => {
    const img = document.querySelector('#inn-sign__dialog__fm img[src^="data:image"]')
             || document.querySelector('form img');
    if (img) img.click();
}'''

JS_REMOVE_POPUPS = '''() => {
    document.querySelectorAll('.poi-dialog__overlay').forEach(el => el.remove());
    document.querySelectorAll('.poi-dialog').forEach(el => {
        if (!el.querySelector('input[name="email"]')) el.remove();
    });
}'''

JS_SUBMIT_LOGIN = '''async ({email, pwd, captcha}) => {
    const form = document.querySelector('#inn-sign__dialog__fm');
    if (!form) return JSON.stringify({code: -1, msg: '找不到登录表单'});

    const triggerChange = (el, val) => {
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
        setter.call(el, val);
        el.dispatchEvent(new Event('input', {bubbles: true}));
        el.dispatchEvent(new Event('change', {bubbles: true}));
    };

    triggerChange(form.querySelector('input[name="email"]'), email);
    triggerChange(form.querySelector('input[name="pwd"]'), pwd);
    triggerChange(form.querySelector('input[name="captcha"]'), captcha);

    const origFetch = window.fetch;
    let responseText = '';
    window.fetch = function(...args) {
        const promise = origFetch.apply(this, args);
        promise.then(async resp => {
            if (resp.url.includes('admin-ajax')) {
                responseText = await resp.clone().text();
            }
        });
        return promise;
    };

    form.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}));
    await new Promise(r => setTimeout(r, 5000));
    window.fetch = origFetch;

    return responseText || JSON.stringify({code: -1, msg: '未获取到响应'});
}'''


async def main():
    logger.info("=" * 50)
    logger.info(f"自动签到任务启动 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    config = load_config()
    max_retries = config.get("retry_count", 5)
    retry_delay = config.get("retry_delay", 3)
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
            )
            page = await ctx.new_page()

            # ---- 1. 访问首页 ----
            logger.info("正在访问 www.mhh1.com ...")
            await page.goto("https://www.mhh1.com", wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(3000)

            # ---- 2. 关闭公告弹窗 ----
            await page.evaluate(JS_REMOVE_POPUPS)
            await page.wait_for_timeout(500)
            logger.info("已清除公告弹窗")

            # ---- 3. 打开登录对话框 ----
            login_btn = page.locator('.inn-sign__login-btn')
            if await login_btn.count() > 0:
                await login_btn.first.click(force=True)
                logger.info("已点击登录按钮")
                await page.wait_for_timeout(2000)

            # ---- 4. 登录流程 ----
            login_success = False

            for attempt in range(1, max_retries + 1):
                logger.info(f"登录尝试 {attempt}/{max_retries}")

                # 获取验证码
                captcha_img = page.locator('#inn-sign__dialog__fm img[src^="data:image"]')
                if await captcha_img.count() == 0:
                    captcha_img = page.locator('form img[title="刷新验证码"]')
                if await captcha_img.count() == 0:
                    logger.error("找不到验证码图片")
                    await page.wait_for_timeout(2000)
                    continue

                captcha_bytes = await captcha_img.first.screenshot()
                captcha_text = recognize_captcha(captcha_bytes)
                logger.info(f"验证码识别: {captcha_text}")

                if len(captcha_text) != 4:
                    logger.warning(f"验证码位数异常 ({len(captcha_text)}位)，刷新")
                    await page.evaluate(JS_REFRESH_CAPTCHA)
                    await page.wait_for_timeout(2000)
                    continue

                # 填写表单
                await page.locator('input[name="email"]').fill(config["username"])
                await page.locator('input[name="pwd"]').fill(config["password"])
                await page.locator('input[name="captcha"]').fill(captcha_text)
                await page.wait_for_timeout(500)

                # 提交登录
                login_result = await page.evaluate(JS_SUBMIT_LOGIN, {
                    "email": config["username"],
                    "pwd": config["password"],
                    "captcha": captcha_text,
                })

                logger.info(f"登录响应: {login_result[:300]}")

                if login_result:
                    try:
                        data = json.loads(login_result)
                        code = data.get("code", -1)
                        msg = data.get("msg", "")

                        if code == 0 or data.get("success"):
                            logger.info("登录成功！")
                            login_success = True
                            break
                        elif code == 70001:
                            # 用户名密码错误，无需重试
                            logger.error(f"登录失败: {msg} (请检查账号密码)")
                            break
                        elif "验证码" in msg:
                            logger.warning(f"验证码错误: {msg}")
                        else:
                            logger.warning(f"登录失败: {msg}")
                    except json.JSONDecodeError:
                        if "成功" in login_result or "refresh" in login_result:
                            login_success = True
                            logger.info("登录成功！")
                            break

                # 刷新验证码
                await page.evaluate(JS_REFRESH_CAPTCHA)
                await page.wait_for_timeout(retry_delay * 1000)

            if not login_success:
                logger.error(f"登录失败")
                await page.screenshot(path=str(LOG_DIR / "login_failed.png"))
                return False

            # ---- 5. 登录后签到 ----
            logger.info("登录成功，正在查找签到入口...")
            await page.wait_for_timeout(3000)

            sign_in_done = False

            # 方式1: 查找签到链接
            sign_keywords = ["签到", "打卡"]
            href_keywords = ["signin", "checkin", "sign"]
            success_keywords = ["签到成功", "已签到", "成功", "恭喜", "连续"]

            all_links = await page.query_selector_all("a")
            for link in all_links:
                try:
                    text = (await link.inner_text()).strip()
                    href = await link.get_attribute("href") or ""
                    if any(kw in text for kw in sign_keywords) or any(kw in href for kw in href_keywords):
                        logger.info(f"找到签到入口: {text} -> {href}")
                        await link.click(force=True)
                        await page.wait_for_timeout(3000)
                        content = await page.inner_text("body")
                        if any(kw in content for kw in success_keywords):
                            logger.info("签到成功！")
                            sign_in_done = True
                            break
                except Exception:
                    continue

            # 方式2: AJAX 签到
            if not sign_in_done:
                logger.info("尝试 AJAX 签到...")
                for action in ["mhh_sign_in", "daily_signin", "signin", "checkin"]:
                    try:
                        result = await page.evaluate('''async (action) => {
                            try {
                                const resp = await fetch('/wp-admin/admin-ajax.php', {
                                    method: 'POST',
                                    headers: {
                                        'Content-Type': 'application/x-www-form-urlencoded',
                                        'X-Requested-With': 'XMLHttpRequest'
                                    },
                                    body: 'action=' + action
                                });
                                return await resp.text();
                            } catch(e) {
                                return 'ERROR: ' + e.message;
                            }
                        }''', action)
                        logger.info(f"AJAX [{action}]: {result[:200]}")
                        if result and "ERROR" not in result:
                            try:
                                data = json.loads(result)
                                if data.get("code") == 0 or data.get("success"):
                                    sign_in_done = True
                                    logger.info("AJAX 签到成功！")
                                    break
                            except json.JSONDecodeError:
                                if "成功" in result:
                                    sign_in_done = True
                                    break
                    except Exception as e:
                        logger.warning(f"AJAX [{action}] 异常: {e}")

            await page.screenshot(path=str(LOG_DIR / "final.png"))

            if sign_in_done:
                logger.info("签到任务完成！")
            else:
                logger.warning("未能确认签到成功，请检查 logs/final.png")

            return sign_in_done

    except Exception as e:
        logger.error(f"运行异常: {e}")
        return False
    finally:
        if browser:
            await browser.close()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
