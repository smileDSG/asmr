#!/bin/bash
# 服务器端每日备份（由 crontab 调用，也可手动 bash ops_remote_backup.sh）
#
# 备份什么：/opt/yexi/data/ 下的账号库 users.db 和订单 json。
# 为什么用 python 的 sqlite backup：服务一直在跑，直接 cp 有可能拷到写了一半的库；
# sqlite 自带 backup 接口会拿锁，能拿到一致快照。
# 保留策略：只留最近 7 份，防止把 40G 的盘塞满。

set -u

APP_DIR=/opt/yexi
KEEP=7
STAMP=$(date +%Y%m%d_%H%M%S)
DIR="$APP_DIR/_backup/db/$STAMP"

mkdir -p "$DIR"

/opt/yexi/venv/bin/python - "$DIR" <<'PY'
import sqlite3
import sys

target = sys.argv[1] + "/users.db"
src = sqlite3.connect("/opt/yexi/data/users.db")
dst = sqlite3.connect(target)
with dst:
    src.backup(dst)
dst.close()
src.close()
print("users.db 已备份到 " + target)
PY

cp "$APP_DIR"/data/*.json "$DIR"/ 2>/dev/null || true

echo "--- 备份内容 ---"
ls -lh "$DIR"

# 只留最近 KEEP 份
ls -1dt "$APP_DIR"/_backup/db/*/ 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -rf
echo -n "现存备份份数："
ls -1d "$APP_DIR"/_backup/db/*/ 2>/dev/null | wc -l
