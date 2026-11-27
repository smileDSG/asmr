// Headless Chrome CDP smoke test: fails on any uncaught JS error, console.error, or same-origin HTTP >= 400.
import { spawn } from "child_process";
import fs from "fs";
import os from "os";
import path from "path";

const BASE = (process.argv[2] || "http://47.101.59.166:8000").replace(/\/+$/, "");
const PAGES = ["/home.html", "/m.html", "/diy.html", "/install.html"];

function findChrome() {
  const candidates = [
    process.env.CHROME_PATH,
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  ].filter(Boolean);
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  throw new Error("Chrome/Chromium binary not found; set CHROME_PATH");
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function run() {
  const chromeBin = findChrome();
  const port = 9400 + Math.floor(Math.random() * 400);
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "yexi-smoke-"));
  const chrome = spawn(
    chromeBin,
    [
      "--headless=new",
      "--no-sandbox",
      "--disable-gpu",
      "--disable-dev-shm-usage",
      "--remote-debugging-port=" + port,
      "--user-data-dir=" + userDataDir,
      "--no-first-run",
      "--window-size=390,844",
      "about:blank"
    ],
    { stdio: "ignore" }
  );

  let ws;
  try {
    let list = null;
    for (let i = 0; i < 60; i++) {
      try {
        const res = await fetch("http://127.0.0.1:" + port + "/json/list");
        const arr = await res.json();
        if (arr && arr.length && arr[0].webSocketDebuggerUrl) {
          list = arr;
          break;
        }
      } catch (e) {}
      await sleep(250);
    }
    if (!list) throw new Error("Timed out waiting for Chrome DevTools port " + port);

    ws = new WebSocket(list[0].webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });

    let seq = 0;
    const pending = new Map();
    const listeners = [];
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && pending.has(msg.id)) {
        pending.get(msg.id)(msg);
        pending.delete(msg.id);
      } else if (msg.method) {
        for (const fn of listeners) fn(msg);
      }
    };

    const cmd = (method, params = {}) =>
      new Promise((resolve, reject) => {
        const id = ++seq;
        const timer = setTimeout(() => {
          pending.delete(id);
          reject(new Error("CDP timeout: " + method));
        }, 15000);
        pending.set(id, (res) => {
          clearTimeout(timer);
          resolve(res);
        });
        ws.send(JSON.stringify({ id, method, params }));
      });

    await cmd("Page.enable");
    await cmd("Runtime.enable");
    await cmd("Network.enable");
    await cmd("Network.setCacheDisabled", { cacheDisabled: true });
    await cmd("Emulation.setDeviceMetricsOverride", {
      width: 390,
      height: 844,
      deviceScaleFactor: 1,
      mobile: true
    });
    await cmd("Page.addScriptToEvaluateOnNewDocument", {
      source: "try{localStorage.setItem('yezi_guest','1')}catch(e){}"
    });

    const baseOrigin = new URL(BASE).origin;
    let totalFailures = 0;

    for (const pagePath of PAGES) {
      const jsErrors = [];
      const consoleErrors = [];
      const httpErrors = [];

      const onEvent = (msg) => {
        if (msg.method === "Runtime.exceptionThrown") {
          const d = msg.params && msg.params.exceptionDetails;
          const text =
            (d && d.exception && d.exception.description) ||
            (d && d.text) ||
            "Unknown exception";
          jsErrors.push(text.split("\n")[0]);
        } else if (
          msg.method === "Runtime.consoleAPICalled" &&
          msg.params &&
          msg.params.type === "error"
        ) {
          const args = (msg.params.args || []).map((a) => a.value || a.description || "").join(" ");
          consoleErrors.push(args.slice(0, 200));
        } else if (msg.method === "Network.responseReceived" && msg.params && msg.params.response) {
          const r = msg.params.response;
          if (r.status >= 400 && r.url && r.url.startsWith(baseOrigin)) {
            httpErrors.push(r.status + " " + r.url.slice(baseOrigin.length));
          }
        }
      };
      listeners.push(onEvent);

      let loadDone = false;
      const waitLoad = new Promise((resolve) => {
        const l = (m) => {
          if (m.method === "Page.loadEventFired") {
            loadDone = true;
            resolve();
          }
        };
        listeners.push(l);
        setTimeout(() => {
          if (!loadDone) resolve();
        }, 12000);
      });

      await cmd("Page.navigate", { url: BASE + pagePath });
      await waitLoad;
      await sleep(1500);

      // Remove page listener
      const idx = listeners.indexOf(onEvent);
      if (idx >= 0) listeners.splice(idx, 1);

      const bad = jsErrors.length + consoleErrors.length + httpErrors.length;
      if (bad === 0) {
        console.log("[OK] " + pagePath + "：0 JS异常, 0 console.error, 0 HTTP>=400");
      } else {
        totalFailures += bad;
        console.log("[X ] " + pagePath + "：发现 " + bad + " 个问题");
        for (const e of jsErrors) console.log("     [JS] " + e);
        for (const e of consoleErrors) console.log("     [Console] " + e);
        for (const e of httpErrors) console.log("     [HTTP] " + e);
      }
    }

    if (totalFailures > 0) {
      console.log("\n浏览器巡检失败，共 " + totalFailures + " 处异常。");
      process.exitCode = 1;
    } else {
      console.log("\n浏览器巡检全部通过（" + PAGES.length + " 个核心页面）。");
    }
  } finally {
    try {
      if (ws && ws.readyState === 1) ws.close();
    } catch (e) {}
    try {
      chrome.kill("SIGKILL");
    } catch (e) {}
    try {
      fs.rmSync(userDataDir, { recursive: true, force: true });
    } catch (e) {}
  }
}

run().catch((err) => {
  console.error("[X ] 浏览器巡检执行报错：" + (err && err.stack ? err.stack : err));
  process.exit(1);
});
