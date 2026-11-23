# ElevenLabs 音效生成调用层
# 用 urllib 标准库，不用装额外依赖
#
# 关键点（已核对官方文档 2026-11）：
# - 端点 POST https://api.elevenlabs.io/v1/sound-generation
# - 认证 header 是 xi-api-key
# - WAV 44.1kHz 要 Pro 订阅才能用，所以默认 MP3_44100_128，本地转成 wav 再处理
# - 模型 eleven_text_to_sound_v3 比 v2 更自然、更不容易在高频削顶
# - 单次最长 30 秒，duration_seconds 留空让模型自己判断更便宜

import os
import json
import time
import urllib.request
import urllib.error

API_URL = "https://api.elevenlabs.io/v1/sound-generation"
RAW_DIR = "raw_generated"


def get_key():
    # 优先读环境变量 XI_API_KEY；没有就读本地 key.txt（一行文本）
    key = os.environ.get("XI_API_KEY", "")
    if key:
        return key.strip()
    if os.path.exists("xi_key.txt"):
        with open("xi_key.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def generate(prompt, out_path, duration=30, loop=True,
             prompt_influence=0.65, model="eleven_text_to_sound_v3",
             output_format="mp3_44100_128", retries=2):
    key = get_key()
    if not key:
        raise RuntimeError(
            "没有找到 API key。请设置环境变量 XI_API_KEY，"
            "或在项目目录建一个 xi_key.txt，里面只写 key 本身。"
        )

    body = {
        "text": prompt,
        "model_id": model,
        "prompt_influence": prompt_influence
    }
    if duration:
        body["duration_seconds"] = duration
    if loop:
        body["loop"] = True

    url = API_URL + "?output_format=" + output_format
    data = json.dumps(body).encode("utf-8")

    last_error = ""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "xi-api-key": key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                audio = resp.read()
            with open(out_path, "wb") as f:
                f.write(audio)
            print("  生成成功：" + out_path + "（" + str(len(audio)) + " 字节）")
            return out_path
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="ignore")
            last_error = "HTTP " + str(e.code) + "：" + detail[:300]
            if e.code in (401, 403):
                break
            if e.code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            break
        except Exception as e:
            last_error = str(e)
            time.sleep(2 * (attempt + 1))

    raise RuntimeError("生成失败：" + last_error)


# 自测：没 key 时只打印将发送的请求，不真的联网
if __name__ == "__main__":
    print("ElevenLabs 调用层自测")
    print("  当前 key：" + ("已配置" if get_key() else "未配置（模拟模式）"))
    print("  端点：" + API_URL)
    print("  模型：eleven_text_to_sound_v3")
    print("  默认输出：mp3_44100_128（本地转 wav 后再做助眠处理）")
