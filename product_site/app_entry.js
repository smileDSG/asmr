// 夜息：站内「装 App」入口（只在首页页眉放一个胶囊）
//
// 为什么单独一个文件：
//   游客在网页里要能一眼找到装 App 的地方，不用去猜 install.html 这个地址；
//   但已经装了 App、正在壳里刷页面的人不该再看到它。两件事都靠这一个脚本判断。
//
// 怎么判断「我在不在 App 里」：
//   App 是用 Capacitor 包的（app/capacitor.config.json，appId com.yexi.nightrest），
//   壳内页面由原生注入 window.Capacitor，官方 API 是
//     Capacitor.isNativePlatform()  → true/false
//     Capacitor.getPlatform()       → 'android' | 'ios' | 'web'
//   普通浏览器里没有这个对象，所以拿不到就是网页端。
//   注意：浏览器没法知道「用户手机里装没装过 App」，只能知道「当前是不是在 App 内」，
//   所以这里隐藏的判据只有一条：正在壳里。
//
// 微信里的特殊情况：
//   微信内置浏览器会拦 apk 下载（微信开放社区官方答复：直接给 apk 下载链接会出现提示，
//   建议复制到外部浏览器打开），所以微信里点按钮先弹一句引导，别让用户白点。

(function () {
  // 是否正跑在夜息 App 的原生壳里
  function isInApp() {
    var cap = window.Capacitor;
    if (!cap) return hasInAppMark();
    if (typeof cap.isNativePlatform === "function") {
      return cap.isNativePlatform() === true;
    }
    // 老版本 Capacitor 没有 isNativePlatform，退化用 getPlatform
    if (typeof cap.getPlatform === "function") {
      return cap.getPlatform() !== "web";
    }
    return false;
  }

  // 兜底判据：壳里加载的地址如果带 ?inapp=1，就记到本机存储里，之后每个页面都认得出。
  // 这条不依赖 Capacitor 桥——万一某些机型的 WebView 不支持 document-start 注入，
  // 桥进不来，靠这个标记照样能藏住入口。需要在 app/capacitor.config.json 的 server.url 上带参数。
  function hasInAppMark() {
    try {
      if (/[?&]inapp=1(&|$)/.test(location.search)) {
        localStorage.setItem("yexi_inapp", "1");
      }
      return localStorage.getItem("yexi_inapp") === "1";
    } catch (e) {
      return false;   // 浏览器禁了本地存储，当网页处理
    }
  }

  function isWeChat() {
    return /MicroMessenger/i.test(navigator.userAgent);
  }

  function injectStyle() {
    if (document.getElementById("yAppEntryStyle")) return;
    var css = document.createElement("style");
    css.id = "yAppEntryStyle";
    css.textContent = [
      // 页眉胶囊：自带一套样式，不依赖各页各自的 class
      // （首页是 v2-ghost 的深色页眉，我的页页眉完全不同，蹭别人的 class 会变成默认蓝链接）
      ".y-app-entry{display:inline-flex;align-items:center;text-decoration:none;white-space:nowrap;",
      "background:rgba(16,12,28,.44);border:1px solid rgba(var(--y-warm-rgb,233,183,131),.42);",
      "color:#f0e9f8;border-radius:999px;padding:7px 16px;font-size:13.5px;letter-spacing:.08em;",
      // line-height 调成和旁边「听觉图鉴」「登录」一样高（实测 1.5 → 36px 对齐）
      "font-family:inherit;line-height:1.5;cursor:pointer;",
      "transition:background .35s ease,color .35s ease,border-color .35s ease}",
      ".y-app-entry:hover{background:rgba(var(--y-warm-rgb,233,183,131),.22);",
      "border-color:rgba(var(--y-warm-rgb,233,183,131),.62);color:#fff}",
      "@media (max-width:430px){.y-app-entry{padding:6px 12px;font-size:12.5px;letter-spacing:.04em}}",
      // 微信里那句引导
      ".y-app-tip{position:fixed;left:0;right:0;top:0;bottom:0;z-index:9999;",
      "background:rgba(6,4,10,.82);display:flex;align-items:flex-start;justify-content:center;",
      "padding:18vh 26px 0;font-family:var(--y-serif,system-ui);animation:yTipIn .22s ease}",
      "@keyframes yTipIn{from{opacity:0}to{opacity:1}}",
      ".y-app-tip .box{max-width:340px;background:rgba(24,19,34,.96);border:1px solid rgba(var(--y-warm-rgb),.34);",
      "border-radius:16px;padding:20px 22px;color:#efe7f7;line-height:1.75;font-size:13.5px}",
      ".y-app-tip b{color:var(--y-warm,#e9b783);font-weight:500}",
      ".y-app-tip .ok{display:block;margin-top:14px;text-align:center;font-size:13px;",
      "color:var(--y-text-muted);letter-spacing:.1em}"
    ].join("");
    document.head.appendChild(css);
  }

  // 微信里点了按钮：告诉用户点右上角三个点选「在浏览器打开」
  function showWeChatTip() {
    if (document.querySelector(".y-app-tip")) return;
    var tip = document.createElement("div");
    tip.className = "y-app-tip";
    tip.innerHTML =
      '<div class="box">微信里没法直接下载安装包。<br>' +
      '请点右上角 <b>···</b> ，选 <b>在浏览器打开</b> ，<br>' +
      '再点下载就正常了。' +
      '<span class="ok">点这一下关掉提示</span></div>';
    tip.addEventListener("click", function () {
      tip.parentNode.removeChild(tip);
    });
    document.body.appendChild(tip);
  }

  function onEntryClick(e) {
    if (isWeChat()) {
      e.preventDefault();
      showWeChatTip();
    }
    // 其它情况交给 <a href="install.html"> 自己跳：手机上是下载按钮，电脑上是二维码
  }

  // 首页页眉：和「听觉图鉴」并排的小胶囊。
  // 只认首页那种页眉（class 里带 v2-top）；其它页页眉结构不同，不硬塞。
  function addHeaderEntry() {
    var top = document.querySelector(".v2-top");
    if (!top) return;
    if (top.querySelector(".y-app-entry")) return;
    var a = document.createElement("a");
    a.className = "y-app-entry";
    a.href = "install.html";
    a.textContent = "装 App";
    a.title = "装到手机上，锁屏也能一直放";
    a.addEventListener("click", onEntryClick);
    var ghost = top.querySelector(".v2-ghost");
    if (ghost && ghost.parentNode === top) {
      top.insertBefore(a, ghost);
    } else {
      top.appendChild(a);
    }
  }

  // 装了 App 的人不该再看到入口：直接什么都不画
  if (isInApp()) return;

  injectStyle();

  function boot() {
    addHeaderEntry();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
