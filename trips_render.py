"""금요일 WEEKEND PICK 3장 캐러셀 그리기 (2026-11-17 형 확정 시안)."""
import datetime as dt, os
from PIL import Image, ImageDraw
from render import font, fit, HERE

W, H = 1080, 1350
CREAM = (250, 246, 238); INK = (18, 30, 52); SUB = (100, 104, 116); ORANGE = (214, 92, 40); LINE = (225, 216, 200)
SAT = (24, 96, 200); SUN = (214, 40, 40)


def _ctext(d, cx, y, t, fn, fill): d.text((cx - d.textlength(t, font=fn) / 2, y), t, font=fn, fill=fill)


def _cover(im, w, h, fx=.5, fy=.5):
    s = max(w / im.width, h / im.height); im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    x = int(max(0, min(im.width - w, im.width * fx - w / 2))); y = int(max(0, min(im.height - h, im.height * fy - h / 2)))
    return im.crop((x, y, x + w, y + h))


def _grad(im, y0, y1, a1=215):
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for y in range(y0, im.height):
        t = min(1, (y - y0) / max(1, y1 - y0)); d.line([(0, y), (W, y)], fill=(12, 20, 36, int(a1 * t ** 1.3)))
    return Image.alpha_composite(im.convert("RGBA"), ov)


def _top(d, head, handle, n):
    M = 48
    tw = d.textlength(head, font=font("Bold", 30))
    d.rounded_rectangle([M, 40, M + tw + 40, 96], radius=28, fill=(18, 30, 52, 210)); d.text((M + 20, 47), head, font=font("Bold", 30), fill="white")
    h = f"{handle}  {n}/3"; hw = d.textlength(h, font=font("Bold", 30))
    d.rounded_rectangle([W - M - hw - 40, 40, W - M, 96], radius=28, fill=(255, 255, 255, 225)); d.text((W - M - hw - 20, 47), h, font=font("Bold", 30), fill=ORANGE)


def _pose(w, region):
    if not w: return "a00"
    hi = max(x["hi"] for x in w); lo = min(x["lo"] for x in w); rain = max(x["rain"] for x in w)
    if rain >= 60: return "w06"
    if (lo <= 0 if region == "kr" else lo <= 35): return "w14"
    if (hi >= 30 if region == "kr" else hi >= 86): return "w15"
    if (hi >= 20 if region == "kr" else hi >= 68): return "w00"
    return "a00"


def _mascot(im, name, h, right, top):
    pz = Image.open(os.path.join(HERE, "assets", "poses", name + ".png")).convert("RGBA"); pz = pz.crop(pz.getbbox())
    s = h / pz.height; pz = pz.resize((int(pz.width * s), h), Image.LANCZOS); im.paste(pz, (right - pz.width, top), pz)


def _info(im, d, rows, y, M=56):
    lab_w = 160
    for lab, txt in rows:
        d.rounded_rectangle([M, y, M + lab_w, y + 60], radius=16, fill=(236, 228, 214))
        _ctext(d, M + lab_w / 2, y + 8, lab, fit(d, lab, "Bold", 32, lab_w - 14, 22), INK)
        d.text((M + lab_w + 24, y + 5), txt, font=fit(d, txt, "Bold", 38, W - 2 * M - lab_w - 24, 24), fill=INK); y += 82
    return y


def _photo_slide(ph, head, handle, n):
    im = Image.new("RGB", (W, H), CREAM)
    im.paste(_cover(ph["im"], W, 860, ph["fx"], ph["fy"]), (0, 0)); d = ImageDraw.Draw(im, "RGBA")
    _top(d, head, handle, n); M = 56
    cap = ph["cap"]; lw = d.textlength(cap, font=font("Bold", 34)) + 44
    d.rounded_rectangle([M, 860 - 94, M + lw, 860 - 30], radius=32, fill=(255, 255, 255, 235)); d.text((M + 22, 860 - 88), cap, font=font("Bold", 34), fill=INK)
    return im, d


def carousel(region, today, spot, w, ph, j, outs):
    ko = region == "kr"
    head = f"WEEKEND PICK · {today.month}.{today.day} ({'월화수목금토일'[today.weekday()]})" if ko else f"WEEKEND PICK · {today.strftime('%a').upper()}, {today.strftime('%b').upper()} {today.day}"
    handle = "@reddenva.kr" if ko else "@reddenva.us"; M = 56
    # 1장: 표지
    p = ph[0]
    im = _grad(_cover(p["im"], W, H, p["fx"], p["fy"]), 620, 1150); d = ImageDraw.Draw(im, "RGBA")
    _top(d, head, handle, 1)
    d.text((M, 790), "이번 주말 서울 나들이" if ko else "This weekend from LA", font=font("Bold", 36), fill=(255, 196, 150))
    d.text((M - 4, 836), spot["name"], font=fit(d, spot["name"], "Black", 128, W - 2 * M, 64), fill="white")
    d.text((M, 1000), j["why"], font=fit(d, j["why"], "Bold", 42, W - 2 * M, 26), fill="white")
    if w:
        from trips import sky
        y = 1090
        for i, (lab, col) in enumerate(((("토" if ko else "Sat"), SAT), (("일" if ko else "Sun"), SUN))):
            x0 = M + i * ((W - 2 * M) // 2 + 8); x1 = x0 + (W - 2 * M) // 2 - 8; z = w[i]
            d.rounded_rectangle([x0, y, x1, y + 92], radius=24, fill=(255, 255, 255, 240))
            d.text((x0 + 26, y + 20), lab, font=font("Bold", 38), fill=col)
            s = sky(z["code"], ko) + (f" {z['rain']}%" if z["rain"] >= 40 else "")
            d.text((x0 + 120, y + 26), s, font=fit(d, s, "Bold", 32, x1 - x0 - 120 - 210, 20), fill=INK)
            t = f"{z['hi']}° / {z['lo']}°"; tw = d.textlength(t, font=font("Bold", 38)); d.text((x1 - 24 - tw, y + 20), t, font=font("Bold", 38), fill=INK)
    d.text((M, 1236), spot["area"], font=font("Bold", 30), fill=(230, 235, 245))
    sw = "넘겨보기 →" if ko else "Swipe →"; tw = d.textlength(sw, font=font("Bold", 30)); d.text((W - M - tw, 1232), sw, font=font("Bold", 30), fill=(230, 235, 245))
    im.convert("RGB").save(outs[0], "JPEG", quality=92)
    # 2장: 가는 법·시간·요금
    im, d = _photo_slide(ph[1], head, handle, 2)
    rows = [(("가는 법" if ko else "Getting there"), spot["how"])]
    if spot.get("hours"): rows.append((("시간" if ko else "Hours"), spot["hours"]))
    if spot.get("fee"): rows.append((("요금" if ko else "Entry"), spot["fee"]))
    rows.append((("팁" if ko else "Tip"), j["tip"]))
    _info(im, d, rows, 900)
    im.save(outs[1], "JPEG", quality=92)
    # 3장: 코스·팁·레드덴바 한마디·사진 출처
    im, d = _photo_slide(ph[2], head, handle, 3)
    y = _info(im, d, [(("코스" if ko else "Route"), spot["course"])], 900)
    d.rounded_rectangle([M, y + 6, W - M - 200, y + 120], radius=28, fill="white", outline=LINE, width=2)
    d.text((M + 30, y + 20), "레드덴바 한마디" if ko else "Red Denva says", font=font("Bold", 28), fill=ORANGE)
    d.text((M + 30, y + 58), j["aside"], font=fit(d, j["aside"], "Bold", 38, W - 2 * M - 260, 24), fill=INK)
    _mascot(im, _pose(w, region), 170, W - M + 10, y - 30); d = ImageDraw.Draw(im)
    lic = lambda c: "퍼블릭 도메인" if c["license"] == "퍼블릭 도메인" and ko else ("Public domain" if c["license"] == "퍼블릭 도메인" else c["license"])
    cr = ("사진: " if ko else "Photos: ") + ", ".join(f"{c['artist']} ({lic(c)})" for c in ph) + " · Wikimedia Commons"
    d.text((M, H - 52), cr, font=fit(d, cr, "Regular", 23, W - 2 * M, 14), fill=SUB)
    im.save(outs[2], "JPEG", quality=92)
