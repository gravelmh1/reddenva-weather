"""목요일 한국 파생 브리핑 (@reddenva.kr). 2장짜리. 지난 수요일 장 마감 기준.
무료 공개 자료: 네이버 증권(K200 선물·현물, 투자자별 선물 순매수, 국고채 10년), FRED(VIX), 금융투자협회 FreeSIS(신용공여 잔고).
  python deriv_kr.py [--dry-run] [--force] [--mock]
결과: out/deriv-kr-YYYY-MM-DD-1.jpg, -2.jpg, out/deriv-kr-latest.json (image_url, image_url2)
"""
import argparse, datetime as dt, json, os, re, subprocess, time
from zoneinfo import ZoneInfo
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm, ticker
from matplotlib.patches import FancyBboxPatch
from PIL import Image
import numpy as np
from datetile import stamp_png

KST = ZoneInfo("Asia/Seoul")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
KRX_HOL = {dt.date(*d) for d in [(2026, 12, 25), (2026, 12, 31), (2027, 1, 1), (2027, 2, 8), (2027, 2, 9), (2027, 3, 1), (2027, 5, 5), (2027, 5, 13),
                                 (2027, 6, 3), (2027, 8, 16), (2027, 9, 14), (2027, 9, 15), (2027, 9, 16), (2027, 10, 4), (2027, 10, 11), (2027, 12, 31)]}
N = lambda s: int(str(s).replace(",", "").replace("+", ""))
D8 = lambda s: dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def get(url, **kw):
    for i in range(3):
        try:
            r = requests.get(url, headers=H, timeout=30, **kw); r.raise_for_status(); return r
        except Exception:
            if i == 2: raise
            time.sleep(3)


def fchart(sym, n=160):
    t = get("https://fchart.stock.naver.com/sise.nhn", params={"symbol": sym, "timeframe": "day", "count": n, "requestType": 0}).content.decode("euc-kr", "replace")
    return {D8(a.split("|")[0]): float(a.split("|")[4]) for a in re.findall(r'data="([^"]+)"', t)}


def fetch(base):
    """base = 기준일(가장 최근 마감일). 그 이후 데이터는 버린다."""
    d = {}
    fut, spot = fchart("FUT"), fchart("KPI200")
    d["fut"] = {k: v for k, v in fut.items() if k <= base}; d["spot"] = {k: v for k, v in spot.items() if k <= base}
    exp = expiries(base)[0]
    days = sorted(k for k in d["fut"] if exp < k <= base and k in d["spot"])
    d["inv"] = {}
    for k in days:
        j = get("https://m.stock.naver.com/api/index/FUT/trend", params={"bizdate": k.strftime("%Y%m%d")}).json()
        if j.get("bizdate") != k.strftime("%Y%m%d"): continue
        d["inv"][k] = {"frn": N(j["foreignValue"]), "ins": N(j["institutionalValue"]), "ind": N(j["personalValue"])}
        time.sleep(0.15)
    print("투자자별", len(d["inv"]), "일 · 외국인 누적", sum(v["frn"] for v in d["inv"].values()))
    j = get("https://m.stock.naver.com/front-api/marketIndex/prices", params={"category": "bond", "reutersCode": "KR10YT=RR", "page": 1, "pageSize": 10}).json()
    d["ktb"] = [(dt.date.fromisoformat(r["localTradedAt"][:10]), float(r["closePrice"])) for r in j["result"]]
    d["ktb"] = [r for r in d["ktb"] if r[0] <= base]
    r = get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": "VIXCLS", "cosd": (base - dt.timedelta(days=20)).isoformat()})
    d["vix"] = [(dt.date.fromisoformat(a), float(b)) for a, b in (ln.split(",") for ln in r.text.strip().splitlines()[1:]) if b not in (".", "")]
    body = {"dmSearch": {"tmpV40": "1000000", "tmpV41": "1", "tmpV1": "D", "tmpV45": (base - dt.timedelta(days=366)).strftime("%Y%m%d"),
                         "tmpV46": base.strftime("%Y%m%d"), "OBJ_NM": "STATSCU0100000070BO"}}
    r = requests.post("https://freesis.kofia.or.kr/meta/getMetaDataList.do", json=body, headers=dict(H, Referer="https://freesis.kofia.or.kr/"), timeout=40); r.raise_for_status()
    d["credit"] = sorted((D8(x["TMPV1"]), x["TMPV3"] / 1e6, x["TMPV4"] / 1e6) for x in r.json()["ds1"])  # 백만원 → 조원 (코스피, 코스닥)
    print("선물", max(d["fut"]), "· 국고채", d["ktb"][0], "· VIX", d["vix"][-1], "· 신용", d["credit"][-1], len(d["credit"]))
    return d


def mock(base):
    import random; random.seed(3)
    days = [base - dt.timedelta(i) for i in range(120, -1, -1)]; days = [k for k in days if k.weekday() < 5]
    s, d = 600.0, {"fut": {}, "spot": {}, "inv": {}}
    for k in days:
        s *= 1 + random.gauss(0.002, 0.02); d["spot"][k] = round(s, 2); d["fut"][k] = round(s + random.gauss(0.5, 2), 2)
    exp = expiries(base)[0]
    for k in days:
        if k > exp: f = random.randint(-9000, 9000); i = -f + random.randint(-800, 800); d["inv"][k] = {"frn": f, "ins": i, "ind": -f - i}
    d["ktb"] = [(base, 3.807), (base - dt.timedelta(1), 3.823)]
    d["vix"] = [(base - dt.timedelta(2), 22.1), (base - dt.timedelta(1), 23.5)]
    c = [(base - dt.timedelta(i), 20 + 5 * np.sin(i / 40), 6 + np.cos(i / 30)) for i in range(365, 0, -1)]
    d["credit"] = [x for x in c if x[0].weekday() < 5]
    return d


def second_thu(y, m):
    f = dt.date(y, m, 1); f += dt.timedelta((3 - f.weekday()) % 7); return f + dt.timedelta(7)


def expiries(base):
    qs = [second_thu(y, m) for y in (base.year - 1, base.year, base.year + 1) for m in (3, 6, 9, 12)]
    return max(q for q in qs if q < base), min(q for q in qs if q > base)


def last_close(now):
    """지금 시각 기준 가장 최근 장 마감일 (16시 전이면 오늘은 아직)."""
    k = now.date() - dt.timedelta(0 if now.hour >= 16 else 1)
    while k.weekday() >= 5 or k in KRX_HOL: k -= dt.timedelta(1)
    return k


WD = "월화수목금토일"
def lab(k): return f"{k.month}/{k.day} ({WD[k.weekday()]})"
BG, CARD, EDGE, WH, GR, UP, DN, GOLD, TEAL, PU = "#f7f8fb", "#ffffff", "#e1e5ee", "#111a2e", "#6f7a90", "#e8343a", "#1f6fe5", "#d9822b", "#14957f", "#7a52c7"
W, Hp = 1080, 1350
for f in ["Regular", "Medium", "Bold", "Black"]:
    p = f"/usr/share/fonts/opentype/noto/NotoSansCJK-{f}.ttc"
    if os.path.exists(p): fm.fontManager.addfont(p)
plt.rcParams.update({"font.family": "Noto Sans CJK JP", "axes.unicode_minus": False})


def render(D, base, out1, out2):
    EXP, NEXT = expiries(base)
    post = [{"date": k, "close": D["fut"][k], "spot": D["spot"][k], "basis": round(D["fut"][k] - D["spot"][k], 2)} for k in sorted(D["fut"]) if EXP < k <= base and k in D["spot"]]
    last, prev = post[-1], post[-2]
    BASE = last["date"]
    bd = sum(1 for i in range(1, (NEXT - BASE).days + 1) if (BASE + dt.timedelta(i)).weekday() < 5 and BASE + dt.timedelta(i) not in KRX_HOL)
    inv = [(k, D["inv"][k]) for k in sorted(D["inv"]) if EXP < k <= BASE]
    cum = {"frn": [], "ins": [], "ind": []}; acc = {k: 0 for k in cum}
    for _, r in inv:
        for k in cum: acc[k] += r[k]; cum[k].append(acc[k])
    ktb, ktb_p = D["ktb"][0], D["ktb"][1]
    vix, vix_p = D["vix"][-1], D["vix"][-2]
    CREDIT = D["credit"]

    def page():
        fig = plt.figure(figsize=(W / 100, Hp / 100), dpi=100, facecolor=BG); fy = lambda px: 1 - px / Hp
        T = lambda x, y, s, size=14, w="regular", c=WH, ha="left", va="top": fig.text(x, fy(y), s, fontsize=size, fontweight=w, color=c, ha=ha, va=va)
        return fig, fy, T

    def head(fig, fy, T, n):
        T(0.19, 46, f"DERIVATIVES WEEKLY   ·   @reddenva.kr   ·   {n}/2", 15, "bold", GOLD)
        T(0.19, 78, "목요일 파생 브리핑", 32, "black")
        T(0.19, 132, f"{lab(BASE)} 한국 장 마감 기준  ·  KOSPI200 선물 {NEXT.month}월물", 14.5, c=GR)
        fig.add_artist(plt.Line2D([0.055, 0.945], [fy(170), fy(170)], color=GOLD, lw=2))
        im = Image.open(f"assets/poses/{'a06' if n == 1 else 'a15'}.png").convert("RGBA"); im = im.crop(im.getbbox())
        h = 150; w = im.width * h / im.height
        ax = fig.add_axes([0.945 - w / W, fy(22 + h), w / W, h / Hp]); ax.imshow(np.asarray(im)); ax.axis("off")

    def style(a, grid=True):
        a.set_facecolor("none"); a.tick_params(colors=GR, labelsize=12, length=0)
        for s in a.spines.values(): s.set_visible(False)
        if grid: a.grid(axis="y", color=EDGE, lw=0.8)

    def chg(v, unit="", pct=None, nd=2):
        a = "▲" if v > 0 else ("▼" if v < 0 else "–"); s = f"{a} {abs(v):,.{nd}f}{unit}"
        if pct is not None: s += f"  {pct:+.2f}%"
        return s, (UP if v > 0 else DN if v < 0 else GR)

    x = list(range(len(post))); ticks = [i for i in x if (i % 7 == 0 and len(post) - 1 - i >= 4) or i == len(post) - 1]
    tl = [f"{post[i]['date'].month}/{post[i]['date'].day}" for i in ticks]
    # ---------- 1장
    fig, fy, T = page(); head(fig, fy, T, 1)
    dF, dS, dB = last["close"] - prev["close"], last["spot"] - prev["spot"], last["basis"] - prev["basis"]
    cards = [("K200 선물", f"{last['close']:.2f}", chg(dF, pct=dF / prev["close"] * 100), f"{NEXT.month}월물 종가"),
             ("K200 현물", f"{last['spot']:.2f}", chg(dS, pct=dS / prev["spot"] * 100), "코스피200 지수"),
             ("베이시스", f"{last['basis']:+.2f}", chg(dB), f"전일 {prev['basis']:+.2f} · " + ("백워데이션" if last["basis"] < 0 else "콘탱고")),
             ("VIX", f"{vix[1]:.2f}", chg(vix[1] - vix_p[1], pct=(vix[1] - vix_p[1]) / vix_p[1] * 100), f"미국 {lab(vix[0])} 종가"),
             ("국고채 10년", f"{ktb[1]:.3f}%", chg((ktb[1] - ktb_p[1]) * 100, "bp", nd=1), f"{lab(ktb[0])} 종가"),
             (f"{NEXT.month}월 만기", f"D-{bd}", ("거래일 남음", GOLD), f"{lab(NEXT)} " + ("동시만기" if NEXT.month in (3, 6, 9, 12) else "만기"))]
    for i, (t, v, (cs, cc), sub) in enumerate(cards):
        cx = 0.055 + (i % 3) * 0.3; top = 200 + (i // 3) * 214
        fig.add_artist(FancyBboxPatch((cx, fy(top + 196)), 0.285, 196 / Hp, boxstyle="round,pad=0,rounding_size=0.01", transform=fig.transFigure, fc=CARD, ec=EDGE, lw=1.2))
        T(cx + 0.02, top + 20, t, 15, "bold", GR); T(cx + 0.02, top + 52, v, 38, "black", WH); T(cx + 0.02, top + 118, cs, 21, "black", cc); T(cx + 0.02, top + 160, sub, 12, c=GR)
    y1 = 652
    T(0.055, y1, f"{EXP.month}월 만기 이후 선물 · 현물 · 베이시스", 21, "black")
    T(0.055, y1 + 36, f"{lab(post[0]['date'])} ~ {lab(BASE)} 일별 종가", 13, c=GR)
    ax = fig.add_axes([0.1, fy(y1 + 390), 0.82, 320 / Hp])
    ax.plot(x, [r["close"] for r in post], color=GOLD, lw=2.8, label=f"선물 {NEXT.month}월물"); ax.plot(x, [r["spot"] for r in post], color=WH, lw=1.6, alpha=0.9, label="현물 K200")
    hi = last["close"] >= last["spot"]
    ax.annotate(f"{last['close']:.2f}", (x[-1], last["close"]), xytext=(6, 8 if hi else -16), textcoords="offset points", color=GOLD, fontsize=12.5, fontweight="bold")
    ax.annotate(f"{last['spot']:.2f}", (x[-1], last["spot"]), xytext=(6, -16 if hi else 8), textcoords="offset points", color=WH, fontsize=12.5, fontweight="bold")
    style(ax); ax.set_xticks(ticks); ax.set_xticklabels([]); ax.set_xlim(-0.6, len(post) + 3)
    ax.legend(loc="best", frameon=False, fontsize=12, ncol=2, labelcolor=WH)
    axb = fig.add_axes([0.1, fy(y1 + 600), 0.82, 175 / Hp])
    bv = [r["basis"] for r in post]; axb.bar(x, bv, color=[UP if v > 0 else DN for v in bv], width=0.7)
    axb.axhline(0, color=GR, lw=0.8); style(axb); axb.set_xlim(-0.6, len(post) + 3); axb.set_xticks(ticks); axb.set_xticklabels(tl, color=GR)
    T(0.1, y1 + 404, "베이시스 (pt)   빨강 콘탱고 · 파랑 백워데이션", 12, c=GR)
    axb.annotate(f"{last['basis']:+.2f}", (x[-1], last["basis"]), xytext=(4, -16 if last["basis"] < 0 else 4), textcoords="offset points", color=UP if last["basis"] > 0 else DN, fontsize=12, fontweight="bold")
    T(0.055, Hp - 34, "자료: 네이버 증권(선물·현물·국고채), FRED(VIX)  ·  투자 권유 아님", 11.5, c=GR)
    fig.savefig("/tmp/_k1.png", facecolor=BG); plt.close(fig); stamp_png("/tmp/_k1.png", "kr")
    # ---------- 2장
    fig, fy, T = page(); head(fig, fy, T, 2)
    xi = list(range(len(inv))); ti = [i for i in xi if (i % 7 == 0 and len(inv) - 1 - i >= 4) or i == len(inv) - 1]
    y2 = 200
    T(0.055, y2, "만기 이후 투자자별 선물 누적 순매수", 21, "black")
    T(0.055, y2 + 36, f"{lab(inv[0][0])}부터 일별 순매수를 더한 값 · 단위 계약", 13, c=GR)
    for i, (k, name) in enumerate((("frn", "외국인"), ("ins", "기관"), ("ind", "개인"))):
        v = cum[k][-1]; T(0.055 + i * 0.3, y2 + 72, name, 15, "bold", GR); T(0.055 + i * 0.3, y2 + 96, f"{v:+,}", 30, "black", UP if v > 0 else DN if v < 0 else WH)
    ax2 = fig.add_axes([0.11, fy(y2 + 500), 0.81, 350 / Hp])
    ax2.axhline(0, color=GR, lw=0.8)
    ax2.plot(xi, cum["frn"], color=GOLD, lw=3, label="외국인"); ax2.plot(xi, cum["ins"], color=TEAL, lw=2.2, label="기관"); ax2.plot(xi, cum["ind"], color=PU, lw=1.8, label="개인")
    style(ax2); ax2.set_xticks(ti); ax2.set_xticklabels([f"{inv[i][0].month}/{inv[i][0].day}" for i in ti], color=GR); ax2.set_xlim(-0.6, len(inv) + 1)
    ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, p: f"{int(v):,}")); ax2.legend(loc="best", frameon=False, fontsize=12, ncol=3, labelcolor=WH)
    y3 = 790
    cl, cp = CREDIT[-1], CREDIT[-2]; pk = max(CREDIT, key=lambda r: r[1] + r[2])
    T(0.055, y3, "신용거래융자 잔고", 21, "black")
    T(0.055, y3 + 36, f"최근 1년 · 단위 조원 · 금융투자협회 · {lab(cl[0])} 기준", 13, c=GR)
    for i, (name, v, dv, c) in enumerate((("코스피", cl[1], cl[1] - cp[1], WH), ("코스닥", cl[2], cl[2] - cp[2], PU))):
        T(0.055 + i * 0.3, y3 + 72, name, 15, "bold", GR); T(0.055 + i * 0.3, y3 + 96, f"{v:.2f}", 30, "black", c)
        s, cc = chg(dv * 10000, "억", nd=0); T(0.055 + i * 0.3 + 0.13, y3 + 108, s, 15, "bold", cc)
    tot = (cl[1] + cl[2]) - (pk[1] + pk[2])
    if pk[0] != cl[0]:
        T(0.655, y3 + 72, f"합계 · {str(pk[0].year)[2:]}.{pk[0].month}.{pk[0].day} 고점 대비", 15, "bold", GR); T(0.655, y3 + 96, f"{tot:+.2f}조", 30, "black", UP if tot > 0 else DN)
    else:
        T(0.655, y3 + 72, "합계 · 1년 최고치", 15, "bold", GR); T(0.655, y3 + 96, f"{cl[1] + cl[2]:.2f}조", 30, "black", GOLD)
    ax3 = fig.add_axes([0.11, fy(y3 + 470), 0.74, 300 / Hp]); cx3 = list(range(len(CREDIT)))
    ax3.plot(cx3, [r[1] for r in CREDIT], color=WH, lw=2.6, label="코스피 (좌)")
    ax3b = ax3.twinx(); ax3b.plot(cx3, [r[2] for r in CREDIT], color=PU, lw=2.2, label="코스닥 (우)")
    for a in (ax3, ax3b): style(a, a is ax3)
    ct, seen = [], set()
    for i, r in enumerate(CREDIT):
        k = (r[0].year, r[0].month)
        if k not in seen and r[0].month % 2 == 1: seen.add(k); ct.append(i)
    ax3.set_xticks(ct); ax3.set_xticklabels([f"{str(CREDIT[i][0].year)[2:]}.{CREDIT[i][0].month}" for i in ct], color=GR); ax3.set_xlim(-1, len(CREDIT) + 1)
    h1, l1 = ax3.get_legend_handles_labels(); h2, l2 = ax3b.get_legend_handles_labels()
    ax3.legend(h1 + h2, l1 + l2, loc="lower center", frameon=False, fontsize=12, ncol=2, labelcolor=WH)
    T(0.055, Hp - 34, "자료: 네이버 증권(투자자별 선물 순매수), 금융투자협회 FreeSIS(신용공여)  ·  투자 권유 아님", 11.5, c=GR)
    fig.savefig("/tmp/_k2.png", facecolor=BG); plt.close(fig); stamp_png("/tmp/_k2.png", "kr")
    for src, dst in (("/tmp/_k1.png", out1), ("/tmp/_k2.png", out2)): Image.open(src).convert("RGB").save(dst, quality=92)
    import reel_data  # 릴스용 숫자
    reel_data.save("deriv", "kr", {"asof": lab(BASE), "xm": f"{EXP.month}월", "nm": f"{NEXT.month}월", "bd": bd,
                   "tiles": [[t, v, cs, sub, cc] for t, v, (cs, cc), sub in cards], "cum": cum, "cum_last": {k: cum[k][-1] for k in cum},
                   "cards": [os.path.abspath(out1), os.path.abspath(out2)]})
    return (f"목요일 파생 브리핑 · {lab(BASE).replace(' ', '')} 마감 기준\n\n"
            "#파생 #선물 #코스피200 #베이시스 #신용잔고 #레드덴바")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--force", action="store_true"); ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    now = dt.datetime.now(KST); today = now.date(); day = today.isoformat()
    os.makedirs("out", exist_ok=True)
    if not a.force and today.weekday() != 3:
        print("목요일이 아님 → 건너뜀"); return
    lp = "out/deriv-kr-latest.json"
    if not a.force and os.path.exists(lp) and json.load(open(lp, encoding="utf-8")).get("date") == day:
        print("오늘 이미 만들었음. 건너뜀"); return
    base = last_close(now)
    rel = [f"out/deriv-kr-{day}-{n}.jpg" for n in (1, 2)]
    cap = render(mock(base) if a.mock else fetch(base), base, *rel); print(cap)
    if a.dry_run or a.mock: print("(dry-run) 카드 저장:", rel); return
    from books import git_push
    git_push(["out"], f"deriv kr {day} cards")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    urls = [f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/{sha}/{r}" for r in rel]
    for u in urls:
        for _ in range(12):
            if requests.head(u, timeout=15).ok: break
            time.sleep(5)
    json.dump({"date": day, "image_url": urls[0], "image_url2": urls[1], "caption": cap, "title": "derivatives weekly"}, open(lp, "w", encoding="utf-8"), ensure_ascii=False)
    git_push(["out"], f"deriv kr {day} latest.json"); print("저장 완료:", urls)


if __name__ == "__main__":
    main()
