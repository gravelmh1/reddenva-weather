// 릴스 장면 공통 도구. 모든 움직임은 시간 t(초)만으로 정해진다(같은 t면 같은 화면).
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const easeOut = x => 1 - Math.pow(1 - clamp(x), 3);
const easeInOut = x => { x = clamp(x); return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const back = x => { x = clamp(x); const c = 1.7; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); };
const P = (t, a, b, f = easeOut) => f((t - a) / (b - a));      // a~b초 사이 0→1
const lerp = (a, b, k) => a + (b - a) * k;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
// 강조 표기: [[up:글자]] [[dn:글자]] [[acc:글자]] → 색 입힌 span
const rich = s => esc(s).replace(/\[\[(\w+):(.+?)\]\]/g, '<span class="$1">$2</span>');
function fmtNum(v, dp = 0, sign = false) {
  const r = Number(v.toFixed(dp)); const z = Math.abs(r) < Math.pow(10, -dp) / 2;
  const s = Math.abs(r).toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp });
  return (z ? "" : r < 0 ? "−" : sign ? "+" : "") + s;
}
// 레드덴바 숨쉬기: 시큰둥하게 아주 살짝 위아래
const breathe = (t, amp = 6, per = 2.4) => Math.sin(t / per * Math.PI * 2) * amp;
function waitImages() {
  return Promise.all([...document.images].map(i => i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; })))
    .then(() => document.fonts.ready).then(() => { window.READY = true; });
}
