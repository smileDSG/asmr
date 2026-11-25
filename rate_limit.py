# 全局限流：防刷 AI 接口烧钱、防暴力猜密码、防爬。
# 只存内存，重启清零——小项目够用，不引入 Redis。
# 写法朴素：字典 + 时间戳列表 + 滑动窗口，不搞令牌桶那套复杂的。
#
# 为什么不用前端的设备 ID？因为那是浏览器自己生成的，随手就能伪造。
# 这里按「客户端 IP」限，才是真正的防线。

import threading
import time

_lock = threading.Lock()
_hits = {}          # key -> [时间戳, ...]
_last_clean = 0.0

# 每类端点：窗口秒数 / 窗口内最多几次
# 生成类调 AI，最贵，卡最严；读类宽松；纯静态页面不设限（在 server 里跳过）
RULES = {
    "generate": (60, 8),     # /api/generate /api/agent_chat /api/preview /api/play 等
    "auth": (60, 10),        # 登录/注册
    "write": (60, 30),       # 发帖/评论/投票/改资料
    "read": (60, 180),       # 普通读接口
}

# 哪些路径算"生成类"（真的会调模型或合成音频，花钱花 CPU）
GENERATE_PATHS = {
    "/api/generate",
    "/api/agent_chat",
    "/api/preview",
    "/api/play",
    "/api/download",
    "/api/export_commercial",
}

AUTH_PATHS = {
    "/api/login",
    "/api/register",
    "/api/pay/mock_success",
}

WRITE_PATHS = {
    "/api/community_posts",
    "/api/community_posts/policy",
    "/api/community_posts/delete",
    "/api/comment",
    "/api/comment/delete",
    "/api/community_vote",
    "/api/feedback",
    "/api/recipes",
    "/api/recipes/delete",
    "/api/ear_profile",
    "/api/profile/update",
    "/api/queue_state",
    "/api/pay/create",
}


def category_of(path):
    if path in GENERATE_PATHS:
        return "generate"
    if path in AUTH_PATHS:
        return "auth"
    if path in WRITE_PATHS:
        return "write"
    return "read"


def client_ip(handler):
    # 不信任 X-Forwarded-For（可伪造），直接用 TCP 连接的对端 IP
    try:
        return handler.client_address[0] or "unknown"
    except Exception:
        return "unknown"


def check(path, handler):
    """返回 (是否放行, 类别, 剩余次数)。
    静态页面/图片/音频文件不走这里（server 会跳过），只管 /api/。"""
    global _last_clean
    cat = category_of(path)
    window, limit = RULES[cat]
    ip = client_ip(handler)
    key = cat + "|" + ip
    now = time.time()

    with _lock:
        # 偶尔清一次过期记录和空桶，防止内存无限涨
        if now - _last_clean > 300:
            for k in list(_hits.keys()):
                _hits[k] = [t for t in _hits[k] if now - t < 60]
                if not _hits[k]:
                    del _hits[k]
            _last_clean = now

        hits = _hits.setdefault(key, [])
        # 丢掉窗口外的旧时间戳
        while hits and now - hits[0] >= window:
            hits.pop(0)

        if len(hits) >= limit:
            return False, cat, 0

        hits.append(now)
        return True, cat, limit - len(hits)
