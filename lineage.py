# 一段音频的「免费 AI 修改」额度：生成后前 3 次改不扣次数，第 4 次起扣。
# 规则：
#   1. 首次生成时服务端发一个 lineage id，前端存下来，后续每次改都带上
#   2. 同一个 lineage 前 FREE_EDITS 次修改免费，之后每次修改按正常生成扣 1 次
#   3. 只记次数，不管用户是游客还是登录；按 lineage id 隔离
#   4. 30 天没动过的 lineage 清掉，防止文件无限涨
# 存储：data/lineage_edits.json（服务端文件，前端拿不到、不能伪造次数）
# 失败时保守放行（宁可多给几次免费，不能让正常用户改不了）

import json
import os
import threading
import time

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
STORE = os.path.join(DATA_DIR, "lineage_edits.json")
FREE_EDITS = 3
MAX_AGE = 30 * 24 * 3600
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
    try:
        if not os.path.isdir(DATA_DIR):
            os.makedirs(DATA_DIR)
        tmp = STORE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, STORE)
    except Exception as ex:
        print("[lineage] 保存失败：" + str(ex), flush=True)


def create(owner=""):
    """首次生成时调用：新建一个 lineage，返回 id。"""
    import secrets
    lid = secrets.token_hex(12)
    with _LOCK:
        data = _load()
        data[lid] = {"edits": 0, "owner": str(owner or ""), "ts": time.time()}
        _save(data)
    return lid


def free_left(lid, owner=""):
    """这段还能免费改几次。不存在时按新段处理（返回满额）。"""
    if not lid:
        return FREE_EDITS
    try:
        with _LOCK:
            data = _load()
            e = data.get(lid)
            if not e:
                return FREE_EDITS
            # 归属不一致：不认这个 lineage，防止拿别人的免费额度
            if e.get("owner") and owner and e.get("owner") != owner:
                return FREE_EDITS
            return max(0, FREE_EDITS - int(e.get("edits", 0)))
    except Exception:
        return FREE_EDITS


def mark_edit(lid, owner=""):
    """记一次修改。返回这次是否扣了额度（True=该扣）。"""
    if not lid:
        return True
    try:
        with _LOCK:
            data = _load()
            e = data.get(lid)
            now = time.time()
            if not e:
                # lineage 不存在（过期被清、或老版本没带），保守给满额
                data[lid] = {"edits": 1, "owner": str(owner or ""), "ts": now}
                _save(data)
                return False
            used = int(e.get("edits", 0))
            e["edits"] = used + 1
            e["ts"] = now
            if owner:
                e["owner"] = str(owner)
            _save(data)
            # 前 FREE_EDITS 次免费，第 FREE_EDITS+1 次起该扣
            return used >= FREE_EDITS
    except Exception:
        return False  # 出错保守放行，不扣用户次数


def cleanup():
    """清掉长期没动的 lineage，防止文件无限涨。启动时调用一次即可。"""
    try:
        with _LOCK:
            data = _load()
            now = time.time()
            fresh = {}
            for k, v in data.items():
                if now - float(v.get("ts", 0)) <= MAX_AGE:
                    fresh[k] = v
            if len(fresh) != len(data):
                _save(fresh)
                print("[lineage] 清理过期记录 " + str(len(data) - len(fresh)) + " 条", flush=True)
    except Exception:
        pass
