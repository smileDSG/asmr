// 夜息：共享 CC0 声音目录、时段问候语与全屏沉浸氛围引擎
// 仅用朴素 ES5 语法，与 auth_ui.js 保持一致

var YEXI_LAYERS = {
  bed: {
    key: "bed",
    name: "底幕铺底",
    sub: "铺出夜色的基底 · 可自由多选叠加",
    badge: "底幕",
    color: "#9f87f5"
  },
  texture: {
    key: "texture",
    name: "中景纹理",
    sub: "可叠加 · 铺出枝叶、夜风与暖度层次",
    badge: "纹理",
    color: "#5ec4a8"
  },
  accent: {
    key: "accent",
    name: "点缀事件",
    sub: "可设偶发 · 偶尔出现一两声，留出呼吸感",
    badge: "点缀",
    color: "#eab464"
  }
};

var YEXI_SOUNDS = [
  {
    path: "母带_城市夜雨_CC0.mp3",
    name: "城市夜雨",
    desc: "窗外绵柔雨幕与细碎雨声",
    group: "雨声",
    layer: "bed",
    defaultWeight: 0.72,
    defaultPan: 0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "🌧",
    img: "img/rain-window.jpg",
    accent: "#8e74e8",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "CC0 Verified",
    sr: "44.1kHz"
  },
  {
    path: "柔和雨.hq.mp3",
    name: "柔和雨幕",
    desc: "绵密轻柔，像盖着薄毯",
    group: "雨声",
    layer: "bed",
    defaultWeight: 0.72,
    defaultPan: 0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "☁",
    img: "img/warm-bedroom.jpg",
    accent: "#b88ce8",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "CC0 Verified",
    sr: "48kHz"
  },
  {
    path: "乡村小雨.hq.mp3",
    name: "乡村小雨",
    desc: "轻缓疏落的檐下小雨",
    group: "雨声",
    layer: "bed",
    defaultWeight: 0.72,
    defaultPan: 0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "🏡",
    img: "img/moon-water.jpg",
    accent: "#7f8ce0",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "CC0 Verified",
    sr: "48kHz"
  },
  {
    path: "海浪_远海.hq.mp3",
    name: "远海潮汐",
    desc: "一层层从远处推来的浪",
    group: "海浪",
    layer: "bed",
    defaultWeight: 0.72,
    defaultPan: 0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "🌊",
    img: "img/night-lake-stars.jpg",
    accent: "#5889d6",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "717853",
    sr: "48kHz"
  },
  {
    path: "海浪_黑海.hq.mp3",
    name: "深沉黑海",
    desc: "更厚重低沉的夜海潮声",
    group: "海浪",
    layer: "bed",
    defaultWeight: 0.72,
    defaultPan: 0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "🌑",
    img: "img/night-lake-stars.jpg",
    accent: "#4a6fb8",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "427086",
    sr: "44.1kHz"
  },
  {
    path: "溪流.hq.mp3",
    name: "山涧溪流",
    desc: "清亮舒缓的山间流水",
    group: "自然",
    layer: "bed",
    defaultWeight: 0.72,
    defaultPan: 0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "💧",
    img: "img/starry-mountain-lake.jpg",
    accent: "#59a5c7",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "853672",
    sr: "48kHz"
  },
  {
    path: "备选_大雨打树叶_CC0.mp3",
    name: "雨打树叶",
    desc: "细碎雨滴落在枝叶间",
    group: "雨声",
    layer: "texture",
    defaultWeight: 0.38,
    defaultPan: -0.28,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "🍃",
    img: "img/dark-forest-lake.jpg",
    accent: "#5fa896",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "CC0 Verified",
    sr: "48kHz"
  },
  {
    path: "夜风.hq.mp3",
    name: "林间夜风",
    desc: "轻轻拂过树梢的晚风",
    group: "自然",
    layer: "texture",
    defaultWeight: 0.35,
    defaultPan: 0.32,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "🌬",
    img: "img/dark-forest-lake.jpg",
    accent: "#6d94b8",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "455949",
    sr: "44.1kHz"
  },
  {
    path: "雨中低鸣.hq.mp3",
    name: "暖夜低鸣",
    desc: "柔和低频包裹感",
    group: "氛围",
    layer: "texture",
    defaultWeight: 0.32,
    defaultPan: 0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    isMixed: true,
    mixHint: "含柔和细雨底",
    icon: "✨",
    img: "img/warm-bedroom.jpg",
    accent: "#c48ad4",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "876926",
    sr: "48kHz"
  },
  {
    path: "远雷.hq.mp3",
    name: "天际远雷",
    desc: "天际缓缓滚过的低沉雷声",
    group: "氛围",
    layer: "accent",
    defaultWeight: 0.45,
    defaultPan: 0.45,
    defaultMode: "intermittent",
    defaultDensity: 0.35,
    icon: "⛈",
    img: "img/dark-forest-lake.jpg",
    accent: "#7d6bc4",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "717890",
    sr: "48kHz"
  },
  {
    path: "虫鸣.hq.mp3",
    name: "夏夜虫鸣",
    desc: "像小时候外婆家院子的夏夜",
    group: "自然",
    layer: "accent",
    defaultWeight: 0.42,
    defaultPan: -0.38,
    defaultMode: "loop",
    defaultDensity: 0.5,
    icon: "🌙",
    img: "img/moon-water.jpg",
    accent: "#9b85d6",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "704381",
    sr: "44.1kHz"
  }
];

var YEXI_STUDIO_PRESETS = [
  {
    id: "p_attic_rain",
    title: "阁楼夜雨",
    desc: "城市夜雨铺底，暖夜低鸣托住温度，右侧天边偶尔滚过一声低沉远雷",
    tracks: [
      { path: "母带_城市夜雨_CC0.mp3", weight: 0.72, pan: 0, mode: "loop", density: 0.4 },
      { path: "雨中低鸣.hq.mp3", weight: 0.32, pan: 0, mode: "loop", density: 0.4 },
      { path: "远雷.hq.mp3", weight: 0.38, pan: 0.48, mode: "intermittent", density: 0.25 }
    ]
  },
  {
    id: "p_forest_leaves",
    title: "深林雨叶",
    desc: "柔和雨幕打底，左窗边树叶沙沙滴雨，右侧林梢吹过晚风",
    tracks: [
      { path: "柔和雨.hq.mp3", weight: 0.68, pan: 0, mode: "loop", density: 0.4 },
      { path: "备选_大雨打树叶_CC0.mp3", weight: 0.46, pan: -0.34, mode: "loop", density: 0.4 },
      { path: "夜风.hq.mp3", weight: 0.30, pan: 0.36, mode: "loop", density: 0.4 }
    ]
  },
  {
    id: "p_star_ocean",
    title: "星夜远海",
    desc: "远海潮汐从正中铺开，夜风在右侧吹过，一点暖夜低频兜底",
    tracks: [
      { path: "海浪_远海.hq.mp3", weight: 0.75, pan: 0, mode: "loop", density: 0.4 },
      { path: "夜风.hq.mp3", weight: 0.34, pan: 0.38, mode: "loop", density: 0.4 },
      { path: "雨中低鸣.hq.mp3", weight: 0.24, pan: -0.2, mode: "loop", density: 0.4 }
    ]
  },
  {
    id: "p_grandma_yard",
    title: "外婆夏夜",
    desc: "檐下乡村小雨轻落，左前方夏夜虫鸣时起时歇，右林微风轻拂",
    tracks: [
      { path: "乡村小雨.hq.mp3", weight: 0.54, pan: -0.1, mode: "loop", density: 0.4 },
      { path: "虫鸣.hq.mp3", weight: 0.44, pan: -0.44, mode: "intermittent", density: 0.55 },
      { path: "夜风.hq.mp3", weight: 0.30, pan: 0.36, mode: "loop", density: 0.4 }
    ]
  },
  {
    id: "p_stream_wind",
    title: "山溪夜风",
    desc: "清亮山涧溪流在左前流淌，夜风与偶发虫鸣从右林远处传来",
    tracks: [
      { path: "溪流.hq.mp3", weight: 0.72, pan: -0.18, mode: "loop", density: 0.4 },
      { path: "夜风.hq.mp3", weight: 0.36, pan: 0.40, mode: "loop", density: 0.4 },
      { path: "虫鸣.hq.mp3", weight: 0.34, pan: 0.52, mode: "intermittent", density: 0.4 }
    ]
  }
];

function yEncodeMix(recipeObj) {
  try {
    var obj = recipeObj || {};
    var srcTracks = obj.tracks || obj.items || [];
    var compact = [];
    for (var i = 0; i < srcTracks.length; i++) {
      var tr = srcTracks[i];
      if (!tr || !tr.path) continue;
      var base = String(tr.path).split("/").pop().split("\\").pop();
      var w = Math.max(0.05, Math.min(1, parseFloat(tr.weight) || 0.5));
      var pan = Math.max(-1, Math.min(1, parseFloat(tr.pan) || 0));
      var modeShort = tr.mode === "intermittent" ? "i" : "l";
      var den = Math.max(0.1, Math.min(1, parseFloat(tr.density) || 0.4));
      compact.push([
        base,
        Math.round(w * 100) / 100,
        Math.round(pan * 100) / 100,
        modeShort,
        Math.round(den * 100) / 100
      ]);
    }
    var payload = JSON.stringify({
      t: String(obj.title || "").slice(0, 40),
      k: compact
    });
    var b64 = btoa(unescape(encodeURIComponent(payload)));
    return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  } catch (e) {
    return "";
  }
}

function yDecodeMix(encoded) {
  try {
    var raw = String(encoded || "").trim();
    if (!raw) return null;
    raw = raw.replace(/^#/, "");
    if (raw.indexOf("mix=") === 0) {
      raw = raw.slice(4);
    }
    raw = decodeURIComponent(raw);
    var b64 = raw.replace(/-/g, "+").replace(/_/g, "/");
    while (b64.length % 4 !== 0) b64 += "=";
    var jsonStr = decodeURIComponent(escape(atob(b64)));
    var data = JSON.parse(jsonStr);
    if (!data || !data.k || !data.k.length) return null;
    var tracks = [];
    for (var i = 0; i < data.k.length; i++) {
      var row = data.k[i];
      if (!row || !row.length) continue;
      var base = String(row[0] || "").split("/").pop().split("\\").pop();
      if (!base) continue;
      var meta = ySoundMeta(base);
      var w = Math.max(0.05, Math.min(1, parseFloat(row[1]) || meta.defaultWeight || 0.5));
      var pan = Math.max(-1, Math.min(1, isNaN(parseFloat(row[2])) ? (meta.defaultPan || 0) : parseFloat(row[2])));
      var mode = row[3] === "i" ? "intermittent" : "loop";
      var den = Math.max(0.1, Math.min(1, parseFloat(row[4]) || meta.defaultDensity || 0.4));
      tracks.push({
        path: base,
        weight: w,
        pan: pan,
        mode: mode,
        density: den
      });
    }
    if (tracks.length === 0) return null;
    return {
      title: String(data.t || "").slice(0, 40),
      tracks: tracks
    };
  } catch (e) {
    return null;
  }
}

function ySoundMeta(filename) {
  var raw = String(filename || "");
  var base = raw.split("/").pop().split("\\").pop();
  for (var i = 0; i < YEXI_SOUNDS.length; i++) {
    if (YEXI_SOUNDS[i].path === base) {
      return YEXI_SOUNDS[i];
    }
  }
  var clean = base
    .replace(/\.(mp3|wav|ogg)$/i, "")
    .replace(/\.hq$/i, "")
    .replace(/^(母带_|备选_)/, "")
    .replace(/_CC0$/i, "");
  return {
    path: base,
    name: clean || "自然声景",
    desc: "真实自然录音",
    group: "自然",
    layer: "texture",
    defaultWeight: 0.4,
    defaultPan: 0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "☾",
    img: "img/moon-water.jpg",
    accent: "#8e74e8",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "CC0 Verified",
    sr: "48kHz"
  };
}

function yTimeGreeting() {
  var h = new Date().getHours();
  if (h >= 0 && h < 6) {
    return {
      title: "凌晨了，把思绪交给窗外",
      sub: "挑一段稳一点、暖一点的真实夜色陪你入睡"
    };
  }
  if (h >= 6 && h < 12) {
    return {
      title: "早安，借一段自然声静心",
      sub: "不抢耳、不打扰，帮白天的思绪慢慢落定"
    };
  }
  if (h >= 12 && h < 18) {
    return {
      title: "午后放空，听点安静的",
      sub: "小憩或专注时，选一段自然声裹住耳朵"
    };
  }
  if (h >= 18 && h < 22) {
    return {
      title: "夜幕降临，慢慢收尾",
      sub: "卸下一天的嘈杂，说一句想听的夜色"
    };
  }
  return {
    title: "今晚，听什么？",
    sub: "说一句想要的夜色，或直接用自然声调出你的专属角落"
  };
}

var _ambientState = {
  inited: false,
  bgA: null,
  bgB: null,
  activeSlot: "A",
  currentImg: "",
  accentHex: "#8e74e8",
  accentRgb: "142, 116, 232",
  playing: false,
  canvas: null,
  ctx: null,
  particles: [],
  rafId: null,
  reducedMotion: false
};

function _yHexToRgb(hex) {
  var s = String(hex || "").replace("#", "");
  if (s.length === 3) {
    s = s.charAt(0) + s.charAt(0) + s.charAt(1) + s.charAt(1) + s.charAt(2) + s.charAt(2);
  }
  if (s.length !== 6) return "142, 116, 232";
  var r = parseInt(s.slice(0, 2), 16);
  var g = parseInt(s.slice(2, 4), 16);
  var b = parseInt(s.slice(4, 6), 16);
  if (isNaN(r) || isNaN(g) || isNaN(b)) return "142, 116, 232";
  return r + ", " + g + ", " + b;
}

function initAmbientStage(initialImg, initialAccent) {
  if (_ambientState.inited) {
    if (initialImg || initialAccent) {
      ySetAmbient(initialImg || _ambientState.currentImg, initialAccent || _ambientState.accentHex, _ambientState.playing);
    }
    return;
  }
  _ambientState.inited = true;

  var stage = document.getElementById("ambientStage");
  if (!stage) {
    stage = document.createElement("div");
    stage.id = "ambientStage";
    stage.className = "ambient-stage";
    document.body.insertBefore(stage, document.body.firstChild);
  }
  stage.innerHTML =
    '<div class="ambient-bg is-active" id="ambientBgA"></div>' +
    '<div class="ambient-bg" id="ambientBgB"></div>' +
    '<div class="ambient-glow"></div>' +
    '<canvas class="ambient-canvas" id="ambientCanvas"></canvas>' +
    '<div class="ambient-vignette"></div>';

  _ambientState.bgA = document.getElementById("ambientBgA");
  _ambientState.bgB = document.getElementById("ambientBgB");
  _ambientState.canvas = document.getElementById("ambientCanvas");
  _ambientState.ctx = _ambientState.canvas ? _ambientState.canvas.getContext("2d") : null;

  var mq = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  _ambientState.reducedMotion = mq ? mq.matches : false;
  if (mq && mq.addEventListener) {
    mq.addEventListener("change", function(e) {
      _ambientState.reducedMotion = e.matches;
      if (_ambientState.reducedMotion && _ambientState.rafId) {
        cancelAnimationFrame(_ambientState.rafId);
        _ambientState.rafId = null;
        _drawAmbientFrame(true);
      } else if (!_ambientState.reducedMotion && !_ambientState.rafId) {
        _tickAmbient();
      }
    });
  }

  _initParticles();
  window.addEventListener("resize", _resizeAmbientCanvas);
  _resizeAmbientCanvas();

  ySetAmbient(initialImg || "img/moon-water.jpg", initialAccent || "#8e74e8", false);

  if (_ambientState.reducedMotion) {
    _drawAmbientFrame(true);
  } else {
    _tickAmbient();
  }
}

function ySetAmbient(imgUrl, accentHex, isPlaying) {
  if (!_ambientState.inited) initAmbientStage();
  if (accentHex) {
    _ambientState.accentHex = accentHex;
    _ambientState.accentRgb = _yHexToRgb(accentHex);
    document.documentElement.style.setProperty("--y-accent", accentHex);
    document.documentElement.style.setProperty("--y-accent-rgb", _ambientState.accentRgb);
  }
  if (typeof isPlaying === "boolean") {
    _ambientState.playing = isPlaying;
    document.body.classList.toggle("is-playing", isPlaying);
  }
  if (imgUrl && imgUrl !== _ambientState.currentImg) {
    _ambientState.currentImg = imgUrl;
    var nextSlot = _ambientState.activeSlot === "A" ? "B" : "A";
    var incoming = nextSlot === "A" ? _ambientState.bgA : _ambientState.bgB;
    var outgoing = _ambientState.activeSlot === "A" ? _ambientState.bgA : _ambientState.bgB;
    if (incoming && outgoing) {
      incoming.style.backgroundImage = "url(" + imgUrl + ")";
      incoming.classList.add("is-active");
      outgoing.classList.remove("is-active");
      _ambientState.activeSlot = nextSlot;
    }
  }
}

function _resizeAmbientCanvas() {
  var c = _ambientState.canvas;
  if (!c) return;
  var dpr = Math.min(window.devicePixelRatio || 1, 2);
  c.width = Math.floor(window.innerWidth * dpr);
  c.height = Math.floor(window.innerHeight * dpr);
  if (_ambientState.ctx) {
    _ambientState.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  if (_ambientState.reducedMotion) {
    _drawAmbientFrame(true);
  }
}

function _initParticles() {
  var list = [];
  var count = 34;
  for (var i = 0; i < count; i++) {
    list.push({
      x: Math.random(),
      y: Math.random(),
      r: 0.7 + Math.random() * 1.8,
      vx: (Math.random() - 0.5) * 0.00018,
      vy: -0.00008 - Math.random() * 0.00022,
      alpha: 0.14 + Math.random() * 0.36,
      phase: Math.random() * Math.PI * 2
    });
  }
  _ambientState.particles = list;
}

function _drawAmbientFrame(freeze) {
  var ctx = _ambientState.ctx;
  var c = _ambientState.canvas;
  if (!ctx || !c) return;
  var w = window.innerWidth;
  var h = window.innerHeight;
  ctx.clearRect(0, 0, w, h);

  var now = Date.now() * 0.0007;
  var speedMul = _ambientState.playing ? 1.45 : 0.85;
  var alphaMul = _ambientState.playing ? 1.15 : 0.75;
  var rgb = _ambientState.accentRgb;

  for (var i = 0; i < _ambientState.particles.length; i++) {
    var p = _ambientState.particles[i];
    if (!freeze) {
      p.x += p.vx * speedMul;
      p.y += p.vy * speedMul;
      if (p.y < -0.05) p.y = 1.05;
      if (p.x < -0.05) p.x = 1.05;
      if (p.x > 1.05) p.x = -0.05;
    }
    var twinkle = freeze ? 1 : (0.65 + 0.35 * Math.sin(now + p.phase));
    var a = Math.min(0.65, p.alpha * twinkle * alphaMul);
    ctx.beginPath();
    ctx.arc(p.x * w, p.y * h, p.r, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(" + rgb + ", " + a.toFixed(3) + ")";
    ctx.fill();
  }
}

function _tickAmbient() {
  if (_ambientState.reducedMotion) {
    _ambientState.rafId = null;
    return;
  }
  _drawAmbientFrame(false);
  _ambientState.rafId = requestAnimationFrame(_tickAmbient);
}

function _yHtmlEsc(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function _ySafeFilename(name) {
  return String(name || "夜息声音明信片")
    .replace(/[\\/:*?"<>|]/g, "_")
    .replace(/\s+/g, "_")
    .slice(0, 48) || "夜息";
}

function _yPanShort(pan) {
  var p = parseFloat(pan) || 0;
  var pct = Math.round(Math.abs(p) * 100);
  if (pct < 5) return "正中";
  return (p < 0 ? "左 " : "右 ") + pct + "%";
}

function _yDrawWrappedText(ctx, text, x, y, maxWidth, lineHeight, maxLines) {
  var chars = String(text || "").split("");
  var line = "";
  var lines = [];
  for (var i = 0; i < chars.length; i++) {
    var test = line + chars[i];
    if (ctx.measureText(test).width > maxWidth && line.length > 0) {
      lines.push(line);
      line = chars[i];
      if (maxLines && lines.length >= maxLines) break;
    } else {
      line = test;
    }
  }
  if (line && (!maxLines || lines.length < maxLines)) {
    lines.push(line);
  }
  for (var j = 0; j < lines.length; j++) {
    ctx.fillText(lines[j], x, y + j * lineHeight);
  }
  return y + lines.length * lineHeight;
}

function _yRoundRect(ctx, x, y, w, h, r) {
  var rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

function yRenderPostcardPng(opts, doneCb) {
  var cfg = opts || {};
  var list = (cfg.tracks || cfg.items || []).slice(0, 5);
  var title = String(cfg.title || "夜息声景").trim() || "夜息声景";
  var author = String(cfg.author || "夜息").trim() || "夜息";
  var story = String(cfg.story || cfg.desc || "").trim();
  var remixOf = cfg.remix_of || null;

  var leadMeta = list.length > 0 ? ySoundMeta(list[0].path) : ySoundMeta("");
  var imgUrl = cfg.img || leadMeta.img || "img/moon-water.jpg";
  var accentRgb = _yHexToRgb(cfg.accent || leadMeta.accent || "#8e74e8");

  var paintCard = function(bgImg) {
    var W = 720;
    var H = 960;
    var canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    var ctx = canvas.getContext("2d");

    ctx.fillStyle = "#0b0814";
    ctx.fillRect(0, 0, W, H);

    // 上半部分自然夜景底图
    var photoH = 420;
    if (bgImg) {
      var scale = Math.max(W / bgImg.width, photoH / bgImg.height);
      var dw = bgImg.width * scale;
      var dh = bgImg.height * scale;
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, 0, W, photoH);
      ctx.clip();
      ctx.globalAlpha = 0.72;
      ctx.drawImage(bgImg, (W - dw) / 2, (photoH - dh) / 2, dw, dh);
      ctx.restore();
    }

    var grad = ctx.createLinearGradient(0, 0, 0, photoH + 40);
    grad.addColorStop(0, "rgba(11, 8, 20, 0.35)");
    grad.addColorStop(0.6, "rgba(11, 8, 20, 0.55)");
    grad.addColorStop(1, "#0b0814");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, photoH + 40);

    var glow = ctx.createRadialGradient(W * 0.5, 195, 12, W * 0.5, 195, 290);
    glow.addColorStop(0, "rgba(" + accentRgb + ", 0.34)");
    glow.addColorStop(1, "rgba(" + accentRgb + ", 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, W, 520);

    // 顶部品牌角标
    ctx.fillStyle = "rgba(255, 255, 255, 0.72)";
    ctx.font = '500 20px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText("☾ 夜息 · 深夜声音明信片", 52, 66);

    // 月亮圆徽
    var moonGrad = ctx.createRadialGradient(344, 178, 8, 360, 195, 58);
    moonGrad.addColorStop(0, "#f5eeff");
    moonGrad.addColorStop(0.6, "rgba(" + accentRgb + ", 0.85)");
    moonGrad.addColorStop(1, "rgba(56, 38, 108, 0.92)");
    ctx.beginPath();
    ctx.arc(360, 195, 54, 0, Math.PI * 2);
    ctx.fillStyle = moonGrad;
    ctx.fill();
    ctx.fillStyle = "#1d1034";
    ctx.font = '600 40px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.textAlign = "center";
    ctx.fillText("☾", 360, 210);
    ctx.textAlign = "left";

    // 标题与故事
    ctx.fillStyle = "#ffffff";
    ctx.font = '600 40px "PingFang SC", "Microsoft YaHei", sans-serif';
    var nextY = _yDrawWrappedText(ctx, title, 52, 345, W - 104, 52, 2);

    if (remixOf && remixOf.title) {
      ctx.fillStyle = "rgba(225, 210, 255, 0.85)";
      ctx.font = '400 20px "PingFang SC", "Microsoft YaHei", sans-serif';
      nextY += 6;
      ctx.fillText("↻ 改编自 @" + (remixOf.author || "夜息") + " · 《" + remixOf.title + "》", 52, nextY);
      nextY += 30;
    }

    if (story) {
      ctx.fillStyle = "#c8bddf";
      ctx.font = '400 23px "PingFang SC", "Microsoft YaHei", sans-serif';
      nextY = _yDrawWrappedText(ctx, story, 52, nextY + 12, W - 104, 34, 3);
    }

    // 声层数值比例条卡片
    var boxY = Math.max(nextY + 28, 495);
    var boxH = Math.min(320, 68 + list.length * 50);
    _yRoundRect(ctx, 48, boxY, W - 96, boxH, 24);
    ctx.fillStyle = "rgba(255, 255, 255, 0.045)";
    ctx.fill();
    ctx.strokeStyle = "rgba(218, 200, 255, 0.16)";
    ctx.lineWidth = 1.5;
    ctx.stroke();

    ctx.fillStyle = "#a99dc5";
    ctx.font = '500 18px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText("真实 CC0 声层配比", 76, boxY + 38);

    for (var i = 0; i < list.length; i++) {
      var tr = list[i];
      var m = ySoundMeta(tr.path);
      var rowY = boxY + 72 + i * 48;
      var pct = Math.round((parseFloat(tr.weight) || 0) * 100);
      var infoText = m.icon + " " + m.name + " · " + pct + "% · " + _yPanShort(tr.pan) +
        (tr.mode === "intermittent" ? (" · 偶发 " + Math.round((tr.density || 0.4) * 100) + "%") : "");

      ctx.fillStyle = "#efe5ff";
      ctx.font = '500 19px "PingFang SC", "Microsoft YaHei", sans-serif';
      ctx.fillText(infoText, 76, rowY);

      var barX = 76;
      var barY = rowY + 10;
      var barW = W - 152;
      _yRoundRect(ctx, barX, barY, barW, 8, 4);
      ctx.fillStyle = "rgba(255, 255, 255, 0.08)";
      ctx.fill();

      var fillW = Math.max(12, Math.round(barW * Math.min(1, parseFloat(tr.weight) || 0)));
      _yRoundRect(ctx, barX, barY, fillW, 8, 4);
      ctx.fillStyle = "rgba(" + accentRgb + ", 0.85)";
      ctx.fill();
    }

    // 底部署名与 CC0 声明
    ctx.fillStyle = "#9d90b8";
    ctx.font = '400 20px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText("调音人：@" + author, 52, H - 78);
    ctx.fillStyle = "#7c7098";
    ctx.font = '400 17px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText("夜息 · 真实 CC0 自然录音 · 零音质篡改", 52, H - 44);

    var fileName = _ySafeFilename(title) + "_声音明信片.png";
    var triggerDownload = function(url) {
      var a = document.createElement("a");
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      if (typeof doneCb === "function") doneCb(true);
    };

    if (canvas.toBlob) {
      canvas.toBlob(function(blob) {
        if (!blob) {
          triggerDownload(canvas.toDataURL("image/png"));
          return;
        }
        var u = URL.createObjectURL(blob);
        triggerDownload(u);
        setTimeout(function() { URL.revokeObjectURL(u); }, 2500);
      }, "image/png");
    } else {
      triggerDownload(canvas.toDataURL("image/png"));
    }
  };

  var img = new Image();
  img.onload = function() { paintCard(img); };
  img.onerror = function() { paintCard(null); };
  img.src = imgUrl;
}

function yBuildCommercialCertHtml(opts) {
  var cfg = opts || {};
  var certId = cfg.certId || ("YX-CC0-" + new Date().toISOString().slice(0, 10).replace(/-/g, ""));
  var title = cfg.title || "夜息自然声景";
  var author = cfg.author || "夜息创作者";
  var seconds = parseInt(cfg.seconds, 10) || 30;
  var createdAt = cfg.createdAt || new Date().toLocaleString("zh-CN");
  var list = cfg.tracks || cfg.items || [];

  var rows = "";
  for (var i = 0; i < list.length; i++) {
    var tr = list[i];
    var m = ySoundMeta(tr.path);
    var pct = Math.round((parseFloat(tr.weight) || 0) * 100) + "%";
    var panStr = _yPanShort(tr.pan);
    var modeStr = tr.mode === "intermittent" ? ("偶发 " + Math.round((tr.density || 0.4) * 100) + "%") : "持续循环";
    rows +=
      "<tr>" +
        "<td>" + (i + 1) + "</td>" +
        "<td>" + _yHtmlEsc(m.name) + "</td>" +
        "<td>" + _yHtmlEsc(pct + " · " + panStr + " · " + modeStr) + "</td>" +
        "<td>" + _yHtmlEsc(m.sr || "48kHz") + "</td>" +
        "<td>" + _yHtmlEsc((m.source || "Freesound") + " #" + (m.freesoundId || "CC0")) + "</td>" +
        "<td>" + _yHtmlEsc(m.license || "CC0 1.0 Public Domain") + "</td>" +
      "</tr>";
  }

  return "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"UTF-8\">\n" +
    "<title>夜息 · CC0 商用音频素材溯源凭证 (" + _yHtmlEsc(certId) + ")</title>\n" +
    "<style>" +
    "body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;background:#f7f6fb;color:#1d1630;margin:0;padding:32px 18px;line-height:1.65}" +
    ".sheet{max-width:820px;margin:0 auto;background:#fff;border:1px solid #dfd8f0;border-radius:16px;padding:34px 36px;box-shadow:0 12px 36px rgba(32,20,64,.08)}" +
    ".head{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #ece6f8;padding-bottom:18px;margin-bottom:20px;gap:12px;flex-wrap:wrap}" +
    "h1{margin:0;font-size:22px;color:#271847}" +
    ".sub{font-size:13px;color:#685b85;margin-top:4px}" +
    ".badge{background:#efe8ff;color:#4a2b91;border:1px solid #d4c3f8;border-radius:999px;padding:5px 14px;font-size:12px;font-weight:600}" +
    ".meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px 18px;background:#faf8ff;border:1px solid #ece6f8;border-radius:12px;padding:14px 16px;margin-bottom:22px;font-size:13px}" +
    ".meta b{color:#35245c}" +
    "table{width:100%;border-collapse:collapse;font-size:13px;margin-bottom:22px}" +
    "th,td{border:1px solid #e6e0f3;padding:10px 11px;text-align:left}" +
    "th{background:#f4effd;color:#35245c;font-weight:600}" +
    ".notice{background:#f7f5fc;border-left:4px solid #7d5fc4;padding:13px 16px;border-radius:6px;font-size:13px;color:#443860}" +
    ".actions{margin-top:20px;text-align:right}" +
    ".btn{background:#5a3fa0;color:#fff;border:none;border-radius:8px;padding:9px 18px;font-size:13px;cursor:pointer}" +
    "@media print{.actions{display:none}body{background:#fff;padding:0}.sheet{box-shadow:none;border:none}}" +
    "</style>\n</head>\n<body>\n<div class=\"sheet\">\n" +
    "<div class=\"head\"><div><h1>☾ 夜息 · CC0 商用音频素材溯源凭证</h1>" +
    "<div class=\"sub\">用于短视频、播客、冥想课程、独立游戏及线下商业空间播放的素材权利说明</div></div>" +
    "<div class=\"badge\">CC0 1.0 · 可商用免署名</div></div>\n" +
    "<div class=\"meta\">" +
    "<div><b>凭证编号：</b>" + _yHtmlEsc(certId) + "</div>" +
    "<div><b>作品名称：</b>" + _yHtmlEsc(title) + "</div>" +
    "<div><b>导出账号/作者：</b>" + _yHtmlEsc(author) + "</div>" +
    "<div><b>音频规格：</b>" + _yHtmlEsc(seconds + " 秒 · 44.1kHz 16-bit 立体声 WAV") + "</div>" +
    "<div><b>生成时间：</b>" + _yHtmlEsc(createdAt) + "</div>" +
    "<div><b>处理方式：</b>零音质篡改（仅声量/声像/自然拼接）</div>" +
    "</div>\n" +
    "<table><thead><tr><th>#</th><th>声层素材</th><th>导出参数</th><th>母带采样率</th><th>原始来源编号</th><th>开源授权协议</th></tr></thead><tbody>" +
    rows +
    "</tbody></table>\n" +
    "<div class=\"notice\"><b>权利声明：</b>本导出音频所含全部原始声层均来自 Freesound 公有领域 CC0（Creative Commons Zero 1.0 Universal）授权录音，夜息平台已对其进行来源留档，未掺杂受版权保护的旋律、人声或第三方商用付费音频，可合法用于商业内容配乐与商业场所环境音播放。</div>\n" +
    "<div class=\"actions\"><button class=\"btn\" onclick=\"window.print()\">打印 / 保存为 PDF</button></div>\n" +
    "</div>\n</body>\n</html>";
}

function yRenderEarReportPng(profile, doneCb) {
  var p = profile || {};
  var list = (p.tracks || []).slice(0, 4);
  var leadMeta = list.length > 0 ? ySoundMeta(list[0].path) : ySoundMeta("");
  var imgUrl = p.img || leadMeta.img || "img/moon-water.jpg";
  var accentRgb = _yHexToRgb(p.accent || leadMeta.accent || "#8e74e8");
  var archName = String(p.archetype_name || "夜息聆听者").trim();
  var icon = String(p.icon || "☾").trim();
  var tagline = String(p.tagline || "在夜色里偏爱稳与暖的声音").trim();
  var scores = p.scores || {};

  var DIMS = [
    { key: "warmth", label: "暖厚包裹" },
    { key: "crisp", label: "清脆颗粒" },
    { key: "space", label: "空间开阔" },
    { key: "nature", label: "自然生机" }
  ];

  var paint = function(bgImg) {
    var W = 720;
    var H = 960;
    var canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    var ctx = canvas.getContext("2d");

    ctx.fillStyle = "#0b0814";
    ctx.fillRect(0, 0, W, H);

    var photoH = 380;
    if (bgImg) {
      var scale = Math.max(W / bgImg.width, photoH / bgImg.height);
      var dw = bgImg.width * scale;
      var dh = bgImg.height * scale;
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, 0, W, photoH);
      ctx.clip();
      ctx.globalAlpha = 0.68;
      ctx.drawImage(bgImg, (W - dw) / 2, (photoH - dh) / 2, dw, dh);
      ctx.restore();
    }

    var grad = ctx.createLinearGradient(0, 0, 0, photoH + 50);
    grad.addColorStop(0, "rgba(11, 8, 20, 0.38)");
    grad.addColorStop(0.55, "rgba(11, 8, 20, 0.62)");
    grad.addColorStop(1, "#0b0814");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, photoH + 50);

    var glow = ctx.createRadialGradient(W * 0.5, 190, 12, W * 0.5, 190, 310);
    glow.addColorStop(0, "rgba(" + accentRgb + ", 0.36)");
    glow.addColorStop(1, "rgba(" + accentRgb + ", 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, W, 500);

    ctx.fillStyle = "rgba(255, 255, 255, 0.76)";
    ctx.font = '500 20px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText("☾ 夜息 · 30秒耳朵人格报告", 52, 64);

    // 居中月亮圆徽
    var moonGrad = ctx.createRadialGradient(344, 166, 10, 360, 184, 62);
    moonGrad.addColorStop(0, "#f7f1ff");
    moonGrad.addColorStop(0.6, "rgba(" + accentRgb + ", 0.88)");
    moonGrad.addColorStop(1, "rgba(52, 34, 102, 0.94)");
    ctx.beginPath();
    ctx.arc(360, 184, 58, 0, Math.PI * 2);
    ctx.fillStyle = moonGrad;
    ctx.fill();

    ctx.textAlign = "center";
    ctx.fillStyle = "#1a0f30";
    ctx.font = '600 42px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText(icon, 360, 199);

    ctx.fillStyle = "#ffffff";
    ctx.font = '600 42px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText(archName, 360, 304);

    ctx.fillStyle = "#cfc3e6";
    ctx.font = '400 22px "PingFang SC", "Microsoft YaHei", sans-serif';
    _yDrawWrappedText(ctx, tagline, 360, 348, W - 120, 32, 2);
    ctx.textAlign = "left";

    // 四维偏好数值卡
    var cardY = 428;
    var cardH = 314;
    _yRoundRect(ctx, 48, cardY, W - 96, cardH, 24);
    ctx.fillStyle = "rgba(255, 255, 255, 0.045)";
    ctx.fill();
    ctx.strokeStyle = "rgba(218, 200, 255, 0.16)";
    ctx.lineWidth = 1.5;
    ctx.stroke();

    ctx.fillStyle = "#a99dc5";
    ctx.font = '500 18px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText("四维听感倾向", 76, cardY + 38);

    for (var i = 0; i < DIMS.length; i++) {
      var dm = DIMS[i];
      var val = Math.max(0, Math.min(100, parseInt(scores[dm.key], 10) || 50));
      var rowY = cardY + 80 + i * 58;

      ctx.fillStyle = "#efe5ff";
      ctx.font = '500 20px "PingFang SC", "Microsoft YaHei", sans-serif';
      ctx.fillText(dm.label, 76, rowY);

      ctx.textAlign = "right";
      ctx.fillStyle = "#dfd1ff";
      ctx.fillText(val + "%", W - 76, rowY);
      ctx.textAlign = "left";

      var barX = 76;
      var barY = rowY + 12;
      var barW = W - 152;
      _yRoundRect(ctx, barX, barY, barW, 10, 5);
      ctx.fillStyle = "rgba(255, 255, 255, 0.08)";
      ctx.fill();

      var fillW = Math.max(14, Math.round((barW * val) / 100));
      _yRoundRect(ctx, barX, barY, fillW, 10, 5);
      ctx.fillStyle = "rgba(" + accentRgb + ", 0.88)";
      ctx.fill();
    }

    // 专属配方一行摘要
    var rParts = [];
    for (var j = 0; j < list.length; j++) {
      var m = ySoundMeta(list[j].path);
      rParts.push(m.name + " " + Math.round((parseFloat(list[j].weight) || 0) * 100) + "%");
    }
    _yRoundRect(ctx, 48, 764, W - 96, 86, 20);
    ctx.fillStyle = "rgba(" + accentRgb + ", 0.12)";
    ctx.fill();
    ctx.strokeStyle = "rgba(" + accentRgb + ", 0.34)";
    ctx.stroke();

    ctx.fillStyle = "#cbb8f5";
    ctx.font = '500 17px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText("专属起眠声景配方", 76, 796);
    ctx.fillStyle = "#ffffff";
    ctx.font = '500 20px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText(rParts.join(" · ") || "城市夜雨 65% · 柔和雨幕 35%", 76, 829);

    ctx.fillStyle = "#7c7098";
    ctx.font = '400 17px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText("夜息 · 真实 CC0 自然录音 · 零音质篡改", 52, H - 46);

    var fileName = _ySafeFilename(archName) + "_耳朵人格报告.png";
    var triggerDownload = function(url) {
      var a = document.createElement("a");
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      if (typeof doneCb === "function") doneCb(true);
    };

    if (canvas.toBlob) {
      canvas.toBlob(function(blob) {
        if (!blob) {
          triggerDownload(canvas.toDataURL("image/png"));
          return;
        }
        var u = URL.createObjectURL(blob);
        triggerDownload(u);
        setTimeout(function() { URL.revokeObjectURL(u); }, 2500);
      }, "image/png");
    } else {
      triggerDownload(canvas.toDataURL("image/png"));
    }
  };

  var img = new Image();
  img.onload = function() { paint(img); };
  img.onerror = function() { paint(null); };
  img.src = imgUrl;
}
