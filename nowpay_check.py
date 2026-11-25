# 即刻收接入自检：配置好商品 ID 后先跑这个，逐项告诉你缺什么。
#
# 用法：
#   python nowpay_check.py              # 只检查本地配置，不联网
#   python nowpay_check.py --online     # 额外查一次支付宝商品状态
#
# 不需要设 YEXI_NOWPAY 环境变量，这个脚本只读配置。

import json
import os
import sys

import nowpay

BASE = os.path.dirname(os.path.abspath(__file__))
GOOD = "[OK]   "
BAD = "[错误] "
WARN = "[提醒] "


def line(text):
    print(text, flush=True)


def check_local():
    problems = 0
    cfg = nowpay.load_config()
    if not cfg:
        line(BAD + "缺少 pay_config.json")
        return 1

    line(GOOD + "找到 pay_config.json")

    if not cfg.get("app_id"):
        line(BAD + "app_id 是空的")
        problems += 1
    else:
        line(GOOD + "app_id：" + str(cfg["app_id"]))

    for key in ("private_key_file", "alipay_public_key_file"):
        name = cfg.get(key, "")
        path = name
        if not os.path.isabs(path):
            path = os.path.join(BASE, name)
        if name and os.path.isfile(path):
            line(GOOD + key + "：" + name)
        else:
            line(BAD + key + " 文件不存在：" + str(name))
            problems += 1

    np = cfg.get("nowpay") or {}
    products = np.get("products") or {}
    if not products:
        line(BAD + "pay_config.json 里还没有 nowpay.products 段")
        line("      去「即刻收」小程序建好商品，复制商品 ID 填进去")
        problems += 1
        return problems

    line(GOOD + "nowpay.products 有 " + str(len(products)) + " 个商品")
    for name, info in products.items():
        pid = (info or {}).get("out_product_id", "")
        # 官方文档示例写 np_，但个人账号实际开出来是 DIRECT_ 开头，两种都认
        if pid.startswith("np_") or pid.startswith("DIRECT_"):
            line(GOOD + "  " + name + " -> " + pid)
        else:
            line(BAD + "  " + name + " 的商品 ID 不对：" + str(pid))
            line("      商品 ID 从小程序商品详情页复制，一般是 DIRECT_ 开头")
            problems += 1

    cb = np.get("callback_url", "")
    if not cb.startswith("https://"):
        line(BAD + "callback_url 必须是 https:// 开头的公网地址")
        problems += 1
    else:
        line(GOOD + "callback_url：" + cb)

    try:
        from alipay import AliPay
        line(GOOD + "python-alipay-sdk 已安装")
    except ImportError:
        line(BAD + "缺少 python-alipay-sdk，执行：pip install python-alipay-sdk")
        problems += 1

    return problems


def check_online():
    line("")
    line("=== 联网检查商品状态 ===")
    products = nowpay.products_config()
    if not products:
        line(WARN + "没有商品 ID，跳过")
        return 0
    bad = 0
    for name in products:
        line("查询 " + name + " ...", flush=True)
        try:
            result = nowpay.charge_query(name)
        except Exception as e:
            line(BAD + "  调用失败：" + str(e))
            bad += 1
            continue
        status = result.get("capability_status", "")
        mode = result.get("billing_mode", "")
        line("  状态：" + str(status) + "  收费模式：" + str(mode))
        if status == "ENABLED":
            line(GOOD + "  商品可售")
        elif status == "ACTION_REQUIRED":
            line(BAD + "  需要去小程序处理认证/签约/商品资料")
            bad += 1
        elif status in ("PENDING", "CONFIGURING", "NOT_CONFIGURED"):
            line(WARN + "  还没准备好，去小程序看进度")
            bad += 1
        elif status == "DISABLED":
            line(WARN + "  已下架，不能新增购买")
        else:
            line(WARN + "  未识别的状态，把上面的输出发给 AI 看")
    return bad


def main():
    line("=== 即刻收本地配置检查 ===")
    problems = check_local()
    if "--online" in sys.argv:
        problems += check_online()

    line("")
    if problems == 0:
        line(GOOD + "全部通过。可以启动：YEXI_NOWPAY=1 python server.py")
        return 0
    line(BAD + "有 " + str(problems) + " 项要处理，处理完再跑一次")
    return 1


if __name__ == "__main__":
    sys.exit(main())
