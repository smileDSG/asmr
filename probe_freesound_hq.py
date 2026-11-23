# 探查 Freesound：1) 按评分排序能否生效 2) hq 预览是不是 44100Hz 原版音质
# 只读探查，不做任何音频处理

import os
import re
import urllib.request
import urllib.parse

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def get_text(url):
    req = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")


def get_bytes(url):
    req = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=60).read()


params = urllib.parse.urlencode({
    "q": "rain",
    "f": 'license:"Creative Commons 0"',
    "s": "rating",
})
url = "https://freesound.org/search/?" + params
print("抓取：" + url)
h = get_text(url)
print("HTML 长度：" + str(len(h)))

with open("probe_search.html", "w", encoding="utf-8") as f:
    f.write(h)

# 看第一条 lq 链接前后的 HTML 结构，找评分字段在哪
idx = h.find("-lq.mp3")
print("\n=== 第一条预览链接上下文 ===")
if idx > 0:
    print(h[max(0, idx - 2500):idx + 200])
else:
    print("没找到 lq.mp3 链接")

# 提取所有 lq 链接
links = re.findall(r'https://cdn\.freesound\.org/previews/[^"\']+?-lq\.mp3', h)
seen = []
for link in links:
    link = link.replace("\\u0026", "&")
    if link not in seen:
        seen.append(link)
print("\n找到 lq 预览：" + str(len(seen)) + " 个")

# 打印前 3 条 lq 链接，供下一步单独下载验证
for link in seen[:3]:
    print("LQ: " + link)
    print("HQ: " + link.replace("-lq.mp3", "-hq.mp3"))
