# 补充采集 v2：放宽过滤（只 CC0，不卡 bitrate），换简单关键词
# 之前 v1 的 bitrate:320 把大量好素材滤掉了，多词 AND 又太严
# hq 预览本身就是 48kHz 高质量，不需要靠 bitrate 过滤

import re
import html
import urllib.request
import urllib.parse

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 单词或两词组合，避免 AND 太严搜不到
SCENES = [
    ("soft_rain", "light rain", "柔和雨"),
    ("window_rain", "rain window", "窗边雨"),
    ("wind_leaves", "leaves rustling", "树叶沙沙"),
    ("crickets", "crickets", "虫鸣"),
    ("ambient_pad", "ambient drone", "音乐垫"),
]


def get_text(url):
    req = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")


def search(query, top_n=5):
    params = urllib.parse.urlencode({
        "q": query,
        "f": 'license:"Creative Commons 0"',
        "s": "rating",
    })
    url = "https://freesound.org/search/?" + params
    try:
        h = get_text(url)
    except Exception as e:
        print("  搜索失败：" + str(e)[:50])
        return []
    blocks = h.split('<div class="bw-search__result"')[1:]
    results = []
    for b in blocks:
        sid = re.search(r'data-sound-id="(\d+)"', b)
        mp3 = re.search(r'data-mp3="([^"]+)-lq\.mp3"', b)
        title = re.search(r'aria-label="Sound\s+(.*?)\s+by\s+([^"]+)"', b)
        if not (sid and mp3):
            continue
        t = html.unescape(title.group(1)).strip() if title else "?"
        a = html.unescape(title.group(2)).strip() if title else "?"
        results.append({
            "id": sid.group(1),
            "title": t,
            "author": a,
            "hq": mp3.group(1).replace("\\u0026", "&") + "-hq.mp3",
        })
        if len(results) >= top_n:
            break
    return results


all_items = []
for key, query, label in SCENES:
    print("=== " + label + " (" + query + ") ===")
    items = search(query)
    for it in items:
        print("  id=" + it["id"] + "  " + it["title"][:70])
        it["label"] = label
        it["key"] = key
        all_items.append(it)
    print()

print("共 " + str(len(all_items)) + " 条，写入 more_links.txt")
with open("more_links.txt", "w", encoding="utf-8") as f:
    for it in all_items:
        f.write("%s\t%s\t%s\t%s\t%s\t%s\n" % (
            it["key"], it["label"], it["id"], it["title"], it["author"], it["hq"]))
