// 夜息：一夜时间线（共享模块）
// 只管"把哪几段拼成一夜、每段多长、用什么方式衔接、现在走到哪一段"，真正的声音交给 yexi_mixer.js。
// 不修改任何原始素材，换段时由页面把该段 tracks 灌进播放器，复用平滑交叉淡化。
// 纯 ES5 语法，和全站其他脚本保持一致。

(function(global) {
  var LEGACY_STORAGE_KEY = "yexi_timeline_v1";
  var STATE_STORAGE_KEY = "yexi_timeline_state_v2";
  var STEP_MINUTES = [1, 2, 3, 5, 10, 15];
  var MAX_SEGMENTS = 8;

  // 3 套成品模板：段内素材都来自已验收的 CC0 真实录音
  var TEMPLATES = [
    {
      id: "rain_night",
      name: "窗边夜雨",
      segs: [
        { id: "rn1", name: "窗雨 + 低鸣", minutes: 5, transition: "crossfade", fadeSec: 4, tracks: [
          { path: "母带_城市夜雨_CC0.mp3", weight: 0.8, pan: 0, mode: "loop", density: 0.4 },
          { path: "雨中低鸣.hq.mp3", weight: 0.3, pan: -0.4, mode: "loop", density: 0.4 }
        ]},
        { id: "rn2", name: "雨 + 远雷", minutes: 3, transition: "crossfade", fadeSec: 4, tracks: [
          { path: "母带_城市夜雨_CC0.mp3", weight: 0.78, pan: 0, mode: "loop", density: 0.4 },
          { path: "远雷.hq.mp3", weight: 0.26, pan: 0.6, mode: "intermittent", density: 0.25 }
        ]},
        { id: "rn3", name: "纯雨底幕", minutes: 10, transition: "crossfade", fadeSec: 5, tracks: [
          { path: "母带_城市夜雨_CC0.mp3", weight: 0.85, pan: 0, mode: "loop", density: 0.4 }
        ]}
      ]
    },
    {
      id: "sea_night",
      name: "远海入眠",
      segs: [
        { id: "sn1", name: "海浪 + 夜风", minutes: 5, transition: "crossfade", fadeSec: 4, tracks: [
          { path: "海浪_远海.hq.mp3", weight: 0.75, pan: 0, mode: "loop", density: 0.4 },
          { path: "夜风.hq.mp3", weight: 0.32, pan: 0.38, mode: "loop", density: 0.4 }
        ]},
        { id: "sn2", name: "湖海柔浪", minutes: 5, transition: "crossfade", fadeSec: 5, tracks: [
          { path: "海浪_湖海柔浪_451532.hq.mp3", weight: 0.78, pan: 0, mode: "loop", density: 0.4 }
        ]},
        { id: "sn3", name: "溪流收尾", minutes: 5, transition: "crossfade", fadeSec: 5, tracks: [
          { path: "溪流_野外溪水_180732.hq.mp3", weight: 0.7, pan: 0, mode: "loop", density: 0.4 }
        ]}
      ]
    },
    {
      id: "rain_road",
      name: "雨中读书",
      segs: [
        { id: "rr1", name: "乡村小雨", minutes: 3, transition: "crossfade", fadeSec: 4, tracks: [
          { path: "乡村小雨.hq.mp3", weight: 0.62, pan: 0, mode: "loop", density: 0.4 }
        ]},
        { id: "rr2", name: "雨 + 翻书", minutes: 5, transition: "crossfade", fadeSec: 4, tracks: [
          { path: "柔和雨.hq.mp3", weight: 0.6, pan: 0, mode: "loop", density: 0.4 },
          { path: "ASMR_翻书多人_575764.hq.mp3", weight: 0.34, pan: -0.3, mode: "intermittent", density: 0.4 }
        ]},
        { id: "rr3", name: "夜风收尾", minutes: 5, transition: "crossfade", fadeSec: 5, tracks: [
          { path: "夜风.hq.mp3", weight: 0.7, pan: 0, mode: "loop", density: 0.4 }
        ]}
      ]
    }
  ];

  var _uidSeq = 1;
  function genId() {
    return "seg_" + Date.now().toString(36) + "_" + (_uidSeq++);
  }

  function clamp(v, lo, hi) {
    v = Number(v);
    if (isNaN(v)) return lo;
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
  }

  function cloneTrack(t) {
    return {
      path: String(t && t.path || ""),
      weight: clamp(parseFloat(t && t.weight) || 0.5, 0.05, 1.0),
      pan: clamp(parseFloat(t && t.pan) || 0, -1.0, 1.0),
      mode: (t && t.mode === "intermittent") ? "intermittent" : "loop",
      density: clamp(parseFloat(t && t.density) || 0.4, 0.1, 1.0)
    };
  }

  function cloneSegment(raw, fallbackName) {
    var s = raw || {};
    var trans = (s.transition === "dip" || s.transition === "cut") ? s.transition : "crossfade";
    var trs = [];
    var rawTr = Array.isArray(s.tracks) ? s.tracks : [];
    for (var i = 0; i < rawTr.length; i++) {
      if (rawTr[i] && rawTr[i].path) trs.push(cloneTrack(rawTr[i]));
    }
    return {
      id: s.id ? String(s.id) : genId(),
      name: String(s.name || fallbackName || "新段落").trim().slice(0, 24) || "新段落",
      minutes: clamp(s.minutes || 3, 1, 30),
      transition: trans,
      fadeSec: clamp(s.fadeSec !== undefined ? s.fadeSec : 4, 0.5, 12),
      tracks: trs
    };
  }

  function noop() {}

  function YexiTimeline(options) {
    var o = options || {};
    this.strip = o.strip || null;
    this.tpls = o.tpls || null;
    this.cursor = o.cursor || null;
    this.onApply = o.onApply || noop;                   // function(tracks, index, seg, silent, transitionOpts)
    this.onTitle = o.onTitle || noop;                   // function(title)
    this.onTemplate = o.onTemplate || noop;             // function(id) 用户选了模板
    this.onEdit = o.onEdit || noop;                     // function(index, minutes) 用户改了段落
    this.onPreload = o.onPreload || noop;               // function(tracks) 预加载下一段素材
    this.onTransitionState = o.onTransitionState || noop; // function(active, label)
    this.onChange = o.onChange || noop;                 // function(timeline) 段落结构变化
    this.onResetWork = o.onResetWork || noop;           // function() 换模板时断掉旧作品关联
    this.isPlaying = o.isPlaying || function() { return false; };
    this.canTick = o.canTick || function() { return true; };
    this.play = o.play || noop;
    this.toast = o.toast || noop;

    this.title = "一夜时间线";
    this.segments = [];
    this.active = false;
    this.templateId = "";
    this.index = 0;
    this.elapsedBefore = 0;
    this.startedAt = Date.now();
    this.timer = null;
    this.playheadEl = null;
    this._preloadedForKey = "";
    this._transitionTimer = null;
    this.self = this;
  }

  YexiTimeline.prototype.persist = function() {
    if (!this.active || this.segments.length === 0) return;
    try {
      var payload = this.serialize();
      payload.templateId = this.templateId || "";
      localStorage.setItem(STATE_STORAGE_KEY, JSON.stringify(payload));
      if (this.templateId) {
        localStorage.setItem(LEGACY_STORAGE_KEY, this.templateId);
      } else {
        localStorage.removeItem(LEGACY_STORAGE_KEY);
      }
    } catch (e) {}
  };

  YexiTimeline.prototype.serialize = function() {
    var segs = [];
    for (var i = 0; i < this.segments.length; i++) {
      segs.push(cloneSegment(this.segments[i]));
    }
    return {
      title: this.title || "我拼的一夜",
      segments: segs
    };
  };

  YexiTimeline.prototype.durationSec = function(i) {
    if (i < 0 || i >= this.segments.length) return 0;
    return (Number(this.segments[i].minutes) || 3) * 60;
  };

  YexiTimeline.prototype.totalSec = function() {
    var s = 0;
    for (var i = 0; i < this.segments.length; i++) s += this.durationSec(i);
    return s;
  };

  YexiTimeline.prototype.offsetOf = function(idx) {
    var acc = 0;
    for (var i = 0; i < idx && i < this.segments.length; i++) {
      acc += this.durationSec(i);
    }
    return acc;
  };

  YexiTimeline.prototype.indexAt = function(sec) {
    var acc = 0;
    for (var i = 0; i < this.segments.length; i++) {
      var d = this.durationSec(i);
      if (sec < acc + d) return i;
      acc += d;
    }
    return Math.max(0, this.segments.length - 1);
  };

  YexiTimeline.prototype.elapsed = function() {
    if (!this.isPlaying()) return this.elapsedBefore;
    return this.elapsedBefore + (Date.now() - this.startedAt) / 1000;
  };

  YexiTimeline.prototype._preloadNextOf = function(i) {
    if (this.segments.length < 2) return;
    var nextIdx = (i + 1) % this.segments.length;
    var nextSeg = this.segments[nextIdx];
    if (!nextSeg || !nextSeg.tracks || nextSeg.tracks.length === 0) return;
    var key = i + "->" + nextIdx + ":" + nextSeg.tracks.map(function(t) { return t.path; }).join(",");
    if (this._preloadedForKey === key) return;
    this._preloadedForKey = key;
    this.onPreload(nextSeg.tracks.slice());
  };

  YexiTimeline.prototype._showTransitionBanner = function(seg) {
    var self = this;
    if (self._transitionTimer) {
      clearTimeout(self._transitionTimer);
      self._transitionTimer = null;
    }
    var tName = seg.transition === "dip" ? "渐弱换场" : (seg.transition === "cut" ? "直接衔接" : "丝滑交叠");
    var sec = seg.transition === "cut" ? 0.5 : (Number(seg.fadeSec) || 4);
    self.onTransitionState(true, "正在" + tName + "至「" + seg.name + "」(" + sec + "s)");
    self._transitionTimer = setTimeout(function() {
      self._transitionTimer = null;
      self.onTransitionState(false, "");
    }, Math.round(Math.max(1.2, sec) * 1000));
  };

  // 把某段的 tracks 交给页面；界面和播放器由页面自己的回调更新
  YexiTimeline.prototype.apply = function(i, silent, transitionOpts) {
    if (i < 0 || i >= this.segments.length) return;
    this.index = i;
    var seg = this.segments[i];
    var copy = [];
    for (var k = 0; k < seg.tracks.length; k++) {
      copy.push(cloneTrack(seg.tracks[k]));
    }
    var opts = transitionOpts || {
      transition: "crossfade",
      fadeOutSec: 0.45,
      fadeInSec: 0.45
    };
    this.onApply(copy, i, seg, !!silent, opts);
    this.render();
    this._preloadNextOf(i);
    if (!silent) {
      this.toast("第 " + (i + 1) + " 段 · " + seg.name);
      if (opts && opts.isBoundary) {
        this._showTransitionBanner(seg);
      }
    }
  };

  YexiTimeline.prototype.tick = function() {
    if (!this.active || !this.isPlaying() || !this.canTick() || this.segments.length === 0) return;
    var sec = this.elapsed();
    var total = this.totalSec();
    if (total <= 0) return;

    if (sec >= total) {
      // 一整夜播完：从头平滑衔接回来
      this.elapsedBefore = 0;
      this.startedAt = Date.now();
      var firstSeg = this.segments[0];
      this.apply(0, false, {
        transition: firstSeg.transition || "crossfade",
        fadeOutSec: firstSeg.fadeSec || 4,
        fadeInSec: firstSeg.fadeSec || 4,
        isBoundary: true
      });
      this.updateCursor();
      return;
    }

    var idx = this.indexAt(sec);
    var curEnd = this.offsetOf(idx) + this.durationSec(idx);
    if (curEnd - sec <= 15) {
      this._preloadNextOf(idx);
    }

    if (idx !== this.index) {
      var targetSeg = this.segments[idx];
      var secFade = clamp(Number(targetSeg.fadeSec) || 4, 0.5, 12);
      this.apply(idx, false, {
        transition: targetSeg.transition || "crossfade",
        fadeOutSec: secFade,
        fadeInSec: secFade,
        isBoundary: true
      });
    }
    this.updateCursor();
  };

  YexiTimeline.prototype.updateCursor = function() {
    var sec = this.elapsed();
    var total = this.totalSec();
    if (this.playheadEl && total > 0) {
      var pct = clamp((sec / total) * 100, 0, 100);
      this.playheadEl.style.left = pct.toFixed(2) + "%";
      this.playheadEl.style.display = "block";
    } else if (this.playheadEl) {
      this.playheadEl.style.display = "none";
    }
    if (!this.cursor) return;
    if (!this.active || this.segments.length === 0) {
      this.cursor.textContent = "";
      return;
    }
    var m = Math.floor(sec / 60);
    var s = Math.floor(sec % 60);
    var totalMin = Math.round(total / 60);
    this.cursor.textContent = "正在第 " + (this.index + 1) + " / " + this.segments.length +
      " 段 · " + m + ":" + (s < 10 ? "0" : "") + s + " / " + totalMin + " 分钟";
  };

  YexiTimeline.prototype.startTicker = function() {
    var self = this;
    if (self.timer) { clearInterval(self.timer); self.timer = null; }
    if (self.active && self.isPlaying() && self.canTick()) {
      self.timer = setInterval(function() { self.tick(); }, 250);
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

  // 立即跳到第 idx 段，并可选设置段内起始秒数
  YexiTimeline.prototype.jumpToSegment = function(idx, offsetInSegSec, autoPlay) {
    if (idx < 0 || idx >= this.segments.length) return;
    var segDur = this.durationSec(idx);
    var off = clamp(Number(offsetInSegSec) || 0, 0, Math.max(0, segDur - 0.5));
    this.elapsedBefore = this.offsetOf(idx) + off;
    this.startedAt = Date.now();
    this._preloadedForKey = "";
    this.apply(idx, true, { transition: "crossfade", fadeOutSec: 0.45, fadeInSec: 0.45 });
    if (autoPlay && !this.isPlaying()) {
      this.play();
    } else {
      this.updateCursor();
    }
  };

  // 试听 fromIdx -> fromIdx+1 的交界过渡：直接跳到交界前 5 秒并开始播放
  YexiTimeline.prototype.previewTransition = function(fromIdx) {
    if (this.segments.length < 2) {
      this.toast("至少需要 2 段才能试听过渡");
      return;
    }
    var idx = clamp(parseInt(fromIdx, 10) || 0, 0, this.segments.length - 2);
    var segDur = this.durationSec(idx);
    var lead = segDur >= 7 ? 5 : Math.max(1, segDur - 2);
    var startOffset = Math.max(0, segDur - lead);
    var nextSeg = this.segments[idx + 1];
    if (nextSeg && nextSeg.tracks) {
      this.onPreload(nextSeg.tracks.slice());
    }
    this.jumpToSegment(idx, startOffset, true);
    this.toast("试听衔接：" + Math.round(lead) + " 秒后切入「" + nextSeg.name + "」");
  };

  YexiTimeline.prototype.addSegment = function(segData, afterIndex) {
    if (this.segments.length >= MAX_SEGMENTS) {
      this.toast("最多拼 " + MAX_SEGMENTS + " 段，足够陪伴一整夜了");
      return -1;
    }
    var insertAt = (afterIndex !== undefined && afterIndex !== null)
      ? clamp(afterIndex + 1, 0, this.segments.length)
      : this.segments.length;

    var base = segData;
    if (!base) {
      var ref = this.segments[clamp(insertAt - 1, 0, this.segments.length - 1)];
      if (ref) {
        base = cloneSegment(ref, "第 " + (this.segments.length + 1) + " 段");
        base.id = genId();
      } else {
        base = cloneSegment({
          name: "夜雨微声",
          minutes: 3,
          transition: "crossfade",
          fadeSec: 4,
          tracks: [{ path: "母带_城市夜雨_CC0.mp3", weight: 0.72, pan: 0, mode: "loop", density: 0.4 }]
        });
      }
    } else {
      base = cloneSegment(base);
      base.id = genId();
    }

    this.segments.splice(insertAt, 0, base);
    this.active = true;
    this.templateId = "";
    this._preloadedForKey = "";
    this.index = insertAt;
    this.elapsedBefore = this.offsetOf(insertAt);
    this.startedAt = Date.now();
    this.persist();
    this.apply(insertAt, true);
    this.onEdit(insertAt, base.minutes);
    this.onChange(this);
    return insertAt;
  };

  YexiTimeline.prototype.removeSegment = function(idx) {
    if (this.segments.length <= 1) {
      this.toast("至少保留 1 段声音");
      return false;
    }
    if (idx < 0 || idx >= this.segments.length) return false;
    this.segments.splice(idx, 1);
    this.templateId = "";
    this._preloadedForKey = "";
    var nextIdx = clamp(idx, 0, this.segments.length - 1);
    this.index = nextIdx;
    this.elapsedBefore = this.offsetOf(nextIdx);
    this.startedAt = Date.now();
    this.persist();
    this.apply(nextIdx, true);
    this.onEdit(nextIdx, this.segments[nextIdx].minutes);
    this.onChange(this);
    return true;
  };

  YexiTimeline.prototype.moveSegment = function(fromIdx, toIdx) {
    if (fromIdx < 0 || fromIdx >= this.segments.length) return false;
    if (toIdx < 0 || toIdx >= this.segments.length || fromIdx === toIdx) return false;
    var item = this.segments.splice(fromIdx, 1)[0];
    this.segments.splice(toIdx, 0, item);
    this.templateId = "";
    this._preloadedForKey = "";
    this.index = toIdx;
    this.elapsedBefore = this.offsetOf(toIdx);
    this.startedAt = Date.now();
    this.persist();
    this.apply(toIdx, true);
    this.onEdit(toIdx, item.minutes);
    this.onChange(this);
    return true;
  };

  YexiTimeline.prototype.updateSegment = function(idx, patch) {
    if (idx < 0 || idx >= this.segments.length || !patch) return false;
    var seg = this.segments[idx];
    var tracksChanged = false;
    if (patch.name !== undefined) {
      seg.name = String(patch.name).trim().slice(0, 24) || seg.name;
    }
    if (patch.minutes !== undefined) {
      seg.minutes = clamp(patch.minutes, 1, 30);
    }
    if (patch.transition !== undefined) {
      seg.transition = (patch.transition === "dip" || patch.transition === "cut") ? patch.transition : "crossfade";
    }
    if (patch.fadeSec !== undefined) {
      seg.fadeSec = clamp(patch.fadeSec, 0.5, 12);
    }
    if (Array.isArray(patch.tracks)) {
      var nextTracks = [];
      for (var i = 0; i < patch.tracks.length; i++) {
        if (patch.tracks[i] && patch.tracks[i].path) nextTracks.push(cloneTrack(patch.tracks[i]));
      }
      seg.tracks = nextTracks;
      tracksChanged = true;
    }
    this.templateId = "";
    this._preloadedForKey = "";
    this.persist();
    if (idx === this.index && tracksChanged) {
      this.apply(idx, true);
    } else {
      this.render();
    }
    this.onEdit(idx, seg.minutes);
    this.onChange(this);
    return true;
  };

  YexiTimeline.prototype.setTitle = function(title) {
    var t = String(title || "").trim().slice(0, 36);
    if (!t) return;
    this.title = t;
    this.onTitle(t);
    this.persist();
  };

  YexiTimeline.prototype.load = function(id, autoStart, userChosen) {
    var tpl = null;
    for (var i = 0; i < TEMPLATES.length; i++) {
      if (TEMPLATES[i].id === id) { tpl = TEMPLATES[i]; break; }
    }
    if (!tpl) return;
    this.active = true;
    this.templateId = tpl.id;
    this.title = tpl.name + " · 一夜时间线";
    this.segments = [];
    for (var j = 0; j < tpl.segs.length; j++) {
      this.segments.push(cloneSegment(tpl.segs[j]));
    }
    this.elapsedBefore = 0;
    this.startedAt = Date.now();
    this.index = 0;
    this._preloadedForKey = "";
    this.onTitle(this.title);
    this.onResetWork();
    this.persist();
    this.apply(0, true);
    // 只有用户主动点模板才算铺底完成；恢复/默认铺的不替用户打勾
    if (userChosen) this.onTemplate(tpl.id);
    this.onChange(this);
    if (autoStart) this.play();
  };

  YexiTimeline.prototype.loadCustom = function(title, segments, autoStart) {
    if (!Array.isArray(segments) || segments.length === 0) return false;
    this.active = true;
    this.templateId = "";
    this.title = String(title || "我拼的一夜").trim().slice(0, 36) || "我拼的一夜";
    this.segments = [];
    for (var i = 0; i < segments.length && i < MAX_SEGMENTS; i++) {
      this.segments.push(cloneSegment(segments[i], "第 " + (i + 1) + " 段"));
    }
    if (this.segments.length === 0) return false;
    this.elapsedBefore = 0;
    this.startedAt = Date.now();
    this.index = 0;
    this._preloadedForKey = "";
    this.onTitle(this.title);
    this.persist();
    this.apply(0, true);
    this.onChange(this);
    if (autoStart) this.play();
    return true;
  };

  YexiTimeline.prototype.restore = function() {
    var rawState = "";
    try { rawState = localStorage.getItem(STATE_STORAGE_KEY) || ""; } catch (e) {}
    if (rawState) {
      try {
        var parsed = JSON.parse(rawState);
        if (parsed && Array.isArray(parsed.segments) && parsed.segments.length > 0) {
          this.loadCustom(parsed.title || "我拼的一夜", parsed.segments, false);
          if (parsed.templateId) {
            this.templateId = parsed.templateId;
            this.render();
          }
          return true;
        }
      } catch (e) {}
    }
    var saved = "";
    try { saved = localStorage.getItem(LEGACY_STORAGE_KEY) || ""; } catch (e) {}
    if (saved) {
      this.load(saved, false);
      return true;
    }
    this.render();
    return false;
  };

  YexiTimeline.prototype.turnOff = function() {
    this.active = false;
    this.templateId = "";
    this.segments = [];
    this.elapsedBefore = 0;
    this.stopTicker();
    try {
      localStorage.removeItem(LEGACY_STORAGE_KEY);
      localStorage.removeItem(STATE_STORAGE_KEY);
    } catch (e) {}
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
        b.onclick = function() { self.load(tpl.id, false, true); };
        tpls.appendChild(b);
      })(TEMPLATES[t]);
    }

    strip.innerHTML = "";
    if (!this.active || this.segments.length === 0) {
      this.playheadEl = null;
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
        var trTag = idx > 0 ? (seg.transition === "dip" ? " · 渐弱" : (seg.transition === "cut" ? " · 直切" : " · 交叠")) : "";
        du.textContent = seg.minutes + " 分" + trTag;
        el.appendChild(nm);
        el.appendChild(du);

        el.onclick = function() {
          self.jumpToSegment(idx, 0, true);
          self.toast("选中第 " + (idx + 1) + " 段 · " + seg.name);
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
            best = clamp(best, 1, 15);
            if (best !== seg.minutes) {
              seg.minutes = best;
              self.templateId = "";
              self.render();
              self.updateCursor();
            }
          }
          function up() {
            window.removeEventListener("pointermove", move);
            window.removeEventListener("pointerup", up);
            if (seg.minutes !== startM) {
              self.persist();
              self.onEdit(idx, seg.minutes);
              self.onChange(self);
            }
            self.toast("这一段改成 " + seg.minutes + " 分钟");
          }
          window.addEventListener("pointermove", move);
          window.addEventListener("pointerup", up);
        };
        el.appendChild(grip);
        strip.appendChild(el);
      })(i);
    }

    var ph = document.createElement("div");
    ph.className = "tl-playhead";
    this.playheadEl = ph;
    strip.appendChild(ph);

    this.updateCursor();
  };

  global.YexiTimeline = YexiTimeline;
  global.YEXI_TIMELINE_TEMPLATES = TEMPLATES;
  global.YEXI_TIMELINE_STEPS = STEP_MINUTES;
})(window);
