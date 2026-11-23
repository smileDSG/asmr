# 抓多个雨声关键词下评分最高的 CC0 + 320kbps 素材，输出 hq 下载清单
# 只读网页，不下载音频

import re
import html
import urllib.request
import urllib.parse

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def get_text(url):
    req = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")


# 不同风格关键词，覆盖 Rainy Mood 那种"窗外大雨"的几种可能
QUERIES = [
    ("rain", "雨"),
    ("heavy rain", "大雨"),
    ("rain on window", "窗雨"),
    ("rain on roof", "屋顶雨"),
    ("rainfall", "降雨"),
    ("rain night", "夜雨"),
]

all_items = []
for q, label in QUERIES:
    params = urllib.parse.urlencode({
        "q": q,
        "f": 'license:"Creative Commons 0" bitrate:320',
        "s": "rating",
    })
    url = "https://freesound.org/search/?" + params
    try:
        h = get_text(url)
    except Exception as e:
        print("搜索失败 " + q + "：" + str(e)[:60])
        continue

    blocks = h.split('<div class="bw-search__result"')[1:]
    print("=== " + label + " (" + q + ") 结果 " + str(len(blocks)) + " ===")

    n = 0
    for b in blocks:
        score = re.search(r'data-score="([\d.]+)"', b)
        sid = re.search(r'data-sound-id="(\d+)"', b)
        mp3 = re.search(r'data-mp3="([^"]+)-lq\.mp3"', b)
        title = re.search(r'aria-label="Sound\s+(.*?)\s+by\s+([^"]+)"', b)
        if not (score and mp3):
            continue
        t = html.unescape(title.group(1)).strip() if title else "?"
        a = html.unescape(title.group(2)).strip() if title else "?"
        item = {
            "score": float(score.group(1)),
            "id": sid.group(1) if sid else "?",
            "hq": mp3.group(1).replace("\\u0026", "&") + "-hq.mp3",
            "title": t,
            "author": a,
            "label": label,
        }
        # 全局去重
        if any(x["id"] == item["id"] for x in all_items):
            continue
        all_items.append(item)
        print("  %.2f  %s  %s" % (item["score"], t[:48], a[:20]))
        n += 1
        if n >= 3:
            break

print("\n\n=== 汇总：去重后 " + str(len(all_items)) + " 条 ===")
with open("hq_links.txt", "w", encoding="utf-8") as f:
    for i, item in enumerate(all_items):
        line = "%d\t%.2f\t%s\t%s\t%s\t%s" % (
            i, item["score"], item["id"], item["label"], item["title"], item["hq"])
        f.write(line + "\n")
        print(line[:150])
