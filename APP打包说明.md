# 夜息 App 打包说明

日期：2026-11-25
一句话：**App = 原生壳 + 你现有的网页。后端和网页一行都不用改，网页一更新 App 里就是新的。**

> 状态：首版 APK 已由 GitHub Actions 编译成功（run 45569651098，产物 `yexi-debug-apk` 6.9MB）。按第三节方式 A 即可下载安装。

---

## 一、为什么这么做（先说清楚取舍）

助眠产品真正值钱的是"锁屏后还能一直播、定时淡出、打开即播"。网页和小程序在这几点上是硬伤：
- 微信小程序切后台音频会停，且只能管一个音频实例，跟"叠几层声音"的核心能力冲突。
- PWA 装到主屏幕后锁屏播放不稳。
- 只有原生壳能完整拿到锁屏播放、桌面图标、全屏沉浸。

所以走 Capacitor：外层是个原生 Android App，里面用 WebView 加载你已经做好的移动端页面。
AI 理解脑、Qwen key、41 段素材、账号记忆支付全留在阿里云服务器——**key 不进 App，安全；网页改了不用重装 App**。

代价：必须联网才能用（AI 和素材都在云端）；服务器未备案只能走 HTTP，壳里已放行明文流量；iOS 上架要开发者账号，安卓可先装来自测。

---

## 二、现在做到哪了

- Capacitor 8 工程在 `app/`，包名 `com.yexi.nightrest`。
- 紫夜星空图标（1024×1024）+ 启动图（2732×2732）已生成，各平台尺寸已铺进 `android/app/src/main/res/`。图标是用项目里已有的 `product_site/img/night-lake-stars.jpg` 裁的，没调用生成模型。
- `AndroidManifest.xml` 已放行 HTTP 明文（`usesCleartextTraffic`），并加了网络状态权限。
- `MainActivity.java` 加了 CPU 唤醒锁（PARTIAL_WAKE_LOCK），锁屏后 CPU 不休眠，音频不会被系统掐断——这是助眠场景的关键。
- 云端编译配置 `.github/workflows/build-apk.yml` 已就位，push 后自动编译，APK 存 90 天。

---

## 三、怎么拿到 APK（三种方式）

### 方式 A：从 GitHub Actions 下载（推荐，无需本机环境）
1. 打开 `https://github.com/smileDSG/asmr/actions`，点「编译夜息 App APK」workflow。
2. 进最新一次运行，页面底部 Artifacts 里下载 `yexi-debug-apk`（是个 zip，解压得到 `app-debug.apk`）。
3. 把 apk 传到安卓手机，点开安装（需允许"安装未知应用"）。

### 方式 B：本机编译（要先装 Android SDK）
本机目前只有 Node/npm 和 Java 21，没有 Android SDK。装好后：
```
# 设置环境变量 ANDROID_HOME 指向 SDK 目录
cd app
npm ci
npx cap sync android
cd android
gradlew assembleDebug
```
产物在 `app/android/app/build/outputs/apk/debug/app-debug.apk`。

### 方式 C：Android Studio 打开直接运行
用 Android Studio 打开 `app/android`，连手机点运行。

---

## 四、改了网页后怎么同步

网页（`product_site/`）的改动已通过原有流程部署到阿里云。因为 App 里加载的是线上地址 `http://47.101.59.166:8000/m.html`，所以：
- 只改网页：**网页一部署，App 里刷新即是新的，不用重新打包**。
- 只有改了原生部分（图标、唤醒锁、包名、权限等 `app/android/` 下的东西），才需要重新走第三节编译一次 APK。

---

## 五、已知限制 / 下一步

- **锁屏按键控制**（锁屏上显示歌名、播放/暂停按钮）：当前只做了保活，没做原生 Media Session 插件。iOS 的 WebView 支持 Web Media Session API，安卓不支持。要做完整的锁屏控制，需接 `@capgo/capacitor-media-session` 之类的插件，并让前端播放器配合调用——这是第二步，先真机验证保活够不够用。
- **拆包内嵌**：现在是"壳 + 远程网页"，首屏依赖网络。远期可把网页和音频打进包里做离线版，但素材 41 段体积大，且 AI 生成必须联网，现阶段性价比低。
- **服务器地址写死**：`app/capacitor.config.json` 里写的是 `47.101.59.166:8000`。以后换服务器或上 HTTPS 域名，改这里再重新编译一次 APK。
- **debug 签名**：现在出的是 debug 包，能装能测。正式上架应用商店要换 release 签名 + 备案域名 + 隐私政策页。

---

## 六、文件索引

| 文件 | 作用 |
|---|---|
| `app/package.json` | Capacitor 依赖与版本 |
| `app/capacitor.config.json` | AppID、加载地址、明文放行 |
| `app/www/index.html` | 离线兜底页（联网失败时显示） |
| `app/make_icons.py` | 图标/启动图生成脚本（源图来自 product_site/img） |
| `app/assets/` | 图标源文件（被 .gitignore 排除，不进仓库） |
| `app/android/` | Android 原生工程 |
| `.github/workflows/build-apk.yml` | 云端自动编译 APK |

---

## 七、装完/发出去之前先自检

```bash
python check_install.py                # 查线上（默认 47.101.59.166:8000）
python check_install.py http://ip:8000 # 查别的地址，比如本机起的 8011
python check_install.py --make-qr      # 重新生成下载二维码，然后自检
```

一次跑完 12 项：页面能不能打开、按钮地址对不对、页面有没有退回 HEAD 预检、
服务器支不支持 HEAD、安装包能不能下、字节数对不对、是不是合法 APK（zip+MANIFEST）、
二维码扫出来是不是当前下载地址、线上文件和本地是否同一份。
任何一项 `[X]` 退出码就是 1，可以直接挂定时任务当探活。

2026-11-27 那次「按钮点了不下载」就是这套检查里第 4 项（HEAD 501）和第 9 项（二维码指向别处）同时坏了，
人眼看不出来，脚本一跑全现形。
