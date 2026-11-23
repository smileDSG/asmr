# 从 Freesound 网页版抓 CC0 音效预览
# 网页版搜索页直接暴露了预览音频链接，不需要申请 API key
# 注意：抓到的是 lq 预览（低码率），只用于试听筛选；正式用要去原页面下载原文件
#
# 用法：用 default 环境运行，会下载到 freesound_previews/

import os
import re
import time
import urllib.request

OUT_DIR = "freesound_previews"
BASE = "https://freesound.org/search/"

# 关键词 -> 文件名前缀
QUERIES = [
    ("rain", "rain"),
    ("heavy rain", "heavyrain"),
    ("rain window", "windowrain"),
    ("rain thunder", "thunder"),
    ("wind rain", "windrain"),
    ("brown noise", "brownnoise"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def fetch_page(query):
    # CC0 过滤参数，网页版用 f=license:"Creative Commons 0"
    import urllib.parse
    params = urllib.parse.urlencode({
        "q": query,
        "f": 'license:"Creative Commons 0"'
    })
    url = BASE + "?" + params
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def extract_previews(html):
    # 找所有 lq mp3 预览链接，去重
    links = re.findall(r'https://cdn\.freesound\.org/previews/[^\"\']+?-lq\.mp3', html)
    seen = []
    for link in links:
        link = link.replace("\\u0026", "&")
        if link not in seen:
            seen.append(link)
    return seen


def download(url, path):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


os.makedirs(OUT_DIR, exist_ok=True)

for query, prefix in QUERIES:
    print("搜索：" + query + "（只要 CC0）")
    try:
        html = fetch_page(query)
        links = extract_previews(html)
        print("  找到 " + str(len(links)) + " 个预览")
        # 每个关键词下前 8 个
        n = 0
        for link in links[:8]:
            name = prefix + "_" + str(n) + ".mp3"
            path = os.path.join(OUT_DIR, name)
            if os.path.exists(path):
                n = n + 1
                continue
            try:
                size = download(link, path)
                print("    " + name + "  " + str(size // 1024) + " KB")
                n = n + 1
                time.sleep(0.3)
            except Exception as e:
                print("    下载失败：" + str(e)[:60])
        time.sleep(1)
    except Exception as e:
        print("  搜索失败：" + str(e)[:80])

print("\n完成，预览在 " + OUT_DIR + "/")
