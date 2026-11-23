# Moodist 开源项目评估：能不能直接拿来用

> 评估日期 2026-11-18

---

## 结论

**代码可以直接借用，音效素材要换掉。** 建议：拿它的交互框架（混音、URL 分享、淡入淡出、预设、睡眠定时），音效素材换成我们自己从 Freesound 筛的 CC0。这样 DIY 次线一周内能做完，主线不受影响。

---

## 项目基本情况

| 项目 | 数据 |
|---|---|
| 仓库 | `github.com/remvze/moodist` |
| 版本 | v3.1.1 |
| 代码协议 | **MIT**（可自由商用、修改、分发） |
| 音效数量 | **84 种** |
| 技术栈 | Astro 7 + React 19 + TypeScript，音频用 Howler.js 2.2.4 |
| 状态管理 | Zustand 4.4.3 |
| 部署 | Docker 一行命令，PWA 可离线 |
| 可访问 | https://moodist.mvze.net |

## 功能清单（比我现在写的 DIY 网页强太多）

- 84 种环境音自由叠加
- 播放/停止和睡眠定时结束时**平滑淡入淡出**
- **URL 分享混音配方**，一键导入（这正是我们想要的）
- 预设保存、重命名、删除、即时调用
- 双耳节拍（binaural beats）和等时音调生成器
- 呼吸练习、番茄钟、倒计时、待办、记事本
- PWA 离线缓存

对照我写的 `diy-site/index.html`：只有 6 个滑块、5 个预设、30 秒导出。**差距明显，没必要重复造。**

## 关键坑：音效素材不是 MIT

README 第 75-80 行明确写着：

> Some sounds used in this project are sourced from third-party providers and are subject to different licenses:
> - Sounds licensed under the **Pixabay Content License**
> - Sounds licensed under **CC0**

**代码 MIT，但音效分两种授权。** 所以不能把整个仓库直接拿来商用，必须：

1. 保留代码框架（MIT，没问题）
2. 逐个检查音效文件的授权归属
3. 把 Pixabay 授权的音效换成我们自己的 Freesound CC0

Pixabay Content License 本身其实很宽松（可商用、无需署名），但禁止"作为独立素材转售"——如果我们的产品是把混音结果卖给用户，可能会有争议。为了干净，统一换成 CC0 最稳。

## 复用方案

### 方案 A：拿代码框架，换素材（推荐）

工作量：
- 拉源码（需解决 GitHub 代理问题，用 jsdelivr 或镜像）
- 找到音效清单和音频文件目录
- 用 Freesound CC0 素材一一替换
- 把主入口改成"AI 生成"页面，DIY 降级为次要标签
- 保留它的 URL 分享、预设、淡入淡出

优点：功能完整、代码质量高、社区维护
缺点：要读一遍它的代码结构（Astro + React，对初学者有点门槛）

### 方案 B：只借鉴设计，自己重写

把它的几个关键交互抄过来：
- URL 分享配方（我已经实现了类似功能）
- 平滑淡入淡出（我已有）
- 预设保存（我已有简化版）
- 睡眠定时（我没有，要加）

优点：代码完全自己掌控，简单
缺点：又造了一遍轮子，功能不全

**建议选 A**，但先让主线跑通再说——DIY 毕竟是次要功能。

---

## 获取源码的注意点

GitHub 直连在本机被代理挡了（`Failed to connect to github.com:443 over proxy 127.0.0.1`），但 jsdelivr CDN 可以访问：

- 单个文件：`https://cdn.jsdelivr.net/gh/remvze/moodist@main/<文件路径>`
- 整个仓库超过 jsdelivr 的 50MB 限制，需分文件取或用其他镜像
- 已下载核心文档到 `moodist_src/`：`README.md`、`LICENSE`、`package.json`、`astro.config.mjs`

---

## 音效素材授权对照（补充调研）

| 来源 | 授权 | 商用 | 署名 | 风险 |
|---|---|---|---|---|
| Freesound CC0 | Creative Commons 0 | ✅ | 不需要 | 最低 |
| Pixabay Content License | Pixabay 自定义 | ✅ | 不需要 | 禁止素材单独转售 |
| Freesound CC BY | Attribution | ✅ | **需要** | 要逐个署名 |

我们的策略：**只用 Freesound CC0**，避开署名义务和转售争议。
