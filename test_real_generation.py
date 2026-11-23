# 真实生成测试：只生成一段，省积分（每次 8 积分，免费约 3 次）
# 用"窗外夜雨"这句，生成后和已挑的 CC0 母带做 A/B 对比

import os
import prompt_builder
import stable_audio_client

OUT_DIR = "raw_generated_v2"

# 用户最关心的一句
say = "我睡不着，脑子停不下来，想慢慢安静下来"
config = prompt_builder.build(say)

print("=" * 60)
print("用户说：" + say)
print("场景：" + config["scene"])
print("提示词：" + config["prompt"])
print()

os.makedirs(OUT_DIR, exist_ok=True)
out_path = os.path.join(OUT_DIR, "AI生成_窗外夜雨.mp3")

print("开始真实生成（180 秒，8 积分）...")
stable_audio_client.generate(
    config["prompt"],
    out_path,
    duration=180,
    max_wait=900
)

print()
print("生成完成：" + out_path)
print("下一步：和 product_assets/母带_城市夜雨_CC0.mp3 放一起听，用耳朵选")
