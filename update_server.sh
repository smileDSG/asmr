#!/bin/bash
# 夜息 ASMR - 本机一键更新脚本（在你自己的 Windows 电脑上跑，Git Bash 里执行）
#
# 作用：把最新代码传到阿里云服务器并重启服务，不碰服务器上的账号数据库和密钥。
#
# 首次用法（把 IP 和用户名填好）：
#   bash update_server.sh 你的公网IP root
# 例：
#   bash update_server.sh 123.45.67.89 root
#
# 前提：本机已能用 ssh 免密或密码登录服务器。

set -e

if [ "$#" -lt 1 ]; then
    echo "用法: bash update_server.sh <服务器公网IP> [用户名，默认root]"
    exit 1
fi

SERVER_IP=$1
USER_NAME=${2:-root}
APP_DIR=/opt/yexi
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)/deploy"

echo "========== 更新到阿里云服务器 $SERVER_IP =========="

if [ ! -f "$LOCAL_DIR/server.py" ]; then
    echo "错误：找不到 $LOCAL_DIR/server.py，请先运行 sync_deploy.py"
    exit 1
fi

echo "[1/3] 同步最新代码到 deploy/ 目录"
cd "$(dirname "$0")"
"C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe" sync_deploy.py >/dev/null

echo "[2/3] 上传代码文件到服务器（保留数据/密钥/素材不动）"
scp "$LOCAL_DIR/server.py" \
    "$LOCAL_DIR/auth_db.py" \
    "$LOCAL_DIR/qwen_client.py" \
    "$LOCAL_DIR/understanding_brain.py" \
    "$LOCAL_DIR/feedback_translate.py" \
    "$LOCAL_DIR/memory_system.py" \
    "$LOCAL_DIR/input_guard.py" \
    "$LOCAL_DIR/素材执行层.py" \
    "$LOCAL_DIR/sound_catalog.py" \
    "$LOCAL_DIR/sound_catalog.json" \
    "$LOCAL_DIR/requirements.txt" \
    "${USER_NAME}@${SERVER_IP}:${APP_DIR}/"

scp -r "$LOCAL_DIR/product_site/." "${USER_NAME}@${SERVER_IP}:${APP_DIR}/product_site/"

echo "[3/3] 重启服务"
ssh "${USER_NAME}@${SERVER_IP}" "systemctl restart yexi && sleep 2 && systemctl status yexi --no-pager | head -8"

echo ""
echo "========== 更新完成 =========="
echo "打开 http://$SERVER_IP:8000 查看效果（若域名已备案可用域名）"
