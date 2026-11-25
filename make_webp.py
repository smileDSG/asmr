# 把所有 JPG/PNG 图片转成同名 WebP，放在原图旁边。
# server.py 会在浏览器支持 WebP 时自动发这些文件，前端代码不用改。
# 用法：改过原图之后，重跑一次这个脚本即可。
# 需要 Pillow：pip install Pillow

import os

from PIL import Image

# 脚本放在项目根目录，图片在 product_site/img
BASE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE, "product_site", "img")

# 画质 82：肉眼基本看不出差别，体积比 JPG 省四成左右
QUALITY = 82

count = 0
saved_total = 0

for name in os.listdir(IMG_DIR):
    low = name.lower()
    if not (low.endswith(".jpg") or low.endswith(".jpeg") or low.endswith(".png")):
        continue

    src = os.path.join(IMG_DIR, name)
    dst = os.path.splitext(src)[0] + ".webp"

    image = Image.open(src).convert("RGB")
    image.save(dst, "WEBP", quality=QUALITY, method=6)

    old_size = os.path.getsize(src)
    new_size = os.path.getsize(dst)
    if new_size >= old_size:
        # 少数图转 WebP 反而更大，删掉并继续用原图
        if os.path.isfile(dst):
            os.remove(dst)
        print("%-28s 转后更大，保留原图" % name)
        continue
    count += 1
    saved_total += old_size - new_size
    print("%-28s %7d -> %7d B" % (name, old_size, new_size))

print("共转换 %d 张，合计省 %.1f KB" % (count, saved_total / 1024))
