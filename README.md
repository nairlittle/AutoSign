# AutoSign - mhh1.com 自动签到

自动完成 [www.mhh1.com](https://www.mhh1.com)（萌幻之乡）每日签到的脚本。

## 技术方案

| 功能 | 方案 |
|------|------|
| 绕过 HMOECDN 防护 | Playwright 真实浏览器 |
| 验证码识别 | ddddocr OCR |
| 表单提交 | Hook React onSubmit |
| 定时任务 | crontab / systemd |

## 环境要求

- Python 3.8+
- Linux / Windows / macOS

## 快速开始

### Linux

```bash
# 一键部署
chmod +x setup.sh && ./setup.sh

# 编辑配置
nano config.json

# 手动测试
./run.sh

# 安装定时任务（每天自动签到）
chmod +x install_cron.sh && ./install_cron.sh
```

### Windows

```bash
# 安装依赖
pip install -r requirements.txt
python -m playwright install chromium

# 编辑 config.json 填写账号密码

# 运行
python signin.py
```

### Docker

```bash
# 编辑 config.json 后
docker-compose up -d mhh1-signin-scheduler
```

## 配置说明

编辑 `config.json`：

```json
{
    "username": "你的邮箱",
    "password": "你的密码",
    "retry_count": 5,
    "retry_delay": 3
}
```

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `username` | 登录邮箱 | 必填 |
| `password` | 登录密码 | 必填 |
| `retry_count` | 验证码重试次数 | 5 |
| `retry_delay` | 重试间隔（秒） | 3 |

## 日志

运行日志和截图保存在 `logs/` 目录：

- `signin.log` - 运行日志
- `login_failed.png` - 登录失败截图
- `final.png` - 最终状态截图

## 定时任务

```bash
# 查看当前 crontab
crontab -l

# 编辑 crontab
crontab -e

# 添加每天 8:00 执行
0 8 * * * /path/to/AutoSign/run.sh >> /path/to/AutoSign/logs/cron.log 2>&1
```

## License

MIT
