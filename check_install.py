# 夜息自检：安装包到底能不能下、下下来是不是好的、页面是不是最新版
#
# 用法：
#   python check_install.py                  # 检查线上（默认地址）
#   python check_install.py http://ip:8000   # 检查别的地址（比如本机起的 8011）
#   python check_install.py --make-qr        # 重新生成下载二维码，顺带自检
#
# 任何一项打 [X] 就是坏的，脚本退出码 1，方便挂定时任务报警。
#
# 为什么要有这个脚本：
#   2026-11-27 线上出过一次「按钮点了不下载」——安装包本身是好的，
#   坏在页面先发 HEAD 探文件，而后端没实现 do_HEAD，一律回 501，
#   预检永远失败。人点一眼看不出来，脚本一跑就现形。

import hashlib
import io
import os
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile

DEFAULT_BASE = "http://47.101.59.166:8000"
APK_PATH = "/download/yexi.apk"
QR_PATH = "/download/qr-download.png"
SITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "product_site")

pass_count = 0
fail_count = 0
warn_count = 0
failures = []


def ok(name, detail):
    global pass_count
    pass_count = pass_count + 1
    print("[OK] " + name + "：" + detail)


def bad(name, detail):
    global fail_count
    fail_count = fail_count + 1
    failures.append(name + "：" + detail)
    print("[X ] " + name + "：" + detail)


def warn(name, detail):
    global warn_count
    warn_count = warn_count + 1
    print("[! ] " + name + "：" + detail)


def wrap(e):
    return str(e)


def http(base, path, method="GET", timeout=90):
    """发一个请求，返回 (状态码, 头字典, 正文bytes, 耗时秒)。
    4xx/5xx 也不抛出去，把状态码拿回来自己判断。"""
    url = base + path
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", "yexi-selfcheck/1.0")
    start = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        body = resp.read()
        headers = dict(resp.headers)
        code = resp.status
        resp.close()
    except urllib.error.HTTPError as e:
        code = e.code
        headers = dict(e.headers)
        body = b""
        e.close()
    except Exception as e:
        code = 0
        headers = {}
        body = b""
        print("     连不上：" + wrap(e))
    return code, headers, body, time.time() - start


def sha256_text(body):
    """算正文指纹。先去 \r，避免 Windows 换行和服务器换行不一致误报。"""
    clean = body.replace(b"\r", b"")
    return hashlib.sha256(clean).hexdigest()


def check_page(base):
    code, headers, body, cost = http(base, "/install.html")
    if code != 200:
        bad("安装页能打开", "HTTP " + str(code))
        return
    ok("安装页能打开", "HTTP 200，" + str(len(body)) + " 字节，" + str(round(cost * 1000)) + " ms")

    html = body.decode("utf-8", "replace")
    if 'href="' + APK_PATH + '"' in html:
        ok("页面指向安装包", "按钮 href=" + APK_PATH)
    else:
        bad("页面指向安装包", "页面里找不到 href=" + APK_PATH + "，按钮可能被改坏了")

    if "method: \"HEAD\"" in html or "method:'HEAD'" in html:
        bad("下载前预检", "页面还在发 HEAD 预检，后端一旦不支持就点不动（上次就是这么坏的）")
    else:
        ok("下载前预检", "页面没有再发 HEAD 预检，点按钮直接下")

    # 线上文件和本地文件是不是同一份，判断"改了有没有真的上线"
    local = os.path.join(SITE_DIR, "install.html")
    if not os.path.isfile(local):
        warn("线上=本地", "本地没有 product_site/install.html，跳过比对")
        return
    f = open(local, "rb")
    local_bytes = f.read()
    f.close()
    if sha256_text(local_bytes) == sha256_text(body):
        ok("线上=本地", "内容一致，最新改动已上线")
    else:
        warn("线上=本地", "线上和本地不一致：要么还没部署，要么部署失败")


def check_head(base):
    # 单独测 HEAD：这是上次那个 bug 的核心，必须常驻检查
    code, headers, body, cost = http(base, APK_PATH, method="HEAD")
    if code == 200:
        ok("HEAD 探文件", "HTTP 200（没实现 do_HEAD 的老版本这里会是 501）")
    elif code == 501:
        bad("HEAD 探文件", "HTTP 501 服务器不支持 HEAD——页面若做预检就会点不动")
    else:
        bad("HEAD 探文件", "HTTP " + str(code))


def check_apk(base):
    code, headers, body, cost = http(base, APK_PATH)
    if code != 200:
        bad("安装包能下载", "HTTP " + str(code) + "（文件不在服务器上？看 /opt/yexi/product_site/download/）")
        return

    size = len(body)
    head_len = headers.get("Content-Length") or headers.get("content-length") or ""
    speed = 0.0
    if cost > 0:
        speed = size / cost / 1024 / 1024
    ok("安装包能下载", "HTTP 200，" + str(size) + " 字节，" + str(round(cost, 1)) + " 秒，"
       + str(round(speed, 2)) + " MB/s")

    if head_len and str(head_len).strip() != str(size):
        bad("下载完整性", "实际收到 " + str(size) + " 字节，服务器声明 " + str(head_len) + "，包被截断了")
    else:
        ok("下载完整性", "收到的字节数和 Content-Length 一致")

    ctype = headers.get("Content-Type") or headers.get("content-type") or ""
    if "android" in ctype:
        ok("下载类型", ctype)
    elif ctype:
        warn("下载类型", ctype + "（不是 android 包类型，安卓一般也能装，但浏览器可能当普通文件）")
    else:
        warn("下载类型", "服务器没给 Content-Type")

    if body[0:2] != b"PK":
        bad("文件是不是 APK", "开头不是 PK，下到的不是 zip/apk（可能是错误页）")
        return
    try:
        z = zipfile.ZipFile(io.BytesIO(body))
        names = z.namelist()
        bad_names = z.testzip()
        z.close()
    except Exception as e:
        bad("文件是不是 APK", "解不开：" + wrap(e))
        return
    if bad_names is not None:
        bad("文件是不是 APK", "zip 里 " + str(bad_names) + " 校验失败，包损坏")
        return
    if "AndroidManifest.xml" not in names:
        bad("文件是不是 APK", "zip 里没有 AndroidManifest.xml，不是正常 APK")
        return
    ok("文件是不是 APK", "zip 完整，" + str(len(names)) + " 个内部文件，MANIFEST 在")


def qr_matrix_from_png(png):
    """把二维码图片读成 0/1 矩阵（不含白边）。
    两步：先用游程公约数算出单个模块多少像素，
    再裁掉四周白边，剩下的宽度 / 模块边长 = 模块数。
    注意别把白边算进模块数：370px 的图可能是 29 模块 + 4 圈白边（共 37 格）。"""
    from PIL import Image
    from math import gcd

    im = Image.open(io.BytesIO(png)).convert("L")
    w = im.size[0]
    h = im.size[1]
    px = im.load()

    g = 0
    for y in range(h):
        last = px[0, y]
        run = 0
        for x in range(w):
            v = px[x, y]
            if v == last:
                run = run + 1
            else:
                g = gcd(g, run)
                last = v
                run = 1
        g = gcd(g, run)
    if g <= 0:
        raise ValueError("算不出模块大小")

    # 找出所有黑像素的范围，把四周白边裁掉
    x0, y0, x1, y1 = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if px[x, y] < 128:
                if x < x0:
                    x0 = x
                if x > x1:
                    x1 = x
                if y < y0:
                    y0 = y
                if y > y1:
                    y1 = y
    if x1 < 0:
        raise ValueError("整张图都是白的，没有二维码")

    mods = (x1 - x0 + 1) // g
    rows = []
    for y in range(mods):
        row = []
        for x in range(mods):
            # 取模块正中心那个像素，避免压在格子边界上
            v = px[x0 + x * g + g // 2, y0 + y * g + g // 2]
            row.append(1 if v < 128 else 0)
        rows.append(row)
    return rows, mods, g


def qr_matrix_for(text):
    """用 qrcode 库按同样内容重建矩阵（border=0，只算二维码本体）。"""
    import qrcode
    q = qrcode.QRCode(border=0, box_size=10)
    q.add_data(text)
    q.make()
    rows = []
    for line in q.get_matrix():
        row = []
        for cell in line:
            row.append(1 if cell else 0)
        rows.append(row)
    return rows


def check_qr(base):
    code, headers, body, cost = http(base, QR_PATH)
    if code != 200:
        bad("下载二维码", "HTTP " + str(code) + "，图片不在服务器上")
        return
    if body[0:8] != b"\x89PNG\r\n\x1a\n":
        bad("下载二维码", "不是 PNG，文件坏了")
        return
    try:
        got, mods, box = qr_matrix_from_png(body)
    except Exception as e:
        bad("下载二维码", "读不出模块：" + wrap(e))
        return

    expect_url = base + APK_PATH
    try:
        want = qr_matrix_for(expect_url)
    except Exception as e:
        warn("下载二维码", str(mods) + "x" + str(mods) + " 模块，但本机没装 qrcode 库，跳过内容校验")
        return

    if len(want) != mods:
        bad("二维码内容", "图是 " + str(mods) + "x" + str(mods) + " 模块，按当前地址应生成 "
            + str(len(want)) + "x" + str(len(want)) + "，内容和 " + expect_url + " 对不上")
        return

    same = 0
    for y in range(mods):
        for x in range(mods):
            if got[y][x] == want[y][x]:
                same = same + 1
    pct = same * 100.0 / (mods * mods)
    if pct > 99:
        ok("二维码内容", "扫出来就是 " + expect_url)
    else:
        bad("二维码内容", "和 " + expect_url + " 只有 " + str(round(pct, 1))
            + "% 一致，扫出来是别的地址，得重生成")


def make_qr(base):
    """重新生成二维码：内容 = 当前地址 + /download/yexi.apk
    带 4 模块白边，手机扫的时候才认得出边界（无白边容易扫不动）。"""
    try:
        import qrcode
    except Exception:
        print("本机没装 qrcode 库，先 pip install qrcode pillow")
        return False
    url = base + APK_PATH
    q = qrcode.QRCode(border=4, box_size=10)
    q.add_data(url)
    q.make()
    img = q.make_image(fill_color="black", back_color="white").convert("RGB")
    out = os.path.join(SITE_DIR, "download", "qr-download.png")
    img.save(out)
    print("已重生成 " + out + "，内容是 " + url + "，尺寸 " + str(img.size[0]) + "px")
    return True


def check_extra(base):
    for path, name in (("/m.html", "手机网页版"), ("/home.html", "首页")):
        code, headers, body, cost = http(base, path)
        if code == 200:
            ok(name + "能打开", "HTTP 200")
        else:
            bad(name + "能打开", "HTTP " + str(code))


def main():
    args = sys.argv[1:]
    base = DEFAULT_BASE
    do_qr = False
    for a in args:
        if a == "--make-qr":
            do_qr = True
        elif a.startswith("http"):
            base = a.rstrip("/")

    print("检查地址：" + base)
    print("-" * 60)

    if do_qr:
        if not make_qr(base):
            return

    check_page(base)
    check_head(base)
    check_apk(base)
    check_qr(base)
    check_extra(base)

    print("-" * 60)
    print("通过 " + str(pass_count) + " 项，警告 " + str(warn_count) + " 项，失败 " + str(fail_count) + " 项")
    if fail_count > 0:
        print("")
        print("坏在哪：")
        for f in failures:
            print("  - " + f)
        sys.exit(1)
    print("安装包链路正常，可以对外发。")


main()
