# -*- coding: utf-8 -*-
"""把根目录的最新代码同步到 deploy/，供发布使用。
用法：在 E:/03_Projects/asmr 目录打开命令行，运行：
  python sync_deploy.py

它会：
1. 复制代码文件和 product_site 前端到 deploy/
2. 自动跳过带下划线的调试页（_g.html、_tmp_*.html 之类）
3. 绝不碰 data/（账号数据库）、qwen_key.txt（密钥）、scene_assets/、product_assets/（素材）
"""
import os
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
DEPLOY = os.path.join(ROOT, "deploy")

# 需要同步的单文件（代码 + 配置 + 说明）
FILES = [
    "server.py", "auth_db.py", "qwen_client.py", "understanding_brain.py",
    "feedback_translate.py", "memory_system.py", "input_guard.py",
    "素材执行层.py", "sound_catalog.py", "sound_catalog.json",
    "pay.py", "requirements.txt",
]

# 前端目录：只同步这个目录里的正式页面
SITE = "product_site"

# 不同步的前端文件（调试/临时/实验页面）
SKIP_PREFIX = ("_",)

# deploy/ 里要删掉的实验产物目录（体积大、非成品）
JUNK_DIRS = ["agent_output", "ai_samples", "ai_samples_v2", "ai_samples_v3"]

# 绝对不动的东西
PROTECT = ["data", "qwen_key.txt", "stability_key.txt",
           "scene_assets", "product_assets"]


def main():
    if not os.path.isdir(DEPLOY):
        print("错误：找不到 deploy/ 目录，请先创建。")
        return

    print("开始同步到 deploy/ ...")

    # 1. 单个代码文件
    for name in FILES:
        src = os.path.join(ROOT, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(DEPLOY, name))
            print("  代码：" + name)

    # 2. 前端目录
    src_site = os.path.join(ROOT, SITE)
    dst_site = os.path.join(DEPLOY, SITE)
    if not os.path.isdir(dst_site):
        os.makedirs(dst_site)
    for name in os.listdir(src_site):
        if name.startswith(SKIP_PREFIX):
            continue
        src = os.path.join(src_site, name)
        dst = os.path.join(dst_site, name)
        if os.path.isdir(src):
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print("  前端目录：" + name + "/")
        elif os.path.isfile(src):
            shutil.copy2(src, dst)
            print("  前端：" + name)

    # 3. 删除实验产物（只删 deploy 里的，不动根目录）
    for name in JUNK_DIRS:
        junk = os.path.join(DEPLOY, name)
        if os.path.isdir(junk):
            shutil.rmtree(junk)
            print("  已删除实验产物：" + name + "/")

    print("同步完成。受保护未改动：" + "、".join(PROTECT))
    print("下一步：用发布工具发布 deploy/ 目录。")


main()
