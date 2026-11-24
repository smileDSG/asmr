# 夜息 · 账号与记忆说明

## 账号怎么存

- 数据库：`data/users.db`（SQLite，本地文件，随项目走）。
- 密码：**绝不存明文**。用 PBKDF2-HMAC-SHA256、60 万次迭代、每个用户独立随机盐。
  依据 OWASP《Password Storage Cheat Sheet》2026——本环境没有 argon2/bcrypt，标准库 pbkdf2 是被认可的可用档位。
- 会话：登录后发一个 43 位随机 token，只存服务端，7 天过期；前端存在浏览器 localStorage，每次请求用 `Authorization: Bearer <token>` 带上。
- 登录防护：错误文案统一（不告诉对方是"用户名不存在"还是"密码错了"，防用户枚举）；同一账号连续失败 5 次锁 15 分钟；所有数据库查询用参数化，防 SQL 注入。

## 记忆怎么隔离

- 没登录（游客）：耳朵档案存在本机 `memory/*.json`，功能完整可用。
- 登录用户：耳朵档案存数据库，按 user_id 分开——A 的配方 B 看不到。
- 注册/登录后调 `/api/migrate`，把游客阶段攒的本机档案并进账号，不丢失；并进后清空本机，避免重复累加。

## 端点

| 端点 | 方法 | 作用 |
|---|---|---|
| `/api/register` | POST | 注册，body `{username, password}` |
| `/api/login` | POST | 登录，返回 `{ok, token, username}` |
| `/api/logout` | POST | 登出，撤销 token |
| `/api/me` | GET | 当前登录状态 |
| `/api/migrate` | POST | 游客档案迁移到账号（需带 token） |
| `/api/memory` | GET | 读记忆（登录读库，游客读本机） |
| `/api/feedback` | POST | 写反馈记忆（登录写库，游客写本机） |
| `/api/play` | POST | 场景卡/播放页按配方出声，返回稳定音频 URL |
| `/api/play_audio?name=` | GET | 取稳定音频文件 |

## 前端怎么接的

- `product_site/auth.html`：登录/注册一个页面切换。注册成功后自动登录并迁移游客档案；`?from=xxx.html` 决定登录后回哪个页面，只允许本站页面名。
- `product_site/auth_ui.js`：三页共用。token 存 localStorage 的 `yezi_token`；`yGet` / `yPost` 自动带 `Authorization` 头；`initAuthBar("页面名")` 在顶部显示"登录"或用户名+退出。
- 首页、生成页、社区页都已接入；`/api/generate`、`/api/feedback`、`/api/memory` 走带 token 的请求，游客没有 token 时照常工作。
- 登录失败提示用琥珀小字，不用红色，不破坏睡前氛围。

## 忘记密码怎么办

当前**没有找回密码功能**。密码是单向哈希，无法反推。
早期的朴素做法：删掉 `data/users.db` 里的该用户记录，重新注册（记忆也会清空）。
正式上线前需要补：邮箱/手机验证码重置，流程是"发一个 32 字节随机 token、存哈希、15–60 分钟有效、点击后改密码"，不要直接告诉用户原密码。

## 安全边界（诚实说明）

- 这是**本地/内网演示级**实现，不是生产级账号系统。
- 传输用 http，token 可能被同网段抓包；正式上线必须上 https。
- 没有邮箱验证、没有二次验证、没有找回密码、没有全局限流（只对单账号失败次数做了限制）。
- key（阿里云百炼）只在服务端，不进浏览器——这点是对的，别改回去。
- 数据库文件别提交到公开仓库（里面有密码哈希和 token）。

## 游客模式的权限边界（游客能用什么 / 不能用什么）

**游客能用（核心听声体验全开，一点不阉割）**
- 听声、调音、DIY 配声、AI 一句话生成、打分反馈
- 本地存配方、本地耳朵档案（存在浏览器，不跨设备）
- 浏览广场、看别人配方、下载音频

**游客不能用（后端返回 401 + `need_login`，前端给"去登录"引导）**
- 把配方发到广场（`/api/community_posts`）
- 给广场配方投票 / 借我一晚（`/api/community_vote`）
- 在广场留言 / 删留言、改自己帖子的改编许可（原有 401 守卫）
- 导出商用音频与授权凭证（`/api/export_commercial`）
- **敏感点测试**（`ear_test.html`）：游客被页面级拦到登录页，读/存档案接口（`/api/ear_profile` GET+POST）也都返回 401
- 跨设备同步账号数据、迁移档案到账号（`/api/migrate`，原有 401 守卫）

**新用户注册后直接进敏感点测试**：注册成功 → 迁移游客档案 → 跳 `ear_test.html`（登录成功仍回原来的 `from`）。从测试页被引导去登录的老用户（`?reason=ear_test`），登录后回测试页继续；点"先不登录"则回 `home.html`，避免反复弹登录

**依据**：调研了 Demofy、Vanilla Forums 社区、Wikipedia guest account 的通行做法——游客限制的是"公共写操作"和"身份/持久性相关功能"，核心体验（听、试、看）不设墙。匿名发帖/投票是社区垃圾内容的主要来源，所以要身份。这样登录的价值也清楚了：把耳朵档案带走 + 参与广场。

**实现（双层）**
- 后端：`server.py` 的 `require_login(handler, what)` 统一守卫，受限端点开头调用；返回中文提示 + `need_login: true`。后端是真正防线，绕过前端也拦得住。
- 前端：`auth_ui.js` 的 `yNeedLogin(what, fromPage)`，游客点受限操作时弹提示并引导去登录；已接入发布、导出、投票、留言入口。
- 实测：游客发帖/投票 → 401；登录用户发帖 → 200；听声接口游客 → 200。

## 入口门闸（登录 / 游客 二选一）

- 首次打开主页面（home / index / agent / community / me / ear_test）会跳到 `gate.html`，让用户明确选：登录注册，或以游客身份进入。
- 游客点一下就写 `yezi_guest=1` 到浏览器本地，之后不再弹；登录成功的 token 同样让门闸放行。
- `gate.html` 与 `auth.html` 自身豁免，不会来回跳。`from` 参数只允许本站 `.html` 页面名。
- 游客模式本来就能完整听声、打分，记忆存本机；门闸只是把这件事说清楚，不是把功能锁起来。
- 依据：App onboarding 主流建议先给价值再要账号、游客模式为推荐形态（Apple App Store Review Guidelines 5.1.1 亦倾向非强制注册）。既然是二选一，游客按钮做成并列可见的大按钮，不做成藏起来的「跳过」小字。
- 想重新体验门闸：在浏览器控制台执行 `localStorage.removeItem("yezi_guest"); localStorage.removeItem("yezi_token")` 后刷新，或用无痕窗口打开。

## 运行

后端必须用带 soundfile 的解释器启动（项目用的是 managed venv）：

```
C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe server.py
```

前端：`cd product_site && python -m http.server 8080`
