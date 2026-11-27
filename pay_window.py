# 即刻收「全库 30 天」时限：纯服务端规则，支付宝那边只管次数、不管时间。
# 规则：
#   1. 第一次查到这个买家有余额 = 真付款成功了，记下当天日期（YYYY-MM-DD）
#   2. 30 天内：给全库；超过 30 天：不给全库（但支付宝的次数还在，不丢失）
#   3. 加购不重置起点，取最早那次付款日
#   4. 只记日期不记精确时间，避开时区/时区差问题
# 存储：data/nowpay_first_paid.json（本地文件，前端拿不到，不能伪造）
# 失败时保守放行（宁可多给几天，不能让付了钱的人用不了）

import json
import os
import secrets
import threading
import time

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
STORE = os.path.join(DATA_DIR, "nowpay_first_paid.json")
DAYS = 30
_LOCK = threading.Lock()


def _load():
    try:
        if os.path.isfile(STORE):
            with open(STORE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save(data):
    tmp = None
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = os.path.join(DATA_DIR, f".nowpay_first_paid.{secrets.token_hex(4)}.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, STORE)
    except Exception as e:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        print("[pay_window] 保存失败：" + str(e)[:100], flush=True)


def expire_at_of(buyer):
    """返回全库到期的时间戳（秒）；没有记录返回 0。给前端显示用。"""
    if not buyer:
        return 0
    with _LOCK:
        first = _load().get(str(buyer))
    if not first:
        return 0
    try:
        t0 = time.mktime(time.strptime(first, "%Y-%m-%d"))
        return t0 + DAYS * 86400
    except Exception:
        return 0


def mark_and_check(buyer):
    """买家有余额时调用。返回 True=还在30天内（给全库），False=过期。
    第一次调用会记下当天日期；已有记录则取最早那次。
    """
    if not buyer:
        return False
    today = time.strftime("%Y-%m-%d")
    with _LOCK:
        data = _load()
        first = data.get(str(buyer))
        if not first:
            data[str(buyer)] = today
            _save(data)
            first = today
    try:
        t0 = time.mktime(time.strptime(first, "%Y-%m-%d"))
        t1 = time.mktime(time.strptime(today, "%Y-%m-%d"))
        return (t1 - t0) < DAYS * 86400
    except Exception:
        return True  # 日期格式坏了，保守放行
