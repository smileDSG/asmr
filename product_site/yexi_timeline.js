// 夜息：一夜时间线（共享模块）
// 只管"把哪几段拼成一夜、现在走到哪一段"，真正的声音交给 yexi_mixer.js。
// 不修改任何原始素材，换段时由页面把该段 tracks 灌进播放器，复用现有淡入淡出。
// 纯 ES5 语法，和全站其他脚本保持一致。

(function(global) {
  var STORAGE_KEY = "yexi_timeline_v1";
  var STEP_MINUTES = [1, 3, 5, 10];

  // 3 套成品模板：段内素材都来自已验收的 CC0 真实录音
  var TEMPLATES = [
    {
      id: "rain_night",
      name: "窗边夜雨",
      segs: [
        { name: "窗雨 + 低鸣", minutes: 5, tracks: [
          { path: "母带_城市夜雨_CC0.mp3", weight: 0.8, pan: 0, mode: "loop", density: 0.4 },
          { path: "雨中低鸣.hq.mp3", weight: 0.3, pan: -0.4, mode: "loop", density: 0.4 }
        ]},
        { name: "雨 + 远雷", minutes: 3, tracks: [
          { path: "母带_城市夜雨_CC0.mp3", weight: 0.78, pan: 0, mode: "loop", density: 0.4 },
          { path: "远雷.hq.mp3", weight: 0.26, pan: 0.6, mode: "intermittent", density: 0.25 }
        ]},
        { name: "纯雨底幕", minutes: 10, tracks: [
          { path: "母带_城市夜雨_CC0.mp3", weight: 0.85, pan: 0, mode: "loop", density: 0.4 }
        ]}
      ]
    },
    {
      id: "sea_night",
      name: "远海入眠",
      segs: [
        { name: "海浪 + 夜风", minutes: 5, tracks: [
          { path: "海浪_远海.hq.mp3", weight: 0.75, pan: 0, mode: "loop", density: 0.4 },
          { path: "夜风.hq.mp3", weight: 0.32, pan: 0.38, mode: "loop", density: 0.4 }
        ]},
        { name: "湖海柔浪", minutes: 5, tracks: [
          { path: "海浪_湖海柔浪_451532.hq.mp3", weight: 0.78, pan: 0, mode: "loop", density: 0.4 }
        ]},
        { name: "溪流收尾", minutes: 5, tracks: [
          { path: "溪流_野外溪水_180732.hq.mp3", weight: 0.7, pan: 0, mode: "loop", density: 0.4 }
        ]}
      ]
    },
    {
      id: "rain_road",
      name: "雨中读书",
      segs: [
        { name: "乡村小雨", minutes: 3, tracks: [
          { path: "乡村小雨.hq.mp3", weight: 0.62, pan: 0, mode: "loop", density: 0.4 }
        ]},
        { name: "雨 + 翻书", minutes: 5, tracks: [
          { path: "柔和雨.hq.mp3", weight: 0.6, pan: 0, mode: "loop", density: 0.4 },
          { path: "ASMR_翻书多人_575764.hq.mp3", weight: 0.34, pan: -0.3, mode: "intermittent", density: 0.4 }
        ]},
        { name: "夜风收尾", minutes: 5, tracks: [
          { path: "夜风.hq.mp3", weight: 0.7, pan: 0, mode: "loop", density: 0.4 }
        ]}
      ]
    }
  ];

  function clamp(v, lo, hi) {
    v = Number(v);
    if (isNaN(v)) return lo;
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
  }

  function noop() {}

  function YexiTimeline(options) {
    var o = options || {};
    this.strip = o.strip || null;
    this.tpls = o.tpls || null;
    this.cursor = o.cursor || null;
    this.onApply = o.onApply || noop;        // function(tracks, index, seg, silent)
    this.onTitle = o.onTitle || noop;        // function(title)
    this.onResetWork = o.onResetWork || noop;// function() 换模板时断掉旧作品关联
    this.isPlaying = o.isPlaying || function() { return false; };
    this.canTick = o.canTick || function() { return true; };
    this.play = o.play || noop;
    this.toast = o.toast || noop;

    this.segments = [];
    this.active = false;
    this.templateId = "";
    this.index = 0;
    this.elapsedBefore = 0;
    this.startedAt = Date.now();
    this.timer = null;
    this.self = this;
  }

  YexiTimeline.prototype.durationSec = function(i) {
    if (i < 0 || i >= this.segments.length) return 0;
    return (Number(this.segments[i].minutes) || 3) * 60;
  };

  YexiTimeline.prototype.totalSec = function() {
    var s = 0;
    for (var i = 0; i < this.segments.length; i++) s += this.durationSec(i);
    return s;
  };

  YexiTimeline.prototype.indexAt = function(sec) {
    var acc = 0;
    for (var i = 0; i < this.segments.length; i++) {
      var d = this.durationSec(i);
      if (sec < acc + d) return i;
      acc += d;
    }
    return this.segments.length - 1;
  };

  YexiTimeline.prototype.elapsed = function() {
    if (!this.isPlaying()) return this.elapsedBefore;
    return this.elapsedBefore + (Date.now() - this.startedAt) / 1000;
  };

  // 把某段的 tracks 交给页面；界面和播放器由页面自己的回调更新
  YexiTimeline.prototype.apply = function(i, silent) {
    if (i < 0 || i >= this.segments.length) return;
    this.index = i;
    var seg = this.segments[i];
    var copy = [];
    for (var k = 0; k < seg.tracks.length; k++) {
      copy.push(seg.tracks[k]);
    }
    this.onApply(copy, i, seg, !!silent);
    this.render();
    if (!silent) this.toast("第 " + (i + 1) + " 段 · " + seg.name);
  };

  YexiTimeline.prototype.tick = function() {
    if (!this.active || !this.isPlaying() || !this.canTick()) return;
    var sec = this.elapsed();
    var total = this.totalSec();
    var idx = this.indexAt(sec);
    if (idx !== this.index) {
      this.apply(idx, false);
    }
    if (sec >= total) {
      // 一整夜播完：从头再来
      this.elapsedBefore = 0;
      this.startedAt = Date.now();
      this.apply(0, true);
    }
    this.updateCursor();
  };

  YexiTimeline.prototype.updateCursor = function() {
    if (!this.cursor) return;
    if (!this.active || this.segments.length === 0) {
      this.cursor.textContent = "";
      return;
    }
    var sec = this.elapsed();
    var m = Math.floor(sec / 60);
    var s = Math.floor(sec % 60);
    this.cursor.textContent = "正在第 " + (this.index + 1) + " / " + this.segments.length +
      " 段 · " + m + ":" + (s < 10 ? "0" : "") + s + " / " + Math.floor(this.totalSec() / 60) + " 分钟";
  };

  YexiTimeline.prototype.startTicker = function() {
    var self = this;
    if (self.timer) { clearInterval(self.timer); self.timer = null; }
    if (self.active && self.isPlaying() && self.canTick()) {
      self.timer = setInterval(function() { self.tick(); }, 1000);
      self.tick();
    }
  };

  YexiTimeline.prototype.stopTicker = function() {
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
  };

  // 播放器开始/暂停时由页面调用；暂停时把已播秒数结算清楚
  YexiTimeline.prototype.onPlayChanged = function(next) {
    if (!this.active) return;
    if (next) {
      this.startedAt = Date.now();
    } else {
      this.elapsedBefore += (Date.now() - this.startedAt) / 1000;
    }
    this.startTicker();
  };

  YexiTimeline.prototype.load = function(id, autoStart) {
    var tpl = null;
    for (var i = 0; i < TEMPLATES.length; i++) {
      if (TEMPLATES[i].id === id) { tpl = TEMPLATES[i]; break; }
    }
    if (!tpl) return;
    this.active = true;
    this.templateId = tpl.id;
    this.segments = [];
    for (var j = 0; j < tpl.segs.length; j++) {
      this.segments.push({
        name: tpl.segs[j].name,
        minutes: tpl.segs[j].minutes,
        tracks: (tpl.segs[j].tracks || []).slice()
      });
    }
    this.elapsedBefore = 0;
    this.startedAt = Date.now();
    this.index = 0;
    this.onTitle(tpl.name + " · 一夜时间线");
    this.onResetWork();
    try { localStorage.setItem(STORAGE_KEY, this.templateId); } catch (e) {}
    this.apply(0, true);
    if (autoStart) this.play();
  };

  YexiTimeline.prototype.restore = function() {
    var saved = "";
    try { saved = localStorage.getItem(STORAGE_KEY) || ""; } catch (e) {}
    if (saved) {
      this.load(saved, false);
    } else {
      this.render();
    }
  };

  YexiTimeline.prototype.turnOff = function() {
    this.active = false;
    this.templateId = "";
    this.segments = [];
    this.elapsedBefore = 0;
    this.stopTicker();
    try { localStorage.removeItem(STORAGE_KEY); } catch (e) {}
    this.render();
  };

  YexiTimeline.prototype.render = function() {
    var self = this;
    var strip = this.strip;
    var tpls = this.tpls;
    if (!strip || !tpls) return;

    tpls.innerHTML = "";
    for (var t = 0; t < TEMPLATES.length; t++) {
      (function(tpl) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "timeline-tpl" + (self.active && self.templateId === tpl.id ? " on" : "");
        b.textContent = tpl.name;
        b.onclick = function() { self.load(tpl.id, false); };
        tpls.appendChild(b);
      })(TEMPLATES[t]);
    }

    strip.innerHTML = "";
    if (!this.active || this.segments.length === 0) {
      strip.innerHTML = '<div class="timeline-foot" style="padding:10px">选一套上面的模板，就能看到拼好的一夜</div>';
      this.updateCursor();
      return;
    }

    var total = this.totalSec() || 1;
    var colors = [
      "rgba(110,160,190,0.22)",
      "rgba(150,130,190,0.22)",
      "rgba(190,150,120,0.22)",
      "rgba(120,170,150,0.22)"
    ];
    for (var i = 0; i < this.segments.length; i++) {
      (function(idx) {
        var seg = self.segments[idx];
        var el = document.createElement("div");
        el.className = "tl-seg" + (idx === self.index ? " on" : "");
        el.style.background = colors[idx % colors.length];
        el.style.flex = ((self.durationSec(idx) / total) * 100) + " 1 0";

        var nm = document.createElement("span");
        nm.className = "tl-seg-name";
        nm.textContent = seg.name;
        var du = document.createElement("span");
        du.className = "tl-seg-dur";
        du.textContent = seg.minutes + " 分钟";
        el.appendChild(nm);
        el.appendChild(du);

        el.onclick = function() {
          var before = 0;
          for (var q = 0; q < idx; q++) before += self.durationSec(q);
          self.elapsedBefore = before;
          self.startedAt = Date.now();
          self.apply(idx, true);
          if (!self.isPlaying()) self.play();
          self.toast("从第 " + (idx + 1) + " 段开始");
        };

        var grip = document.createElement("div");
        grip.className = "tl-seg-grip";
        grip.title = "拖动改时长";
        grip.onpointerdown = function(e) {
          e.stopPropagation();
          var startX = e.clientX;
          var startM = seg.minutes;
          function move(ev) {
            var steps = Math.round((ev.clientX - startX) / 22);
            var guess = startM + steps;
            var best = STEP_MINUTES[0];
            for (var z = 0; z < STEP_MINUTES.length; z++) {
              if (Math.abs(STEP_MINUTES[z] - guess) < Math.abs(best - guess)) {
                best = STEP_MINUTES[z];
              }
            }
            best = clamp(best, 1, 10);
            if (best !== seg.minutes) {
              seg.minutes = best;
              self.render();
              self.updateCursor();
            }
          }
          function up() {
            window.removeEventListener("pointermove", move);
            window.removeEventListener("pointerup", up);
            self.toast("这一段改成 " + seg.minutes + " 分钟");
          }
          window.addEventListener("pointermove", move);
          window.addEventListener("pointerup", up);
        };
        el.appendChild(grip);
        strip.appendChild(el);
      })(i);
    }
    this.updateCursor();
  };

  global.YexiTimeline = YexiTimeline;
  global.YEXI_TIMELINE_TEMPLATES = TEMPLATES;
})(window);
