# 夜息 · 一句话生成你的助眠音

真实 CC0 录音挑配的助眠声音应用。AI 只负责听懂你的话、挑素材、定配比，**不合成音频**。

## 本地运行

需要 Python 3.10+：

```bash
pip install -r requirements.txt
python server.py
```

打开 <http://127.0.0.1:8000/>。

可选：在根目录放 `qwen_key.txt`（可从 `qwen_key.example.txt` 复制改名），或设置环境变量 `DASHSCOPE_API_KEY`。没有 key 也能跑，会自动降级到规则和本地模型。

支付默认是 sandbox；本地演示可设 `YEXI_PAY_MODE=mock`，线上由 CI 写成 `prod`。

## 项目结构

| 路径 | 作用 |
|---|---|
| `server.py` | 唯一入口：静态页面 + 所有 API |
| `backend/` | 运行时依赖模块，启动时自动加入导入路径 |
| `product_site/` | 前端页面 |
| `scene_assets/`、`product_assets/` | 已验收的 CC0 音频 |
| `sound_catalog.json` | 声音目录 |
| `data/`、`memory/` | 运行时数据，不进仓库 |
| `check_install.py` | 安装链路自检 |
| `.github/workflows/` | 部署、安全扫描、每小时巡检 |

完整方案文档在本地 `docs/` 目录，不进仓库；目录规则见 `docs/目录规则.md`。

## 部署

push 到 `master` 后，GitHub Actions 自动 SSH 到服务器拉取代码并重启 `yexi` 服务，然后从外网跑一遍 `check_install.py` 校验安装包下载链路；另有每小时轻量巡检。

线上地址：<http://47.101.59.166:8000/>（IP 直连，域名未备案）。

## 自检

```bash
python check_install.py            # 完整自检（含安装包下载校验）
python check_install.py --light    # 轻量巡检
```

## 密钥与数据

`qwen_key.txt`、`stability_key.txt`、`pay_config.json`、`pay_keys/`、`.deploy_key/`、`data/`、`memory/` 都已被 `.gitignore` 排除，不会进仓库。克隆后请自行填写。
