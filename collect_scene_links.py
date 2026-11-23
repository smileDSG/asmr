# 按助眠场景抓 Freesound 高评分 CC0 + 320kbps 素材，输出 hq 链接清单
# 复用之前验证过的规律：搜索页 data-mp3 的 lq 链接换成 hq 就是 48kHz 高码率
# 只读网页，不下载音频（下载慢，单独用 curl 断点续传）
#
# 用法：python collect_scene_links.py

import re
import html
import urllib.request
import urllib.parse

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def get_text(url):
    req = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")


# 每个助眠场景的搜索关键词。之前只做了雨，这次补齐其他场景
SCENES = [
    ("forest_rain", "rain forest", "树林雨"),
    ("fireplace", "fireplace crackling", "壁炉"),
    ("ocean", "ocean waves", "海浪"),
    ("wind", "night wind", "夜风"),
    ("stream", "stream water", "溪流"),
    ("rain_roof", "rain on roof", "屋顶雨"),
    ("thunder_far", "distant thunder", "远雷"),
    ("brown_noise", "brown noise", "褐噪音"),
]


def search(query, label, top_n=3):
    params = urllib.parse.urlencode({
        "q": query,
        "f": 'license:"Creative Commons 0" bitrate:320',
    })
    url = "https://freesound.org/search/?" + params
    try:
        h = get_text(url)
    except Exception as e:
        print("搜索失败 " + label + "：" + str(e)[:60])
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
            "label": label,
        })
        if len(results) >= top_n:
            break
    return results


all_items = []
for key, query, label in SCENES:
    print("=== " + label + " (" + query + ") ===")
    items = search(query, label)
    for it in items:
        print("  id=" + it["id"] + "  " + it["title"][:55])
        all_items.append(it)

print("\n\n共 " + str(len(all_items)) + " 条，写入 scene_links.txt")
with open("scene_links.txt", "w", encoding="utf-8") as f:
    for it in all_items:
        f.write("%s\t%s\t%s\t%s\t%s\n" % (
            it["label"], it["id"], it["title"], it["author"], it["hq"]))
