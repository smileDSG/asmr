# 验证：1) 解析每条素材的评分和标题 2) hq 预览的真实采样率
# 只读 + 下载一条样本做验证，不做任何音频处理

import re
import html
import urllib.request
import urllib.parse

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def get_text(url):
    req = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")


def get_bytes(url):
    req = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=60).read()


params = urllib.parse.urlencode({
    "q": "rain",
    "f": 'license:"Creative Commons 0" bitrate:320',
    "s": "rating",
})
url = "https://freesound.org/search/?" + params
h = get_text(url)
print("HTML 长度：" + str(len(h)))

blocks = h.split('<div class="bw-search__result"')[1:]
print("结果块：" + str(len(blocks)))

results = []
for b in blocks:
    score = re.search(r'data-score="([\d.]+)"', b)
    sid = re.search(r'data-sound-id="(\d+)"', b)
    mp3 = re.search(r'data-mp3="([^"]+)-lq\.mp3"', b)
    title = re.search(r'aria-label="Sound\s+(.*?)\s+by\s+([^"]+)"', b)
    if score and mp3:
        t = html.unescape(title.group(1)).strip() if title else "?"
        a = html.unescape(title.group(2)).strip() if title else "?"
        results.append({
            "score": float(score.group(1)),
            "id": sid.group(1) if sid else "?",
            "lq": mp3.group(1).replace("\\u0026", "&"),
            "title": t,
            "author": a,
        })

print("\n=== 评分最高的 CC0 + 320kbps 雨声 ===")
for i, r in enumerate(results[:10]):
    print("[%d] 评分%.2f  id=%s  %s — %s" % (i, r["score"], r["id"], r["title"][:55], r["author"][:25]))

if results:
    first = results[0]
    hq = first["lq"] + "-hq.mp3"
    print("\n待验证 HQ：" + hq)
    with open("hq_url.txt", "w", encoding="utf-8") as f:
        f.write(hq + "\n")
        f.write(first["lq"] + "-lq.mp3\n")
