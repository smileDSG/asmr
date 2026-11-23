# 主编排：一句话 → 助眠音频
# 完整链路：文本 → 结构化提示词 → ElevenLabs 生成 → 助眠后处理
#
# 用法：
#   有 key：先设置 XI_API_KEY 环境变量，或建 xi_key.txt，然后直接运行
#   没 key：自动进模拟模式，用现有雨声素材当"生成的母带"，全链路照样跑通
#
# 用户是初学者，所以脚本刻意写成"定义函数 + 从上往下顺序执行"的朴素结构

import os
import prompt_builder
import elevenlabs_client
import postprocess_generated

OUT_DIR = "final_output"
RAW_DIR = "raw_generated"


def make_mock_source(config, path):
    # 模拟模式：没有 API key 时，用现成雨声拼一段"母带"
    # 目的只是验证后面几步链路通不通，不代表真实生成质量
    import soundfile as sf
    import numpy as np
    data, sr = sf.read("real_sounds/sleep_rain.ogg", dtype="float64")
    need = int(config["duration"] * sr)
    if len(data) < need:
        times = need // len(data) + 1
        data = np.tile(data, (times, 1))
    data = data[:need]
    sf.write(path, data, sr)
    print("  [模拟模式] 母带来自现有雨声：" + path)


def run(say, index):
    print("=" * 60)
    print("用户说：" + say)

    config = prompt_builder.build(say)
    print("  场景：" + config["scene"])
    print("  提示词：" + config["prompt"])

    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    raw_path = os.path.join(RAW_DIR, "generated_%02d.mp3" % index)
    final_path = os.path.join(OUT_DIR, "生成_%02d.wav" % index)

    has_key = bool(elevenlabs_client.get_key())
    if has_key:
        print("  调用 ElevenLabs 生成中...")
        elevenlabs_client.generate(
            config["prompt"], raw_path,
            duration=config["duration"],
            loop=config["loop"],
            prompt_influence=config["prompt_influence"]
        )
    else:
        raw_path = os.path.join(RAW_DIR, "mock_%02d.wav" % index)
        make_mock_source(config, raw_path)

    postprocess_generated.process(raw_path, final_path, config, seconds=config["duration"])
    print()


# 默认跑用户最关心的四句话
sentences = [
    "我睡不着，脑子停不下来，想慢慢安静下来",
    "太累了，想彻底放空，什么都不想",
    "凌晨三点还很清醒，有点焦虑，加一点远处闷雷的滚声",
    "想专注学习，别打扰我，声音要稳，动态范围小一点"
]

print("文本生成音频 - 全链路")
print("API key：" + ("已配置，走真实生成" if elevenlabs_client.get_key()
                    else "未配置，走模拟模式（只验证链路）"))
print()

i = 1
for s in sentences:
    run(s, i)
    i = i + 1

print("全部完成，成品在 " + OUT_DIR + "/")
