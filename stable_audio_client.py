# Stable Audio 3.0 文生音频调用层
# 基于官方文档 docs.stability.ai/api-reference/stable-audio/text-to-audio（2026-11 查证）
#
# 关键点：
# - 端点 POST https://api.stability.ai/v2beta/audio/stable-audio/text-to-audio
# - 认证 header 是 authorization: Bearer <key>
# - 异步：POST 返回 id（202），再轮询 GET /v2beta/audio/results/<id> 拿音频（200）
# - 最长 6 分 20 秒，44.1kHz 立体声，比 ElevenLabs 的 30 秒适合助眠
# - 注册送 25 积分，每次生成 8 积分（1 积分=$0.01），约够 3 次
# - 官方承诺输出可商用、训练数据全授权
# 写法刻意朴素：定义函数 + 顺序执行，方便初学者看懂

import os
import json
import time
import urllib.request
import urllib.error
import uuid

BASE = "https://api.stability.ai/v2beta/audio"
GEN_URL = BASE + "/stable-audio/text-to-audio"
RESULT_URL = BASE + "/results/"

# 从环境变量 STABILITY_KEY 或本地 stability_key.txt 读 key
KEY_FILE = "stability_key.txt"


def get_key():
    key = os.environ.get("STABILITY_KEY", "")
    if key:
        return key.strip()
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


# 手工拼 multipart/form-data（标准库没有现成的，用 uuid 当边界）
def build_multipart(fields):
    boundary = "----asmrBoundary" + uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append("--" + boundary)
        parts.append('Content-Disposition: form-data; name="' + name + '"')
        parts.append("")
        parts.append(str(value))
    parts.append("--" + boundary + "--")
    parts.append("")
    body = ("\r\n".join(parts)).encode("utf-8")
    content_type = "multipart/form-data; boundary=" + boundary
    return body, content_type


def headers(key, content_type=None):
    h = {
        "authorization": "Bearer " + key,
        "accept": "audio/*",
    }
    if content_type:
        h["Content-Type"] = content_type
    return h


# 第一步：提交生成任务，拿到任务 id
def submit(key, prompt, duration=60, output_format="mp3"):
    fields = {
        "prompt": prompt,
        "duration": duration,
        "output_format": output_format,
    }
    body, ct = build_multipart(fields)
    req = urllib.request.Request(GEN_URL, data=body, headers=headers(key, ct),
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError("提交失败 HTTP " + str(e.code) + "：" + detail[:400])

    if "id" not in result:
        raise RuntimeError("提交失败，返回里没有 id：" + str(result)[:400])
    return result["id"]


# 第二步：轮询任务，直到出音频
# 官方例子：202=还在生成，200=完成，其他=报错
def poll(key, task_id, out_path, max_wait=600, interval=10):
    url = RESULT_URL + task_id
    waited = 0
    while waited < max_wait:
        req = urllib.request.Request(url, headers=headers(key))
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                status = resp.status
                if status == 200:
                    audio = resp.read()
                    with open(out_path, "wb") as f:
                        f.write(audio)
                    print("  生成成功：" + out_path + "（" + str(len(audio)) + " 字节）")
                    return out_path
                # 200 以外又没抛异常，当作还在处理
        except urllib.error.HTTPError as e:
            if e.code == 202:
                pass  # 还在生成
            else:
                detail = e.read().decode("utf-8", errors="ignore")
                raise RuntimeError("轮询失败 HTTP " + str(e.code) + "：" + detail[:400])
        print("  生成中，等 " + str(interval) + " 秒再问...")
        time.sleep(interval)
        waited += interval
    raise RuntimeError("生成超时（等了 " + str(max_wait) + " 秒）")


# 一步到位：提交 + 轮询
def generate(prompt, out_path, duration=60, output_format="mp3", max_wait=600):
    key = get_key()
    if not key:
        raise RuntimeError(
            "没有找到 Stability API key。请设置环境变量 STABILITY_KEY，"
            "或在项目目录建 stability_key.txt，里面只写 key 本身。"
        )
    print("  提交生成任务（时长 " + str(duration) + " 秒）...")
    task_id = submit(key, prompt, duration=duration, output_format=output_format)
    print("  任务 id：" + task_id)
    return poll(key, task_id, out_path, max_wait=max_wait)


# 自测：没 key 时只打印，不联网
if __name__ == "__main__":
    print("Stable Audio 3.0 调用层自测")
    print("  当前 key：" + ("已配置" if get_key() else "未配置"))
    print("  端点：" + GEN_URL)
    print("  认证：Bearer key")
    print("  流程：POST 提交 → 轮询 GET 结果")
    print("  最长：6 分 20 秒，44.1kHz 立体声")
