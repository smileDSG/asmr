# 即刻收（支付宝智能收款套件）接入
#
# 它和 pay.py 是两套完全不同的东西：
#   pay.py    = 电脑网站支付。自己建订单、等支付宝回调、自己发权益。
#   nowpay.py = 即刻收。商品、价格、订单、权益都在支付宝的「即刻收」小程序里配，
#               我们的代码只做三件事：查权益、给购买链接、用掉次数。
#
# 好处：不用自己接异步通知，不用自己管退款，不用网站备案（文档里没提）。
# 代价：要先拿到白名单资格，并且在小程序里把商品配好。
#
# 怎么用：
#   1. 配 pay_config.json 的 nowpay 段（商品 ID 从小程序商品详情页复制）
#   2. YEXI_NOWPAY=1 python server.py
#   3. 不设这个环境变量时，本模块完全不生效，原来的 mock 模式照常用
#
# 铁律：购买页跳回来（callback_url）只代表"页面回来了"，不代表付成功。
#       必须重新查一次权益，只有 decision=ALLOW 才放行。

import json
import os
import re
import secrets
import time
import urllib.parse

import auth_db

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "pay_config.json")

# 环境变量开关。不打开就完全不碰支付宝。
ENABLED = os.environ.get("YEXI_NOWPAY", "").strip().lower() in ("1", "true", "yes")

# 官方文档里的 6 个接口名，逐个封装在下面
M_CHARGE = "alipay.aipay.nowpaydirect.charge.query"
M_CONSULT = "alipay.aipay.nowpaydirect.purchase.consult"
M_PURCHASE = "alipay.aipay.nowpaydirect.purchase.create"
M_QUOTA_QUERY = "alipay.aipay.nowpaydirect.quota.query"
M_QUOTA_VERIFY = "alipay.aipay.nowpaydirect.quota.verify"
M_QUOTA_REFRESH = "alipay.aipay.nowpaydirect.quota.refresh"
M_PURCHASE_QUERY = "alipay.aipay.nowpaydirect.purchase.query"

# 本地保存每次下单的请求号——查交易号(purchase.query)要用原请求号，
# 不然超过 30 分钟就查不到了。比赛提交要填支付宝交易号，靠它取。
ORDERS_FILE = os.path.join(BASE, "data", "nowpay_orders.json")


def load_config():
    if not os.path.isfile(CONFIG_PATH):
        return None
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("[nowpay] 读配置失败：" + str(e), flush=True)
        return None


def products_config():
    """返回我们自己的商品名 -> 支付宝商品 ID 的映射。"""
    cfg = load_config() or {}
    return (cfg.get("nowpay") or {}).get("products") or {}


def callback_url():
    cfg = load_config() or {}
    return (cfg.get("nowpay") or {}).get("callback_url", "")


def _client():
    try:
        from alipay import AliPay
    except ImportError:
        raise RuntimeError("缺少依赖：pip install python-alipay-sdk")
    cfg = load_config()
    if not cfg:
        raise RuntimeError("缺少 pay_config.json")
    key_dir = BASE

    def read_key(name):
        path = name
        if not os.path.isabs(path):
            path = os.path.join(key_dir, name)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    return AliPay(
        appid=cfg.get("app_id", ""),
        app_private_key_string=read_key(cfg.get("private_key_file", "")),
        alipay_public_key_string=read_key(cfg.get("alipay_public_key_file", "")),
        sign_type="RSA2",
        debug=False,
    )


def _call(method, biz_content):
    """调一个即刻收接口，返回业务结果字典（已经验过签）。"""
    client = _client()
    # server_api 会自己签名、发请求、验响应签名
    raw = client.server_api(method, biz_content)
    # python-alipay-sdk 的 server_api 已经把外层 xxx_response 解开了，
    # 直接返回业务字典；有些版本仍带外层，两种都兼容。
    key = method.replace(".", "_") + "_response"
    if key in raw:
        result = raw.get(key) or {}
    else:
        result = raw
    code = str(result.get("code", ""))
    if code != "10000":
        # 把业务错误码打出来，方便对着官方文档排查
        print(
            "[nowpay] 接口 %s 返回 %s %s %s"
            % (method, code, result.get("sub_code", ""), result.get("sub_msg", "")),
            flush=True,
        )
    return result


def _product_id(product_key):
    """把我们自己的商品名翻译成支付宝商品 ID。"""
    return products_config().get(product_key, {}).get("out_product_id", "")


# ---------------- 1. 查商品状态 ----------------
def charge_query(product_key):
    """看商品在支付宝那边是不是可售。ENABLED 才展示购买入口。"""
    out_product_id = _product_id(product_key)
    if not out_product_id:
        return {"capability_status": "NOT_CONFIGURED", "billing_mode": ""}
    return _call(M_CHARGE, {"out_product_id": out_product_id})


# ---------------- 2. 查权益（决定放行还是引导购买）----------------
def purchase_consult(user_id, product_key):
    """
    问支付宝：这个用户能不能用这个商品。
    返回 ALLOW / PURCHASE_REQUIRED / DENY。
    """
    out_product_id = _product_id(product_key)
    if not out_product_id:
        return {"decision": "DENY", "reason_code": "NO_PRODUCT_ID"}

    biz = {
        "out_product_id": out_product_id,
        "external_buyer_id": str(user_id),
    }
    cb = callback_url()
    if cb.startswith("https://"):
        biz["callback_url"] = cb
    return _call(M_CONSULT, biz)


# ---------------- 3. 生成购买链接 ----------------
def purchase_create(user_id, product_key, sku_id=""):
    """返回支付宝托管购买页的链接，用户跳过去付款。"""
    out_product_id = _product_id(product_key)
    if not out_product_id:
        return {"error": "商品还没配置好"}

    biz = {
        "out_request_no": _request_no("purchase"),
        "out_product_id": out_product_id,
        "external_buyer_id": str(user_id),
    }
    # callback_url 必须是 HTTPS。没有 HTTPS 就别传——它是可选的，
    # 付完不自动跳回也没关系，权益一律靠 quota.query 查余额确认。
    cb = callback_url()
    if cb.startswith("https://"):
        biz["callback_url"] = cb
    if sku_id:
        biz["sku_id"] = sku_id
    result = _call(M_PURCHASE, biz)
    if str(result.get("code", "")) == "10000":
        # 存下来，付完靠它查支付宝交易号（比赛要填的那个）
        link_id = ""
        purchase_url = str(result.get("purchase_url", ""))
        m = re.search(r"purchaseLinkId=([^&]+)", purchase_url)
        if m:
            link_id = urllib.parse.unquote(m.group(1))
        _save_order({
            "out_request_no": biz["out_request_no"],
            "out_product_id": out_product_id,
            "external_buyer_id": str(user_id),
            "sku_id": sku_id,
            "purchase_link_id": link_id,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "qr_code": result.get("purchase_qr_code", ""),
        })
    return result


def _save_order(rec):
    """把一次下单的请求号存到本地，供以后查交易号。"""
    try:
        os.makedirs(os.path.dirname(ORDERS_FILE), exist_ok=True)
        orders = []
        if os.path.isfile(ORDERS_FILE):
            with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                orders = json.load(f)
        orders.append(rec)
        # 只留最近 200 条，够比赛用了
        orders = orders[-200:]
        with open(ORDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[nowpay] 保存订单记录失败：" + str(e), flush=True)


def _request_no(prefix):
    return prefix + time.strftime("%Y%m%d%H%M%S") + secrets.token_hex(3).upper()


# ---------------- 4. 查次数余额 ----------------
def quota_query(user_id, product_key):
    out_product_id = _product_id(product_key)
    if not out_product_id:
        return {"total": 0, "used": 0, "remaining": 0}
    return _call(
        M_QUOTA_QUERY,
        {
            "out_product_id": out_product_id,
            "external_buyer_id": str(user_id),
        },
    )


# ---------------- 5. 核销次数 ----------------
def quota_verify(user_id, product_key, amount=1, reason="生成一次助眠音频"):
    """
    真正消费时才调这个。光查到余额够，不等于已经扣掉了。
    必须自己保存 out_request_no，结果不确定时用原请求号查。
    """
    out_product_id = _product_id(product_key)
    if not out_product_id:
        return {"code": "ERROR", "error": "商品还没配置好"}
    return _call(
        M_QUOTA_VERIFY,
        {
            "out_request_no": _request_no("consume"),
            "out_product_id": out_product_id,
            "external_buyer_id": str(user_id),
            "amount": amount,
            "consume_reason": reason[:256],
        },
    )


# ---------------- 6. 查核销结果 ----------------
def quota_refresh(user_id, product_key, out_request_no):
    """网络超时或结果不明时，用原请求号查，不要换号重扣。"""
    out_product_id = _product_id(product_key)
    if not out_product_id:
        return {"code": "ERROR", "error": "商品还没配置好"}
    return _call(
        M_QUOTA_REFRESH,
        {
            "out_request_no": out_request_no,
            "out_product_id": out_product_id,
            "external_buyer_id": str(user_id),
        },
    )


# ---------------- 7. 查支付宝交易号（比赛提交要用）----------------
def purchase_query(rec=None):
    """
    查一笔购买是否成功，成功时返回支付宝交易号 trade_no。
    rec 是 purchase_create 时保存的订单记录；不传就取最近一笔。
    """
    if rec is None:
        rec = latest_order()
    if not rec:
        return {"error": "没有可查询的订单"}

    biz = {
        "out_product_id": rec.get("out_product_id", ""),
        "external_buyer_id": rec.get("external_buyer_id", ""),
    }
    if rec.get("out_request_no"):
        biz["out_request_no"] = rec["out_request_no"]
    if rec.get("purchase_link_id"):
        biz["purchase_link_id"] = rec["purchase_link_id"]
    if rec.get("sku_id"):
        biz["sku_id"] = rec["sku_id"]
    return _call(M_PURCHASE_QUERY, biz)


def latest_order():
    """取最近一笔下单记录。"""
    if not os.path.isfile(ORDERS_FILE):
        return None
    try:
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            orders = json.load(f)
        return orders[-1] if orders else None
    except Exception:
        return None


def list_orders():
    if not os.path.isfile(ORDERS_FILE):
        return []
    try:
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []
