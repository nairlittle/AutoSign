#!/bin/bash
# mhh1.com 自动签到 - 安装 crontab 定时任务
# 默认每天早上 8:00 自动签到

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_SCRIPT="$SCRIPT_DIR/run.sh"

echo "=========================================="
echo "  mhh1.com 自动签到 - 定时任务设置"
echo "=========================================="
echo ""

# 显示当前 crontab
echo "当前 crontab 条目:"
crontab -l 2>/dev/null || echo "  (无)"
echo ""

# 询问签到时间
echo "请选择签到时间:"
echo "  1) 每天 08:00 (推荐)"
echo "  2) 每天 09:00"
echo "  3) 每天 12:00"
echo "  4) 每天 20:00"
echo "  5) 自定义"
echo ""
read -p "请选择 [1-5]: " choice

case $choice in
    1) CRON_TIME="0 8 * * *" ;;
    2) CRON_TIME="0 9 * * *" ;;
    3) CRON_TIME="0 12 * * *" ;;
    4) CRON_TIME="0 20 * * *" ;;
    5)
        read -p "请输入 cron 表达式 (例如: 30 7 * * *): " CRON_TIME
        ;;
    *) 
        echo "无效选择，默认使用 08:00"
        CRON_TIME="0 8 * * *"
        ;;
esac

# 添加随机延迟 (0-30分钟)
echo ""
echo "是否添加随机延迟避免请求集中？"
read -p "添加随机延迟？(y/n) [y]: " add_delay
add_delay=${add_delay:-y}

CRON_LOG="$SCRIPT_DIR/logs/cron.log"

if [ "$add_delay" = "y" ]; then
    CRON_CMD="sleep \$((RANDOM \% 1800)) && $CRON_SCRIPT >> $CRON_LOG 2>&1"
else
    CRON_CMD="$CRON_SCRIPT >> $CRON_LOG 2>&1"
fi

# 写入 crontab
CRON_ENTRY="$CRON_TIME $CRON_CMD"

# 检查是否已存在
if crontab -l 2>/dev/null | grep -q "$CRON_SCRIPT"; then
    echo ""
    echo "[提示] 检测到已存在的签到任务，将更新时间..."
    crontab -l 2>/dev/null | grep -v "$CRON_SCRIPT" | { cat; echo "$CRON_ENTRY"; } | crontab -
else
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
fi

echo ""
echo "=========================================="
echo "  定时任务设置完成！"
echo "=========================================="
echo ""
echo "当前 crontab:"
crontab -l
echo ""
echo "日志文件: $CRON_LOG"
echo ""
echo "管理命令:"
echo "  查看日志: tail -f $CRON_LOG"
echo "  查看任务: crontab -l"
echo "  编辑任务: crontab -e"
echo "  删除任务: crontab -l | grep -v '$CRON_SCRIPT' | crontab -"
echo ""
