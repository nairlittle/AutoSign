#!/bin/bash
# mhh1.com 自动签到 - 一键部署脚本
# 适用于 Linux 系统 (Ubuntu/Debian/CentOS)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

echo "=========================================="
echo "  mhh1.com 自动签到 - 环境部署"
echo "=========================================="

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 Python3，请先安装:"
    echo "  Ubuntu/Debian: sudo apt update && sudo apt install python3 python3-pip python3-venv -y"
    echo "  CentOS: sudo yum install python3 python3-pip -y"
    exit 1
fi

echo "[1/4] 创建虚拟环境..."
python3 -m venv "$VENV_DIR"

echo "[2/4] 激活虚拟环境并安装依赖..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$SCRIPT_DIR/requirements.txt"

echo "[3/5] 安装 Playwright Chromium 浏览器..."
python3 -m playwright install chromium

echo "[4/5] 创建日志目录和配置文件..."
mkdir -p "$SCRIPT_DIR/logs"
if [ ! -f "$SCRIPT_DIR/config.json" ]; then
    cp "$SCRIPT_DIR/config.example.json" "$SCRIPT_DIR/config.json"
    echo "  已创建 config.json，请编辑填写账号密码"
fi

echo "[5/5] 设置脚本权限..."
chmod +x "$SCRIPT_DIR/signin.py"
chmod +x "$SCRIPT_DIR/run.sh"

echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
echo "下一步操作:"
echo "  1. 编辑配置文件: nano $SCRIPT_DIR/config.json"
echo "     填写你的邮箱和密码"
echo ""
echo "  2. 手动测试: $SCRIPT_DIR/run.sh"
echo ""
echo "  3. 设置定时任务 (每天自动签到):"
echo "     $SCRIPT_DIR/install_cron.sh"
echo ""
