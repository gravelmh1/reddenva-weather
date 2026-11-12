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
    lang = cp["lang"]; unit = f["unit"]; u = "°C" if unit == "C" else "°F"
    days = p["days"]; t = f["today"]
    c1, c2 = palette(f["grp"], f["hi_c"], f["lo_c"])
    im = grad(c1, c2); d = ImageDraw.Draw(im, "RGBA")
    d.ellipse([500, 110, 1120, 640], fill=(255, 255, 255, 110))
    d.rectangle([0, 0, W, 110], fill=NAVY + (255,))
    d.text((60, 30), "Red Denva", font=font("Bold", 44), fill="white")
    tag = "오늘의 날씨" if lang == "ko" else "TODAY'S WEATHER"
    tw = d.textlength(tag, font=font("Bold", 32))
    d.rounded_rectangle([W - 60 - tw - 46, 20, W - 60, 90], radius=35, fill=ORANGE + (255,))
    d.text((W - 60 - tw - 23, 33), tag, font=font("Bold", 32), fill="white")
    if lang == "ko":
        datecity = f"{now.month}월 {now.day}일 {'월화수목금토일'[now.weekday()]}요일 · {city}"
        hi_l, lo_l = "오늘 최고", "최저"
    else:
        datecity = f"{now.strftime('%A')}, {now.strftime('%b')} {now.day} · {city}"
        hi_l, lo_l = "Today's high", "Low"
    d.text((60, 135), datecity, font=font("Bold", 40), fill=NAVY)
    d.text((60, 192), hi_l, font=font("Medium", 30), fill=GRAY)
    d.text((56, 222), f"{t['hi']}{u}", font=font("Bold", 160), fill=ORANGE)
    d.text((62, 415), f"{lo_l} {t['lo']}{u}", font=font("Bold", 54), fill=BLUE)
    pose = Image.open(os.path.join(HERE, "assets", "poses", cp["pose"] + ".png")).convert("RGBA")
    s = min(480 / pose.width, 420 / pose.height)
    pose = pose.resize((int(pose.width * s), int(pose.height * s)), Image.LANCZOS).filter(ImageFilter.UnsharpMask(2, 60, 3))
    im.paste(pose, (560 + (480 - pose.width) // 2, 590 - pose.height), pose)
    d = ImageDraw.Draw(im, "RGBA")
    y = 605
    for ln in wrap(d, cp["headline"], font("Bold", 46), W - 120):
        d.text((60, y), ln, font=font("Bold", 46), fill=NAVY); y += 60
    y += 16
    for i, (lab, txt) in enumerate(cp["rows"]):
        fl = font("Bold", 27); lw = d.textlength(lab, font=fl) + 36
        d.rounded_rectangle([60, y, 60 + lw, y + 48], radius=24, fill=ROW_COL[i] + (255,)); d.text((78, y + 7), lab, font=fl, fill="white")
        tx = 60 + lw + 18
        d.text((tx, y + 4), txt, font=fit(d, txt, "Medium", 34, W - 60 - tx), fill=NAVY); y += 64
    py = y + 6
    d.rounded_rectangle([40, py, W - 40, H - 45], radius=40, fill=(255, 255, 255, 255), outline=(238, 220, 205), width=3)
    d.text((80, py + 16), "이번 주 기온" if lang == "ko" else "This week's temps", font=font("Bold", 32), fill=NAVY)
    highs = [x["hi"] for x in days]; lows = [x["lo"] for x in days]; rain = [x["rain"] for x in days]
    labels = []
    for i, x in enumerate(days):
        wd = dt.date.fromisoformat(x["date"]).weekday()
        labels.append(("오늘" if lang == "ko" else "Today") if i == 0 else ("월화수목금토일"[wd] if lang == "ko" else ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][wd]))
    x0, x1 = 130, 950; y0 = py + 105; y1 = py + 235
    vmin, vmax = min(lows) - 6, max(highs) + 3
    ys = lambda v: y1 - (v - vmin) / (vmax - vmin) * (y1 - y0)
    n = len(days); xs = [x0 + i * (x1 - x0) / (n - 1) for i in range(n)]
    d.rounded_rectangle([xs[0] - 50, py + 60, xs[0] + 50, H - 60], radius=24, fill=(255, 236, 222, 255))
    for i, xx in enumerate(xs): d.line([(xx, ys(highs[i])), (xx, ys(lows[i]))], fill=(225, 225, 232), width=4)
    for arr, col, above in ((highs, ORANGE, True), (lows, BLUE, False)):
        pts = [(xs[i], ys(v)) for i, v in enumerate(arr)]
        d.line(pts, fill=col, width=6, joint="curve")
        for i, (xx, yy) in enumerate(pts):
            d.ellipse([xx - 10, yy - 10, xx + 10, yy + 10], fill="white", outline=col, width=5)
            tt = f"{arr[i]}°"; w2 = d.textlength(tt, font=font("Bold", 29))
            d.text((xx - w2 / 2, yy - 46 if above else yy + 14), tt, font=font("Bold", 29), fill=col)
    ly = y1 + 58
    for i, xx in enumerate(xs):
        w2 = d.textlength(labels[i], font=font("Bold", 32))
        d.text((xx - w2 / 2, ly), labels[i], font=font("Bold", 32), fill=NAVY if i else ORANGE)
        if rain[i] >= 50:
            tt = (f"비 {rain[i]}%" if lang == "ko" else f"Rain {rain[i]}%"); fw = font("Bold", 24); w2 = d.textlength(tt, font=fw)
            d.rounded_rectangle([xx - w2 / 2 - 10, ly + 44, xx + w2 / 2 + 10, ly + 76], radius=16, fill=BLUE + (255,))
            d.text((xx - w2 / 2, ly + 46), tt, font=fw, fill="white")
    d.rectangle([0, H - 24, W, H], fill=ORANGE + (255,))
    im.save(out, "JPEG", quality=92)
