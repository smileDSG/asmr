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

function yHeaders(withJson) {
  var h = {};
  if (withJson) {
    h["Content-Type"] = "application/json";
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
    ".auth-link{font-size:12px;color:#d9c4ff;text-decoration:none;" +
      "border:1px solid rgba(196,168,255,.4);border-radius:15px;padding:5px 11px;" +
      "background:rgba(196,168,255,.08)}" +
    ".auth-name{font-size:12px;color:#c9bce0;max-width:90px;overflow:hidden;" +
      "text-overflow:ellipsis;white-space:nowrap}" +
    ".auth-out{font-size:11px;color:#a99cc4;background:transparent;" +
      "border:1px solid rgba(196,168,255,.25);border-radius:13px;padding:4px 9px;" +
      "cursor:pointer;font-family:inherit}";
  document.head.appendChild(style);

  var slot = document.createElement("div");
  slot.className = "auth-slot";
  slot.innerHTML = '<a class="auth-link" href="auth.html?from=' +
    encodeURIComponent(fromPage) + '">登录</a>';
  top.appendChild(slot);

  yGet("/api/me").then(function(r) { return r.json(); }).then(function(d) {
    if (!d.logged_in) return;
    slot.innerHTML = '<span class="auth-name" title="' + yEscape(d.username) +
      '">' + yEscape(d.username) + '</span>' +
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
