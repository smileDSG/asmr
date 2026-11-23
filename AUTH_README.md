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

## 运行

后端必须用带 soundfile 的解释器启动（项目用的是 managed venv）：

```
C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe server.py
```

前端：`cd product_site && python -m http.server 8080`
