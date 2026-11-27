# 支付：商品定义、下单、验签、入账
#
# 三种模式，由环境变量 YEXI_PAY_MODE 控制：
#   mock    本地演示，不连支付宝，点按钮即视为支付成功（用于开发和路演彩排）
#   sandbox 支付宝沙箱，走真实接口但不扣真钱
#   prod    正式收款
#
# mock 模式不依赖任何第三方包；sandbox / prod 需要：
#   pip install python-alipay-sdk
#
# 铁律：支付是否成功，只认「异步通知(notify)」或「主动查单(query)」，
# 绝不认浏览器 return_url 跳回来的结果——用户付完直接关页面，同步回调就不来了；
# 反过来，return_url 是可以被伪造的。

import json
import os
import secrets
import time

import auth_db

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "pay_config.json")

# 安全默认：sandbox（没配支付宝 key 就付不了，但绝不会白送权益）。
# 本地路演要白嫖演示，必须显式设 YEXI_PAY_MODE=mock（见 legacy/scripts/start-local.bat）。
# 线上由部署脚本写 /etc/yexi.env 设 YEXI_PAY_MODE=prod，下面会读。
def _read_env_file(path):
    """从 env 文件读一个 key——不依赖 systemd 是否配置了 EnvironmentFile。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("YEXI_PAY_MODE="):
                    return line.split("=", 1)[1].strip().strip("'\"")
    except Exception:
        pass
    return ""


MODE_FROM_ENV = os.environ.get("YEXI_PAY_MODE", "").strip().lower()
MODE_FROM_FILE = _read_env_file("/etc/yexi.env") if os.path.exists("/etc/yexi.env") else ""
PAY_MODE = (MODE_FROM_ENV or MODE_FROM_FILE or "sandbox").lower()
VALID_MODES = ("mock", "sandbox", "prod")
if PAY_MODE not in VALID_MODES:
    raise RuntimeError("YEXI_PAY_MODE 只能是 mock / sandbox / prod，当前是：" + PAY_MODE)


def startup_check():
    """启动时检查支付配置。不崩服务（听声不能受影响），但把问题喊出来。"""
    if PAY_MODE == "mock":
        print("[pay 警告] 当前是 mock 模式：点一下就当付款成功，只能本地演示用，绝不能上公网！", flush=True)
        return True
    cfg = load_config()
    if not cfg or not cfg.get("app_id"):
        print("[pay 错误] " + PAY_MODE + " 模式缺少 pay_config.json 或 app_id，支付不可用（但听声正常）", flush=True)
        return False
    print("[pay] 支付模式：" + PAY_MODE + "，配置已就绪", flush=True)
    return True

# ---------------- 商品 ----------------
# price_cents 用「分」，避免浮点。kind 是权益类型：
#   full       解锁全部素材 + 不限次生成，按期到期
#   commercial 商用买断，永久有效
PRODUCTS = {
    "trial3": {
        "id": "trial3",
        "name": "夜息 · 三次体验",
        "short": "3 段音频（追问不扣）+ 全库 30 天",
        "price_cents": 290,
        "kind": "full",
        "quota": 3,
        "days": 30,
        "note": "先过三个晚上试试",
    },
    "day3": {
        "id": "day3",
        "name": "夜息 · 三日全库",
        "short": "3 天全库 + 不限次生成",
        "price_cents": 290,
        "kind": "full",
        "quota": 1,
        "days": 3,
        "note": "先过三个晚上试试",
    },
    "month": {
        "id": "month",
        "name": "夜息 · 整月全库",
        "short": "30 天全库 + 不限次生成",
        "price_cents": 1500,
        "kind": "full",
        "quota": 1,
        "days": 30,
        "note": "一个月，每晚都有得挑",
    },
    "commercial": {
        "id": "commercial",
        "name": "夜息 · 商用买断",
        "short": "商用授权 + 授权证书",
        "price_cents": 3990,
        "kind": "commercial",
        "quota": 1,
        "days": 0,
        "note": "永久，可用于自己的作品",
    },
}

def public_products():
    # 给前端商品墙用：只暴露该看的东西，不把内部字段漏出去
    out = []
    for p in PRODUCTS.values():
        out.append({
            "id": p["id"],
            "name": p["name"],
            "short": p["short"],
            "price": format_cents(p["price_cents"]),
            "price_cents": p["price_cents"],
            "note": p["note"],
        })
    return out


def format_cents(cents):
    return "%d.%02d" % (int(cents) // 100, int(cents) % 100)


def parse_yuan(text):
    # 支付宝的金额固定两位小数字符串，用字符串解析，不经过 float
    text = str(text or "0").strip()
    if "." in text:
        whole, frac = text.split(".", 1)
        frac = (frac + "00")[:2]
    else:
        whole, frac = text, "00"
    try:
        return int(whole) * 100 + int(frac)
    except ValueError:
        return -1


def get_product(product_id):
    return PRODUCTS.get(str(product_id or "").strip())


def new_out_trade_no():
    # 商户订单号全局唯一，重复的话支付宝会关联到原单据
    return "YX" + time.strftime("%Y%m%d%H%M%S") + secrets.token_hex(3).upper()


# ---------------- 配置 ----------------
def load_config():
    if not os.path.isfile(CONFIG_PATH):
        return None
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("[pay] 读取 pay_config.json 失败：%s" % e, flush=True)
        return None


def _client():
    # 延迟导入：mock 模式完全不需要这个包
    try:
        from alipay import AliPay
    except ImportError:
        raise RuntimeError(
            "缺少依赖：请先执行 pip install python-alipay-sdk"
        )
    cfg = load_config()
    if not cfg:
        raise RuntimeError("缺少 pay_config.json，正式支付无法下单")
    key_dir = BASE

    def read_key(name):
        path = name
        if not os.path.isabs(path):
            path = os.path.join(key_dir, name)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    return AliPay(
        appid=cfg.get("app_id", ""),
        app_notify_url=cfg.get("notify_url", ""),
        app_private_key_string=read_key(cfg.get("private_key_file", "")),
        alipay_public_key_string=read_key(cfg.get("alipay_public_key_file", "")),
        sign_type="RSA2",
        debug=(PAY_MODE != "prod"),
    )


def configured():
    # 前端用它决定「能不能真的付」，避免用户点了按钮才发现没配好
    if PAY_MODE == "mock":
        return True
    cfg = load_config()
    if not cfg:
        return False
    return bool(cfg.get("app_id"))


# ---------------- 下单 ----------------
def create(user_id, product_id, channel=""):
    p = get_product(product_id)
    if not p:
        return None
    out_trade_no = new_out_trade_no()
    auth_db.create_order(
        out_trade_no, user_id, p["id"], p["name"], p["price_cents"], channel
    )
    return {
        "out_trade_no": out_trade_no,
        "pay_url": _pay_url(out_trade_no, p),
        "product": {
            "id": p["id"],
            "name": p["name"],
            "price": format_cents(p["price_cents"]),
        },
        "mode": PAY_MODE,
    }


def _pay_url(out_trade_no, p):
    if PAY_MODE == "mock":
        # 本地模拟收银台，点一下就等于支付成功，走的是同一套入账逻辑
        return "/pay_mock.html?order=" + out_trade_no

    cfg = load_config() or {}
    client = _client()
    order_string = client.api_alipay_trade_page_pay(
        out_trade_no=out_trade_no,
        total_amount=format_cents(p["price_cents"]),
        subject=p["name"],
        return_url=cfg.get("return_url", ""),
        notify_url=cfg.get("notify_url", ""),
    )
    # 沙箱和生产是不同的网关，拼错了会一直报「验签失败」
    if PAY_MODE == "sandbox":
        gateway = "https://openapi.alipaydev.com/gateway.do"
    else:
        gateway = cfg.get("gateway", "https://openapi.alipay.com/gateway.do")
    return gateway + "?" + order_string


# ---------------- 回调与入账 ----------------
def verify_notify(form):
    # mock 模式下前端会直接调 mock_success，这里不做验签。
    # 生产/沙箱必须是真验签，签不过一律当假。
    if PAY_MODE == "mock":
        return True
    client = _client()
    data = dict(form)
    signature = data.pop("sign", "")
    data.pop("sign_type", None)
    if not signature:
        return False
    return bool(client.verify(data, signature))


def check_notify(order, form):
    # 验签通过还不够：时间窗 + 金额 + 订单号都要对上。
    # 时间窗挡「录一条真通知以后反复重放」；幂等由 grant() 的 mark_order_paid 保证。
    if not order:
        return False
    # 防重放：notify_time 是支付宝必填字段，格式 yyyy-MM-dd HH:mm:ss（北京时间 UTC+8）。
    # 关键：只对「还没入账」的订单查时间窗。因为支付宝合法重发可能在几小时后，
    # 若一律按 5 分钟拒，遇到"首次通知没入账成功、靠重发补救"的场景会让用户付了钱没拿到权益。
    # 已 paid 的订单直接放行——grant() 的幂等会挡住重复入账，不会多发权益。
    if PAY_MODE != "mock" and order.get("status") != "paid":
        notify_time = str(form.get("notify_time") or "").strip()
        try:
            from datetime import datetime, timedelta, timezone
            tz8 = timezone(timedelta(hours=8))
            sent = datetime.strptime(notify_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz8)
            now = datetime.now(tz8)
            # 允许前后 5 分钟：容忍网络延迟和轻微时钟偏差
            delta = abs((now - sent).total_seconds())
            if delta > 300:
                print("[pay] 通知时间超出5分钟窗口（%.0f秒），丢弃" % delta, flush=True)
                return False
        except (ValueError, TypeError):
            print("[pay] notify_time 格式不对，丢弃", flush=True)
            return False
    status = str(form.get("trade_status", ""))
    if status not in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        return False
    paid_cents = parse_yuan(form.get("total_amount", "0"))
    if paid_cents != int(order["amount_cents"]):
        print(
            "[pay] 金额不符 %s：应付 %d，实付 %d"
            % (order["out_trade_no"], order["amount_cents"], paid_cents),
            flush=True,
        )
        return False
    if str(form.get("out_trade_no", "")) != order["out_trade_no"]:
        return False
    return True


def grant(out_trade_no, trade_no=""):
    # 幂等入账：同一订单重复通知只会发一次权益
    order = auth_db.get_order(out_trade_no)
    if not order:
        return False
    if order["status"] == "paid":
        return True
    changed = auth_db.mark_order_paid(out_trade_no, trade_no)
    if not changed:
        return True
    p = get_product(order["product_id"])
    if not p:
        print("[pay] 未知商品：%s" % order["product_id"], flush=True)
        return False
    expire_at = 0
    if p["days"] > 0:
        expire_at = time.time() + p["days"] * 86400
    auth_db.add_entitlement(order["user_id"], p["kind"], p["quota"], expire_at)
    # 买了商用买断的人，当然也得能用全库素材，否则拿到授权却生成不了东西
    if p["kind"] == "commercial":
        auth_db.add_entitlement(order["user_id"], "full", 1, 0)
    print(
        "[pay] 入账 %s 用户%d %s +%d"
        % (out_trade_no, order["user_id"], p["kind"], p["quota"]),
        flush=True,
    )
    return True


def query(out_trade_no):
    # 通知丢失时的兜底：主动去支付宝问这笔单子到底付了没
    if PAY_MODE == "mock":
        order = auth_db.get_order(out_trade_no)
        return order["status"] if order else "TRADE_NOT_EXIST"
    client = _client()
    result = client.api_alipay_trade_query(out_trade_no=out_trade_no)
    return str(result.get("trade_status", ""))
