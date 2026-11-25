// 릴스 장면 공통 도구. 모든 움직임은 시간 t(초)만으로 정해진다(같은 t면 같은 화면).
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const easeOut = x => 1 - Math.pow(1 - clamp(x), 3);
const easeInOut = x => { x = clamp(x); return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const back = x => { x = clamp(x); const c = 1.7; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); };
const P = (t, a, b, f = easeOut) => f((t - a) / (b - a));      // a~b초 사이 0→1
const lerp = (a, b, k) => a + (b - a) * k;
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
function set(el, { o, x = 0, y = 0, s = 1, r = 0 } = {}) {
  if (typeof el === "string") el = $(el);
  if (!el) return;
  if (o !== undefined) el.style.opacity = o;
  el.style.transform = `translate(${x}px,${y}px) scale(${s}) rotate(${r}deg)`;
}
// 들어왔다 나가는 등장: in a~a+d, out b~b+d
function inout(t, a, b, d = .45) { return Math.min(P(t, a, a + d), 1 - P(t, b, b + d, easeInOut)); }
const fmt = (v, sign = false) => { v = Math.round(v) || 0; return (sign && v > 0 ? "+" : "") + v.toLocaleString("en-US").replace("-", "−"); };
// 레드덴바 숨쉬기: 시큰둥하게 아주 살짝 위아래
const breathe = (t, amp = 6, per = 2.4) => Math.sin(t / per * Math.PI * 2) * amp;
function waitImages() {
  return Promise.all([...document.images].map(i => i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; })))
    .then(() => document.fonts.ready).then(() => { window.READY = true; });
}
