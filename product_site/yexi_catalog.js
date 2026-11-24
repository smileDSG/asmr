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
    icon: "",
    img: "img/city-rain-night.jpg",
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
    icon: "",
    img: "img/rain-window.jpg",
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
    icon: "",
    img: "img/raindrops-macro.jpg",
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
    icon: "",
    img: "img/ocean-waves.jpg",
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
    icon: "",
    img: "img/ocean-deep.jpg?v=2",
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
    icon: "",
    img: "img/forest-stream.jpg?v=2",
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
    icon: "",
    img: "img/raindrops-macro.jpg",
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
    icon: "",
    img: "img/calm-forest.jpg",
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
    icon: "",
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
    icon: "",
    img: "img/city-rain-night.jpg",
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
    icon: "",
    img: "img/starry-mountain-lake.jpg",
    accent: "#9b85d6",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "704381",
    sr: "44.1kHz"
  },
  {
    path: "帐篷雨_小帐篷大雨_592996.hq.mp3",
    name: "帐篷夜雨",
    desc: "雨点密集落在小帐篷帆布上，被包裹的安全感",
    group: "雨声",
    layer: "bed",
    defaultWeight: 0.68,
    defaultPan: 0.0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/rain-window.jpg",
    accent: "#7a6fe0",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "592996",
    sr: "48kHz"
  },
  {
    path: "海浪_湖海柔浪_451532.hq.mp3",
    name: "湖海柔浪",
    desc: "长段平稳拍岸的轻柔水浪声",
    group: "海浪",
    layer: "bed",
    defaultWeight: 0.7,
    defaultPan: 0.0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/ocean-waves.jpg",
    accent: "#5b9bd5",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "451532",
    sr: "48kHz"
  },
  {
    path: "海浪_沙滩柔浪_325197.hq.mp3",
    name: "沙滩柔浪",
    desc: "海浪温柔漫过沙滩又缓缓退去",
    group: "海浪",
    layer: "bed",
    defaultWeight: 0.68,
    defaultPan: 0.0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/ocean-deep.jpg?v=2",
    accent: "#6aa8e0",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "325197",
    sr: "44.1kHz"
  },
  {
    path: "溪流_野外溪水_180732.hq.mp3",
    name: "野外溪水",
    desc: "自然流动的户外山谷溪水，水花质感丰沛",
    group: "自然",
    layer: "bed",
    defaultWeight: 0.68,
    defaultPan: 0.0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/forest-stream.jpg?v=2",
    accent: "#4ba3c3",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "180732",
    sr: "48kHz"
  },
  {
    path: "溪流_柔和河水_707576.hq.mp3",
    name: "柔和河水",
    desc: "平稳不刺耳的宽阔缓流河水，循环极自然",
    group: "自然",
    layer: "bed",
    defaultWeight: 0.72,
    defaultPan: 0.0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/forest-stream.jpg?v=2",
    accent: "#5098b8",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "707576",
    sr: "48kHz"
  },
  {
    path: "溪流_小溪循环_767320.hq.mp3",
    name: "林间小溪",
    desc: "轻缓细小的林间溪流，平稳安静不抢耳",
    group: "自然",
    layer: "bed",
    defaultWeight: 0.7,
    defaultPan: 0.0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/forest-stream.jpg?v=2",
    accent: "#66b2cc",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "767320",
    sr: "44.1kHz"
  },
  {
    path: "林风_树林波浪风_637989.hq.mp3",
    name: "松林风涛",
    desc: "风一阵阵穿过高大树林，像林海波浪般涌动",
    group: "自然",
    layer: "bed",
    defaultWeight: 0.65,
    defaultPan: 0.0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/calm-forest.jpg",
    accent: "#5b9c8a",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "637989",
    sr: "48kHz"
  },
  {
    path: "林风_Akacie_73708.hq.mp3",
    name: "静谧林风",
    desc: "轻柔安静的林间空气流动与远树微响",
    group: "自然",
    layer: "bed",
    defaultWeight: 0.68,
    defaultPan: 0.0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/calm-forest.jpg",
    accent: "#6aa892",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "73708",
    sr: "44.1kHz"
  },
  {
    path: "微风_小镇傍晚风_321904.hq.mp3",
    name: "傍晚微风",
    desc: "开阔宁静的傍晚轻风，带着温柔夜幕前的松弛感",
    group: "自然",
    layer: "bed",
    defaultWeight: 0.66,
    defaultPan: 0.0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/night-lake-stars.jpg",
    accent: "#7b8dc9",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "321904",
    sr: "48kHz"
  },
  {
    path: "炉火_壁炉低燃_836535.hq.mp3",
    name: "壁炉低燃",
    desc: "室内壁炉木柴平稳燃烧的温暖火光声，几乎无尖锐爆响",
    group: "炉火",
    layer: "bed",
    defaultWeight: 0.72,
    defaultPan: 0.0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/fireplace-night.jpg?v=2",
    accent: "#e07a5f",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "836535",
    sr: "44.1kHz"
  },
  {
    path: "炉火_夜营氛围_766127.hq.mp3",
    name: "夜营微火",
    desc: "夜晚露营地极轻柔平稳的余烬微火氛围，柔和不刺耳",
    group: "炉火",
    layer: "bed",
    defaultWeight: 0.74,
    defaultPan: 0.0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/fireplace-night.jpg?v=2",
    accent: "#d9825b",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "766127",
    sr: "48kHz"
  },
  {
    path: "炉火_营地篝火_62487.hq.mp3",
    name: "营地篝火",
    desc: "户外木柴篝火燃烧声，带真实轻微木柴噼啪颗粒",
    group: "炉火",
    layer: "bed",
    defaultWeight: 0.64,
    defaultPan: 0.0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/fireplace-night.jpg?v=2",
    accent: "#e6915c",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "62487",
    sr: "44.1kHz"
  },
  {
    path: "微风_麦田柔风_447810.hq.mp3",
    name: "麦田柔风",
    desc: "轻风拂过宽阔麦田的轻柔沙沙声，温暖放松",
    group: "自然",
    layer: "texture",
    defaultWeight: 0.42,
    defaultPan: 0.28,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/wheat-sunset.jpg",
    accent: "#9eb878",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "447810",
    sr: "48kHz"
  },
  {
    path: "ASMR_麦套轻扫抓挠_803595.hq.mp3",
    name: "麦套轻扫",
    desc: "海绵麦套被轻缓抓挠扫过，绵密近场触发感",
    group: "ASMR",
    layer: "texture",
    defaultWeight: 0.56,
    defaultPan: 0.0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/warm-bedroom.jpg",
    accent: "#b58ae8",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "803595",
    sr: "48kHz"
  },
  {
    path: "ASMR_翻书多人_575764.hq.mp3",
    name: "书房翻书",
    desc: "自习室里轻缓持续翻阅书页的纸张沙沙声",
    group: "ASMR",
    layer: "texture",
    defaultWeight: 0.42,
    defaultPan: -0.25,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/notebook-desk.jpg?v=2",
    accent: "#c9a078",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "575764",
    sr: "48kHz"
  },
  {
    path: "ASMR_铅笔写字柔_336381.hq.mp3",
    name: "铅笔慢写",
    desc: "铅笔在纸面稳重均匀摩擦的柔和沙沙写字声",
    group: "ASMR",
    layer: "texture",
    defaultWeight: 0.44,
    defaultPan: 0.25,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/asmr-pencil.jpg",
    accent: "#d4b483",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "336381",
    sr: "48kHz"
  },
  {
    path: "ASMR_轻触麦克风_530347.hq.mp3",
    name: "轻触麦头",
    desc: "近距离轻柔碰触麦克风的细腻酥麻触发音",
    group: "ASMR",
    layer: "texture",
    defaultWeight: 0.36,
    defaultPan: 0.0,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/warm-bedroom.jpg",
    accent: "#c07be8",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "530347",
    sr: "44.1kHz"
  },
  {
    path: "ASMR_采耳_690078.hq.mp3",
    name: "轻柔采耳",
    desc: "近场轻柔掏耳与细微耳道触碰感，平稳舒适",
    group: "ASMR",
    layer: "texture",
    defaultWeight: 0.5,
    defaultPan: -0.2,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/asmr-earpick.jpg",
    accent: "#d992e8",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "690078",
    sr: "48kHz"
  },
  {
    path: "ASMR_轻柔梳头_825798.hq.mp3",
    name: "轻柔梳头",
    desc: "平稳柔和的木梳梳理发丝声，亲切放松",
    group: "ASMR",
    layer: "texture",
    defaultWeight: 0.45,
    defaultPan: 0.18,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/asmr-comb.jpg",
    accent: "#a68ae8",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "825798",
    sr: "44.1kHz"
  },
  {
    path: "ASMR_毛刷梳发_765369.hq.mp3",
    name: "毛刷梳发",
    desc: "毛刷轻扫发丝的绵柔沙沙声，温柔解压",
    group: "ASMR",
    layer: "texture",
    defaultWeight: 0.45,
    defaultPan: -0.18,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/warm-bedroom.jpg",
    accent: "#9484e8",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "765369",
    sr: "48kHz"
  },
  {
    path: "ASMR_海绵抓挠_690084.hq.mp3",
    name: "海绵抓挠",
    desc: "指尖轻轻抓挠海绵的细密沙沙触发音",
    group: "ASMR",
    layer: "texture",
    defaultWeight: 0.4,
    defaultPan: 0.25,
    defaultMode: "loop",
    defaultDensity: 0.4,
    icon: "",
    img: "img/warm-bedroom.jpg",
    accent: "#7eb8d6",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "690084",
    sr: "48kHz"
  },
  {
    path: "鸟鸣_夜莺鸣叫_853566.hq.mp3",
    name: "夜莺鸟鸣",
    desc: "林间婉转清脆的夜莺鸣叫，适合作稀疏自然点缀",
    group: "自然",
    layer: "accent",
    defaultWeight: 0.3,
    defaultPan: 0.42,
    defaultMode: "intermittent",
    defaultDensity: 0.3,
    icon: "",
    img: "img/calm-forest.jpg",
    accent: "#76b89e",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "853566",
    sr: "48kHz"
  },
  {
    path: "ASMR_羽毛轻拂_708086.hq.mp3",
    name: "羽毛轻拂",
    desc: "手指轻拂羽毛或羽毛轻触耳畔的纤细轻响",
    group: "ASMR",
    layer: "accent",
    defaultWeight: 0.4,
    defaultPan: 0.32,
    defaultMode: "intermittent",
    defaultDensity: 0.38,
    icon: "",
    img: "img/feather-soft.jpg",
    accent: "#d1b3ff",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "708086",
    sr: "44.1kHz"
  },
  {
    path: "ASMR_翻书单人_360781.hq.mp3",
    name: "深夜翻书",
    desc: "一个人安安静静一页页翻书的清脆纸张声",
    group: "ASMR",
    layer: "accent",
    defaultWeight: 0.4,
    defaultPan: -0.28,
    defaultMode: "intermittent",
    defaultDensity: 0.45,
    icon: "",
    img: "img/notebook-desk.jpg?v=2",
    accent: "#d4a872",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "360781",
    sr: "44.1kHz"
  },
  {
    path: "ASMR_铅笔写字轻快_376706.hq.mp3",
    name: "轻快记笔记",
    desc: "轻快沙沙的铅笔记录笔记声，带一点学习节奏感",
    group: "ASMR",
    layer: "accent",
    defaultWeight: 0.38,
    defaultPan: 0.3,
    defaultMode: "intermittent",
    defaultDensity: 0.48,
    icon: "",
    img: "img/asmr-pencil.jpg",
    accent: "#c8b07a",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "376706",
    sr: "44.1kHz"
  },
  {
    path: "ASMR_指尖轻敲刮擦_866230.hq.mp3",
    name: "指尖轻敲",
    desc: "指尖轻敲与柔和刮擦箱体表面的近场触发音",
    group: "ASMR",
    layer: "accent",
    defaultWeight: 0.36,
    defaultPan: -0.32,
    defaultMode: "intermittent",
    defaultDensity: 0.4,
    icon: "",
    img: "img/asmr-tapping.jpg",
    accent: "#b08ad9",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "866230",
    sr: "48kHz"
  },
  {
    path: "ASMR_木件桌游轻敲_569788.hq.mp3",
    name: "木件轻敲",
    desc: "木质小物件与桌游棋子清脆轻敲碰触声",
    group: "ASMR",
    layer: "accent",
    defaultWeight: 0.32,
    defaultPan: 0.34,
    defaultMode: "intermittent",
    defaultDensity: 0.35,
    icon: "",
    img: "img/warm-bedroom.jpg",
    accent: "#c9956b",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "569788",
    sr: "44.1kHz"
  },
  {
    path: "ASMR_手部轻搓抓挠_684746.hq.mp3",
    name: "手部轻搓",
    desc: "手掌干搓与指尖轻挠皮肤的近场摩擦触发音",
    group: "ASMR",
    layer: "accent",
    defaultWeight: 0.34,
    defaultPan: 0.2,
    defaultMode: "intermittent",
    defaultDensity: 0.32,
    icon: "",
    img: "img/warm-bedroom.jpg",
    accent: "#d9a2b4",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "684746",
    sr: "48kHz"
  },
  {
    path: "ASMR_轻抚抓挠_695629.hq.mp3",
    name: "轻抚抓挠",
    desc: "轻柔缓缓抚摸与抓挠的近场软触发声",
    group: "ASMR",
    layer: "accent",
    defaultWeight: 0.4,
    defaultPan: -0.22,
    defaultMode: "intermittent",
    defaultDensity: 0.38,
    icon: "",
    img: "img/warm-bedroom.jpg",
    accent: "#d6a4c8",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "695629",
    sr: "48kHz"
  },
  {
    path: "ASMR_糖纸揉捏_802609.hq.mp3",
    name: "糖纸揉捏",
    desc: "糖纸包装被缓缓揉捏起皱的清脆沙沙触发音",
    group: "ASMR",
    layer: "accent",
    defaultWeight: 0.3,
    defaultPan: 0.3,
    defaultMode: "intermittent",
    defaultDensity: 0.32,
    icon: "",
    img: "img/warm-bedroom.jpg",
    accent: "#e0b878",
    license: "CC0 1.0 Public Domain",
    source: "Freesound",
    freesoundId: "802609",
    sr: "44.1kHz"
  }
];

var YEXI_STUDIO_PRESETS = [
  {
    id: "p_attic_rain",
    title: "阁楼夜雨",
    desc: "城市夜雨铺底，暖夜低鸣托住温度，右侧天边偶尔滚过一声低沉远雷",
    tracks: [
      { path: "母带_城市夜雨_CC0.mp3", weight: 0.82, pan: 0, mode: "loop", density: 0.4 },
      { path: "雨中低鸣.hq.mp3", weight: 0.32, pan: -0.45, mode: "loop", density: 0.4 },
      { path: "远雷.hq.mp3", weight: 0.22, pan: 0.62, mode: "intermittent", density: 0.25 }
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
    icon: "",
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
  accentHex: "#e9b783",
  accentRgb: "233, 183, 131",
  playing: false,
  fxType: "night",
  nextFxType: null,
  fadingOut: false,
  fade: 1,
  level: 0,
  avg: 0,
  peak: 0.04,
  inten: 0.42,
  analyser: null,
  ampBuf: null,
  audioMap: [],
  p: [],
  extra: [],
  rings: [],
  t: 0,
  last: 0,
  lastRing: 0,
  w: 0,
  h: 0,
  canvas: null,
  ctx: null,
  rafId: null,
  reducedMotion: false
};

function _yHexToRgb(hex) {
  var s = String(hex || "").replace("#", "");
  if (s.length === 3) {
    s = s.charAt(0) + s.charAt(0) + s.charAt(1) + s.charAt(1) + s.charAt(2) + s.charAt(2);
  }
  if (s.length !== 6) return "233, 183, 131";
  var r = parseInt(s.slice(0, 2), 16);
  var g = parseInt(s.slice(2, 4), 16);
  var b = parseInt(s.slice(4, 6), 16);
  if (isNaN(r) || isNaN(g) || isNaN(b)) return "233, 183, 131";
  return r + ", " + g + ", " + b;
}

function _yInferFxType(imgUrl, explicitFx) {
  if (explicitFx) return explicitFx;
  var s = String(imgUrl || "").toLowerCase();
  if (s.indexOf("rain") >= 0) return "rain";
  if (s.indexOf("fireplace") >= 0) return "fire";
  if (s.indexOf("ocean") >= 0 || s.indexOf("stream") >= 0 || s.indexOf("water") >= 0) return "water";
  if (s.indexOf("forest") >= 0 || s.indexOf("wheat") >= 0) return "wind";
  if (s.indexOf("asmr") >= 0 || s.indexOf("feather") >= 0 || s.indexOf("notebook") >= 0 || s.indexOf("book") >= 0) return "asmr";
  if (s.indexOf("warm-bedroom") >= 0) return "bed";
  return "night";
}

function _yRnd(a, b) {
  return a + Math.random() * (b - a);
}

function yBindAmbientAnalyser(analyserNode) {
  if (!analyserNode) return;
  _ambientState.analyser = analyserNode;
  if (!_ambientState.ampBuf || _ambientState.ampBuf.length !== analyserNode.fftSize) {
    _ambientState.ampBuf = new Uint8Array(analyserNode.fftSize);
  }
}

function yBindAmbientAudio(audioEl) {
  if (!audioEl) return;
  for (var i = 0; i < _ambientState.audioMap.length; i++) {
    if (_ambientState.audioMap[i].el === audioEl) {
      var entry = _ambientState.audioMap[i];
      if (entry.ctx && entry.ctx.state === "suspended") {
        entry.ctx.resume().catch(function() {});
      }
      if (entry.analyser) yBindAmbientAnalyser(entry.analyser);
      return;
    }
  }
  try {
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    var ctx = new AC();
    var src = ctx.createMediaElementSource(audioEl);
    var an = ctx.createAnalyser();
    an.fftSize = 1024;
    an.smoothingTimeConstant = 0.6;
    src.connect(an);
    an.connect(ctx.destination);
    _ambientState.audioMap.push({ el: audioEl, ctx: ctx, analyser: an });
    yBindAmbientAnalyser(an);
  } catch (e) {
    // 浏览器策略或跨源限制时安静退化到呼吸模拟
  }
}

function initAmbientStage(initialImg, initialAccent, initialFx) {
  if (_ambientState.inited) {
    if (initialImg || initialAccent || initialFx) {
      ySetAmbient(
        initialImg || _ambientState.currentImg,
        initialAccent || _ambientState.accentHex,
        _ambientState.playing,
        initialFx
      );
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
    '<div class="ambient-vignette"></div>' +
    '<div class="ambient-grain"></div>';

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
        _ambientState.inten = 0.55;
        _drawAmbientFrame(true, 1);
      } else if (!_ambientState.reducedMotion && !_ambientState.rafId) {
        _ambientState.last = 0;
        _tickAmbient();
      }
    });
  }

  _resizeAmbientCanvas();
  window.addEventListener("resize", function() {
    _resizeAmbientCanvas();
    _buildAmbientFx(_ambientState.fxType);
  });

  var startImg = initialImg || "img/night-lake-stars.jpg";
  var startFx = _yInferFxType(startImg, initialFx);
  _buildAmbientFx(startFx);
  ySetAmbient(startImg, initialAccent || "#e9b783", false, startFx);

  if (_ambientState.reducedMotion) {
    _ambientState.inten = 0.55;
    _drawAmbientFrame(true, 1);
  } else {
    _tickAmbient();
  }
}

function ySetAmbient(imgUrl, accentHex, isPlaying, fxType) {
  if (!_ambientState.inited) initAmbientStage(imgUrl, accentHex, fxType);
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
  var nextFx = _yInferFxType(imgUrl || _ambientState.currentImg, fxType);
  if (nextFx && nextFx !== _ambientState.fxType) {
    _ambientState.nextFxType = nextFx;
    _ambientState.fadingOut = true;
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
  var dpr = Math.min(window.devicePixelRatio || 1, 1.5);
  _ambientState.w = window.innerWidth;
  _ambientState.h = window.innerHeight;
  c.width = Math.floor(_ambientState.w * dpr);
  c.height = Math.floor(_ambientState.h * dpr);
  if (_ambientState.ctx) {
    _ambientState.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  if (_ambientState.reducedMotion) {
    _drawAmbientFrame(true, 1);
  }
}

function _buildAmbientFx(type) {
  _ambientState.fxType = type || "night";
  _ambientState.p = [];
  _ambientState.extra = [];
  _ambientState.rings = [];
  var w = _ambientState.w || window.innerWidth;
  var h = _ambientState.h || window.innerHeight;
  var area = Math.min(1.4, (w * h) / (1280 * 800));
  var i, n;
  if (type === "rain") {
    n = Math.round(140 * area);
    for (i = 0; i < n; i++) {
      _ambientState.p.push({ x: _yRnd(0, w), y: _yRnd(-h, h), len: _yRnd(12, 32), sp: _yRnd(0.7, 1.45), a: _yRnd(0.05, 0.22), wd: _yRnd(0.5, 1.15), z: Math.random() });
    }
    for (i = 0; i < 18; i++) {
      _ambientState.extra.push({ x: _yRnd(0, w), y: _yRnd(0, h), r: _yRnd(1.5, 4.2), vy: 0, hold: _yRnd(0, 600) });
    }
  } else if (type === "fire") {
    // 余烬动态生成
  } else if (type === "water") {
    for (i = 0; i < 64; i++) {
      _ambientState.p.push({ x: _yRnd(0, w), y: _yRnd(h * 0.55, h), ph: _yRnd(0, 6.28), f: _yRnd(0.6, 1.8), r: _yRnd(0.6, 1.6) });
    }
  } else if (type === "wind") {
    for (i = 0; i < 6; i++) {
      _ambientState.extra.push({ x: _yRnd(-w * 0.2, w), y: _yRnd(h * 0.3, h * 0.95), r: _yRnd(h * 0.25, h * 0.48), vx: _yRnd(0.08, 0.22), a: _yRnd(0.03, 0.065) });
    }
    for (i = 0; i < Math.round(52 * area); i++) {
      _ambientState.p.push({ x: _yRnd(0, w), y: _yRnd(0, h), vx: _yRnd(0.18, 0.62), ph: _yRnd(0, 6.28), r: _yRnd(0.6, 1.7), a: _yRnd(0.14, 0.4) });
    }
  } else if (type === "asmr") {
    for (i = 0; i < Math.round(50 * area); i++) {
      _ambientState.p.push({ x: _yRnd(0, w), y: _yRnd(0, h), vx: _yRnd(-0.08, 0.08), vy: _yRnd(-0.12, -0.02), r: _yRnd(0.5, 1.5), a: _yRnd(0.1, 0.36), ph: _yRnd(0, 6.28) });
    }
  } else if (type === "bed") {
    for (i = 0; i < 5; i++) {
      _ambientState.extra.push({ x: _yRnd(0, w), y: _yRnd(h * 0.2, h), r: _yRnd(h * 0.3, h * 0.55), vx: _yRnd(-0.1, 0.1), a: _yRnd(0.03, 0.055) });
    }
  } else {
    for (i = 0; i < Math.round(95 * area); i++) {
      _ambientState.p.push({ x: _yRnd(0, w), y: _yRnd(0, h * 0.65), r: _yRnd(0.4, 1.25), ph: _yRnd(0, 6.28), f: _yRnd(0.4, 1.3) });
    }
    for (i = 0; i < 16; i++) {
      _ambientState.extra.push({ x: _yRnd(0, w), y: _yRnd(h * 0.45, h * 0.95), vx: _yRnd(-0.26, 0.26), vy: _yRnd(-0.18, 0.18), ph: _yRnd(0, 6.28), f: _yRnd(0.5, 1.15) });
    }
  }
}

function _readAmbientLevel(dt) {
  var st = _ambientState;
  var target = 0;
  if (st.playing) {
    if (st.analyser && st.ampBuf) {
      st.analyser.getByteTimeDomainData(st.ampBuf);
      var sum = 0;
      for (var i = 0; i < st.ampBuf.length; i++) {
        var v = (st.ampBuf[i] - 128) / 128;
        sum += v * v;
      }
      var rms = Math.sqrt(sum / st.ampBuf.length);
      st.peak = Math.max(rms, st.peak * 0.9985, 0.015);
      target = Math.pow(Math.min(1, rms / st.peak), 1.6);
    } else {
      target = 0.42 + 0.24 * Math.sin(st.t * 0.0011) + 0.08 * Math.sin(st.t * 0.0047);
    }
  }
  var k = target > st.level ? 0.3 : 0.07;
  st.level += (target - st.level) * Math.min(1, k * dt);
  st.avg += (st.level - st.avg) * 0.02 * dt;
  st.inten += ((st.playing ? 1 : 0.4) - st.inten) * 0.014 * dt;
}

function _ambientRingCenter(w, h) {
  var el = document.querySelector(".breath-btn, .orb, #miniPlayBtn");
  if (el) {
    var r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) {
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    }
  }
  return { x: w * 0.5, y: h * 0.42 };
}

function _drawAmbientFrame(freeze, dt) {
  var st = _ambientState;
  var g = st.ctx;
  if (!g || !st.canvas) return;
  var w = st.w || window.innerWidth;
  var h = st.h || window.innerHeight;
  var step = freeze ? 0 : (dt || 1);
  var L = st.level;
  var I = st.inten * st.fade;
  var t = st.t;
  var rgb = st.accentRgb;
  var i, q;

  g.clearRect(0, 0, w, h);

  if (st.fxType === "rain") {
    var speed = 0.55 + L * 0.85 + (st.playing ? 0.25 : 0);
    var active = Math.floor(st.p.length * (0.32 + 0.68 * st.inten));
    g.lineCap = "round";
    for (i = 0; i < active; i++) {
      q = st.p[i];
      if (!freeze) {
        var vy = q.sp * (6 + q.z * 8) * speed * step;
        q.y += vy;
        q.x -= vy * 0.12;
        if (q.y > h + 40) { q.y = _yRnd(-80, -10); q.x = _yRnd(0, w * 1.1); }
      }
      g.strokeStyle = "rgba(214,222,255," + (q.a * (0.55 + 0.7 * L) * I).toFixed(3) + ")";
      g.lineWidth = q.wd * (0.6 + q.z * 0.8);
      g.beginPath();
      g.moveTo(q.x, q.y);
      g.lineTo(q.x + q.len * 0.12, q.y - q.len * (0.7 + q.z * 0.6));
      g.stroke();
    }
    for (i = 0; i < st.extra.length; i++) {
      q = st.extra[i];
      if (!freeze) {
        if (q.hold > 0) q.hold -= step * (1 + L * 2);
        else { q.vy = Math.min(3, q.vy + 0.04 * step); q.y += q.vy * step; }
        if (q.y > h + 10) { q.y = _yRnd(-10, h * 0.4); q.x = _yRnd(0, w); q.vy = 0; q.hold = _yRnd(200, 900); }
      }
      var ga = (0.2 + 0.18 * L) * I;
      var gr = g.createRadialGradient(q.x - q.r * 0.3, q.y - q.r * 0.3, 0, q.x, q.y, q.r * 1.6);
      gr.addColorStop(0, "rgba(255,255,255," + (ga * 1.15).toFixed(3) + ")");
      gr.addColorStop(0.5, "rgba(" + rgb + "," + (ga * 0.48).toFixed(3) + ")");
      gr.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = gr;
      g.beginPath();
      g.arc(q.x, q.y, q.r * 1.6, 0, 6.283);
      g.fill();
    }
  } else if (st.fxType === "fire") {
    var flick = 0.5 + 0.5 * Math.sin(t * 0.009) * Math.sin(t * 0.0037);
    var glowA = (0.09 + 0.2 * L + 0.04 * flick) * I;
    var fg = g.createRadialGradient(w * 0.5, h * 1.08, 0, w * 0.5, h * 1.08, h * 0.92);
    fg.addColorStop(0, "rgba(255,160,90," + glowA.toFixed(3) + ")");
    fg.addColorStop(1, "rgba(255,120,60,0)");
    g.fillStyle = fg;
    g.fillRect(0, 0, w, h);
    if (!freeze) {
      var spawn = (0.14 + 1.3 * L) * I * step;
      while (spawn > 0) {
        if (Math.random() < spawn) {
          st.p.push({ x: _yRnd(w * 0.1, w * 0.9), y: h + 6, vx: _yRnd(-0.3, 0.3), vy: _yRnd(-1.5, -0.5), life: 1, dec: _yRnd(0.002, 0.006), r: _yRnd(0.8, 2.1), ph: _yRnd(0, 6.28) });
        }
        spawn -= 1;
      }
    }
    for (i = st.p.length - 1; i >= 0; i--) {
      q = st.p[i];
      if (!freeze) {
        q.x += (q.vx + Math.sin(t * 0.002 + q.ph) * 0.32) * step;
        q.y += q.vy * step * (0.8 + L * 0.6);
        q.life -= q.dec * step;
        if (q.life <= 0 || q.y < -10) { st.p.splice(i, 1); continue; }
      }
      var ea = q.life * (0.55 + 0.45 * Math.sin(t * 0.02 + q.ph)) * I;
      g.fillStyle = "rgba(255,170,100," + (ea * 0.18).toFixed(3) + ")";
      g.beginPath();
      g.arc(q.x, q.y, q.r * 4, 0, 6.283);
      g.fill();
      g.fillStyle = "rgba(255,215,160," + (ea * 0.88).toFixed(3) + ")";
      g.beginPath();
      g.arc(q.x, q.y, q.r, 0, 6.283);
      g.fill();
    }
  } else if (st.fxType === "water") {
    for (var layer = 0; layer < 6; layer++) {
      var y0 = h * (0.62 + layer * 0.06);
      var amp = (2 + layer * 1.5) * (0.5 + L * 1.3);
      var sp = 0.0006 + layer * 0.00012;
      g.strokeStyle = "rgba(" + rgb + "," + ((0.045 + 0.055 * L) * I * (1 - layer * 0.08)).toFixed(3) + ")";
      g.lineWidth = 1;
      g.beginPath();
      for (var x = -20; x <= w + 20; x += 18) {
        var y = y0 + Math.sin(x * (0.006 - layer * 0.0004) + t * sp + layer) * amp + Math.sin(x * 0.017 + t * sp * 1.7) * amp * 0.35;
        if (x === -20) g.moveTo(x, y); else g.lineTo(x, y);
      }
      g.stroke();
    }
    for (i = 0; i < st.p.length; i++) {
      q = st.p[i];
      var s = Math.sin(t * 0.002 * q.f + q.ph);
      if (s < 0.32) continue;
      var sa = (s - 0.32) * (0.38 + 0.75 * L) * I;
      g.fillStyle = "rgba(235,240,255," + sa.toFixed(3) + ")";
      g.fillRect(q.x + Math.sin(t * 0.0005 + q.ph) * 8, q.y, q.r * 3, q.r * 0.7);
    }
  } else if (st.fxType === "wind") {
    for (i = 0; i < st.extra.length; i++) {
      q = st.extra[i];
      if (!freeze) {
        q.x += q.vx * (0.6 + L * 1.5) * step;
        if (q.x - q.r > w) q.x = -q.r;
      }
      var mg = g.createRadialGradient(q.x, q.y, 0, q.x, q.y, q.r);
      mg.addColorStop(0, "rgba(220,226,240," + (q.a * (0.6 + 0.6 * L) * I).toFixed(3) + ")");
      mg.addColorStop(1, "rgba(220,226,240,0)");
      g.fillStyle = mg;
      g.fillRect(q.x - q.r, q.y - q.r, q.r * 2, q.r * 2);
    }
    for (i = 0; i < st.p.length; i++) {
      q = st.p[i];
      if (!freeze) {
        q.x += q.vx * (0.5 + L * 2.0) * step;
        q.y += Math.sin(t * 0.0012 + q.ph) * 0.24 * step;
        if (q.x > w + 10) { q.x = -10; q.y = _yRnd(0, h); }
      }
      g.fillStyle = "rgba(240,236,220," + (q.a * (0.5 + 0.6 * L) * I).toFixed(3) + ")";
      g.beginPath();
      g.arc(q.x, q.y, q.r, 0, 6.283);
      g.fill();
    }
  } else if (st.fxType === "asmr") {
    for (i = 0; i < st.p.length; i++) {
      q = st.p[i];
      if (!freeze) {
        q.x += q.vx * step;
        q.y += q.vy * step * (0.6 + L);
        if (q.y < -10) { q.y = h + 10; q.x = _yRnd(0, w); }
      }
      g.fillStyle = "rgba(" + rgb + "," + (q.a * (0.5 + 0.5 * Math.sin(t * 0.002 + q.ph)) * I).toFixed(3) + ")";
      g.beginPath();
      g.arc(q.x, q.y, q.r, 0, 6.283);
      g.fill();
    }
    if (!freeze) {
      var onset = st.playing && (L - st.avg > 0.12) && (t - st.lastRing > 220);
      var idle = t - st.lastRing > (st.playing ? 1900 : 4200);
      if (onset || idle) {
        st.lastRing = t;
        var oc = _ambientRingCenter(w, h);
        st.rings.push({ x: oc.x, y: oc.y, r: 36, a: onset ? 0.25 + L * 0.28 : 0.12 });
      }
      for (i = st.rings.length - 1; i >= 0; i--) {
        q = st.rings[i];
        q.r += (0.85 + L * 1.5) * step;
        q.a *= Math.pow(0.988, step);
        if (q.a < 0.008) { st.rings.splice(i, 1); continue; }
        g.strokeStyle = "rgba(" + rgb + "," + (q.a * st.fade).toFixed(3) + ")";
        g.lineWidth = 1;
        g.beginPath();
        g.arc(q.x, q.y, q.r, 0, 6.283);
        g.stroke();
      }
    }
  } else if (st.fxType === "bed") {
    var br = 0.5 + 0.5 * Math.sin(t * 0.00063);
    for (i = 0; i < st.extra.length; i++) {
      q = st.extra[i];
      if (!freeze) {
        q.x += q.vx * step;
        if (q.x < -q.r) q.x = w + q.r;
        if (q.x > w + q.r) q.x = -q.r;
      }
      var bg2 = g.createRadialGradient(q.x, q.y, 0, q.x, q.y, q.r * (0.9 + 0.14 * br));
      bg2.addColorStop(0, "rgba(" + rgb + "," + (q.a * (0.7 + 0.75 * L + 0.35 * br) * I).toFixed(3) + ")");
      bg2.addColorStop(1, "rgba(" + rgb + ",0)");
      g.fillStyle = bg2;
      g.fillRect(q.x - q.r * 1.2, q.y - q.r * 1.2, q.r * 2.4, q.r * 2.4);
    }
  } else {
    // night: 星光与萤火
    for (i = 0; i < st.p.length; i++) {
      q = st.p[i];
      var tw = freeze ? 0.7 : (0.5 + 0.5 * Math.sin(t * 0.0015 * q.f + q.ph));
      g.fillStyle = "rgba(240,236,255," + ((0.14 + 0.5 * tw) * I).toFixed(3) + ")";
      g.beginPath();
      g.arc(q.x, q.y, q.r, 0, 6.283);
      g.fill();
    }
    for (i = 0; i < st.extra.length; i++) {
      q = st.extra[i];
      if (!freeze) {
        q.vx += _yRnd(-0.018, 0.018) * step;
        q.vy += _yRnd(-0.018, 0.018) * step;
        q.vx = Math.max(-0.36, Math.min(0.36, q.vx));
        q.vy = Math.max(-0.28, Math.min(0.28, q.vy));
        q.x += q.vx * step;
        q.y += q.vy * step;
        if (q.x < -20) q.x = w + 20;
        if (q.x > w + 20) q.x = -20;
        if (q.y < h * 0.35) q.vy += 0.02;
        if (q.y > h) q.vy -= 0.02;
      }
      var blink = freeze ? 0.6 : Math.max(0, Math.sin(t * 0.0018 * q.f + q.ph));
      var fa = blink * (0.32 + 0.62 * L) * I;
      if (fa < 0.01) continue;
      var ff = g.createRadialGradient(q.x, q.y, 0, q.x, q.y, 14);
      ff.addColorStop(0, "rgba(233,220,166," + (fa * 0.85).toFixed(3) + ")");
      ff.addColorStop(1, "rgba(210,200,130,0)");
      g.fillStyle = ff;
      g.beginPath();
      g.arc(q.x, q.y, 14, 0, 6.283);
      g.fill();
    }
  }
}

function _tickAmbient(now) {
  var st = _ambientState;
  if (st.reducedMotion) {
    st.rafId = null;
    return;
  }
  var ts = typeof now === "number" ? now : performance.now();
  var dt = st.last ? Math.min(3, (ts - st.last) / 16.67) : 1;
  st.last = ts;
  st.t = ts;

  if (st.fadingOut) {
    st.fade -= 0.025 * dt;
    if (st.fade <= 0) {
      st.fade = 0;
      st.fadingOut = false;
      _buildAmbientFx(st.nextFxType);
    }
  } else if (st.fade < 1) {
    st.fade = Math.min(1, st.fade + 0.015 * dt);
  }

  _readAmbientLevel(dt);
  _drawAmbientFrame(false, dt);
  document.documentElement.style.setProperty("--y-lvl", (st.playing ? st.level : 0).toFixed(3));
  st.rafId = requestAnimationFrame(_tickAmbient);
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
