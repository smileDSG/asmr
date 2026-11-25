// 夜息 · 付费墙
// 依赖 auth_ui.js（yGet / yPost / yToken / yNeedLogin）
// 任何页面引入本文件后，调 yexiPayWall("day3") 即可弹出商品墙。

var yPayCache = null;
var yPayPending = false;

function yPayMoney(cents) {
  var yuan = Math.floor(cents / 100);
  var fen = cents % 100;
  return yuan + "." + (fen < 10 ? "0" + fen : "" + fen);
}

function yexiPayProducts(cb) {
  if (yPayCache) {
    cb(yPayCache);
    return;
  }
  yGet("/api/pay/products").then(function (r) {
    return r.json();
  }).then(function (d) {
    yPayCache = d;
    cb(d);
  }).catch(function () {
    cb({ products: [], mode: "unknown", configured: false });
  });
}

function yPayInjectStyle() {
  if (document.getElementById("yPayStyle")) return;
  var css = ""
    + ".ypay-mask{position:fixed;inset:0;z-index:9998;background:rgba(3,2,8,.74);"
    + "backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);"
    + "display:flex;align-items:flex-end;justify-content:center;}"
    + ".ypay-sheet{width:100%;max-width:520px;background:#0d0a16;"
    + "border:1px solid rgba(233,183,131,.16);border-bottom:none;"
    + "border-radius:20px 20px 0 0;padding:22px 20px 26px;"
    + "font-family:var(--y-serif,'Noto Serif SC',serif);color:#efe9f7;"
    + "max-height:88vh;overflow:auto;}"
    + ".ypay-head{display:flex;align-items:baseline;justify-content:space-between;"
    + "margin-bottom:4px;}"
    + ".ypay-title{font-size:19px;color:#e9b783;letter-spacing:.04em;}"
    + ".ypay-close{background:none;border:none;color:rgba(236,228,248,.5);"
    + "font-size:20px;cursor:pointer;padding:0 4px;line-height:1;}"
    + ".ypay-sub{font-size:12.5px;color:rgba(236,228,248,.55);"
    + "line-height:1.6;margin:6px 0 18px;}"
    + ".ypay-card{display:flex;align-items:center;gap:14px;"
    + "border:1px solid rgba(233,183,131,.14);border-radius:14px;"
    + "padding:13px 15px;margin-bottom:10px;background:rgba(255,255,255,.02);}"
    + ".ypay-card.hot{border-color:rgba(233,183,131,.42);"
    + "background:rgba(233,183,131,.055);}"
    + ".ypay-info{flex:1;min-width:0;}"
    + ".ypay-name{font-size:14px;color:#efe9f7;margin-bottom:3px;}"
    + ".ypay-note{font-size:12px;color:rgba(236,228,248,.5);}"
    + ".ypay-price{font-size:17px;color:#e9b783;white-space:nowrap;}"
    + ".ypay-price small{font-size:11px;opacity:.7;}"
    + ".ypay-btn{border:none;border-radius:10px;padding:8px 15px;"
    + "background:#e9b783;color:#1a1208;font-size:13px;cursor:pointer;"
    + "font-family:inherit;white-space:nowrap;}"
    + ".ypay-btn:disabled{opacity:.55;cursor:default;}"
    + ".ypay-foot{font-size:11.5px;color:rgba(236,228,248,.38);"
    + "text-align:center;margin-top:14px;line-height:1.7;}"
    + "@media(min-width:720px){.ypay-mask{align-items:center;}"
    + ".ypay-sheet{border-radius:20px;border-bottom:1px solid rgba(233,183,131,.16);}}";
  var tag = document.createElement("style");
  tag.id = "yPayStyle";
  tag.textContent = css;
  document.head.appendChild(tag);
}

function yPayClose() {
  var mask = document.getElementById("yPayMask");
  if (mask) mask.parentNode.removeChild(mask);
}

function yPayCardHtml(p, hot) {
  return ''
    + '<div class="ypay-card' + (hot ? " hot" : "") + '">'
    + '<div class="ypay-info">'
    + '<div class="ypay-name">' + p.name + '</div>'
    + '<div class="ypay-note">' + p.short + ' · ' + p.note + '</div>'
    + '</div>'
    + '<div class="ypay-price">¥' + p.price + '</div>'
    + '<button class="ypay-btn" type="button" data-pid="' + p.id + '">带走</button>'
    + '</div>';
}

function yexiPayWall(productId) {
  if (!yToken()) {
    if (window.yNeedLogin) {
      var page = location.pathname.split("/").pop() || "index.html";
      yNeedLogin("购买", page);
      return;
    }
  }
  yPayInjectStyle();
  yPayClose();

  var mask = document.createElement("div");
  mask.id = "yPayMask";
  mask.className = "ypay-mask";
  mask.innerHTML = ''
    + '<div class="ypay-sheet">'
    + '<div class="ypay-head">'
    + '<div class="ypay-title">把这一夜留下来</div>'
    + '<button class="ypay-close" type="button" aria-label="关闭">×</button>'
    + '</div>'
    + '<div class="ypay-sub" id="yPaySub">正在读取商品…</div>'
    + '<div id="yPayList"></div>'
    + '<div class="ypay-foot" id="yPayFoot">支付宝支付 · 导出即交付 · 不满意可申请退款</div>'
    + '</div>';
  document.body.appendChild(mask);

  mask.querySelector(".ypay-close").onclick = yPayClose;
  mask.onclick = function (e) {
    if (e.target === mask) yPayClose();
  };

  yexiPayProducts(function (d) {
    var sub = document.getElementById("yPaySub");
    var list = document.getElementById("yPayList");
    var foot = document.getElementById("yPayFoot");
    if (!d.products || d.products.length === 0) {
      sub.textContent = "商品还没配好，稍后再试。";
      return;
    }
    sub.textContent = "解锁后能用全部素材，生成也不限次数。到期自动停，不会自动续费。";
    var html = "";
    for (var i = 0; i < d.products.length; i++) {
      var p = d.products[i];
      html += yPayCardHtml(p, p.id === productId);
    }
    list.innerHTML = html;
    if (d.mode === "mock") {
      foot.textContent = "当前是演示模式，不会真的扣钱";
    } else if (!d.configured) {
      foot.textContent = "收款还没开通，暂时无法支付";
    }
    list.onclick = function (e) {
      var btn = e.target;
      if (!btn || !btn.getAttribute) return;
      var pid = btn.getAttribute("data-pid");
      if (!pid) return;
      yPayBuy(pid, btn);
    };
  });
}

function yPayBuy(productId, btn) {
  if (yPayPending) return;
  yPayPending = true;
  var oldText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "下单中";

  yPost("/api/pay/create", { product_id: productId })
    .then(function (r) {
      return r.json().then(function (d) {
        return { code: r.status, data: d };
      });
    })
    .then(function (res) {
      var d = res.data || {};
      if (res.code === 401) {
        yPayPending = false;
        btn.disabled = false;
        btn.textContent = oldText;
        if (window.yNeedLogin) yNeedLogin("购买", location.pathname.split("/").pop());
        return;
      }
      if (!d.pay_url) {
        yPayPending = false;
        btn.disabled = false;
        btn.textContent = oldText;
        alert(d.error || "下单失败，请稍后再试");
        return;
      }
      location.href = d.pay_url;
    })
    .catch(function () {
      yPayPending = false;
      btn.disabled = false;
      btn.textContent = oldText;
      alert("网络不稳，没连上收款服务");
    });
}
