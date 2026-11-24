// 夜息：登录状态小工具。三页共用，逻辑只写这一份。
// 写法保持朴素：var + function + 顺序执行，不使用新语法。

// 同源：页面和 API 由同一个服务提供，浏览器会自动用当前域名，
// 本地开发访问 8000、线上访问分享链接都不用改这里
var YEXI_API = "";

function yToken() {
  return localStorage.getItem("yezi_token") || "";
}

function ySetToken(token) {
  if (token) {
    localStorage.setItem("yezi_token", token);
  } else {
    localStorage.removeItem("yezi_token");
  }
}

function yClientId() {
  try {
    var cid = localStorage.getItem("yezi_client_id");
    if (!cid || !/^[A-Za-z0-9_-]{4,40}$/.test(cid)) {
      cid = "c_" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);
      localStorage.setItem("yezi_client_id", cid);
    }
    return cid;
  } catch (e) {
    return "";
  }
}

function yHeaders(withJson) {
  var h = {};
  if (withJson) {
    h["Content-Type"] = "application/json";
  }
  var cid = yClientId();
  if (cid) {
    h["X-Yexi-Client"] = cid;
  }
  var token = yToken();
  if (token) {
    h["Authorization"] = "Bearer " + token;
  }
  return h;
}

// 带登录状态的 GET / POST，生成的请求头不用自己拼
function yGet(path) {
  return fetch(YEXI_API + path, { headers: yHeaders(false) });
}

function yPost(path, body) {
  return fetch(YEXI_API + path, {
    method: "POST",
    headers: yHeaders(true),
    body: JSON.stringify(body || {})
  });
}

// 用户名显示在页面上前先转义，避免把字符当成 HTML
function yEscape(s) {
  var div = document.createElement("div");
  div.textContent = s || "";
  return div.innerHTML;
}

// 给每个页面顶部加一小块登录状态：未登录显示"登录"，已登录显示用户名和退出
function initAuthBar(fromPage) {
  var top = document.querySelector(".top");
  if (!top) return;

  var style = document.createElement("style");
  style.textContent =
    ".auth-slot{display:flex;align-items:center;gap:8px;flex:0 0 auto}" +
    ".auth-link{font-size:12px;letter-spacing:.08em;color:rgba(236,228,248,.82);text-decoration:none;" +
      "border:none;border-radius:999px;padding:6px 14px;" +
      "background:rgba(255,255,255,.07);transition:background .5s ease,color .5s ease}" +
    ".auth-link:hover{background:rgba(233,183,131,.18);color:#fff}" +
    ".auth-name{font-size:12px;color:rgba(236,228,248,.86);max-width:96px;overflow:hidden;" +
      "text-overflow:ellipsis;white-space:nowrap;text-decoration:none;" +
      "border-bottom:1px dashed rgba(233,183,131,.4);padding-bottom:1px}" +
    ".auth-name:hover{color:#fff;border-bottom-color:rgba(233,183,131,.85)}" +
    ".auth-out{font-size:11px;color:rgba(226,216,244,.6);background:rgba(255,255,255,.055);" +
      "border:none;border-radius:999px;padding:4px 10px;" +
      "cursor:pointer;font-family:inherit;transition:background .5s ease,color .5s ease}" +
    ".auth-out:hover{background:rgba(233,183,131,.16);color:#fff}";
  document.head.appendChild(style);

  var slot = document.createElement("div");
  slot.className = "auth-slot";
  slot.innerHTML = '<a class="auth-link" href="auth.html?from=' +
    encodeURIComponent(fromPage) + '">登录</a>';
  top.appendChild(slot);

  yGet("/api/me").then(function(r) { return r.json(); }).then(function(d) {
    if (!d.logged_in) return;
    slot.innerHTML = '<a class="auth-name" href="me.html" title="打开我的 ASMR 主页：' + yEscape(d.username) +
      '">' + yEscape(d.username) + '</a>' +
      '<button class="auth-out" id="authOutBtn">退出</button>';
    document.getElementById("authOutBtn").onclick = function() {
      yPost("/api/logout", {}).then(function() {
        ySetToken("");
        location.reload();
      }).catch(function() {
        ySetToken("");
        location.reload();
      });
    };
  }).catch(function() {
    // 后端没开时安静降级，不影响听声音
  });
}

// ===== 游客模式边界：受限操作统一引导登录 =====
// 判断当前是不是游客（有 token 才是登录用户）
function yIsGuest() {
  return !yToken();
}

// 游客点了需要登录的功能：给出温和提示，不破坏睡前氛围
// what = 功能名，fromPage = 登录后回哪个页面
function yNeedLogin(what, fromPage) {
  if (!yIsGuest()) return false;
  var page = fromPage || (location.pathname.split("/").pop() || "home.html");
  var msg = "登录后才能" + what + "，游客可以先听听看";
  // 优先用页面自带的 toast（如果有），否则用浏览器原生确认
  if (typeof window.showToast === "function") {
    window.showToast(msg);
    return true;
  }
  var go = window.confirm(msg + "\n\n现在去登录？");
  if (go) {
    location.href = "auth.html?from=" + encodeURIComponent(page);
  }
  return true;
}

// ===== 入口门闸：没登录、也没选过游客，就先去 gate.html 二选一 =====
// gate.html 和 auth.html 自己不拦，否则会来回跳
function yGateCheck() {
  var page = location.pathname.split("/").pop() || "index.html";
  if (page === "gate.html" || page === "auth.html") return;

  // 有 token 说明登录过，直接放行
  if (yToken()) return;

  // 选过游客就记住，不再弹
  try {
    if (localStorage.getItem("yezi_guest") === "1") return;
  } catch (e) {
    // 本地存储不可用时别把人挡在外面
    return;
  }

  var from = page;
  if (!/^[A-Za-z0-9_-]+\.html$/.test(from)) from = "home.html";
  location.href = "gate.html?from=" + encodeURIComponent(from);
}
yGateCheck();
