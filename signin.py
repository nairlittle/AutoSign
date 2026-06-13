#!/usr/bin/env python3
"""
mhh1.com 自动签到脚本 (Playwright + ddddocr)
支持 cookie 持久化，避免重复登录
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

COOKIE_FILE = Path(__file__).parent / "cookies.json"

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


def save_cookies(cookies: list):
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    logger.info(f"Cookies 已保存 ({len(cookies)} 条)")


def load_cookies() -> list:
    if not COOKIE_FILE.exists():
        return []
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        logger.info(f"已加载 Cookies ({len(cookies)} 条)")
        return cookies
    except (json.JSONDecodeError, KeyError):
        logger.warning("Cookie 文件损坏，将重新登录")
        return []


async def check_login_status(page) -> bool:
    """检查当前页面是否已登录"""
    result = await page.evaluate('''() => {
        const avatar = document.querySelector('.inn-sign__avatar')
                    || document.querySelector('.inn-user__avatar')
                    || document.querySelector('[class*="avatar"]');

        // 遍历所有链接查找 logout
        let hasLogout = false;
        document.querySelectorAll('a').forEach(a => {
            if (a.href && a.href.includes('logout')) hasLogout = true;
        });

        let isLoggedIn = false;
        try {
            if (window.K && window.K.isLoggedIn) isLoggedIn = true;
        } catch(e) {}

        return {
            hasAvatar: !!avatar,
            hasLogout: hasLogout,
            isLoggedIn: isLoggedIn
        };
    }''')
    logged_in = result.get("isLoggedIn") or result.get("hasAvatar") or result.get("hasLogout")
    return logged_in


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


async def do_sign_in(page) -> bool:
    """执行签到操作"""
    logger.info("正在查找签到入口...")
    await page.wait_for_timeout(3000)

    sign_keywords = ["签到", "打卡"]
    href_keywords = ["signin", "checkin", "sign"]
    success_keywords = ["签到成功", "已签到", "成功", "恭喜", "连续"]

    # 方式1: 查找签到链接
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
                    return True
        except Exception:
            continue

    # 方式2: AJAX 签到
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
                    if isinstance(data, dict):
                        if data.get("code") == 0 or data.get("success"):
                            logger.info("AJAX 签到成功！")
                            return True
                    elif isinstance(data, int) and data == 0:
                        logger.info("AJAX 签到成功！")
                        return True
                except json.JSONDecodeError:
                    if "成功" in result or result.strip() == "0":
                        logger.info("AJAX 签到成功！")
                        return True
        except Exception as e:
            logger.warning(f"AJAX [{action}] 异常: {e}")

    return False


async def do_login(page, config, max_retries, retry_delay) -> bool:
    """执行登录流程"""
    # 关闭公告弹窗
    await page.evaluate(JS_REMOVE_POPUPS)
    await page.wait_for_timeout(500)

    # 打开登录对话框
    login_btn = page.locator('.inn-sign__login-btn')
    if await login_btn.count() > 0:
        await login_btn.first.click(force=True)
        logger.info("已点击登录按钮")
        await page.wait_for_timeout(2000)

    for attempt in range(1, max_retries + 1):
        logger.info(f"登录尝试 {attempt}/{max_retries}")

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

        await page.locator('input[name="email"]').fill(config["username"])
        await page.locator('input[name="pwd"]').fill(config["password"])
        await page.locator('input[name="captcha"]').fill(captcha_text)
        await page.wait_for_timeout(500)

        # Hook fetch 捕获响应，然后点击按钮提交
        await page.evaluate('''() => {
            window.__loginResponse = null;
            const origFetch = window.fetch;
            window.fetch = function(...args) {
                const promise = origFetch.apply(this, args);
                promise.then(async resp => {
                    if (resp.url.includes('admin-ajax')) {
                        try { window.__loginResponse = await resp.clone().text(); } catch(e) {}
                    }
                }).catch(() => {});
                return promise;
            };
            window.__origFetch = origFetch;
        }''')

        submit = page.locator('#inn-sign__dialog__fm .poi-dialog__footer__btn')
        try:
            async with page.expect_navigation(timeout=10000):
                await submit.first.click(force=True)
            # 页面跳转了，说明登录成功
            logger.info("登录成功！(页面已跳转)")
            login_result = '{"code": 0}'
        except Exception:
            # 没有跳转，检查 fetch 响应
            login_result = await page.evaluate('() => window.__loginResponse || JSON.stringify({code: -1, msg: "未获取到响应"})')
            logger.info(f"登录响应: {login_result[:300]}")

        # 恢复 fetch
        try:
            await page.evaluate('() => { if (window.__origFetch) window.fetch = window.__origFetch; }')
        except Exception:
            pass

        if login_result:
            try:
                data = json.loads(login_result)
                code = data.get("code", -1)
                msg = data.get("msg", "")

                if code == 0 or data.get("success"):
                    logger.info("登录成功！")
                    return True
                elif code == 70001:
                    logger.error(f"登录失败: {msg} (请检查账号密码)")
                    return False
                elif "验证码" in msg:
                    logger.warning(f"验证码错误: {msg}")
                else:
                    logger.warning(f"登录失败: {msg}")
            except json.JSONDecodeError:
                if "成功" in login_result or "refresh" in login_result:
                    logger.info("登录成功！")
                    return True

        await page.evaluate(JS_REFRESH_CAPTCHA)
        await page.wait_for_timeout(retry_delay * 1000)

    logger.error("登录失败，已达最大重试次数")
    return False


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

            # 加载已保存的 cookies
            cookies = load_cookies()
            if cookies:
                await ctx.add_cookies(cookies)
                logger.info("已恢复登录态")

            page = await ctx.new_page()

            # ---- 1. 访问首页 ----
            logger.info("正在访问 www.mhh1.com ...")
            await page.goto("https://www.mhh1.com", wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(3000)

            # ---- 2. 检查登录状态 ----
            is_logged_in = await check_login_status(page)

            if is_logged_in:
                logger.info("检测到已登录，跳过登录步骤")
            else:
                logger.info("未登录，开始登录流程...")
                # 关闭公告弹窗
                await page.evaluate(JS_REMOVE_POPUPS)
                await page.wait_for_timeout(500)

                login_success = await do_login(page, config, max_retries, retry_delay)

                if not login_success:
                    await page.screenshot(path=str(LOG_DIR / "login_failed.png"))
                    return False

                # 登录成功后保存 cookies
                new_cookies = await ctx.cookies()
                save_cookies(new_cookies)

            # ---- 3. 执行签到 ----
            sign_in_done = await do_sign_in(page)

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
