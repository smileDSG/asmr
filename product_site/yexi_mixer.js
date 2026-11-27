// 夜息 · Web Audio 分层声景混音引擎（纯 ES5，严格零音质处理）
// 铁律：只使用 AudioBufferSourceNode / GainNode / StereoPannerNode，不做任何滤波/EQ/混响/压缩/降噪

(function(global) {
  function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
  }

  // 预生成 64 点等功率余弦曲线与 S 型偶发包络曲线
  function makeCurve(len, fn) {
    var arr = new Float32Array(len);
    for (var i = 0; i < len; i++) {
      arr[i] = fn(i / (len - 1));
    }
    return arr;
  }

  var SIN_IN = makeCurve(64, function(t) { return Math.sin(t * Math.PI * 0.5); });
  var COS_OUT = makeCurve(64, function(t) { return Math.cos(t * Math.PI * 0.5); });
  var HANN_IN = makeCurve(64, function(t) { return 0.5 * (1 - Math.cos(t * Math.PI)); });
  var HANN_OUT = makeCurve(64, function(t) { return 0.5 * (1 + Math.cos(t * Math.PI)); });

  function analyzeAudioBuffer(buffer) {
    var sr = buffer.sampleRate || 44100;
    var nCh = buffer.numberOfChannels || 1;
    var ch0 = buffer.getChannelData(0);
    var ch1 = nCh > 1 ? buffer.getChannelData(1) : ch0;
    var len = buffer.length;

    // 0.25s 分块测有效 RMS，忽略极静音块，对齐到柔和睡前基准 (-32 dBFS / 0.025) 并保护峰值不削波
    var block = Math.max(1, Math.floor(sr * 0.25));
    var activeRms = [];
    var sumSqAll = 0;
    var countAll = 0;
    var peak = 0;
    for (var p = 0; p < len; p += 4) {
      var pa = Math.abs(ch0[p]);
      var pb = Math.abs(ch1[p]);
      if (pa > peak) peak = pa;
      if (pb > peak) peak = pb;
      sumSqAll += (pa * pa + pb * pb) * 0.5;
      countAll += 1;
    }
    for (var i = 0; i + block <= len; i += block) {
      var sumSq = 0;
      for (var j = 0; j < block; j += 4) {
        var a = ch0[i + j];
        var b = ch1[i + j];
        sumSq += (a * a + b * b) * 0.5;
      }
      var samplesCount = Math.ceil(block / 4);
      var rms = Math.sqrt(sumSq / Math.max(1, samplesCount));
      if (rms >= 0.0002) {
        activeRms.push(rms);
      }
    }

    var calGain = 1.0;
    var med = countAll > 0 ? Math.sqrt(sumSqAll / countAll) : 0;
    if (activeRms.length > 0) {
      activeRms.sort(function(x, y) { return x - y; });
      med = activeRms[Math.floor(activeRms.length * 0.5)];
    }
    if (med > 1e-6) {
      calGain = clamp(0.025 / med, 0.20, 20.0);
      if (peak > 1e-6 && peak * calGain > 0.85) {
        calGain = Math.max(0.20, 0.85 / peak);
      }
    }

    // 2s 切片记录有声音的起播秒数，供偶发调度挑选有效段落
    var bucketFrames = Math.max(1, Math.floor(sr * 2.0));
    var bucketList = [];
    var bucketRmsList = [];
    for (var s = 0; s + bucketFrames <= len; s += bucketFrames) {
      var bSum = 0;
      for (var k = 0; k < bucketFrames; k += 8) {
        var va = ch0[s + k];
        var vb = ch1[s + k];
        bSum += (va * va + vb * vb) * 0.5;
      }
      var bCount = Math.ceil(bucketFrames / 8);
      var bRms = Math.sqrt(bSum / Math.max(1, bCount));
      bucketList.push({ sec: s / sr, rms: bRms });
      bucketRmsList.push(bRms);
    }

    var activeBuckets = [];
    if (bucketList.length > 0) {
      bucketRmsList.sort(function(x, y) { return x - y; });
      var bMed = bucketRmsList[Math.floor(bucketRmsList.length * 0.5)];
      var threshold = Math.max(0.002, bMed * 0.65);
      for (var bi = 0; bi < bucketList.length; bi++) {
        if (bucketList[bi].rms >= threshold) {
          activeBuckets.push(bucketList[bi].sec);
        }
      }
    }
    if (activeBuckets.length === 0) {
      activeBuckets.push(0);
    }

    // 若音频开头明显静音/极轻（例如麦套轻扫前5秒、深夜翻书前4秒），记录首个有效发声秒数，首轮循环直接跳过静音段
    var firstActiveSec = 0;
    if (bucketList.length > 2 && activeBuckets.length > 0 && activeBuckets[0] > 0) {
      var startRms = bucketList[0].rms;
      if (startRms < Math.max(0.0025, bMed * 0.45)) {
        var maxSkip = Math.max(0, (len / sr) - 4.0);
        firstActiveSec = Math.min(activeBuckets[0], maxSkip);
      }
    }

    return {
      buffer: buffer,
      calGain: calGain,
      activeBuckets: activeBuckets,
      firstActiveSec: firstActiveSec
    };
  }

  function gapRangeForDensity(density) {
    var d = clamp(parseFloat(density) || 0.4, 0.1, 1.0);
    var minGap, maxGap, u;
    if (d <= 0.5) {
      u = clamp((0.5 - d) / 0.4, 0, 1);
      minGap = 7 + u * 9;
      maxGap = 14 + u * 14;
    } else {
      u = clamp((d - 0.5) / 0.4, 0, 1);
      minGap = 7 - u * 5;
      maxGap = 14 - u * 8;
    }
    return { min: minGap, max: maxGap };
  }

  function audioBufferToWavBlob(buffer) {
    var numCh = buffer.numberOfChannels;
    var len = buffer.length;
    var sampleRate = buffer.sampleRate;
    var channels = [];
    var c, i;
    for (c = 0; c < numCh; c++) {
      channels.push(buffer.getChannelData(c));
    }

    // 仅在峰值超过 0.95 时做全局等比防削波保护（零音色处理）
    var peak = 0;
    for (c = 0; c < numCh; c++) {
      var chData = channels[c];
      for (i = 0; i < len; i++) {
        var absV = Math.abs(chData[i]);
        if (absV > peak) peak = absV;
      }
    }
    var scale = peak > 0.95 ? (0.95 / peak) : 1.0;

    var bytesPerSample = 2;
    var dataSize = len * numCh * bytesPerSample;
    var ab = new ArrayBuffer(44 + dataSize);
    var view = new DataView(ab);

    function writeStr(offset, s) {
      for (var idx = 0; idx < s.length; idx++) {
        view.setUint8(offset + idx, s.charCodeAt(idx));
      }
    }

    writeStr(0, "RIFF");
    view.setUint32(4, 36 + dataSize, true);
    writeStr(8, "WAVE");
    writeStr(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, numCh, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * numCh * bytesPerSample, true);
    view.setUint16(32, numCh * bytesPerSample, true);
    view.setUint16(34, 16, true);
    writeStr(36, "data");
    view.setUint32(40, dataSize, true);

    var off = 44;
    for (i = 0; i < len; i++) {
      for (c = 0; c < numCh; c++) {
        var v = clamp(channels[c][i] * scale, -1, 1);
        view.setInt16(off, v < 0 ? v * 0x8000 : v * 0x7FFF, true);
        off += 2;
      }
    }
    return new Blob([ab], { type: "audio/wav" });
  }

  function YexiMixer(options) {
    var opts = options || {};
    this.apiBase = opts.apiBase || "";
    this.onPulse = typeof opts.onPulse === "function" ? opts.onPulse : function() {};
    this.onLoadState = typeof opts.onLoadState === "function" ? opts.onLoadState : function() {};
    this.onError = typeof opts.onError === "function" ? opts.onError : function() {};

    this.ctx = null;
    this.masterGain = null;
    this.analyser = null;
    this.buffers = {};
    this.loadingPromises = {};
    this.channels = {};
    this.currentTracks = [];
    this.isPlaying = false;
    this.masterVolume = 0.85;
  }

  YexiMixer.isSupported = function() {
    return !!(global.AudioContext || global.webkitAudioContext);
  };

  YexiMixer.prototype._ensureContext = function() {
    if (!this.ctx) {
      var Ctx = global.AudioContext || global.webkitAudioContext;
      this.ctx = new Ctx();
      this.masterGain = this.ctx.createGain();
      this.masterGain.gain.setValueAtTime(this.isPlaying ? this.masterVolume : 0, this.ctx.currentTime);
      try {
        this.analyser = this.ctx.createAnalyser();
        this.analyser.fftSize = 512;
        this.analyser.smoothingTimeConstant = 0.65;
        this.masterGain.connect(this.analyser);
        this.analyser.connect(this.ctx.destination);
        if (typeof global.yBindAmbientAnalyser === "function") {
          global.yBindAmbientAnalyser(this.analyser);
        }
      } catch (e) {
        this.analyser = null;
        this.masterGain.connect(this.ctx.destination);
      }
    }
    if (this.analyser && typeof global.yBindAmbientAnalyser === "function") {
      global.yBindAmbientAnalyser(this.analyser);
    }
    if (this.ctx.state === "suspended" && typeof this.ctx.resume === "function") {
      this.ctx.resume().catch(function() {});
    }
    return this.ctx;
  };

  YexiMixer.prototype.loadBuffer = function(path) {
    var self = this;
    if (self.buffers[path]) {
      return Promise.resolve(self.buffers[path]);
    }
    if (self.loadingPromises[path]) {
      return self.loadingPromises[path];
    }
    var ctx = self._ensureContext();
    var url = self.apiBase + "/api/asset?name=" + encodeURIComponent(path);
    self.onLoadState(path, "loading");

    var attemptFetchAndDecode = function(retriesLeft) {
      return fetch(url)
        .then(function(res) {
          if (!res.ok) {
            throw new Error("素材加载失败 (" + res.status + ")");
          }
          return res.arrayBuffer();
        })
        .then(function(arr) {
          return new Promise(function(resolve, reject) {
            var ret = ctx.decodeAudioData(arr, resolve, reject);
            if (ret && typeof ret.then === "function") {
              ret.then(resolve, reject);
            }
          });
        })
        .catch(function(err) {
          if (retriesLeft > 0) {
            return new Promise(function(r) { setTimeout(r, 220); }).then(function() {
              return attemptFetchAndDecode(retriesLeft - 1);
            });
          }
          throw err;
        });
    };

    var p = attemptFetchAndDecode(1)
      .then(function(decoded) {
        var entry = analyzeAudioBuffer(decoded);
        self.buffers[path] = entry;
        delete self.loadingPromises[path];
        self.onLoadState(path, "ready");
        return entry;
      })
      .catch(function(err) {
        delete self.loadingPromises[path];
        self.onLoadState(path, "error");
        self.onError(path, err);
        throw err;
      });

    self.loadingPromises[path] = p;
    return p;
  };

  YexiMixer.prototype._computeNorm = function(tracks) {
    var list = tracks || this.currentTracks;
    var sum = 0;
    for (var i = 0; i < list.length; i++) {
      sum += clamp(parseFloat(list[i].weight) || 0, 0, 1);
    }
    return Math.max(1.0, sum * 0.85);
  };

  YexiMixer.prototype._createChannel = function(tr) {
    var ctx = this._ensureContext();
    var trackGain = ctx.createGain();
    trackGain.gain.setValueAtTime(0, ctx.currentTime);

    var panner = null;
    if (typeof ctx.createStereoPanner === "function") {
      panner = ctx.createStereoPanner();
      panner.pan.setValueAtTime(clamp(parseFloat(tr.pan) || 0, -1, 1), ctx.currentTime);
      trackGain.connect(panner);
      panner.connect(this.masterGain);
    } else {
      trackGain.connect(this.masterGain);
    }

    var ch = {
      path: tr.path,
      weight: tr.weight,
      pan: clamp(parseFloat(tr.pan) || 0, -1, 1),
      mode: tr.mode === "intermittent" ? "intermittent" : "loop",
      density: clamp(parseFloat(tr.density) || 0.4, 0.1, 1),
      trackGain: trackGain,
      panner: panner,
      playingSources: [],
      loopTimer: null,
      intermittentTimer: null,
      pulseOffTimer: null,
      nextStartTime: 0,
      started: false,
      disposed: false
    };
    return ch;
  };

  YexiMixer.prototype._clearChannelTimers = function(ch) {
    if (ch.loopTimer) {
      clearInterval(ch.loopTimer);
      ch.loopTimer = null;
    }
    if (ch.intermittentTimer) {
      clearTimeout(ch.intermittentTimer);
      ch.intermittentTimer = null;
    }
    if (ch.pulseOffTimer) {
      clearTimeout(ch.pulseOffTimer);
      ch.pulseOffTimer = null;
    }
  };

  YexiMixer.prototype._fadeOutAndStopSources = function(ch, fadeSec) {
    var self = this;
    var ctx = self.ctx;
    self._clearChannelTimers(ch);
    ch.started = false;
    self.onPulse(ch.path, false);

    if (!ctx) return;
    var now = ctx.currentTime;
    var list = ch.playingSources.slice();
    ch.playingSources = [];

    for (var i = 0; i < list.length; i++) {
      (function(item) {
        try {
          if (typeof item.subGain.gain.cancelScheduledValues === "function") {
            item.subGain.gain.cancelScheduledValues(now);
          }
          item.subGain.gain.setTargetAtTime(0, now, Math.max(0.05, fadeSec * 0.25));
          item.src.stop(now + fadeSec + 0.08);
        } catch (e) {}
      })(list[i]);
    }
  };

  YexiMixer.prototype._disposeChannel = function(ch, fadeSec) {
    var self = this;
    var dur = Math.max(0.05, Number(fadeSec) || 0.45);
    ch.disposed = true;
    self._clearChannelTimers(ch);
    if (ch._delayTimer) {
      clearTimeout(ch._delayTimer);
      ch._delayTimer = null;
    }
    self.onPulse(ch.path, false);
    if (!self.ctx) return;
    var now = self.ctx.currentTime;
    try {
      if (typeof ch.trackGain.gain.cancelScheduledValues === "function") {
        ch.trackGain.gain.cancelScheduledValues(now);
      }
      ch.trackGain.gain.setValueAtTime(ch.trackGain.gain.value, now);
      ch.trackGain.gain.linearRampToValueAtTime(0, now + dur);
    } catch (e) {}
    setTimeout(function() {
      for (var i = 0; i < ch.playingSources.length; i++) {
        try { ch.playingSources[i].src.stop(); } catch (e) {}
      }
      ch.playingSources = [];
      try { ch.trackGain.disconnect(); } catch (e) {}
      if (ch.panner) {
        try { ch.panner.disconnect(); } catch (e) {}
      }
    }, Math.round((dur + 0.25) * 1000));
  };

  YexiMixer.prototype._scheduleLoopSegment = function(ch, entry, startTime, isFirst) {
    var self = this;
    var ctx = self.ctx;
    var buffer = entry.buffer;
    var dur = buffer.duration;

    var src = ctx.createBufferSource();
    src.buffer = buffer;
    var subGain = ctx.createGain();
    src.connect(subGain);
    subGain.connect(ch.trackGain);

    if (dur <= 0.2) {
      src.loop = true;
      subGain.gain.setValueAtTime(1, startTime);
      src.start(startTime);
      ch.playingSources.push({ src: src, subGain: subGain });
      ch.nextStartTime = startTime + 999999;
      return;
    }

    var offset = (isFirst && entry.firstActiveSec > 0 && entry.firstActiveSec < dur - 2.5)
      ? entry.firstActiveSec
      : 0;
    var playDur = Math.max(0.25, dur - offset);
    var xfade = Math.min(2.0, Math.max(0.25, playDur * 0.12));
    if (xfade > playDur * 0.4) xfade = playDur * 0.4;
    var step = Math.max(0.2, playDur - xfade);

    if (isFirst) {
      subGain.gain.setValueAtTime(1, startTime);
    } else {
      subGain.gain.setValueAtTime(0, startTime);
      subGain.gain.setValueCurveAtTime(SIN_IN, startTime, xfade);
    }
    subGain.gain.setValueCurveAtTime(COS_OUT, startTime + step, xfade);

    var rec = { src: src, subGain: subGain };
    ch.playingSources.push(rec);
    src.onended = function() {
      var idx = ch.playingSources.indexOf(rec);
      if (idx !== -1) ch.playingSources.splice(idx, 1);
    };

    src.start(startTime, offset, playDur + 0.03);
    src.stop(startTime + playDur + 0.06);
    ch.nextStartTime = startTime + step;
  };

  YexiMixer.prototype._startLoop = function(ch, entry) {
    var self = this;
    if (ch.disposed || !self.isPlaying) return;
    ch.started = true;
    var ctx = self.ctx;
    ch.nextStartTime = ctx.currentTime + 0.04;
    self._scheduleLoopSegment(ch, entry, ch.nextStartTime, true);

    if (entry.buffer.duration > 0.2) {
      ch.loopTimer = setInterval(function() {
        if (ch.disposed || !self.isPlaying) return;
        var horizon = ctx.currentTime + 1.0;
        while (ch.nextStartTime < horizon) {
          self._scheduleLoopSegment(ch, entry, ch.nextStartTime, false);
        }
      }, 200);
    }
  };

  YexiMixer.prototype._triggerIntermittentBurst = function(ch, entry, isFirstBurst) {
    var self = this;
    if (ch.disposed || !self.isPlaying) return;
    var ctx = self.ctx;
    var buffer = entry.buffer;
    var dur = buffer.duration;
    var now = ctx.currentTime + 0.03;

    var burstDur = Math.min(Math.max(2.0, dur), 6.0 + Math.random() * 4.0);
    var buckets = entry.activeBuckets && entry.activeBuckets.length ? entry.activeBuckets : [0];
    var srcOffset = buckets[Math.floor(Math.random() * buckets.length)] || 0;
    if (srcOffset >= dur - 0.5) srcOffset = 0;

    var src = ctx.createBufferSource();
    src.buffer = buffer;
    if (srcOffset + burstDur > dur) {
      src.loop = true;
    }

    var subGain = ctx.createGain();
    var fi = isFirstBurst ? Math.min(0.45, burstDur * 0.2) : Math.min(1.6, burstDur * 0.30);
    var fo = Math.min(2.2, burstDur * 0.34);

    subGain.gain.setValueAtTime(0, now);
    subGain.gain.setValueCurveAtTime(HANN_IN, now, fi);
    subGain.gain.setValueCurveAtTime(HANN_OUT, now + burstDur - fo, fo);

    src.connect(subGain);
    subGain.connect(ch.trackGain);

    var rec = { src: src, subGain: subGain };
    ch.playingSources.push(rec);
    src.onended = function() {
      var idx = ch.playingSources.indexOf(rec);
      if (idx !== -1) ch.playingSources.splice(idx, 1);
    };

    src.start(now, srcOffset, burstDur + 0.05);
    src.stop(now + burstDur + 0.08);

    self.onPulse(ch.path, true);
    if (ch.pulseOffTimer) clearTimeout(ch.pulseOffTimer);
    ch.pulseOffTimer = setTimeout(function() {
      if (!ch.disposed) self.onPulse(ch.path, false);
    }, Math.max(400, Math.round((burstDur - fo * 0.45) * 1000)));

    var range = gapRangeForDensity(ch.density);
    // 若当前只有这一条偶发轨（无底幕托底），缩短休眠空窗，防止出现十几秒死寂像没声音
    if (self.currentTracks.length <= 1) {
      range = { min: 1.2, max: 2.8 };
    }
    var gapSec = range.min + Math.random() * (range.max - range.min);
    ch.nextWaitMaxMs = Math.round((burstDur + range.max) * 1000);
    ch.intermittentTimer = setTimeout(function() {
      self._triggerIntermittentBurst(ch, entry, false);
    }, Math.round((burstDur + gapSec) * 1000));
  };

  YexiMixer.prototype._startIntermittent = function(ch, entry) {
    var self = this;
    if (ch.disposed || !self.isPlaying) return;
    ch.started = true;
    var firstDelayMs = 80;
    ch.intermittentTimer = setTimeout(function() {
      self._triggerIntermittentBurst(ch, entry, true);
    }, firstDelayMs);
  };

  YexiMixer.prototype._startChannelIfReady = function(ch) {
    var self = this;
    if (ch.disposed || !self.isPlaying || ch.started) return;
    self.loadBuffer(ch.path).then(function(entry) {
      if (ch.disposed || !self.isPlaying) return;
      var fadeIn = ch._pendingFadeInSec || 0;
      ch._pendingFadeInSec = 0;
      self._applyChannelGain(ch, entry.calGain, 0.08, fadeIn);
      if (!ch.started) {
        if (ch.mode === "intermittent") {
          self._startIntermittent(ch, entry);
        } else {
          self._startLoop(ch, entry);
        }
      }
    }).catch(function() {});
  };

  YexiMixer.prototype._applyChannelGain = function(ch, calGain, timeConstant, rampSec) {
    if (!this.ctx || ch.disposed) return;
    var norm = this._computeNorm(this.currentTracks);
    var target = clamp((ch.weight / norm) * (calGain || 1.0), 0, 20.0);
    var now = this.ctx.currentTime;
    try {
      ch.trackGain.gain.cancelScheduledValues(now);
      ch.trackGain.gain.setValueAtTime(ch.trackGain.gain.value, now);
    } catch (e) {}
    if (rampSec && rampSec > 0.2) {
      ch.trackGain.gain.linearRampToValueAtTime(target, now + rampSec);
    } else {
      ch.trackGain.gain.setTargetAtTime(target, now, timeConstant || 0.06);
    }
  };

  YexiMixer.prototype.syncTracks = function(tracks, opts) {
    var self = this;
    var cfg = opts || {};
    var trans = cfg.transition || "crossfade";
    var baseFadeOut = cfg.fadeOutSec !== undefined ? Number(cfg.fadeOutSec) : 0.45;
    var baseFadeIn = cfg.fadeInSec !== undefined ? Number(cfg.fadeInSec) : 0;
    var fadeOutSec = baseFadeOut;
    var fadeInSec = baseFadeIn;
    var delayInMs = 0;

    if (trans === "cut") {
      fadeOutSec = 0.15;
      fadeInSec = 0.15;
    } else if (trans === "dip") {
      var dipRef = Math.max(baseFadeOut, baseFadeIn, 2.0);
      fadeOutSec = dipRef * 0.55;
      fadeInSec = dipRef * 0.55;
      delayInMs = Math.round(dipRef * 450);
    }

    self.currentTracks = (tracks || []).slice();
    var nextMap = {};
    var i, tr, ch;

    for (i = 0; i < self.currentTracks.length; i++) {
      tr = self.currentTracks[i];
      if (!tr || !tr.path) continue;
      nextMap[tr.path] = tr;
    }

    // 淡出并移除不在列表里的轨道
    for (var oldPath in self.channels) {
      if (Object.prototype.hasOwnProperty.call(self.channels, oldPath) && !nextMap[oldPath]) {
        self._disposeChannel(self.channels[oldPath], fadeOutSec);
        delete self.channels[oldPath];
      }
    }

    // 新增或更新已有轨道
    for (i = 0; i < self.currentTracks.length; i++) {
      tr = self.currentTracks[i];
      if (!tr || !tr.path) continue;
      ch = self.channels[tr.path];
      if (!ch) {
        ch = self._createChannel(tr);
        ch._pendingFadeInSec = fadeInSec;
        self.channels[tr.path] = ch;
        var startNewChannel = function(channelRef, inSec) {
          self.loadBuffer(channelRef.path).then(function(entry) {
            if (channelRef.disposed) return;
            var useIn = inSec > 0 ? inSec : (channelRef._pendingFadeInSec || 0);
            channelRef._pendingFadeInSec = 0;
            self._applyChannelGain(channelRef, entry.calGain, 0.14, useIn);
            if (self.isPlaying && !channelRef.started) {
              self._startChannelIfReady(channelRef);
            }
          }).catch(function() {});
        };
        if (delayInMs > 0) {
          ch._delayTimer = setTimeout((function(channelRef, inSec) {
            return function() {
              channelRef._delayTimer = null;
              if (!channelRef.disposed) startNewChannel(channelRef, inSec);
            };
          })(ch, fadeInSec), delayInMs);
        } else {
          startNewChannel(ch, fadeInSec);
        }
      } else {
        var modeChanged = ch.mode !== (tr.mode === "intermittent" ? "intermittent" : "loop");
        var oldDensity = ch.density;
        ch.weight = clamp(parseFloat(tr.weight) || 0, 0, 1);
        ch.pan = clamp(parseFloat(tr.pan) || 0, -1, 1);
        ch.mode = tr.mode === "intermittent" ? "intermittent" : "loop";
        ch.density = clamp(parseFloat(tr.density) || 0.4, 0.1, 1);

        if (ch.panner && self.ctx) {
          ch.panner.pan.setTargetAtTime(ch.pan, self.ctx.currentTime, 0.06);
        }
        var entry = self.buffers[tr.path];
        if (entry) {
          var sharedRamp = fadeInSec > 0.4 ? Math.max(0.4, fadeInSec * 0.6) : 0;
          self._applyChannelGain(ch, entry.calGain, 0.06, sharedRamp);
        }

        if (modeChanged && self.isPlaying) {
          self._fadeOutAndStopSources(ch, 0.35);
          self._startChannelIfReady(ch);
        } else if (!modeChanged && ch.mode === "intermittent" && self.isPlaying &&
                   ch.density > oldDensity + 0.15 && ch.playingSources.length === 0) {
          // 频率明显调高且当前在休眠时，提早下一轮触发
          if (ch.intermittentTimer) {
            clearTimeout(ch.intermittentTimer);
            ch.intermittentTimer = null;
          }
          if (entry) {
            ch.intermittentTimer = setTimeout((function(channelRef, bufEntry) {
              return function() { self._triggerIntermittentBurst(channelRef, bufEntry); };
            })(ch, entry), 600);
          }
        }
      }
    }
  };

  YexiMixer.prototype.setPlaying = function(next) {
    var self = this;
    self.isPlaying = !!next;
    var ctx = self._ensureContext();
    var now = ctx.currentTime;

    var startAll = function() {
      if (!self.isPlaying || !self.ctx) return;
      var t = self.ctx.currentTime;
      try {
        self.masterGain.gain.cancelScheduledValues(t);
        self.masterGain.gain.setValueAtTime(self.masterGain.gain.value, t);
      } catch (e) {}
      self.masterGain.gain.setTargetAtTime(self.masterVolume, t, 0.08);
      for (var p in self.channels) {
        if (Object.prototype.hasOwnProperty.call(self.channels, p)) {
          self._startChannelIfReady(self.channels[p]);
        }
      }
    };

    if (self.isPlaying) {
      startAll();
      if (ctx.state === "suspended" && typeof ctx.resume === "function") {
        ctx.resume().then(function() {
          if (self.isPlaying) startAll();
        }).catch(function() {});
      }
    } else {
      try {
        self.masterGain.gain.cancelScheduledValues(now);
        self.masterGain.gain.setValueAtTime(self.masterGain.gain.value, now);
      } catch (e) {}
      self.masterGain.gain.setTargetAtTime(0, now, 0.08);
      for (var q in self.channels) {
        if (Object.prototype.hasOwnProperty.call(self.channels, q)) {
          self._fadeOutAndStopSources(self.channels[q], 0.25);
        }
      }
    }
  };

  YexiMixer.prototype.setMasterVolume = function(val) {
    this.masterVolume = clamp(parseFloat(val) || 0, 0, 1);
    if (this.ctx && this.masterGain && this.isPlaying) {
      var now = this.ctx.currentTime;
      try {
        this.masterGain.gain.cancelScheduledValues(now);
        this.masterGain.gain.setValueAtTime(this.masterGain.gain.value, now);
      } catch (e) {}
      this.masterGain.gain.setTargetAtTime(this.masterVolume, now, 0.05);
    }
  };

  YexiMixer.prototype.preloadTracks = function(tracks) {
    var self = this;
    var list = tracks || [];
    var ps = [];
    for (var i = 0; i < list.length; i++) {
      if (list[i] && list[i].path) {
        ps.push(self.loadBuffer(list[i].path));
      }
    }
    return Promise.all(ps);
  };

  YexiMixer.prototype.exportWav = function(tracks, masterVol, seconds) {
    var self = this;
    var list = (tracks || []).slice();
    var durSec = clamp(parseInt(seconds, 10) || 30, 5, 180);
    var sr = 44100;
    if (list.length === 0) {
      return Promise.reject(new Error("当前没有可导出的声轨"));
    }

    var OfflineCtx = global.OfflineAudioContext || global.webkitOfflineAudioContext;
    if (!OfflineCtx) {
      return Promise.reject(new Error("当前浏览器不支持离线 WAV 导出"));
    }

    return self.preloadTracks(list).then(function() {
      var offline = new OfflineCtx(2, durSec * sr, sr);
      var master = offline.createGain();
      var mv = clamp(parseFloat(masterVol) || 0.85, 0, 1);
      master.gain.setValueAtTime(0, 0);
      master.gain.linearRampToValueAtTime(mv, Math.min(0.5, durSec * 0.1));
      master.gain.setValueAtTime(mv, Math.max(0.5, durSec - 0.5));
      master.gain.linearRampToValueAtTime(0, durSec);
      master.connect(offline.destination);

      var norm = self._computeNorm(list);

      for (var i = 0; i < list.length; i++) {
        var tr = list[i];
        var entry = self.buffers[tr.path];
        if (!entry || !tr.weight) continue;

        var buffer = entry.buffer;
        var bufDur = buffer.duration;
        var trackGain = offline.createGain();
        trackGain.gain.setValueAtTime(clamp((tr.weight / norm) * entry.calGain, 0, 20.0), 0);

        if (typeof offline.createStereoPanner === "function") {
          var panner = offline.createStereoPanner();
          panner.pan.setValueAtTime(clamp(parseFloat(tr.pan) || 0, -1, 1), 0);
          trackGain.connect(panner);
          panner.connect(master);
        } else {
          trackGain.connect(master);
        }

        if (tr.mode === "intermittent") {
          var pos = 0.6;
          var buckets = entry.activeBuckets && entry.activeBuckets.length ? entry.activeBuckets : [0];
          var range = gapRangeForDensity(tr.density);
          var seedIdx = i;
          while (pos < durSec - 1.5) {
            var burstDur = Math.min(Math.max(2.0, bufDur), 6.0 + ((seedIdx * 1.7) % 4.0));
            var actualDur = Math.min(burstDur, durSec - pos);
            if (actualDur < 1.5) break;
            var offset = buckets[seedIdx % buckets.length] || 0;
            if (offset >= bufDur - 0.5) offset = 0;

            var bSrc = offline.createBufferSource();
            bSrc.buffer = buffer;
            if (offset + actualDur > bufDur) bSrc.loop = true;
            var bGain = offline.createGain();
            var fi = Math.min(2.0, actualDur * 0.32);
            var fo = Math.min(2.5, actualDur * 0.36);
            bGain.gain.value = 0;
            bGain.gain.setValueCurveAtTime(HANN_IN, pos, fi);
            bGain.gain.setValueCurveAtTime(HANN_OUT, pos + actualDur - fo, fo);
            bSrc.connect(bGain);
            bGain.connect(trackGain);
            bSrc.start(pos, offset, actualDur + 0.02);
            bSrc.stop(pos + actualDur + 0.04);

            var gap = range.min + ((seedIdx * 3.13) % Math.max(1, range.max - range.min));
            pos += actualDur + gap;
            seedIdx += 1;
          }
        } else {
          if (bufDur <= 0.2) {
            var s0 = offline.createBufferSource();
            s0.buffer = buffer;
            s0.loop = true;
            s0.connect(trackGain);
            s0.start(0);
          } else {
            var xfade = Math.min(2.0, Math.max(0.35, bufDur * 0.12));
            var step = Math.max(0.2, bufDur - xfade);
            var t = 0;
            var first = true;
            while (t < durSec) {
              var lSrc = offline.createBufferSource();
              lSrc.buffer = buffer;
              var lGain = offline.createGain();
              if (first) {
                lGain.gain.setValueAtTime(1, t);
              } else {
                lGain.gain.value = 0;
                lGain.gain.setValueCurveAtTime(SIN_IN, t, xfade);
              }
              lGain.gain.setValueCurveAtTime(COS_OUT, t + step, xfade);
              lSrc.connect(lGain);
              lGain.connect(trackGain);
              lSrc.start(t, 0, bufDur + 0.02);
              lSrc.stop(t + bufDur + 0.04);
              t += step;
              first = false;
            }
          }
        }
      }

      return offline.startRendering().then(function(rendered) {
        return audioBufferToWavBlob(rendered);
      });
    });
  };

  YexiMixer.prototype.exportTimelineWav = function(segments, masterVol, options) {
    var self = this;
    var segs = (segments || []).slice();
    var opts = options || {};
    var maxTotalSec = clamp(parseInt(opts.maxTotalSec, 10) || 300, 10, 300);
    var previewSegSec = Number(opts.previewSegSec) || 0;
    var sr = 44100;
    if (segs.length === 0) {
      return Promise.reject(new Error("当前没有可导出的段落"));
    }

    var OfflineCtx = global.OfflineAudioContext || global.webkitOfflineAudioContext;
    if (!OfflineCtx) {
      return Promise.reject(new Error("当前浏览器不支持离线 WAV 导出"));
    }

    var allTracks = [];
    var seenPath = {};
    var rawDurs = [];
    var sumRaw = 0;
    var si, ti;
    for (si = 0; si < segs.length; si++) {
      var segTracks = segs[si].tracks || [];
      for (ti = 0; ti < segTracks.length; ti++) {
        if (segTracks[ti] && segTracks[ti].path && !seenPath[segTracks[ti].path]) {
          seenPath[segTracks[ti].path] = true;
          allTracks.push(segTracks[ti]);
        }
      }
      var d = previewSegSec > 0 ? previewSegSec : Math.max(5, Number(segs[si].durationSec) || ((Number(segs[si].minutes) || 3) * 60));
      rawDurs.push(d);
      sumRaw += d;
    }
    if (allTracks.length === 0) {
      return Promise.reject(new Error("当前没有可导出的声轨"));
    }

    // 若未开启精华试听模式且总长超过 maxTotalSec，则按比例缩放到 maxTotalSec 以内
    var scaleRatio = (previewSegSec <= 0 && sumRaw > maxTotalSec) ? (maxTotalSec / sumRaw) : 1.0;
    var placements = [];
    var cursorSec = 0;
    for (si = 0; si < segs.length; si++) {
      var seg = segs[si];
      var segDur = Math.max(4, rawDurs[si] * scaleRatio);
      var trans = si === 0 ? "cut" : (seg.transition || "crossfade");
      var reqFade = clamp(Number(seg.fadeSec) || 4, 0.2, 12);
      var startSec = cursorSec;
      var inFade = 0.3;
      var outFade = 0.3;
      if (si > 0) {
        var prevP = placements[si - 1];
        if (trans === "crossfade") {
          var ov = Math.min(reqFade, prevP.dur * 0.4, segDur * 0.4);
          startSec = Math.max(0, prevP.end - ov);
          prevP.outFade = Math.max(prevP.outFade, ov);
          inFade = ov;
        } else if (trans === "dip") {
          var dipFade = Math.min(reqFade * 0.5, prevP.dur * 0.35, segDur * 0.35);
          prevP.outFade = Math.max(prevP.outFade, dipFade);
          inFade = dipFade;
          startSec = prevP.end + 0.35;
        } else {
          prevP.outFade = Math.max(prevP.outFade, 0.12);
          inFade = 0.12;
          startSec = prevP.end;
        }
      }
      var endSec = startSec + segDur;
      placements.push({
        tracks: seg.tracks || [],
        start: startSec,
        end: endSec,
        dur: segDur,
        inFade: inFade,
        outFade: outFade
      });
      cursorSec = endSec;
    }

    var totalSec = Math.min(maxTotalSec + 5, Math.max(4, cursorSec));
    return self.preloadTracks(allTracks).then(function() {
      var offline = new OfflineCtx(2, Math.ceil(totalSec * sr), sr);
      var master = offline.createGain();
      var mv = clamp(parseFloat(masterVol) || 0.85, 0, 1);
      master.gain.setValueAtTime(0, 0);
      master.gain.linearRampToValueAtTime(mv, Math.min(0.6, totalSec * 0.1));
      master.gain.setValueAtTime(mv, Math.max(0.6, totalSec - 0.8));
      master.gain.linearRampToValueAtTime(0, totalSec);
      master.connect(offline.destination);

      for (var pi = 0; pi < placements.length; pi++) {
        var pl = placements[pi];
        var segStart = pl.start;
        var segEnd = Math.min(totalSec, pl.end);
        var segDur = segEnd - segStart;
        if (segDur <= 0.2 || pl.tracks.length === 0) continue;

        var segGain = offline.createGain();
        var fi = Math.min(pl.inFade, segDur * 0.45);
        var fo = Math.min(pl.outFade, segDur * 0.45);
        segGain.gain.setValueAtTime(0, segStart);
        segGain.gain.setValueCurveAtTime(SIN_IN, segStart, Math.max(0.05, fi));
        segGain.gain.setValueAtTime(1, segStart + Math.max(0.05, fi));
        if (segEnd - fo > segStart + fi) {
          segGain.gain.setValueAtTime(1, segEnd - fo);
        }
        segGain.gain.setValueCurveAtTime(COS_OUT, Math.max(segStart + 0.05, segEnd - fo), Math.max(0.05, fo));
        segGain.connect(master);

        var norm = self._computeNorm(pl.tracks);
        for (var i = 0; i < pl.tracks.length; i++) {
          var tr = pl.tracks[i];
          var entry = self.buffers[tr.path];
          if (!entry || !tr.weight) continue;

          var buffer = entry.buffer;
          var bufDur = buffer.duration;
          var trackGain = offline.createGain();
          trackGain.gain.setValueAtTime(clamp((tr.weight / norm) * entry.calGain, 0, 20.0), segStart);

          if (typeof offline.createStereoPanner === "function") {
            var panner = offline.createStereoPanner();
            panner.pan.setValueAtTime(clamp(parseFloat(tr.pan) || 0, -1, 1), segStart);
            trackGain.connect(panner);
            panner.connect(segGain);
          } else {
            trackGain.connect(segGain);
          }

          if (tr.mode === "intermittent") {
            var pos = segStart + 0.4;
            var buckets = entry.activeBuckets && entry.activeBuckets.length ? entry.activeBuckets : [0];
            var range = gapRangeForDensity(tr.density);
            var seedIdx = i + pi * 7;
            while (pos < segEnd - 1.2) {
              var burstDur = Math.min(Math.max(2.0, bufDur), 6.0 + ((seedIdx * 1.7) % 4.0));
              var actualDur = Math.min(burstDur, segEnd - pos);
              if (actualDur < 1.2) break;
              var offset = buckets[seedIdx % buckets.length] || 0;
              if (offset >= bufDur - 0.5) offset = 0;

              var bSrc = offline.createBufferSource();
              bSrc.buffer = buffer;
              if (offset + actualDur > bufDur) bSrc.loop = true;
              var bGain = offline.createGain();
              var bfi = Math.min(1.8, actualDur * 0.32);
              var bfo = Math.min(2.2, actualDur * 0.36);
              bGain.gain.value = 0;
              bGain.gain.setValueCurveAtTime(HANN_IN, pos, bfi);
              bGain.gain.setValueCurveAtTime(HANN_OUT, pos + actualDur - bfo, bfo);
              bSrc.connect(bGain);
              bGain.connect(trackGain);
              bSrc.start(pos, offset, actualDur + 0.02);
              bSrc.stop(pos + actualDur + 0.04);

              var gap = range.min + ((seedIdx * 3.13) % Math.max(1, range.max - range.min));
              pos += actualDur + gap;
              seedIdx += 1;
            }
          } else {
            if (bufDur <= 0.2) {
              var s0 = offline.createBufferSource();
              s0.buffer = buffer;
              s0.loop = true;
              s0.connect(trackGain);
              s0.start(segStart);
              s0.stop(segEnd + 0.05);
            } else {
              var xfade = Math.min(2.0, Math.max(0.35, bufDur * 0.12));
              var step = Math.max(0.2, bufDur - xfade);
              var t = segStart;
              var first = true;
              while (t < segEnd) {
                var lSrc = offline.createBufferSource();
                lSrc.buffer = buffer;
                var lGain = offline.createGain();
                if (first) {
                  lGain.gain.setValueAtTime(1, t);
                } else {
                  lGain.gain.value = 0;
                  lGain.gain.setValueCurveAtTime(SIN_IN, t, xfade);
                }
                lGain.gain.setValueCurveAtTime(COS_OUT, t + step, xfade);
                lSrc.connect(lGain);
                lGain.connect(trackGain);
                lSrc.start(t, 0, Math.min(bufDur + 0.02, segEnd - t + 0.2));
                lSrc.stop(Math.min(t + bufDur + 0.04, segEnd + 0.2));
                t += step;
                first = false;
              }
            }
          }
        }
      }

      return offline.startRendering().then(function(rendered) {
        return audioBufferToWavBlob(rendered);
      });
    });
  };

  global.YexiMixer = YexiMixer;
})(window);
