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


def card_old(out, region, now, p, f, cp, city):
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


# ---------------- 시안 B (2026-11-17 형 확정): 남색 띠 + 달력 날짜, 출근길 어제→오늘 비교, 어제부터 시작하는 주간 ----------------
INK = (18, 30, 52); SUB = (92, 102, 122); UP = (214, 66, 26); DN = (24, 96, 200); OK = (36, 128, 84)
BAND = (20, 40, 78); BG = (244, 246, 250); SAT = (24, 96, 200); SUN = (214, 40, 40)
WD_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _ctext(d, cx, y, t, fn, fill):
    d.text((cx - d.textlength(t, font=fn) / 2, y), t, font=fn, fill=fill)


def _icon(d, cx, cy, s, code):
    """날씨 코드 → 작은 그림 (해·구름·비·눈·번개·안개). 이모지 폰트 없이 도형으로 그린다."""
    import math
    SUNC, CL, CLD = (255, 176, 32), (176, 186, 202), (128, 140, 160)
    RAIN, BOLT = (36, 112, 220), (255, 196, 0)

    def sun(x, y, r):
        for k in range(8):
            a = k * math.pi / 4
            d.line([x + math.cos(a) * r * 1.35, y + math.sin(a) * r * 1.35, x + math.cos(a) * r * 1.85, y + math.sin(a) * r * 1.85], fill=SUNC, width=max(3, int(s * .07)))
        d.ellipse([x - r, y - r, x + r, y + r], fill=SUNC)

    def cloud(x, y, w, col):
        h = w * .42
        d.ellipse([x - w * .5, y - h * .1, x - w * .05, y + h * .75], fill=col)
        d.ellipse([x - w * .28, y - h * .75, x + w * .22, y + h * .55], fill=col)
        d.ellipse([x + w * .02, y - h * .35, x + w * .5, y + h * .75], fill=col)
        d.rounded_rectangle([x - w * .5, y + h * .2, x + w * .5, y + h * .75], radius=int(h * .3), fill=col)

    heavy = code in (65, 67, 82, 75, 86) or code >= 95
    if code == 0:
        sun(cx, cy, s * .28)
    elif code in (1, 2):
        sun(cx + s * .16, cy - s * .14, s * .2); cloud(cx - s * .06, cy + s * .06, s * .78, CL)
    elif code == 3:
        cloud(cx, cy, s * .9, CLD)
    elif code in (45, 48):
        for k in range(4):
            yy = cy - s * .3 + k * s * .2
            d.rounded_rectangle([cx - s * .42 + (k % 2) * s * .08, yy, cx + s * .42 - (k % 2) * s * .08, yy + s * .09], radius=int(s * .05), fill=CL)
    else:
        cloud(cx, cy - s * .16, s * .9, CLD if heavy else CL)
        base = cy + s * .2
        if 71 <= code <= 77 or code in (85, 86):
            for k, dx in enumerate((-.26, 0, .26)):
                x, y, r = cx + s * dx, base + (k % 2) * s * .12, s * .07
                d.line([x - r, y, x + r, y], fill=(90, 150, 230), width=3); d.line([x, y - r, x, y + r], fill=(90, 150, 230), width=3)
                d.line([x - r * .7, y - r * .7, x + r * .7, y + r * .7], fill=(90, 150, 230), width=3)
                d.line([x - r * .7, y + r * .7, x + r * .7, y - r * .7], fill=(90, 150, 230), width=3)
        else:
            drops = (-.3, -.1, .1, .3) if heavy else (-.22, 0, .22)
            for k, dx in enumerate(drops):
                x, y = cx + s * dx, base + (k % 2) * s * .1
                d.line([x + s * .05, y, x - s * .03, y + s * .2], fill=RAIN, width=max(4, int(s * .08)))
        if code >= 95:
            x, y = cx + s * .02, cy - s * .02
            d.polygon([(x, y), (x - s * .16, y + s * .26), (x - s * .02, y + s * .26), (x - s * .1, y + s * .5),
                       (x + s * .16, y + s * .18), (x + s * .02, y + s * .18), (x + s * .08, y)], fill=BOLT)


def alert(p, f, ko):
    """오늘 크게 경고할 날씨가 있으면 (제목, 부제, 색) 아니면 None."""
    t = f["today"]; hrs = p["hourly"].get(t["date"], {})
    codes = [hrs[h]["code"] for h in range(6, 23) if h in hrs] + [t.get("code", 0)]
    mm = t.get("mm", 0) or 0
    amt = (f"{mm:.0f}mm" if ko else f"{mm / 25.4:.1f} in") if mm >= 1 else ""
    wind_big = t.get("wind", 0) >= (50 if f["unit"] == "C" else 31)
    if any(c >= 95 for c in codes):
        return ("천둥·번개 조심" if ko else "Thunderstorms today", (((f"비 {amt} · ") if ko else f"Rain {amt} · ") if amt else "") + ("외출 땐 우산 꼭 챙기세요" if ko else "stay safe out there"), (110, 60, 170))
    if any(c in (65, 67, 82) for c in codes) or mm >= 25:
        return ("폭우 조심" if ko else "Heavy rain — take care", (((f"하루 {amt} · ") if ko else f"Up to {amt} · ") if amt else "") + ("길 미끄러워요, 천천히" if ko else "slick roads, slow down"), (20, 90, 200))
    if any(c in (75, 86) for c in codes):
        return ("폭설 조심" if ko else "Heavy snow — take care", "빙판길 미끄럼 주의" if ko else "icy roads, slow down", (60, 110, 190))
    if any(c in (63, 81) for c in codes) or mm >= 8:
        return ("비 많이 와요" if ko else "Steady rain today", (((f"하루 {amt} · ") if ko else f"Up to {amt} · ") if amt else "") + ("우산 필수" if ko else "bring an umbrella"), (40, 110, 210))
    if f["hi_c"] >= 33:
        return ("폭염 조심" if ko else "Heat warning", "물 자주 마시고 그늘로" if ko else "drink water, stay in the shade", (214, 66, 26))
    if f["lo_c"] <= -10:
        return ("한파 조심" if ko else "Hard freeze", "따뜻하게 꽁꽁 싸매세요" if ko else "bundle up", (24, 96, 200))
    if wind_big:
        return ("강풍 조심" if ko else "Strong winds", "간판·나뭇가지 조심" if ko else "watch for falling branches", (90, 100, 120))
    return None


def _week(d, x0, x1, y, h, cols, ko):
    """cols: [(day dict, kind)] kind = 'yday' | 'today' | 'next'"""
    n = len(cols); cw = (x1 - x0) / n
    hi = [z["hi"] for z, _ in cols]; lo = [z["lo"] for z, _ in cols]
    vmin, vmax = min(lo), max(hi)
    has_rain = any(z["rain"] >= 50 for z, k in cols if k == "next")
    top, bot = y + 166, y + h - (84 if has_rain else 56)
    sc = lambda v: bot - (v - vmin) / max(1, vmax - vmin) * (bot - top)
    for i, (z, kind) in enumerate(cols):
        cx = x0 + cw * (i + .5); wdi = dt.date.fromisoformat(z["date"]).weekday()
        if kind == "today":
            d.rounded_rectangle([cx - cw / 2 + 6, y, cx + cw / 2 - 6, y + h], radius=20, fill=(255, 236, 224))
            lab, lc = ("오늘" if ko else "Today"), UP
        elif kind == "yday":
            lab, lc = ("어제" if ko else "Yest."), SUB
        else:
            lab = "월화수목금토일"[wdi] if ko else WD_EN[wdi]
            lc = SAT if wdi == 5 else SUN if wdi == 6 else INK
        _ctext(d, cx, y + 12, lab, font("Bold", 34 if n <= 7 else 30), lc)
        _icon(d, cx, y + 88, 54, z.get("code", 0))
        faded = kind == "yday"
        bar = (205, 210, 220) if faded else (255, 170, 120)
        d.rounded_rectangle([cx - 9, sc(z["hi"]), cx + 9, sc(z["lo"])], radius=9, fill=bar)
        _ctext(d, cx, sc(z["hi"]) - 44, f"{z['hi']}°", font("Bold", 32), SUB if faded else UP)
        _ctext(d, cx, sc(z["lo"]) + 6, f"{z['lo']}°", font("Bold", 32), SUB if faded else DN)
        if kind == "next" and z["rain"] >= 50:
            _ctext(d, cx, y + h - 44, ("비 " if ko else "") + f"{z['rain']}%", font("Bold", 28), DN)


def card(out, region, now, p, f, cp, city):
    ko = cp["lang"] == "ko"; t = f["today"]
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    # 머리: 남색 띠 + 달력 타일 + 요일
    d.rectangle([0, 0, W, 300], fill=BAND)
    d.rounded_rectangle([64, 52, 264, 252], radius=28, fill="white")
    d.rounded_rectangle([64, 52, 264, 102], radius=28, fill=UP); d.rectangle([64, 80, 264, 102], fill=UP)
    _ctext(d, 164, 56, f"{now.month}월" if ko else now.strftime("%b").upper(), font("Bold", 34), "white")
    _ctext(d, 164, 96, str(now.day), font("Black", 120), INK)
    wd = ("월화수목금토일"[now.weekday()] + "요일") if ko else now.strftime("%A")
    d.text((300, 70), wd, font=fit(d, wd, "Black", 92, W - 300 - 330, 50), fill="white")
    cname = "서울" if ko else ("Los Angeles" if city == "Los Angeles" else city)
    d.text((304, 186), f"{cname} · {'오늘의 날씨' if ko else 'Today'}", font=font("Bold", 38), fill=(190, 205, 230))
    pose = Image.open(os.path.join(HERE, "assets", "poses", cp["pose"] + ".png")).convert("RGBA")
    s = min(300 / pose.width, 270 / pose.height)
    pose = pose.resize((int(pose.width * s), int(pose.height * s)), Image.LANCZOS).filter(ImageFilter.UnsharpMask(2, 60, 3))
    im.paste(pose, (W - 40 - pose.width, 330 - pose.height), pose); d = ImageDraw.Draw(im)

    # 출근길(아침 7~9시) 어제 → 오늘
    cy = 336; dm = f["d_morn"]
    d.rounded_rectangle([40, cy, W - 40, cy + 330], radius=32, fill="white")
    d.text((80, cy + 28), "출근길 아침 7~9시" if ko else "Morning commute 7–9am", font=font("Bold", 36), fill=SUB)
    col = UP if (dm or 0) > 0 else DN if (dm or 0) < 0 else OK
    if dm is not None:
        d.text((80, cy + 86), "어제 아침" if ko else "Yesterday", font=font("Bold", 34), fill=SUB)
        d.text((76, cy + 130), f"{f['morning'] - dm}°", font=font("Black", 112), fill=SUB)
        _ctext(d, 330, cy + 160, "→", font("Bold", 72), SUB)
        d.text((400, cy + 86), "오늘" if ko else "Today", font=font("Bold", 34), fill=SUB)
        d.text((396, cy + 112), f"{f['morning']}°", font=font("Black", 140), fill=col)
        bx0, bx1 = 690, W - 80
        d.rounded_rectangle([bx0, cy + 96, bx1, cy + 290], radius=28, fill=col)
        if dm == 0:
            _ctext(d, (bx0 + bx1) / 2, cy + 120, "＝", font("Black", 84), "white")
            sub = "어제랑 같아요" if ko else "same"
        else:
            _ctext(d, (bx0 + bx1) / 2, cy + 112, f"{'▲' if dm > 0 else '▼'} {abs(dm)}°", font("Black", 84), "white")
            sub = ("어제보다 " + ("따뜻해요" if dm > 0 else "추워요")) if ko else ("warmer" if dm > 0 else "colder")
        _ctext(d, (bx0 + bx1) / 2, cy + 226, sub, fit(d, sub, "Bold", 34, bx1 - bx0 - 30, 26), "white")
    else:
        d.text((76, cy + 96), f"{f['morning']}°", font=font("Black", 160), fill=INK)

    # 경고 배너 (폭우·뇌우·폭설·폭염·한파·강풍)
    y = cy + 352
    al = alert(p, f, ko)
    if al:
        title, sub, colr = al
        d.rounded_rectangle([40, y, W - 40, y + 140], radius=30, fill=colr)
        d.polygon([(84, y + 104), (122, y + 34), (160, y + 104)], fill="white")
        _ctext(d, 122, y + 52, "!", font("Black", 44), colr)
        d.text((190, y + 6), title, font=fit(d, title, "Black", 62, W - 40 - 190 - 30, 40), fill="white")
        d.text((192, y + 92), sub, font=fit(d, sub, "Bold", 30, W - 40 - 192 - 30, 22), fill=(230, 238, 250))
        y += 158
    else:
        y += 8

    # 낮 최고 / 밤 최저 + 우산·옷차림
    d.text((64, y), f"{'낮 최고' if ko else 'High'} {t['hi']}°", font=font("Bold", 48), fill=UP)
    d.text((440, y), f"{'밤 최저' if ko else 'Low'} {t['lo']}°", font=font("Bold", 48), fill=DN)
    y += 84
    rows = [r for r in (cp["card_rows"] if cp.get("compare") else cp["rows"]) if not r[0].startswith(("어제", "vs"))][:0 if al else 2]
    lab_w = 170
    for lab, txt in rows:
        d.rounded_rectangle([64, y, 64 + lab_w, y + 58], radius=14, fill=(226, 232, 242))
        _ctext(d, 64 + lab_w / 2, y + 7, lab, fit(d, lab, "Bold", 32, lab_w - 16, 24), INK)
        d.text((64 + lab_w + 24, y + 4), txt, font=fit(d, txt, "Bold", 40, W - 128 - lab_w - 24, 30), fill=INK)
        y += 76

    # 주간: 어제 → 오늘(강조) → 다음 5일, 토 파랑·일 빨강
    cols = ([(p["yday"], "yday")] if p.get("yday") else []) + [(p["days"][0], "today")] + [(z, "next") for z in p["days"][1:]]
    cols = cols[:7]
    d.rounded_rectangle([40, y + 4, W - 40, H - 40], radius=32, fill="white")
    _week(d, 64, W - 64, y + 20, H - 56 - (y + 20), cols, ko)
    im.save(out, "JPEG", quality=92)
    import reel_data  # 릴스용으로 같은 숫자를 남겨둠
    wk = []
    for z, kind in cols:
        wdi = dt.date.fromisoformat(z["date"]).weekday()
        lab = ("오늘" if ko else "Today") if kind == "today" else ("어제" if ko else "Yest.") if kind == "yday" else ("월화수목금토일"[wdi] if ko else WD_EN[wdi])
        wk.append(dict(d=lab, wd=wdi, code=z.get("code", 0), hi=z["hi"], lo=z["lo"], rain=z.get("rain", 0), today=kind == "today", faded=kind == "yday"))
    reel_data.save("weather", region, dict(ko=ko, city=cname, wd=wd, month=now.month, day=now.day, mon_en=now.strftime("%b"),
                   morning=f["morning"], dm=dm, hi=t["hi"], lo=t["lo"], rows=rows, alert=list(al) [:2] if al else None,
                   headline=cp["headline"], pose=cp["pose"], week=wk, card=os.path.abspath(out)))
