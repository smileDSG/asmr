#!/bin/bash
# 夜息运维入口（在你自己的 Windows 电脑上跑，Git Bash 里执行）
#
# 用法：
#   bash ops.sh status            # 体检：服务/内存/磁盘/日志/数据库/端口 一次看全
#   bash ops.sh logs [行数]        # 最近日志，默认 60 行，自动滤掉 [GET] 刷屏
#   bash ops.sh backup            # 备份账号库+订单到服务器，并拉一份回本机
#   bash ops.sh cron              # 装每日自动备份（04:10）
#   bash ops.sh cron-off          # 卸掉自动备份
#   bash ops.sh trim-log          # 日志瘦身：journald 上限降到 500M
#   bash ops.sh rollback -y       # 应急回退到上一个提交并重启（临时止血）
#   bash ops.sh restart           # 重启服务
#   bash ops.sh health            # 从本机完整自检（等于 check_install.py）
#
# 跟已有脚本的分工：
#   git push            → GitHub Actions 自动部署 + 部署后自检（日常都走这条）
#   bash ops.sh ...     → 看状态、备份、救火（服务器侧动作）
#   update_server.sh    → 老的手动 scp 推代码（CI 挂了才用）
#   check_install.py    → 检查"安装包能不能下"这一条业务链路
#
# 为什么需要它：
#   线上跑着的是用户账号库 data/users.db，之前没有任何定时备份，
#   服务器一坏账号和订单就没了；journal 也已经吃到 3.9G。
#   这些事不该靠记性，要有一条命令能查、能备、能救。

set -u

KEY="$(cd "$(dirname "$0")" && pwd)/.deploy_key/id_ed25519"
SERVER="${YEXI_SERVER:-47.101.59.166}"
SERVER_USER="${YEXI_USER:-root}"
APP_DIR="${YEXI_DIR:-/opt/yexi}"
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=10 $SERVER_USER@$SERVER"

if [ ! -f "$KEY" ]; then
    echo "找不到部署密钥：$KEY"
    echo "可以先设置环境变量：YEXI_SERVER=服务器IP YEXI_USER=root"
    exit 1
fi

CMD="${1:-status}"

case "$CMD" in

status)
    echo "========== 夜息体检 $SERVER =========="
    $SSH "
        echo '--- 服务 ---'
        echo -n '状态：'; systemctl is-active yexi
        echo -n '开机自启：'; systemctl is-enabled yexi 2>/dev/null
        echo -n '启动于：'; systemctl show yexi -p ExecMainStartTimestamp --value
        echo -n '异常重启次数：'; systemctl show yexi -p NRestarts --value
        echo -n '内存占用：'; systemctl show yexi -p MemoryCurrent --value | awk '{printf \"%.0f MB\n\", \$1/1024/1024}'
        echo -n '内存上限：'; systemctl show yexi -p MemoryMax --value | awk '{if (\$1 > 0) printf \"%.0f MB\n\", \$1/1024/1024; else print \"无\"}'

        echo '--- 机器 ---'
        echo -n '磁盘：'; df -h / | tail -1 | awk '{print \$3\" 已用 / \"\$2\" 总，剩 \"\$4\"（\"\$5\"）\"}'
        echo -n '日志占用：'; journalctl --disk-usage 2>/dev/null | sed 's/Archived and active journals take up //; s/ in the file system\.//'
        echo -n '内存：'; free -m | awk '/^Mem:/{print \$3\" MB 已用 / \"\$2\" MB 总，可用 \"\$7\" MB\"}'

        echo '--- 数据（丢了就找不回来）---'
        ls -lh $APP_DIR/data/ 2>/dev/null | tail -n +2
        echo -n '数据库备份份数：'; ls -1d $APP_DIR/_backup/db/*/ 2>/dev/null | wc -l
        LAST=\$(ls -1d $APP_DIR/_backup/db/*/ 2>/dev/null | tail -1); echo \"最近一次备份：\${LAST:-还没有备份}\"

        echo '--- 端口/防火墙 ---'
        ss -ltnp 2>/dev/null | grep 8000 | sed 's/^/  /'
        echo -n 'ufw：'; ufw status 2>/dev/null | head -1

        echo '--- 线上版本 ---'
        git -C $APP_DIR log -1 --oneline
        echo -n '磁盘上的 APK：'; ls -lh $APP_DIR/product_site/download/*.apk 2>/dev/null | awk '{print \$5\" \"\$9}' || echo '没有'
    "
    ;;

logs)
    N="${2:-60}"
    echo "========== 最近 $N 行日志（已滤掉 [GET] 刷屏）=========="
    $SSH "journalctl -u yexi --no-pager -n 400 | grep -v '\[GET\]' | tail -n $N"
    ;;

backup)
    STAMP=$(date +%Y%m%d_%H%M%S)
    echo "========== 备份数据 =========="
    # 备份逻辑只写一份（ops_remote_backup.sh），本地手动跑和服务器定时跑用的是同一段代码
    scp -i "$KEY" -o StrictHostKeyChecking=no \
        "$(dirname "$0")/ops_remote_backup.sh" \
        "$SERVER_USER@$SERVER:$APP_DIR/ops_remote_backup.sh" >/dev/null 2>&1
    $SSH "bash $APP_DIR/ops_remote_backup.sh"
    # 再拉一份回本机：服务器整台挂了也有底
    LATEST=$($SSH "ls -1d $APP_DIR/_backup/db/*/ 2>/dev/null | tail -1")
    if [ -n "$LATEST" ]; then
        NAME=$(basename "$LATEST")
        mkdir -p "$(dirname "$0")/_backup_db/$NAME"
        scp -i "$KEY" -o StrictHostKeyChecking=no -r \
            "$SERVER_USER@$SERVER:$LATEST." \
            "$(dirname "$0")/_backup_db/$NAME/" >/dev/null 2>&1
        echo "已拉回本机：_backup_db/$NAME/"
    else
        echo "注意：服务器上没找到备份目录，只完成了服务器侧备份"
    fi
    ;;

cron)
    echo "========== 装每日自动备份（04:10）=========="
    scp -i "$KEY" -o StrictHostKeyChecking=no \
        "$(dirname "$0")/ops_remote_backup.sh" \
        "$SERVER_USER@$SERVER:$APP_DIR/ops_remote_backup.sh" >/dev/null 2>&1
    $SSH "
        chmod +x $APP_DIR/ops_remote_backup.sh
        ( crontab -l 2>/dev/null | grep -v 'yexi_backup' ; \
          echo '10 4 * * * /bin/bash $APP_DIR/ops_remote_backup.sh >/dev/null 2>&1  # yexi_backup' ) | crontab -
        echo '已装：'
        crontab -l | grep yexi_backup
    "
    echo "备份落在 $APP_DIR/_backup/db/，只留最近 7 份。"
    ;;

cron-off)
    $SSH "
        crontab -l 2>/dev/null | grep -v 'yexi_backup' | crontab -
        echo '已卸掉每日备份。剩下的备份：'
        ls -1d $APP_DIR/_backup/db/*/ 2>/dev/null | wc -l
    "
    ;;

trim-log)
    echo "========== 日志瘦身 =========="
    $SSH "
        echo -n '当前：'; journalctl --disk-usage
        mkdir -p /etc/systemd/journald.conf.d
        printf '[Journal]\nSystemMaxUse=500M\n' > /etc/systemd/journald.conf.d/yexi-size.conf
        systemctl restart systemd-journald
        journalctl --vacuum-size=500M
        echo -n '之后：'; journalctl --disk-usage
        df -h / | tail -1
    "
    ;;

rollback)
    if [ "${2:-}" != "-y" ]; then
        echo "回退会把线上代码退回上一个提交，然后重启服务。"
        echo "确认执行请加 -y：bash ops.sh rollback -y"
        echo ""
        echo "服务器上最近 3 个提交："
        $SSH "git -C $APP_DIR log --oneline -3"
        exit 0
    fi
    echo "========== 应急回退 =========="
    $SSH "
        set -e
        cd $APP_DIR
        echo -n '回退前：'; git log -1 --oneline
        git stash list | head -3
        git reset --hard HEAD~1
        echo -n '回退后：'; git log -1 --oneline
        systemctl restart yexi
        sleep 3
        systemctl is-active yexi
        curl -s -o /dev/null -w '首页 HTTP %{http_code}\n' http://127.0.0.1:8000/
    "
    echo ""
    echo "注意：这只是临时止血。master 上还是坏的那版，"
    echo "下次任何人 push 触发部署会把坏版本再拉回来。"
    echo "真要修好：本地 git revert 坏提交 → push → 自动部署。"
    ;;

restart)
    echo "========== 重启服务 =========="
    $SSH "systemctl restart yexi && sleep 3 && systemctl is-active yexi && curl -s -o /dev/null -w '首页 HTTP %{http_code}\n' http://127.0.0.1:8000/"
    ;;

health)
    echo "========== 从本机自检线上安装链路 =========="
    PY="python"
    if [ -x "C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe" ]; then
        PY="C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
    fi
    "$PY" "$(dirname "$0")/check_install.py" "${2:-}"
    ;;

*)
    echo "不认识的命令：$CMD"
    echo "可用：status / logs / backup / cron / cron-off / trim-log / rollback / restart / health"
    exit 1
    ;;
esac
