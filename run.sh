#!/bin/bash
# mhh1.com 自动签到 - 运行脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

# 激活虚拟环境
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
else
    echo "[错误] 虚拟环境不存在，请先运行 setup.sh"
    exit 1
fi

# 运行签到脚本
cd "$SCRIPT_DIR"
python3 signin.py "$@"
