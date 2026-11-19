"""목요일 미국 파생 브리핑 (Thursday Derivatives Briefing, @reddenva.us). 2장짜리.
공식 공개 자료: FRED(S&P 500·VIX·미국채 10년), CFTC TFF(E-mini S&P 500 포지션), FINRA(신용융자). ES 선물만 Yahoo(비공식).
  python deriv_us.py [--dry-run] [--force]
결과: out/deriv-us-YYYY-MM-DD-1.jpg, -2.jpg, out/deriv-us-latest.json (image_url, image_url2)
"""
import argparse, datetime as dt, io, json, os, subprocess, time
from datetile import stamp_png
from zoneinfo import ZoneInfo
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm, ticker
from matplotlib.patches import FancyBboxPatch
from PIL import Image
import numpy as np
from books import git_push

UA = {"User-Agent": "RedDenvaBot/1.0 (https://github.com/gravelmh1/reddenva-weather)"}
NYSE_HOL = {dt.date(*d) for d in [(2026, 11, 26), (2026, 12, 25), (2027, 1, 1), (2027, 1, 18), (2027, 2, 15), (2027, 3, 26), (2027, 5, 31), (2027, 6, 18), (2027, 7, 5), (2027, 9, 6), (2027, 11, 25), (2027, 12, 24)]}


def fetch():
    d = {}
    start = (dt.date.today() - dt.timedelta(days=150)).isoformat()
    d["fred"] = {}
    for sid in ("SP500", "VIXCLS", "DGS10"):
        r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": sid, "cosd": start}, headers=UA, timeout=40); r.raise_for_status()
        rows = [ln.split(",") for ln in r.text.strip().splitlines()[1:]]
        d["fred"][sid] = [[a, float(b)] for a, b in rows if b not in (".", "")]
        print(sid, d["fred"][sid][-2:])
    r = requests.get("https://publicreporting.cftc.gov/resource/gpe5-46if.json", params={"cftc_contract_market_code": "13874A", "$order": "report_date_as_yyyy_mm_dd DESC", "$limit": 20}, headers=UA, timeout=40); r.raise_for_status()
    d["cot"] = r.json(); print("COT", d["cot"][0]["report_date_as_yyyy_mm_dd"])
    r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/ES=F", params={"range": "6mo", "interval": "1d"}, headers={"User-Agent": "Mozilla/5.0"}, timeout=40); r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    d["es"] = [[dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"), c] for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"]) if c]
    print("ES", d["es"][-2:])
    r = requests.get("https://www.finra.org/rules-guidance/key-topics/margin-accounts/margin-statistics", headers={"User-Agent": "Mozilla/5.0"}, timeout=40); r.raise_for_status()
    import pandas as pd
    d["finra"] = pd.read_html(io.StringIO(r.text))[0].head(13).astype(str).values.tolist(); print("FINRA", d["finra"][0][:2])
    return d


def third_friday(y, m):
    f = dt.date(y, m, 1); f += dt.timedelta((4 - f.weekday()) % 7); return f + dt.timedelta(14)


def expiries(base):
    qs = [third_friday(y, m) for y in (base.year - 1, base.year, base.year + 1) for m in (3, 6, 9, 12)]
    return max(q for q in qs if q < base), min(q for q in qs if q > base)


P = lambda s: dt.date.fromisoformat(s[:10])
def lab(d): return f"{d:%b} {d.day} ({d:%a})"
BG, CARD, EDGE, WH, GR, UP, DN, GOLD, TEAL, PU = "#f7f8fb", "#ffffff", "#e1e5ee", "#111a2e", "#6f7a90", "#14935f", "#e0343a", "#d9822b", "#14957f", "#7a52c7"
W, Hp = 1080, 1350
for f in ["Regular", "Medium", "Bold", "Black"]:
    p = f"/usr/share/fonts/opentype/noto/NotoSansCJK-{f}.ttc"
    if os.path.exists(p): fm.fontManager.addfont(p)
plt.rcParams.update({"font.family": "Noto Sans CJK JP", "axes.unicode_minus": False})


def render(D, out1, out2):
    spx = {P(a): b for a, b in D["fred"]["SP500"]}; es = {P(a): b for a, b in D["es"]}
    common = sorted(d for d in spx if d in es)
    BASE = common[-1]; EXP, NEXT = expiries(BASE)
    post = [{"date": d, "fut": es[d], "spot": spx[d], "basis": round(es[d] - spx[d], 2)} for d in common if EXP < d <= BASE]
    last, prev = post[-1], post[-2]
    bd = sum(1 for i in range(1, (NEXT - BASE).days + 1) if (BASE + dt.timedelta(i)).weekday() < 5 and BASE + dt.timedelta(i) not in NYSE_HOL)
    vix = D["fred"]["VIXCLS"]; v_last, v_prev = (P(vix[-1][0]), vix[-1][1]), vix[-2][1]
    ten = D["fred"]["DGS10"]; t_last, t_prev = (P(ten[-1][0]), ten[-1][1]), ten[-2][1]
    xm = f"{EXP:%b}" if EXP.month != 9 else "Sept"; nm = f"{NEXT:%b}"

    def page():
        fig = plt.figure(figsize=(W / 100, Hp / 100), dpi=100, facecolor=BG); fy = lambda px: 1 - px / Hp
        T = lambda x, y, s, size=14, w="regular", c=WH, ha="left", va="top": fig.text(x, fy(y), s, fontsize=size, fontweight=w, color=c, ha=ha, va=va)
        return fig, fy, T

    def head(fig, fy, T, n):
        T(0.19, 46, f"DERIVATIVES WEEKLY   ·   @reddenva.us   ·   {n}/2", 15, "bold", GOLD)
        T(0.19, 78, "Thursday Derivatives Briefing", 28, "black")
        T(0.19, 132, f"As of {lab(BASE)} US close  ·  E-mini S&P 500, front month", 14.5, c=GR)
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

    x = list(range(len(post))); ticks = [i for i in x if i % 7 == 0 or i == len(post) - 1]; tl = [f"{post[i]['date'].month}/{post[i]['date'].day}" for i in ticks]
    fig, fy, T = page(); head(fig, fy, T, 1)
    dF, dS, dB, dV = last["fut"] - prev["fut"], last["spot"] - prev["spot"], last["basis"] - prev["basis"], v_last[1] - v_prev
    cards = [("ES futures", f"{last['fut']:,.2f}", chg(dF, pct=dF / prev["fut"] * 100), "Front-month close"),
             ("S&P 500", f"{last['spot']:,.2f}", chg(dS, pct=dS / prev["spot"] * 100), "Cash index close"),
             ("Basis", f"{last['basis']:+.2f}", chg(dB), f"Prior {prev['basis']:+.2f} · {'contango' if last['basis'] > 0 else 'backwardation'}"),
             ("VIX", f"{v_last[1]:.2f}", chg(dV, pct=dV / v_prev * 100), f"{lab(v_last[0])} close"),
             ("US 10Y", f"{t_last[1]:.2f}%", chg((t_last[1] - t_prev) * 100, "bp", nd=0), f"{lab(t_last[0])} · Treasury"),
             (f"{nm} expiry", f"D-{bd}", ("trading days", GOLD), f"{lab(NEXT)} quad witching")]
    for i, (t, v, (cs, cc), sub) in enumerate(cards):
        cx = 0.055 + (i % 3) * 0.3; top = 200 + (i // 3) * 214
        fig.add_artist(FancyBboxPatch((cx, fy(top + 196)), 0.285, 196 / Hp, boxstyle="round,pad=0,rounding_size=0.01", transform=fig.transFigure, fc=CARD, ec=EDGE, lw=1.2))
        T(cx + 0.02, top + 20, t, 15, "bold", GR); T(cx + 0.02, top + 52, v, 36, "black", WH); T(cx + 0.02, top + 118, cs, 21, "black", cc); T(cx + 0.02, top + 160, sub, 12, c=GR)
    y1 = 652
    T(0.055, y1, f"Futures vs. cash since the {xm} expiry", 21, "black")
    T(0.055, y1 + 36, f"{lab(post[0]['date'])} – {lab(BASE)}, daily closes", 13, c=GR)
    ax = fig.add_axes([0.11, fy(y1 + 390), 0.81, 320 / Hp])
    ax.plot(x, [r["fut"] for r in post], color=GOLD, lw=2.8, label="ES front"); ax.plot(x, [r["spot"] for r in post], color=WH, lw=1.6, label="S&P 500")
    ax.annotate(f"{last['fut']:,.0f}", (x[-1], last["fut"]), xytext=(6, 8), textcoords="offset points", color=GOLD, fontsize=12.5, fontweight="bold")
    ax.annotate(f"{last['spot']:,.0f}", (x[-1], last["spot"]), xytext=(6, -16), textcoords="offset points", color=WH, fontsize=12.5, fontweight="bold")
    style(ax); ax.set_xticks(ticks); ax.set_xticklabels([]); ax.set_xlim(-0.6, len(post) + 3); ax.legend(loc="upper left", frameon=False, fontsize=12, ncol=2)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, p: f"{int(v):,}"))
    T(0.11, y1 + 404, "Basis (pts)   green = contango · red = backwardation", 12, c=GR)
    axb = fig.add_axes([0.11, fy(y1 + 600), 0.81, 175 / Hp])
    bv = [r["basis"] for r in post]; axb.bar(x, bv, color=[UP if v > 0 else DN for v in bv], width=0.7)
    axb.axhline(0, color=GR, lw=0.8); style(axb); axb.set_xlim(-0.6, len(post) + 3); axb.set_xticks(ticks); axb.set_xticklabels(tl, color=GR)
    axb.annotate(f"{last['basis']:+.1f}", (x[-1], last["basis"]), xytext=(4, 4), textcoords="offset points", color=UP if last["basis"] > 0 else DN, fontsize=12, fontweight="bold")
    T(0.055, Hp - 34, "Sources: FRED (S&P 500, VIX, 10Y), Yahoo Finance (ES)", 11.5, c=GR)
    fig.savefig("/tmp/_d1.png", facecolor=BG); plt.close(fig); stamp_png("/tmp/_d1.png", "us")

    cot = sorted(D["cot"], key=lambda c: c["report_date_as_yyyy_mm_dd"]); cd = [P(c["report_date_as_yyyy_mm_dd"]) for c in cot]
    net = {k: [int(c[f"{p}_long{s}"]) - int(c[f"{p}_short{s}"]) for c in cot] for k, p, s in (("lev", "lev_money_positions", ""), ("am", "asset_mgr_positions", ""), ("dl", "dealer_positions", "_all"))}
    i0 = max([i for i, d in enumerate(cd) if d <= EXP + dt.timedelta(4)] or [0])
    fig, fy, T = page(); head(fig, fy, T, 2)
    y2 = 200
    T(0.055, y2, "E-mini S&P 500 net positions (CFTC)", 21, "black")
    T(0.055, y2 + 36, f"Contracts · weekly, latest report {lab(cd[-1])} · change vs. {lab(cd[i0])}", 13, c=GR)
    for j, (k, name) in enumerate((("lev", "Leveraged funds"), ("am", "Asset managers"), ("dl", "Dealers"))):
        v, dv = net[k][-1], net[k][-1] - net[k][i0]; s, c = chg(dv, nd=0)
        T(0.055 + j * 0.3, y2 + 72, name, 15, "bold", GR); T(0.055 + j * 0.3, y2 + 96, f"{v:+,}", 28, "black", WH); T(0.055 + j * 0.3, y2 + 140, s, 15, "bold", c)
    ax2 = fig.add_axes([0.13, fy(y2 + 520), 0.79, 330 / Hp]); cx = list(range(len(cd)))
    ax2.axhline(0, color=GR, lw=0.8)
    for k, name, c in (("am", "Asset managers", GOLD), ("lev", "Leveraged funds", TEAL), ("dl", "Dealers", PU)): ax2.plot(cx, net[k], color=c, lw=2.6, marker="o", ms=4, label=name)
    if i0 > 0: ax2.axvline(i0 - 0.5, color=GR, lw=0.9, ls=":"); ax2.text(i0 - 0.4, ax2.get_ylim()[1], f"{xm} expiry", fontsize=11, color=GR, va="top")
    style(ax2); ax2.set_xticks(cx[::2]); ax2.set_xticklabels([f"{d.month}/{d.day}" for d in cd[::2]], color=GR)
    ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, p: f"{int(v/1000):,}k")); ax2.legend(loc="center left", frameon=False, fontsize=12, ncol=3, bbox_to_anchor=(0, 0.62))
    fin = list(reversed(D["finra"][:13])); fmo = [dt.datetime.strptime(r[0], "%b-%y").date() for r in fin]; debit = [float(r[1].replace(",", "")) / 1e6 for r in fin]
    y3 = 790
    T(0.055, y3, "Margin debt (FINRA)", 21, "black")
    T(0.055, y3 + 36, "Debit balances in customers' margin accounts · $ trillion · monthly, last 13 months", 13, c=GR)
    pk = max(range(len(debit)), key=lambda i: debit[i]); s, c = chg((debit[-1] - debit[-2]) / debit[-2] * 100, "%", nd=1)
    T(0.055, y3 + 72, f"{fmo[-1]:%b %Y}", 15, "bold", GR); T(0.055, y3 + 96, f"${debit[-1]:.2f}T", 30, "black", WH); T(0.25, y3 + 108, s + " m/m", 15, "bold", c)
    if pk != len(debit) - 1:
        s2, c2 = chg((debit[-1] / debit[pk] - 1) * 100, "%", nd=1); T(0.655, y3 + 72, f"vs. {fmo[pk]:%b %Y} peak", 15, "bold", GR); T(0.655, y3 + 96, s2, 26, "black", c2)
    else:
        T(0.655, y3 + 72, "13-month high", 15, "bold", GR); T(0.655, y3 + 96, "Record level", 26, "black", GOLD)
    ax3 = fig.add_axes([0.13, fy(y3 + 470), 0.79, 300 / Hp]); bx = list(range(len(debit)))
    ax3.bar(bx, debit, color=[GOLD if i == len(debit) - 1 else "#c9d2e3" for i in bx], width=0.65)
    for i, v in enumerate(debit): ax3.text(i, v + 0.01, f"{v:.2f}", ha="center", va="bottom", fontsize=10.5, color=WH if i == len(debit) - 1 else GR, fontweight="bold" if i == len(debit) - 1 else "regular")
    style(ax3); ax3.set_ylim(min(debit) * 0.9, max(debit) * 1.06); ax3.set_xticks(bx); ax3.set_xticklabels([f"{d:%b}\n{d:%y}" if d.month == 1 or i == 0 else f"{d:%b}" for i, d in enumerate(fmo)], color=GR, fontsize=11); ax3.set_yticks([])
    T(0.055, Hp - 34, "Sources: CFTC Traders in Financial Futures, FINRA margin statistics", 11.5, c=GR)
    fig.savefig("/tmp/_d2.png", facecolor=BG); plt.close(fig); stamp_png("/tmp/_d2.png", "us")
    for src, dst in (("/tmp/_d1.png", out1), ("/tmp/_d2.png", out2)): Image.open(src).convert("RGB").save(dst, quality=92)
    cap = (f"📊 Thursday Derivatives Briefing · S&P 500 futures, basis, VIX, CFTC positioning, margin debt · as of {lab(BASE)}\n\n"
           "#SP500 #ESfutures #futures #derivatives #VIX #COT #margindebt #reddenva")
    return cap


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    today = dt.datetime.now(ZoneInfo("America/Los_Angeles")).date(); day = today.isoformat()
    os.makedirs("out", exist_ok=True)
    if not a.force and today.weekday() != 3:
        print("목요일이 아님 → 건너뜀"); return
    lp = "out/deriv-us-latest.json"
    if not a.force and os.path.exists(lp) and json.load(open(lp, encoding="utf-8")).get("date") == day:
        print("오늘 이미 만들었음. 건너뜀"); return
    rel = [f"out/deriv-us-{day}-{n}.jpg" for n in (1, 2)]
    cap = render(fetch(), *rel); print(cap)
    if a.dry_run: print("(dry-run) 카드 저장:", rel); return
    git_push(["out"], f"deriv us {day} cards")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    urls = [f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/{sha}/{r}" for r in rel]
    for u in urls:
        for _ in range(12):
            if requests.head(u, timeout=15).ok: break
            time.sleep(5)
    json.dump({"date": day, "image_url": urls[0], "image_url2": urls[1], "caption": cap, "title": "derivatives weekly"}, open(lp, "w", encoding="utf-8"), ensure_ascii=False)
    git_push(["out"], f"deriv us {day} latest.json"); print("저장 완료:", urls)


if __name__ == "__main__":
    main()
