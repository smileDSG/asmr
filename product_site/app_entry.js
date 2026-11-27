// 夜息：站内「装 App」入口（首页页眉一个胶囊 + 我的页一行）
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
    if (!cap) return false;
    if (typeof cap.isNativePlatform === "function") {
      return cap.isNativePlatform() === true;
    }
    // 老版本 Capacitor 没有 isNativePlatform，退化用 getPlatform
    if (typeof cap.getPlatform === "function") {
      return cap.getPlatform() !== "web";
    }
    return false;
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
      // line-height 跟着页面正文（1.7）走，才能和旁边「听觉图鉴」「登录」一样高
      "font-family:inherit;line-height:1.7;cursor:pointer;",
      "transition:background .35s ease,color .35s ease,border-color .35s ease}",
      ".y-app-entry:hover{background:rgba(var(--y-warm-rgb,233,183,131),.22);",
      "border-color:rgba(var(--y-warm-rgb,233,183,131),.62);color:#fff}",
      "@media (max-width:430px){.y-app-entry{padding:6px 12px;font-size:12.5px;letter-spacing:.04em}}",
      // 我的页那一行（放在首屏权益条下面，不用滚动就能看到）
      ".y-app-row-wrap{text-align:center;margin:2px 0 22px}",
      ".y-app-entry-row{display:inline-block;padding:11px 22px;border-radius:999px;",
      "background:rgba(var(--y-warm-rgb,233,183,131),.1);",
      "border:1px solid rgba(var(--y-warm-rgb,233,183,131),.34);",
      "color:var(--y-warm,#e9b783);font-size:13.5px;letter-spacing:.06em;text-decoration:none;",
      "line-height:1.5;transition:background .3s ease,border-color .3s ease}",
      ".y-app-entry-row:hover{background:rgba(var(--y-warm-rgb,233,183,131),.18);",
      "border-color:rgba(var(--y-warm-rgb,233,183,131),.55)}",
      ".y-app-entry-row small{display:block;font-size:11px;color:var(--y-text-muted,#a99fbb);",
      "letter-spacing:.02em;margin-top:3px}",
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
  // 只认首页那种页眉（class 里带 v2-top）；「我的」页页眉结构完全不同，
  // 硬塞进去会挤到「登录」旁边，所以那边只留下面那一行。
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

  // 我的页：权益条下面加一行（在首屏内，不用滚到底部找）
  function addProfileRow() {
    var row = document.createElement("a");
    row.className = "y-app-entry-row";
    row.href = "install.html";
    row.innerHTML = "把夜息装到手机上<small>装成 App 后锁屏也能一直放</small>";
    row.addEventListener("click", onEntryClick);

    var wrap = document.createElement("div");
    wrap.className = "y-app-row-wrap";
    wrap.appendChild(row);

    var hero = document.querySelector("header.page-hero");
    if (hero) {
      if (document.querySelector(".y-app-row-wrap")) return;
      hero.parentNode.insertBefore(wrap, hero.nextSibling);
      return;
    }
    // 兜底：没有这个结构就放在意见反馈上面
    var fb = document.getElementById("feedbackEntry");
    if (fb && fb.parentNode) {
      if (document.querySelector(".y-app-entry-row")) return;
      fb.parentNode.insertBefore(wrap, fb);
    }
  }

  // 装了 App 的人不该再看到入口：直接什么都不画
  if (isInApp()) return;

  injectStyle();

  function boot() {
    addHeaderEntry();
    addProfileRow();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
