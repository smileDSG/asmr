# 夜息 · 一句话生成你的助眠音

真实 CC0 录音挑配的助眠声音应用。AI 只负责听懂你的话、挑素材、定配比，**不合成音频**。

## 三条铁律

1. 真实专业素材 > AI 生成。
2. AI 只当脑，不当耳朵；默认零处理，不滤波、不降噪、不压缩、不加混响。
3. 学配方，不搬文件；只用权利干净的素材。

## 本地运行

需要 Python 3.10+，以及 numpy、soundfile：

```bash
pip install -r requirements.txt
```

在 `qwen_key.txt` 里填入阿里云百炼 API key（可从 `qwen_key.example.txt` 复制改名）。没有 key 也能跑——会自动降级到规则和本地模型。

启动（单端口，页面和 API 都从这里出）：

```bash
python server.py
```

浏览器打开 `http://127.0.0.1:8000/`。

## 项目结构

- `server.py` — 单端口 HTTP 服务：静态页面 + 所有 API
- `understanding_brain.py` / `qwen_client.py` — 需求理解脑（Qwen3.8-Flash + 两层降级）
- `素材执行层.py` — 按意图从 CC0 素材库挑配，零处理拼接
- `feedback_translate.py` — 把用户反馈翻译成素材取舍动作
- `memory_system.py` / `auth_db.py` — 记忆系统与账号数据库
- `product_site/` — 前端页面
- `product_assets/` / `scene_assets/` — 已验收的 CC0 素材
- `AGENT_DESIGN.md` — agent 设计文档
- `素材库清单.md` — 素材入库/淘汰记录

## 安全说明

`qwen_key.txt`、`stability_key.txt`、`data/*.db` 已被 `.gitignore` 排除，不会进仓库。
克隆后请自行填写 key。**不要把真实 key 提交到公开仓库。**

`product_site/img/night-lake.webp` 授权不明，正式发布前需替换。
