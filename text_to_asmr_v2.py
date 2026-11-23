# 主编排 v2：一句话 → 助眠音频（零处理版）
# 与 v1 的唯一区别：默认不做任何后处理，生成什么就输出什么。
#
# 为什么改：用户反复听感否决了所有后处理（叠低频/窄带沙沙/慢起伏/压缩限幅
# 把雨声变成流水声、震动声），最终确认"原始的好"。所以新主线遵守：
#   - 生成母带原样输出，不加滤波、不加混响、不压缩、不归一化
#   - 只在时长不够时做无缝循环拼接（这是长度需要，不是音质加工）
#
# 前提：先配置 Stability API key（见 README 或下面提示），否则只能跑模拟模式
# 写法朴素：定义函数 + 顺序执行

import os
import prompt_builder
import stable_audio_client

OUT_DIR = "final_output_v2"
RAW_DIR = "raw_generated_v2"


# 无缝循环：把音频重复到目标时长，接缝处短交叉淡化（避免 click）
# 这是唯一保留的处理，目的是补时长，不是改音质
def loop_to_length(input_path, out_path, seconds, crossfade=0.15):
    import soundfile as sf
    import numpy as np

    data, sr = sf.read(input_path, dtype="float64")
    if len(data.shape) == 1:
        data = np.stack([data, data], axis=1)
    need = int(seconds * sr)
    if len(data) >= need:
        sf.write(out_path, data[:need], sr, subtype="PCM_24")
        print("  [零处理] 直接截取到 " + str(seconds) + " 秒")
        return out_path

    fade = min(int(crossfade * sr), len(data) // 10)
    ramp = np.linspace(0, 1, fade)
    out = data.copy()
    while len(out) < need:
        # 接缝：尾巴和头部交叉淡化
        tail_start = len(out) - fade
        for ch in range(2):
            out[tail_start:tail_start + fade, ch] = (
                out[tail_start:tail_start + fade, ch] * (1 - ramp)
                + data[:fade, ch] * ramp
            )
        out = np.concatenate([out, data[fade:]], axis=0)
    sf.write(out_path, out[:need], sr, subtype="PCM_24")
    print("  [零处理] 循环补到 " + str(seconds) + " 秒（只做接缝淡化）")
    return out_path


# 模拟模式：没 key 时，用已锁定的 CC0 母带当"生成结果"
# 目的只是验证链路，不代表真实生成质量
def make_mock_source(config, out_path):
    import shutil
    source = "product_assets/母带_城市夜雨_CC0.mp3"
    shutil.copyfile(source, out_path)
    print("  [模拟模式] 母带来自已锁定的 CC0 素材：" + source)
    return out_path


def run(say, index, duration=180):
    print("=" * 60)
    print("用户说：" + say)

    config = prompt_builder.build(say)
    print("  场景：" + config["scene"])
    print("  提示词：" + config["prompt"])

    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    raw_path = os.path.join(RAW_DIR, "generated_%02d.mp3" % index)
    final_path = os.path.join(OUT_DIR, "生成_%02d.wav" % index)

    has_key = bool(stable_audio_client.get_key())
    if has_key:
        print("  调用 Stable Audio 3.0 生成中...")
        stable_audio_client.generate(
            config["prompt"], raw_path,
            duration=min(duration, 380),  # 官方上限 6分20秒
            max_wait=600
        )
    else:
        raw_path = make_mock_source(config, raw_path)

    # 零处理：只补时长，不加任何音质加工
    loop_to_length(raw_path, final_path, duration)
    print()


# 默认跑用户最关心的四句话
sentences = [
    "我睡不着，脑子停不下来，想慢慢安静下来",
    "太累了，想彻底放空，什么都不想",
    "凌晨三点还很清醒，有点焦虑，加一点远处闷雷的滚声",
    "想专注学习，别打扰我，声音要稳，动态范围小一点"
]

print("文本生成音频 - 全链路 v2（零处理版）")
print("API key：" + ("已配置，走 Stable Audio 真实生成"
                    if stable_audio_client.get_key()
                    else "未配置，走模拟模式（用已锁定 CC0 母带验证链路）"))
print()

i = 1
for s in sentences:
    run(s, i)
    i = i + 1

print("全部完成，成品在 " + OUT_DIR + "/")
