"""Lightweight error-tracking and webhook alerting using Python stdlib only."""

import collections
import json
import os
import threading
import time
import urllib.request

WINDOW_SECONDS = 300
DEDUP_SECONDS = 600
MAX_RECENT = 30
CLIENT_ALERT_THRESHOLD = 3

_LOCK = threading.Lock()
_SERVER_ERR_TIMES = collections.deque()
_CLIENT_ERR_TIMES = collections.deque()
_CLIENT_ERR_BY_KEY = {}
_RECENT_ERRORS = collections.deque(maxlen=MAX_RECENT)
_LAST_SENT = {}


def _webhook_url():
    return (os.environ.get("YEXI_ALERT_WEBHOOK") or "").strip()


def _prune(dq, now):
    cutoff = now - WINDOW_SECONDS
    while dq and dq[0] < cutoff:
        dq.popleft()


def _format_payload(url, title, detail):
    text = f"[夜息告警] {title}\n{detail}".strip()
    low = url.lower()
    if "feishu.cn" in low or "larksuite.com" in low:
        return {"msg_type": "text", "content": {"text": text}}
    if "dingtalk.com" in low or "qyapi.weixin.qq.com" in low:
        return {"msgtype": "text", "text": {"content": text}}
    if "api.day.app" in low or "/push" in low:
        return {"title": title, "body": detail[:500]}
    return {"text": text, "title": title, "message": detail}


def _post_webhook(url, payload):
    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read(256)
    except Exception as exc:
        print(f"[alerts] webhook send failed: {exc}", flush=True)


def send_alert(title, detail, dedup_key=""):
    """Send an asynchronous webhook alert if YEXI_ALERT_WEBHOOK is configured."""
    url = _webhook_url()
    if not url:
        return False

    now = time.time()
    key = dedup_key or title
    with _LOCK:
        last = _LAST_SENT.get(key, 0.0)
        if now - last < DEDUP_SECONDS:
            return False
        _LAST_SENT[key] = now

    payload = _format_payload(url, title, detail)
    t = threading.Thread(target=_post_webhook, args=(url, payload), daemon=True)
    t.start()
    return True


def record_server_error(path, status_code, detail):
    """Record a 5xx/unhandled server error and trigger a deduplicated alert."""
    now = time.time()
    clean_path = (path or "").split("?", 1)[0][:120]
    clean_detail = str(detail or "")[:300]
    with _LOCK:
        _SERVER_ERR_TIMES.append(now)
        _prune(_SERVER_ERR_TIMES, now)
        _RECENT_ERRORS.append(
            {
                "kind": "server",
                "ts": int(now),
                "path": clean_path,
                "status": int(status_code),
                "detail": clean_detail,
            }
        )
    send_alert(
        f"服务端 {status_code} ({clean_path})",
        clean_detail or f"HTTP {status_code} on {clean_path}",
        dedup_key=f"server:{status_code}:{clean_path}",
    )


def record_client_error(page, message, detail="", kind="error"):
    """Record a frontend client error; alert on fatal or repeated bursts."""
    now = time.time()
    clean_page = (page or "")[:120]
    clean_msg = str(message or "")[:200]
    clean_detail = str(detail or "")[:400]
    key = f"{clean_page}:{clean_msg[:80]}"

    with _LOCK:
        _CLIENT_ERR_TIMES.append(now)
        _prune(_CLIENT_ERR_TIMES, now)
        dq = _CLIENT_ERR_BY_KEY.setdefault(key, collections.deque())
        dq.append(now)
        _prune(dq, now)
        burst_count = len(dq)
        _RECENT_ERRORS.append(
            {
                "kind": "client",
                "ts": int(now),
                "page": clean_page,
                "message": clean_msg,
                "detail": clean_detail,
            }
        )

    if kind == "fatal" or burst_count >= CLIENT_ALERT_THRESHOLD:
        send_alert(
            f"前端异常 ({clean_page})",
            f"5分钟内触发 {burst_count} 次：{clean_msg}\n{clean_detail}".strip(),
            dedup_key=f"client:{key}",
        )


def stats():
    """Return 5-minute error counts and webhook configuration status."""
    now = time.time()
    with _LOCK:
        _prune(_SERVER_ERR_TIMES, now)
        _prune(_CLIENT_ERR_TIMES, now)
        return {
            "server_5xx_5m": len(_SERVER_ERR_TIMES),
            "client_err_5m": len(_CLIENT_ERR_TIMES),
            "webhook_configured": bool(_webhook_url()),
        }
