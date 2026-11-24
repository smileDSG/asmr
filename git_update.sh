#!/bin/bash
# 夜息 ASMR - 服务器端 GitHub 更新脚本
# 在服务器上执行：bash /opt/yexi/git_update.sh
# 作用：从 GitHub 拉最新代码，重启服务。不碰素材、密钥、账号数据库。

set -e

# 切到脚本所在目录（也就是仓库目录）
cd "$(dirname "$0")"

echo "========== 从 GitHub 拉取最新代码 =========="

echo "[1/3] 当前提交："
git log -1 --oneline

echo "[2/3] 拉取..."
git pull origin master

echo "[3/3] 新提交："
git log -1 --oneline

echo "重启服务..."
systemctl restart yexi
sleep 2
systemctl status yexi --no-pager | head -8

echo ""
echo "========== 更新完成 =========="
