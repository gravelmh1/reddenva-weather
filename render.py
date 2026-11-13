"""1080x1350 날씨 카드를 그린다."""
import datetime as dt
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1350
NAVY = (15, 34, 64); ORANGE = (205, 92, 40); BLUE = (70, 120, 190); GRAY = (110, 120, 140)
ROW_COL = [(40, 140, 90), (205, 92, 40), (120, 80, 170)]
FONT_DIRS = [os.environ.get("FONT_DIR", ""), "/usr/share/fonts/opentype/noto", "/usr/share/fonts/truetype/noto",
             "/usr/share/fonts/noto-cjk", "/usr/share/fonts/truetype/noto-cjk"]
HERE = os.path.dirname(os.path.abspath(__file__))


FALLBACK = {"Black": ["Black", "Bold", "Regular"], "Bold": ["Bold", "Regular"],
            "Medium": ["Medium", "Regular"], "Light": ["Light", "DemiLight", "Regular"],
            "DemiLight": ["DemiLight", "Regular"], "Regular": ["Regular"]}


def font(weight, size):
    # 굵기 파일이 없으면(우분투 기본 설치에는 Regular/Bold만 있어요) 가장 가까운 굵기로 대체
    for w in FALLBACK.get(weight, [weight, "Regular"]):
        for d in FONT_DIRS:
            p = os.path.join(d, f"NotoSansCJK-{w}.ttc") if d else ""
            if p and os.path.exists(p):
                return ImageFont.truetype(p, size, index=1)  # index 1 = KR
    raise RuntimeError("Noto Sans CJK 폰트를 찾지 못했어요 (fonts-noto-cjk 설치 필요)")


def fit(d, text, weight, size, maxw, min_size=22):
    while size > min_size and d.textlength(text, font=font(weight, size)) > maxw:
        size -= 2
    return font(weight, size)


def grad(c1, c2):
    g = Image.new("RGB", (W, H)); d = ImageDraw.Draw(g)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3)))
    return g


def wrap(d, t, fn, mw):
    out, cur = [], ""
    sep = " " if " " in t else ""
    for w in (t.split(" ") if sep else list(t)):
        tr = (cur + sep + w) if cur else w
        if d.textlength(tr, font=fn) > mw and cur: out.append(cur); cur = w
        else: cur = tr
    out.append(cur); return out


def palette(grp, hi_c, lo_c):
    if grp in ("rain", "thunder"): return (219, 229, 240), (186, 202, 222)
    if grp == "snow": return (232, 240, 248), (205, 220, 238)
    if lo_c <= 3: return (222, 232, 245), (191, 211, 234)
    if hi_c >= 24: return (255, 238, 205), (255, 214, 160)
    return (255, 233, 199), (255, 214, 168)


def card(out, region, now, p, f, cp, city):
    """폰 화면(인스타 피드)에서 읽히도록 글자를 크게 잡은 레이아웃."""
    lang = cp["lang"]; unit = f["unit"]; u = "°C" if unit == "C" else "°F"
    days = p["days"]; t = f["today"]
    c1, c2 = palette(f["grp"], f["hi_c"], f["lo_c"])
    im = grad(c1, c2); d = ImageDraw.Draw(im, "RGBA")
    d.ellipse([520, 112, 1130, 538], fill=(255, 255, 255, 110))
    d.rectangle([0, 0, W, 110], fill=NAVY + (255,))
    d.text((60, 26), "Red Denva", font=font("Bold", 50), fill="white")
    tag = "오늘의 날씨" if lang == "ko" else "TODAY'S WEATHER"
    tw = d.textlength(tag, font=font("Bold", 36))
    d.rounded_rectangle([W - 60 - tw - 50, 18, W - 60, 92], radius=37, fill=ORANGE + (255,))
    d.text((W - 60 - tw - 25, 28), tag, font=font("Bold", 36), fill="white")
    if lang == "ko":
        datecity = f"{now.month}월 {now.day}일 {'월화수목금토일'[now.weekday()]}요일 · {city}"
        hi_l, lo_l = "오늘 최고", "최저"
    else:
        datecity = f"{now.strftime('%a')}, {now.strftime('%b')} {now.day} · {'LA' if city == 'Los Angeles' else city}"
        hi_l, lo_l = "Today's high", "Low"
    d.text((60, 128), datecity, font=font("Bold", 46), fill=NAVY)
    d.text((60, 190), hi_l, font=font("Bold", 38), fill=(60, 72, 95))
    d.text((52, 218), f"{t['hi']}{u}", font=font("Bold", 180), fill=ORANGE)
    d.text((62, 424), f"{lo_l} {t['lo']}{u}", font=font("Bold", 64), fill=BLUE)
    pose = Image.open(os.path.join(HERE, "assets", "poses", cp["pose"] + ".png")).convert("RGBA")
    s = min(440 / pose.width, 380 / pose.height)
    pose = pose.resize((int(pose.width * s), int(pose.height * s)), Image.LANCZOS).filter(ImageFilter.UnsharpMask(2, 60, 3))
    im.paste(pose, (575 + (470 - pose.width) // 2, 528 - pose.height), pose)
    d = ImageDraw.Draw(im, "RGBA")

    y = 556
    cmp_ = cp.get("compare")
    if cmp_:  # 어제와 비교: 큰 색 띠
        col = {1: ORANGE, -1: BLUE, 0: (80, 140, 110)}[cmp_["tone"]]
        arrow = {1: "▲ ", -1: "▼ ", 0: "＝ "}[cmp_["tone"]]
        txt = arrow + cmp_["text"]
        d.rounded_rectangle([40, y, W - 40, y + 96], radius=48, fill=col + (255,))
        fnt = fit(d, txt, "Bold", 56, W - 40 - 60 - 40, min_size=38)
        tw2 = d.textlength(txt, font=fnt)
        d.text(((W - tw2) / 2, y + 48 - fnt.size * 0.62), txt, font=fnt, fill="white")
        y += 96 + 28
    else:
        y += 6
    for ln in wrap(d, cp["headline"], font("Bold", 54), W - 100)[:2]:
        d.text((50, y), ln, font=font("Bold", 54), fill=NAVY); y += 68
    y += 12
    for i, (lab, txt) in enumerate(cp["card_rows"] if cmp_ else cp["rows"]):
        fl = font("Bold", 34); lw = d.textlength(lab, font=fl) + 40
        d.rounded_rectangle([50, y, 50 + lw, y + 62], radius=31, fill=ROW_COL[i % 3] + (255,)); d.text((70, y + 9), lab, font=fl, fill="white")
        tx = 50 + lw + 20
        d.text((tx, y + 3), txt, font=fit(d, txt, "Bold", 46, W - 40 - tx, min_size=36), fill=NAVY); y += 80

    py = y + 4
    bot = H - 40
    d.rounded_rectangle([30, py, W - 30, bot], radius=36, fill=(255, 255, 255, 255), outline=(238, 220, 205), width=3)
    d.text((64, py + 12), "이번 주 기온" if lang == "ko" else "This week's temps", font=font("Bold", 36), fill=NAVY)
    highs = [x["hi"] for x in days]; lows = [x["lo"] for x in days]; rain = [x["rain"] for x in days]
    labels = []
    for i, x in enumerate(days):
        wd = dt.date.fromisoformat(x["date"]).weekday()
        labels.append(("오늘" if lang == "ko" else "Today") if i == 0 else ("월화수목금토일"[wd] if lang == "ko" else ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][wd]))
    x0, x1 = 120, 960
    y0 = py + 112
    avail = (bot - 28) - y0 - 140          # 아래쪽 요일/비 확률 칸을 뺀 그래프 높이
    y1 = y0 + max(55, min(130, avail))
    vmin, vmax = min(lows) - 4, max(highs) + 2
    ys = lambda v: y1 - (v - vmin) / (vmax - vmin) * (y1 - y0)
    n = len(days); xs = [x0 + i * (x1 - x0) / (n - 1) for i in range(n)]
    d.rounded_rectangle([xs[0] - 52, py + 58, xs[0] + 52, bot - 16], radius=24, fill=(255, 236, 222, 255))
    for i, xx in enumerate(xs): d.line([(xx, ys(highs[i])), (xx, ys(lows[i]))], fill=(225, 225, 232), width=4)
    for arr, col, above in ((highs, ORANGE, True), (lows, BLUE, False)):
        pts = [(xs[i], ys(v)) for i, v in enumerate(arr)]
        d.line(pts, fill=col, width=7, joint="curve")
        for i, (xx, yy) in enumerate(pts):
            d.ellipse([xx - 11, yy - 11, xx + 11, yy + 11], fill="white", outline=col, width=5)
            tt = f"{arr[i]}°"; fv = font("Bold", 36); w2 = d.textlength(tt, font=fv)
            d.text((xx - w2 / 2, yy - 54 if above else yy + 14), tt, font=fv, fill=col)
    ly = y1 + 62
    for i, xx in enumerate(xs):
        w2 = d.textlength(labels[i], font=font("Bold", 38))
        d.text((xx - w2 / 2, ly), labels[i], font=font("Bold", 38), fill=NAVY if i else ORANGE)
        if rain[i] >= 50:
            tt = (f"비 {rain[i]}%" if lang == "ko" else f"{rain[i]}%"); fw = font("Bold", 27); w2 = d.textlength(tt, font=fw)
            d.rounded_rectangle([xx - w2 / 2 - 10, ly + 50, xx + w2 / 2 + 10, ly + 88], radius=19, fill=BLUE + (255,))
            d.text((xx - w2 / 2, ly + 51), tt, font=fw, fill="white")
    d.rectangle([0, H - 22, W, H], fill=ORANGE + (255,))
    im.save(out, "JPEG", quality=92)
