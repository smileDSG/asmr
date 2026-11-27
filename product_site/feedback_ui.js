/* 夜息 · 意见箱弹窗组件
   用法：引入本文件后，任意地方调用 openFeedback(preset) 即可。
   preset 可选 { category: 'bug', content: '...' }，用于情境入口预填。
   设计依据：必填只留「内容」一项 + 类型单选，联系方式选填，不强制登录。
*/
(function () {
  if (document.getElementById("fbOverlay")) return; // 防重复注入

  var css = document.createElement("style");
  css.textContent = [
    "#fbOverlay{position:fixed;inset:0;z-index:120;display:none;align-items:center;justify-content:center;padding:20px;background:rgba(4,3,8,.72);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px)}",
    "#fbOverlay.open{display:flex}",
    ".fb-card{width:100%;max-width:420px;max-height:90vh;overflow-y:auto;background:linear-gradient(160deg,rgba(30,26,48,.98),rgba(16,13,28,.98));border:1px solid rgba(233,183,131,.22);border-radius:20px;padding:24px 22px;box-shadow:0 24px 70px rgba(0,0,0,.55);color:#f8f5fd}",
    ".fb-h{font-family:var(--serif,serif);font-size:21px;font-weight:300;letter-spacing:.08em;margin:0 0 6px}",
    ".fb-sub{font-size:12.5px;color:rgba(235,226,250,.6);line-height:1.7;margin:0 0 18px}",
    ".fb-cats{display:flex;gap:8px;margin-bottom:14px}",
    ".fb-cat{flex:1;padding:9px 4px;text-align:center;font-size:13px;border-radius:11px;border:1px solid rgba(233,183,131,.22);background:rgba(255,255,255,.03);color:rgba(248,245,253,.72);cursor:pointer;transition:.18s}",
    ".fb-cat.on{background:rgba(233,183,131,.18);border-color:rgba(233,183,131,.6);color:#fff}",
    ".fb-label{display:block;font-size:12px;color:rgba(235,226,250,.6);margin:0 0 7px;letter-spacing:.05em}",
    ".fb-input,.fb-textarea{width:100%;box-sizing:border-box;background:rgba(255,255,255,.05);border:1px solid rgba(233,183,131,.22);border-radius:12px;padding:12px 13px;color:#f8f5fd;font-size:14px;font-family:inherit;outline:none;transition:.18s}",
    ".fb-input:focus,.fb-textarea:focus{border-color:rgba(233,183,131,.65)}",
    ".fb-textarea{min-height:104px;resize:vertical;line-height:1.6}",
    ".fb-row{margin-bottom:14px}",
    ".fb-tip{font-size:11.5px;color:rgba(235,226,250,.4);margin-top:6px;line-height:1.5}",
    ".fb-acts{display:flex;gap:10px;margin-top:18px}",
    ".fb-btn{flex:1;padding:12px;border-radius:12px;border:1px solid rgba(233,183,131,.35);background:rgba(233,183,131,.16);color:#fff;font-size:14px;cursor:pointer;transition:.18s}",
    ".fb-btn:hover{background:rgba(233,183,131,.26)}",
    ".fb-btn.ghost{background:transparent;border-color:rgba(235,226,250,.2);color:rgba(235,226,250,.7)}",
    ".fb-btn:disabled{opacity:.5;cursor:default}",
    ".fb-msg{font-size:12.5px;text-align:center;min-height:18px;margin-top:12px;color:rgba(235,226,250,.7)}",
    ".fb-msg.ok{color:#9be0b0}"
  ].join("\n");
  document.head.appendChild(css);

  var overlay = document.createElement("div");
  overlay.id = "fbOverlay";
  overlay.innerHTML = [
    '<div class="fb-card" role="dialog" aria-modal="true" aria-label="意见反馈">',
    '  <h2 class="fb-h">说点什么</h2>',
    '  <p class="fb-sub">哪里不舒服、想要什么声音，都可以说。不用登录，也可以不留联系方式。</p>',
    '  <div class="fb-cats">',
    '    <div class="fb-cat" data-cat="bug">出问题了</div>',
    '    <div class="fb-cat on" data-cat="suggestion">有个建议</div>',
    '    <div class="fb-cat" data-cat="other">其他</div>',
    '  </div>',
    '  <div class="fb-row">',
    '    <label class="fb-label" for="fbContent">你想说的</label>',
    '    <textarea class="fb-textarea" id="fbContent" placeholder="比如：雨声听到一半突然停了 / 想要雷声再远一点…"></textarea>',
    '    <div class="fb-tip">写得越具体，越容易改好。最多 1000 字。</div>',
    '  </div>',
    '  <div class="fb-row">',
    '    <label class="fb-label" for="fbContact">联系方式（选填）</label>',
    '    <input class="fb-input" id="fbContact" placeholder="邮箱 / 微信，留了才能回复你" />',
    '  </div>',
    '  <div class="fb-acts">',
    '    <button class="fb-btn ghost" id="fbCancel">先不了</button>',
    '    <button class="fb-btn" id="fbSend">发出去</button>',
    '  </div>',
    '  <div class="fb-msg" id="fbMsg"></div>',
    '</div>'
  ].join("");
  document.body.appendChild(overlay);

  var cat = "suggestion";
  var cats = overlay.querySelectorAll(".fb-cat");
  for (var i = 0; i < cats.length; i++) {
    (function(el) {
      el.onclick = function() {
        cat = el.getAttribute("data-cat");
        for (var j = 0; j < cats.length; j++) cats[j].classList.toggle("on", cats[j] === el);
      };
    })(cats[i]);
  }

  function close() {
    overlay.classList.remove("open");
    document.body.style.overflow = "";
  }
  document.getElementById("fbCancel").onclick = close;
  overlay.onclick = function(e) { if (e.target === overlay) close(); };
  document.addEventListener("keydown", function(e) { if (e.key === "Escape" && overlay.classList.contains("open")) close(); });

  function post(path, body) {
    // yPost 带登录态（返回 Response，要再 .json()）；没有就退回普通 fetch
    if (typeof window.yPost === "function") {
      return window.yPost(path, body).then(function(r) { return r.json(); });
    }
    return fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function(r) { return r.json(); });
  }

  document.getElementById("fbSend").onclick = function() {
    var content = document.getElementById("fbContent").value.trim();
    var contact = document.getElementById("fbContact").value.trim();
    var msg = document.getElementById("fbMsg");
    var btn = document.getElementById("fbSend");
    if (!content) { msg.textContent = "先写点什么吧"; msg.className = "fb-msg"; return; }
    if (content.length > 1000) { msg.textContent = "最多 1000 个字"; msg.className = "fb-msg"; return; }
    btn.disabled = true;
    msg.textContent = "正在发出…";
    msg.className = "fb-msg";
    function done() { btn.disabled = false; }
    post("/api/feedback_submit", { category: cat, content: content, contact: contact })
      .then(function(d) {
        done();
        if (d && d.ok) {
          msg.textContent = "收到了，谢谢你愿意说。";
          msg.className = "fb-msg ok";
          document.getElementById("fbContent").value = "";
          document.getElementById("fbContact").value = "";
          setTimeout(close, 1200);
        } else {
          msg.textContent = (d && d.error) || "没发出去，稍后再试";
          msg.className = "fb-msg";
        }
      })
      .catch(function() {
        done();
        msg.textContent = "没发出去，稍后再试";
        msg.className = "fb-msg";
      });
  };

  window.openFeedback = function(preset) {
    preset = preset || {};
    if (preset.category) {
      cat = preset.category;
      for (var j = 0; j < cats.length; j++) cats[j].classList.toggle("on", cats[j].getAttribute("data-cat") === cat);
    }
    if (preset.content) document.getElementById("fbContent").value = preset.content;
    document.getElementById("fbMsg").textContent = "";
    document.getElementById("fbMsg").className = "fb-msg";
    overlay.classList.add("open");
    document.body.style.overflow = "hidden";
    setTimeout(function() { document.getElementById("fbContent").focus(); }, 50);
  };
})();
