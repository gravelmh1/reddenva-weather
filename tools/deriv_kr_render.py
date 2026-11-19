import sys; sys.path.insert(0, "/home/claude/reddenva-weather")
from datetile import stamp_png
import sys, datetime as dt
sys.path.insert(0, "/tmp/deriv")
from data import ROWS
from data2 import K200
CREDIT=[(dt.date(2000+int(a[:2]),int(a[2:4]),int(a[4:])),int(b)/1e4,int(c)/1e4) for a,b,c in (x.split(",") for x in open("/tmp/deriv/credit1y.txt").read().strip().split(";"))]
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm, ticker
from matplotlib.patches import FancyBboxPatch
for f in ["Regular", "Medium", "Bold", "Black"]: fm.fontManager.addfont(f"/usr/share/fonts/opentype/noto/NotoSansCJK-{f}.ttc")
plt.rcParams.update({"font.family": "Noto Sans CJK JP", "axes.unicode_minus": False})
WD = "월화수목금토일"
def lab(d): return f"{d.month}/{d.day} ({WD[d.weekday()]})"
EXP, BASE, NEXT = dt.date(2026, 9, 10), dt.date(2026, 11, 18), dt.date(2026, 12, 10)
post = [r for r in ROWS if r["date"] > EXP]
for r in post: r["spot"] = K200[r["date"]]; r["basis"] = round(r["close"] - r["spot"], 2)
cum = {"frn": [], "ins": [], "ind": []}; acc = {k: 0 for k in cum}
for r in post:
    for k in cum: acc[k] += r[k]; cum[k].append(acc[k])
last, prev = post[-1], post[-2]
bd = sum(1 for i in range(1, (NEXT - BASE).days + 1) if (BASE + dt.timedelta(i)).weekday() < 5)
BG, CARD, EDGE, WH, GR, UP, DN, GOLD, TEAL, PU = "#f7f8fb", "#ffffff", "#e1e5ee", "#111a2e", "#6f7a90", "#e8343a", "#1f6fe5", "#d9822b", "#14957f", "#7a52c7"
W, Hp = 1080, 1350
def page():
    fig = plt.figure(figsize=(W / 100, Hp / 100), dpi=100, facecolor=BG)
    fy = lambda px: 1 - px / Hp
    T = lambda x, y, s, size=14, w="regular", c=WH, ha="left", va="top": fig.text(x, fy(y), s, fontsize=size, fontweight=w, color=c, ha=ha, va=va)
    return fig, fy, T
from PIL import Image as _I
import numpy as _np
def mascot(fig, fy, name):
    im = _I.open(f"/home/claude/reddenva-weather/assets/poses/{name}.png").convert("RGBA"); im = im.crop(im.getbbox())
    h = 150; w = im.width * h / im.height
    ax = fig.add_axes([0.945 - w / W, fy(22 + h), w / W, h / Hp]); ax.imshow(_np.asarray(im)); ax.axis("off")
def head(T, fig, fy, n):
    T(0.19, 46, f"DERIVATIVES WEEKLY   ·   @reddenva.kr   ·   {n}/2", 15, "bold", GOLD)
    mascot(fig, fy, "a06" if n == 1 else "a15")
    T(0.19, 78, "목요일 파생 브리핑", 32, "black")
    T(0.19, 132, f"{lab(BASE)} 한국 장 마감 기준  ·  KOSPI200 선물 12월물", 14.5, c=GR)
    fig.add_artist(plt.Line2D([0.055, 0.945], [fy(170), fy(170)], color=GOLD, lw=2))
def style(a, grid=True):
    a.set_facecolor("none"); a.tick_params(colors=GR, labelsize=12, length=0)
    for s in a.spines.values(): s.set_visible(False)
    if grid: a.grid(axis="y", color=EDGE, lw=0.8)
def chg(v, unit="", pct=None, nd=2):
    a = "▲" if v > 0 else ("▼" if v < 0 else "–"); s = f"{a} {abs(v):.{nd}f}{unit}"
    if pct is not None: s += f"  {pct:+.2f}%"
    return s, (UP if v > 0 else DN if v < 0 else GR)
x = list(range(len(post))); ticks = [i for i in x if (i % 7 == 0 and len(post) - 1 - i >= 4) or i == len(post) - 1]; tl = [f"{post[i]['date'].month}/{post[i]['date'].day}" for i in ticks]
# ---------- page 1
fig, fy, T = page(); head(T, fig, fy, 1)
dF, dS, dB = last["close"] - prev["close"], last["spot"] - prev["spot"], last["basis"] - prev["basis"]
cards = [("K200 선물", f"{last['close']:.2f}", chg(dF, pct=dF / prev["close"] * 100), "12월물 종가"),
         ("K200 현물", f"{last['spot']:.2f}", chg(dS, pct=dS / prev["spot"] * 100), "코스피200 지수"),
         ("베이시스", f"{last['basis']:+.2f}", chg(dB), f"전일 {prev['basis']:+.2f} · " + ("백워데이션" if last["basis"] < 0 else "콘탱고")),
         ("VIX", "25.46", chg(2.55, pct=11.13), "미국 11/17 (화) 종가"),
         ("국고채 10년", "3.966%", chg(-1.9, "bp", nd=1), "11/18 (수) 종가"),
         ("12월 만기", f"D-{bd}", ("거래일 남음", GOLD), f"{lab(NEXT)} 동시만기")]
for i, (t, v, (cs, cc), sub) in enumerate(cards):
    cx = 0.055 + (i % 3) * 0.3; top = 200 + (i // 3) * 214
    fig.add_artist(FancyBboxPatch((cx, fy(top + 196)), 0.285, 196 / Hp, boxstyle="round,pad=0,rounding_size=0.01", transform=fig.transFigure, fc=CARD, ec=EDGE, lw=1.2))
    T(cx + 0.02, top + 20, t, 15, "bold", GR)
    T(cx + 0.02, top + 52, v, 38, "black", WH)
    T(cx + 0.02, top + 118, cs, 21, "black", cc)
    T(cx + 0.02, top + 160, sub, 12, c=GR)
y1 = 652
T(0.055, y1, "9월 만기 이후 선물 · 현물 · 베이시스", 21, "black")
T(0.055, y1 + 36, f"{lab(post[0]['date'])} ~ {lab(BASE)} 일별 종가", 13, c=GR)
ax = fig.add_axes([0.1, fy(y1 + 390), 0.82, 320 / Hp])
ax.plot(x, [r["close"] for r in post], color=GOLD, lw=2.8, label="선물 12월물")
ax.plot(x, [r["spot"] for r in post], color=WH, lw=1.6, alpha=0.9, label="현물 K200")
ax.annotate(f"{last['close']:.2f}", (x[-1], last["close"]), xytext=(6, 8), textcoords="offset points", color=GOLD, fontsize=12.5, fontweight="bold")
ax.annotate(f"{last['spot']:.2f}", (x[-1], last["spot"]), xytext=(6, -16), textcoords="offset points", color=WH, fontsize=12.5, fontweight="bold")
style(ax); ax.set_xticks(ticks); ax.set_xticklabels([]); ax.set_xlim(-0.6, len(post) + 3)
ax.legend(loc="upper right", frameon=False, fontsize=12, ncol=2, labelcolor=WH)
axb = fig.add_axes([0.1, fy(y1 + 600), 0.82, 175 / Hp])
bv = [r["basis"] for r in post]; axb.bar(x, bv, color=[UP if v > 0 else DN for v in bv], width=0.7)
axb.axhline(0, color=GR, lw=0.8); style(axb); axb.set_xlim(-0.6, len(post) + 3)
axb.set_xticks(ticks); axb.set_xticklabels(tl, color=GR)
T(0.1, y1 + 404, "베이시스 (pt)   빨강 콘탱고 · 파랑 백워데이션", 12, c=GR)
axb.annotate(f"{last['basis']:+.2f}", (x[-1], last["basis"]), xytext=(4, -16), textcoords="offset points", color=DN, fontsize=12, fontweight="bold")
T(0.055, Hp - 34, "자료: 다음 금융(선물·현물), Investing.com(VIX·국고채)", 11.5, c=GR)
fig.savefig("/tmp/deriv/thu_1.png", facecolor=BG); plt.close(fig); stamp_png("/tmp/deriv/thu_1.png", "kr")
# ---------- page 2
fig, fy, T = page(); head(T, fig, fy, 2)
y2 = 200
T(0.055, y2, "만기 이후 투자자별 선물 누적 순매수", 21, "black")
T(0.055, y2 + 36, "9/11 (금)부터 일별 순매수를 더한 값 · 단위 계약", 13, c=GR)
for i, (k, name, c) in enumerate((("frn", "외국인", UP if cum["frn"][-1] > 0 else DN), ("ins", "기관", UP if cum["ins"][-1] > 0 else DN), ("ind", "개인", UP if cum["ind"][-1] > 0 else DN))):
    T(0.055 + i * 0.3, y2 + 72, name, 15, "bold", GR); T(0.055 + i * 0.3, y2 + 96, f"{cum[k][-1]:+,}", 30, "black", c)
ax2 = fig.add_axes([0.11, fy(y2 + 500), 0.81, 350 / Hp])
ax2.axhline(0, color=GR, lw=0.8)
ax2.plot(x, cum["frn"], color=GOLD, lw=3, label="외국인"); ax2.plot(x, cum["ins"], color=TEAL, lw=2.2, label="기관"); ax2.plot(x, cum["ind"], color=PU, lw=1.8, label="개인")
style(ax2); ax2.set_xticks(ticks); ax2.set_xticklabels(tl, color=GR); ax2.set_xlim(-0.6, len(post) + 1)
ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, p: f"{int(v):,}")); ax2.legend(loc="upper left", frameon=False, fontsize=12, ncol=3, labelcolor=WH)
y3 = 790
cl, pk = CREDIT[-1], max(CREDIT, key=lambda r: r[1] + r[2]); cp = CREDIT[-2]
T(0.055, y3, "신용거래융자 잔고", 21, "black")
T(0.055, y3 + 36, f"최근 1년 · 단위 조원 · 금융투자협회 · {lab(cl[0])} 기준", 13, c=GR)
for i, (name, v, dv, c) in enumerate((("코스피", cl[1], cl[1] - cp[1], WH), ("코스닥", cl[2], cl[2] - cp[2], PU))):
    T(0.055 + i * 0.3, y3 + 72, name, 15, "bold", GR); T(0.055 + i * 0.3, y3 + 96, f"{v:.2f}", 30, "black", c)
    s, cc = chg(dv * 10000, "억", nd=0); s = s.replace(f"{abs(dv*10000):.0f}", f"{abs(dv*10000):,.0f}"); T(0.055 + i * 0.3 + 0.13, y3 + 108, s, 15, "bold", cc)
tot = (cl[1] + cl[2]) - (pk[1] + pk[2]); T(0.655, y3 + 72, f"합계 · {str(pk[0].year)[2:]}.{pk[0].month}.{pk[0].day} 고점 대비", 15, "bold", GR); T(0.655, y3 + 96, f"{tot:+.2f}조", 30, "black", DN)
ax3 = fig.add_axes([0.11, fy(y3 + 470), 0.74, 300 / Hp]); cx3 = list(range(len(CREDIT)))
ax3.plot(cx3, [r[1] for r in CREDIT], color=WH, lw=2.6, label="코스피 (좌)")
ax3b = ax3.twinx(); ax3b.plot(cx3, [r[2] for r in CREDIT], color=PU, lw=2.2, label="코스닥 (우)")
ei = None
for a in (ax3, ax3b): style(a, a is ax3)
ct=[]; seen=set()
for i,r in enumerate(CREDIT):
    k=(r[0].year,r[0].month)
    if k not in seen and r[0].month%2==1: seen.add(k); ct.append(i)
ax3.set_xticks(ct); ax3.set_xticklabels([f"{str(CREDIT[i][0].year)[2:]}.{CREDIT[i][0].month}" for i in ct], color=GR); ax3.set_xlim(-1, len(CREDIT) + 1)
h1, l1 = ax3.get_legend_handles_labels(); h2, l2 = ax3b.get_legend_handles_labels(); ax3.legend(h1 + h2, l1 + l2, loc="lower center", frameon=False, fontsize=12, ncol=2, labelcolor=WH)
T(0.055, Hp - 34, "자료: 다음 금융(투자자별 선물 순매수), 금융투자협회 FreeSIS(신용공여)", 11.5, c=GR)
fig.savefig("/tmp/deriv/thu_2.png", facecolor=BG); plt.close(fig); stamp_png("/tmp/deriv/thu_2.png", "kr")
