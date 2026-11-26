"""수요일 다트 예측 카드(1080x1350). 이번 주 다트(오른다/내린다) + 지난주 채점 + 누적 적중 전적. 종목은 절대 안 나옴."""
import math, os
from PIL import Image, ImageDraw
from datetile import cream_header
from render import font, fit
from news_render import W, H, M, CREAM, NAVY, OR, GR, LINE, POSES

WHITE = (255, 255, 255)


def colors(region):
    # 한국식 빨강 상승·파랑 하락 / 미국식 초록 상승·빨강 하락
    return ((214, 56, 40), (36, 96, 200)) if region == "kr" else ((30, 140, 90), (214, 56, 40))


def pct(x): return "0.0%" if abs(x) < 5e-4 else f"{x * 100:+.1f}%"


def lvl(v): return f"{v:,.2f}"


def arrow(d, cx, cy, s, up, col):
    """굵은 위/아래 화살표."""
    k = -1 if up else 1
    d.polygon([(cx, cy + k * s), (cx - s * .8, cy + k * s * .1), (cx - s * .32, cy + k * s * .1), (cx - s * .32, cy - k * s),
               (cx + s * .32, cy - k * s), (cx + s * .32, cy + k * s * .1), (cx + s * .8, cy + k * s * .1)], fill=col)


def target(d, cx, cy, r):
    for i, col in enumerate([(214, 56, 40), WHITE, (214, 56, 40), WHITE, (214, 56, 40)]):
        rr = r * (1 - i * .2); d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col, outline=NAVY if i == 0 else None, width=5)
    hx, hy = cx + r * .12, cy - r * .08; ang = math.radians(-35); L = r * 1.05
    tx, ty = hx + L * math.cos(ang), hy + L * math.sin(ang)
    d.line([(hx, hy), (tx, ty)], fill=NAVY, width=12)
    px, py = -math.sin(ang), math.cos(ang)
    for s in (1, -1):
        d.polygon([(tx, ty), (tx - 52 * math.cos(ang) + s * 30 * px, ty - 52 * math.sin(ang) + s * 30 * py), (tx - 36 * math.cos(ang), ty - 36 * math.sin(ang))], fill=OR)


def card(c: dict, out: str):
    region = c["region"]; ko = region == "kr"; upc, dnc = colors(region); idx = c["index_name"]
    im = Image.new("RGB", (W, H), CREAM); d = ImageDraw.Draw(im)
    cream_header(im, d, {"handle": c["handle"], "top": c["top"], "date": c["day"]}, W, M, NAVY, OR)
    badge = f"레드덴바 다트 예측 · {c['week']}주차" if ko else f"Red Denva's dart call · week {c['week']}"
    bf = font("Bold", 30); bw = int(d.textlength(badge, font=bf)) + 64
    d.rounded_rectangle([M, 160, M + bw, 218], radius=29, fill=OR); d.text((M + bw / 2, 189), badge, font=bf, fill=WHITE, anchor="mm")

    # A. 이번 주 다트
    n = c["new"]; up = n["call"] == "up"; col = upc if up else dnc
    q = f"다음 주 수요일까지 {idx}는" if ko else f"By next Wednesday, the {idx} will go"
    d.text((M, 250), q, font=fit(d, q, "Bold", 38, W - 2 * M - 300, 24), fill=NAVY)
    word = ("오른다" if up else "내린다") if ko else ("UP" if up else "DOWN")
    wf = font("Black", 150); d.text((M, 300), word, font=wf, fill=col)
    ww = d.textlength(word, font=wf); arrow(d, M + ww + 80, 395, 62, up, col)
    base = (f"기준 {lvl(n['entry'])} · 다트가 정함" if ko else f"Starting at {lvl(n['entry'])} · a dart decided")
    d.text((M, 500), base, font=font("Medium", 32), fill=GR)
    target(d, W - M - 150, 360, 135)
    p = Image.open(os.path.join(POSES, "a00.png")).convert("RGBA"); p = p.crop(p.getbbox()); k = 170 / p.height
    p = p.resize((int(p.width * k), 170), Image.LANCZOS); im.paste(p, (W - M - 300, 430), p)

    # B. 지난주 채점
    y = 600; h = 360
    d.rounded_rectangle([M, y, W - M, y + h], radius=40, fill=NAVY)
    last = c.get("last")
    if not last:
        d.text((M + 44, y + 44), "지난주 다트" if ko else "Last week's dart", font=font("Bold", 32), fill=(240, 170, 120))
        msg = ["첫 다트.", "채점은 다음 주 수요일에."] if ko else ["First dart.", "Graded next Wednesday."]
        for i, s in enumerate(msg): d.text((M + 44, y + 120 + i * 84), s, font=font("Black", 64), fill=WHITE)
    else:
        lu = last["call"] == "up"
        head = (f"지난주 다트: {'오른다' if lu else '내린다'}" if ko else f"Last week's dart: {'UP' if lu else 'DOWN'}")
        d.text((M + 44, y + 40), head, font=font("Bold", 36), fill=(240, 170, 120))
        r = last["result"]; rc = upc if r > 0 else dnc if r < 0 else WHITE
        d.text((M + 44, y + 100), f"{idx} {pct(r)}", font=fit(d, f"{idx} {pct(r)}", "Black", 88, W - 2 * M - 360, 50), fill=rc)
        d.text((M + 44, y + 210), f"{lvl(last['entry'])} → {lvl(last['exit'])}", font=font("Medium", 32), fill=(200, 208, 225))
        hit = last["hit"]; stamp = ("적중" if hit else "빗나감") if ko else ("HIT" if hit else "MISS")
        sf = font("Black", 64); sw = d.textlength(stamp, font=sf) + 70
        sx, sy = W - M - 44 - sw, y + 96
        d.rounded_rectangle([sx, sy, sx + sw, sy + 110], radius=24, outline=(255, 120, 80) if hit else (150, 160, 180), width=8)
        d.text((sx + sw / 2, sy + 55), stamp, font=sf, fill=(255, 120, 80) if hit else (170, 178, 196), anchor="mm")
        cm = (("레드덴바 감 좋음. 다트 덕분." if hit else "다트 탓. 레드덴바는 잤음.") if ko else ("Nailed it. The dart did.") if hit else "Blame the dart. I was asleep.")
        d.text((M + 44, y + h - 76), cm, font=font("Bold", 36), fill=WHITE)

    # C. 누적 적중 전적
    y = 1000; rec = c["rec"]
    if rec["n"]:
        t = (f"누적 전적  {rec['hit']}승 {rec['miss']}패 · 적중률 {rec['rate'] * 100:.0f}%" if ko else f"Record  {rec['hit']}-{rec['miss']} · {rec['rate'] * 100:.0f}% hit rate")
        d.text((M, y), t, font=fit(d, t, "Black", 46, W - 2 * M, 28), fill=NAVY)
        coin = "동전 던지기는 50%. 레드덴바는 과연." if ko else "A coin flip gets 50%. Let's see."
        d.text((M, y + 66), coin, font=font("Medium", 30), fill=GR)
        x = M; y2 = y + 128
        for hv in rec["streak"]:
            s = ("적중" if hv else "꽝") if ko else ("HIT" if hv else "MISS")
            d.rounded_rectangle([x, y2, x + 64, y2 + 64], radius=16, fill=OR if hv else (205, 205, 210))
            d.text((x + 32, y2 + 32), "○" if hv else "×", font=font("Black", 36), fill=WHITE, anchor="mm"); x += 76
            if x > W - M - 64: break
    else:
        s = "매주 수요일, 다트로 정하는 다음 주 지수 방향." if ko else "Every Wednesday, a dart picks next week's direction."
        d.text((M, y + 20), s, font=fit(d, s, "Bold", 38, W - 2 * M, 22), fill=NAVY)
        s2 = "맞히면 다트 덕, 틀리면 다트 탓." if ko else "Right? The dart. Wrong? Also the dart."
        d.text((M, y + 80), s2, font=font("Medium", 32), fill=GR)
    d.line([(M, H - 84), (W - M, H - 84)], fill=LINE, width=2)
    d.text((M, H - 62), c["foot"], font=fit(d, c["foot"], "Medium", 22, W - 2 * M, 15), fill=GR)
    im.save(out, quality=92)
