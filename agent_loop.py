# 完整反馈闭环：一句话 → 生成 → 用户听 → 说反馈 → 调配比 → 再生成 → 满意存记忆
# AI 只做理解和挑配，绝不自己判断音质；好不好由用户的耳朵裁决
# 铁律：不滤波、不降噪、不压缩、不加混响

import os
import time
import json

import understanding_brain
import 素材执行层 as executor
import feedback_translate as ft
import memory_system as memory

OUT_DIR = "agent_output"


def render_once(items, minutes, tag):
    # 按给定配比渲染一段成品（只做拼接补时长，零音质处理）
    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = time.strftime("%m%d_%H%M%S")
    out_path = os.path.join(OUT_DIR, "闭环_" + tag + "_" + stamp + ".wav")

    # 直接调用执行层的 render，但它按意图重新挑素材；这里要覆盖配比
    # 做法：临时造一个只含目标配比的路径，手动混合
    import soundfile as sf
    import numpy as np
    sr = 44100
    frames = int(sr * 60 * minutes)
    mix = np.zeros((frames, 2), dtype="float32")
    for rel, w in items:
        if w <= 0:
            continue
        path = os.path.join(executor.BASE, rel)
        if not os.path.exists(path):
            print("  跳过缺失素材：" + rel)
            continue
        seg = executor.load_loop(path, frames, sr)
        mix += seg * w
    peak = np.max(np.abs(mix))
    if peak > 0.95:
        mix = mix * (0.95 / peak)
    fi = int(sr * 1.0)
    mix[:fi] *= np.linspace(0, 1, fi)[:, None]
    mix[-fi:] *= np.linspace(1, 0, fi)[:, None]
    sf.write(out_path, mix, sr)
    return out_path


def items_to_pairs(items):
    # 把 (路径, 权重) 转成相对路径，方便存记忆
    pairs = []
    for path, w in items:
        pairs.append([path, round(w, 3)])
    return pairs


def run(say, feedbacks, minutes=1):
    # feedbacks: 用户每轮听后的反馈列表，空字符串表示满意
    print("========== 需求 ==========")
    print(say)

    # 1. 理解脑
    intent, source = understanding_brain.understand(say)
    print("\n[理解] 来源：" + source)
    print("  场景=" + intent["scene"] + " 暖度=" + intent["warmth"]
          + " 动态=" + intent["dynamics"] + " 心情=" + intent["mood"])

    # 2. 记忆召回
    recalled = memory.recall_recipe(intent)
    base_items = executor.pick(intent)
    if recalled is not None:
        print("\n[记忆] 召回一条相似满意配方，作为起点")
        base_items = []
        for pair in recalled["items"]:
            base_items.append((pair[0], pair[1]))

    # 3. 逐轮生成 + 反馈
    current = base_items
    for i, fb in enumerate(feedbacks):
        out = render_once(current, minutes, "第" + str(i + 1) + "轮")
        print("\n[生成 " + str(i + 1) + "] " + out)
        for path, w in current:
            if w > 0:
                print("  %.2f  %s" % (w, os.path.basename(path)))

        if fb == "" or fb == "满意":
            memory.save_preferences(intent)
            memory.save_good_recipe(say, intent, items_to_pairs(current))
            print("\n[记忆] 用户满意，配方已存入 good_recipes.json")
            break
        else:
            memory.save_bad_case(say, fb, items_to_pairs(current))
            current, notes = ft.apply_feedback(fb, current)
            print("\n[反馈翻译] " + fb)
            for note in notes:
                print("  -> " + note)
    else:
        print("\n[结束] 反馈轮次用完，未确认满意")

    return current


if os.environ.get("LOOP_SELFTEST") == "1":
    # 闭环自测：需求 + 两轮反馈（第2轮满意）
    run("睡不着，想要窗外下雨的声音，暖一点，别突然炸",
        ["有点吵", "满意"], minutes=1)
    memory.summary()
