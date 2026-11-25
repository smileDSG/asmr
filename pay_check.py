# 支付配置自检
# 用法：
#   YEXI_PAY_MODE=sandbox python pay_check.py
#   YEXI_PAY_MODE=prod    python pay_check.py
# mock 模式不需要任何配置，跑这个只会告诉你「不用配」。

import os
import sys
import time

import pay

BASE = os.path.dirname(os.path.abspath(__file__))


def ok(msg):
    print("[OK]   " + msg)


def warn(msg):
    print("[注意] " + msg)


def bad(msg):
    print("[错误] " + msg)


def main():
    mode = pay.PAY_MODE
    print("当前模式：" + mode)

    if mode not in ("mock", "sandbox", "prod"):
        bad("YEXI_PAY_MODE 只能是 mock / sandbox / prod")
        return 1

    if mode == "mock":
        ok("mock 模式不需要任何配置，点按钮就是演示支付")
        return 0

    cfg = pay.load_config()
    if not cfg:
        bad("缺少 pay_config.json，从 pay_config.example.json 复制一份再填")
        return 1

    need = [
        "app_id",
        "private_key_file",
        "alipay_public_key_file",
        "notify_url",
        "return_url",
    ]
    for k in need:
        if not str(cfg.get(k) or "").strip():
            bad("配置缺字段：" + k)
            return 1
    ok("配置字段齐全")

    for key in ("private_key_file", "alipay_public_key_file"):
        name = str(cfg.get(key))
        path = name
        if not os.path.isabs(path):
            path = os.path.join(BASE, name)
        if not os.path.isfile(path):
            bad("找不到密钥文件：" + path)
            return 1
        text = open(path, "r", encoding="utf-8").read()
        if "BEGIN" not in text:
            bad(path + " 不像 PEM 文件，缺 -----BEGIN----- 头")
            return 1
        ok("密钥文件正常：" + name)

    notify = str(cfg.get("notify_url"))
    if not notify.startswith("http"):
        bad("notify_url 必须是 http(s) 地址，支付宝才能回调")
        return 1
    if "127.0.0.1" in notify or "localhost" in notify:
        bad("notify_url 不能是 localhost，支付宝的回调进不来，要用内网穿透地址")
        return 1
    if "REPLACE-ME" in notify or "example.com" in notify:
        bad("notify_url 还是占位地址，换成真实公网地址才能收款")
        return 1
    warn("确认这个地址外网能打开：" + notify)

    try:
        client = pay._client()
        order_string = client.api_alipay_trade_page_pay(
            out_trade_no="SELFTEST" + str(int(time.time())),
            total_amount="0.01",
            subject="夜息配置自检",
            return_url=str(cfg.get("return_url")),
            notify_url=notify,
        )
        ok("签名算得出来，支付链接长度 " + str(len(order_string)))
    except Exception as e:
        bad("生成支付链接失败：" + str(e))
        print("      常见原因：私钥不是 PKCS8、公钥填成了「应用公钥」而不是「支付宝公钥」")
        return 1

    print("")
    print("下一步：")
    print("  1. 用浏览器打开一次支付链接，确认能跳到支付宝收银台")
    print("  2. 付 0.01 元，看服务端日志有没有 [pay] notify ... TRADE_SUCCESS")
    print("  3. 回到页面看权益有没有到账")
    return 0


if __name__ == "__main__":
    sys.exit(main())
