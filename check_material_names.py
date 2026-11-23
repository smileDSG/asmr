# 查 Freesound 上这些素材的真实标题和标签
# 怀疑 windowrain_3 本身就是流水，不是雨

import urllib.request
import urllib.parse
import re
import html

QUERIES = ["window rain", "rain"]

for q in QUERIES:
    url = "https://freesound.org/search/?" + urllib.parse.urlencode({
        "q": q,
        "f": 'license:"Creative Commons 0"'
    })
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    h = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "ignore")

    # Freesound 搜索结果里每条有 data-sound-id 和标题
    ids = re.findall(r'data-sound-id="(\d+)"', h)
    titles = re.findall(r'class="sound_title"[^>]*>\s*<a[^>]*>(.*?)</a>', h, re.S)
    if not titles:
        titles = re.findall(r'<h3[^>]*class="[^"]*sound[^"]*"[^>]*>(.*?)</h3>', h, re.S)

    print("=== 搜索：" + q + " ===")
    print("找到 " + str(len(ids)) + " 个 id，" + str(len(titles)) + " 个标题")
    for i in range(min(8, len(ids))):
        tid = ids[i]
        title = ""
        if i < len(titles):
            title = re.sub("<[^>]+>", "", titles[i]).strip()
            title = html.unescape(title)
        print("  [" + str(i) + "] id=" + tid + "  " + title[:70])
