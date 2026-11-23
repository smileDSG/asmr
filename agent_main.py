# 主编排：一句话 → 理解脑抽意图 → 素材执行层挑配 → 成品
# 这是新路线的核心：AI 只理解和挑素材，不生成音频、不后处理、不判断音质
# 用法：python agent_main.py "你想要的话"

import json
import os
import sys
import time

import understanding_brain
import 素材执行层 as executor

OUT_DIR = "agent_output"


def generate(say, minutes=None):
    os.makedirs(OUT_DIR, exist_ok=True)

    # 1. 理解脑：一句话 → 意图（三层降级）
    intent, source = understanding_brain.understand(say)
    duration = minutes if minutes else intent.get("duration_minutes", 30)

    print("== 理解 ==")
    print("来源：" + source)
    print("场景：" + intent["scene"] + "（" + intent["scene_detail"] + "）")
    print("心情：" + intent["mood"] + "  暖度：" + intent["warmth"]
          + "  动态：" + intent["dynamics"])
    print("禁忌：" + str(intent.get("avoid", [])))
    print("时长：" + str(duration) + " 分钟")

    # 2. 执行层：挑素材 + 零处理拼接
    stamp = time.strftime("%m%d_%H%M%S")
    safe_name = intent["scene"]
    out_path = os.path.join(OUT_DIR, "生成_" + safe_name + "_" + stamp + ".wav")
    print("\n== 执行 ==")
    items = executor.render(intent, out_path, duration)
    for path, w in items:
        if w > 0:
            print("  %.2f  %s" % (w, os.path.basename(path)))

    size_mb = os.path.getsize(out_path) / 1048576
    print("\n成品：" + out_path + "（%.1f MB）" % size_mb)
    return out_path, intent


if __name__ == "__main__":
    if len(sys.argv) > 1:
        say = sys.argv[1]
    else:
        say = "睡不着，想要窗外下大雨的声音，暖一点，别突然炸一下，不要雷声"
    generate(say, minutes=1)
