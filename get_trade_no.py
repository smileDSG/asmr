# 查支付宝交易号——比赛提交表单要填的那个。
#
# 朋友付款成功后，直接双击运行这个文件（或 python get_trade_no.py），
# 它会打印出 28 位交易号，复制去填表即可。
#
# 不依赖本地服务，直接读下单记录去问支付宝。

import nowpay
import json

orders = nowpay.list_orders()
if not orders:
    print("还没有下单记录。先在网页上点一次「带走」生成付款二维码。")
else:
    print("最近一笔下单：", orders[-1].get("created_at", ""))
    r = nowpay.purchase_query(orders[-1])
    status = r.get("purchase_status", "")
    trade_no = r.get("trade_no", "")
    print("支付状态：", status)
    if status == "SUCCESS" and trade_no:
        print("")
        print("========================================")
        print("支付宝交易号（复制这个填比赛表单）：")
        print(trade_no)
        print("========================================")
    elif status == "WAIT_PAY":
        print("还没查到付款。确认朋友已付成功，再跑一次。")
    else:
        print("查询结果：", json.dumps(r, ensure_ascii=False)[:500])
