// 夜息：全站统一导航外壳（桌面顶栏导航 + 移动底栏胶囊，ES5 语法）

function initYexiTabbar(activePage) {
  var tabs = [
    {
      href: "home.html",
      label: "今晚",
      svg: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>'
    },
    {
      href: "agent.html",
      label: "AI 配声",
      svg: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 10v4M8 7v10M12 4v16M16 7v10M20 10v4"/></svg>'
    },
    {
      href: "diy.html",
      label: "DIY",
      svg: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16M9 4v4M15 10v4M11 16v4"/></svg>'
    },
    {
      href: "community.html",
      label: "广场",
      svg: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20.5s-7-4.5-9-9a5.2 5.2 0 0 1 9-4.5 5.2 5.2 0 0 1 9 4.5c-2 4.5-9 9-9 9z"/></svg>'
    },
    {
      href: "me.html",
      label: "我的",
      svg: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8.5" r="3.5"/><path d="M5 19.5c.8-3.2 3.5-5 7-5s6.2 1.8 7 5"/></svg>'
    }
  ];

  // 做底层(index.html)和做拼接(stitch.html)都算 DIY 这一栏
  var active = activePage;
  if (active === "index.html" || active === "stitch.html") active = "diy.html";

  // 1. 移动端底部悬浮导航（桌面端由 theme.css 隐藏）
  var html = "";
  var navHtml = "";
  for (var i = 0; i < tabs.length; i++) {
    var t = tabs[i];
    var on = active === t.href ? ' class="on"' : "";
    html += '<a href="' + t.href + '"' + on + '><span class="ti">' + t.svg + '</span>' + t.label + "</a>";
    navHtml += '<a href="' + t.href + '"' + on + '>' + t.label + "</a>";
  }

  var bar = document.querySelector(".tabbar");
  if (!bar) {
    bar = document.createElement("div");
    bar.className = "tabbar";
    document.body.appendChild(bar);
  }
  bar.innerHTML = html;

  // 2. 桌面端顶栏内嵌静谧文字导航（插入在 .brand 之后）
  var top = document.querySelector(".top");
  if (top && !top.querySelector(".y-top-nav") && !top.querySelector(".v2-nav")) {
    var nav = document.createElement("nav");
    nav.className = "y-top-nav";
    nav.setAttribute("aria-label", "主导航");
    nav.innerHTML = navHtml;
    var brand = top.querySelector(".brand");
    if (brand && brand.nextSibling) {
      top.insertBefore(nav, brand.nextSibling);
    } else {
      top.appendChild(nav);
    }
  }
}
