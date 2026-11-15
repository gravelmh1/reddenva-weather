"""좋은 소식 카드(1080x1350). 한국판/미국판 공용."""
import os
from PIL import Image, ImageDraw
from render import font, wrap, fit

W, H, M = 1080, 1350, 84
CREAM = (247, 242, 234); NAVY = (15, 34, 64); OR = (205, 92, 40); GR = (125, 128, 138); LINE = (222, 214, 201)
HERE = os.path.dirname(os.path.abspath(__file__)); POSES = os.path.join(HERE, "assets", "poses")


def _pose(im, name, box, x, y_bottom=None, y=None, scale=1.0):
    p = Image.open(os.path.join(POSES, name)).convert("RGBA").crop(box)
    p = p.resize((int(p.width * scale), int(p.height * scale)), Image.LANCZOS)
    im.paste(p, (x(p.width) if callable(x) else x, (y_bottom - p.height) if y_bottom else y), p)


def card(c: dict, out: str):
    im = Image.new("RGB", (W, H), CREAM); d = ImageDraw.Draw(im)
    d.text((M, 70), c["top"], font=font("Bold", 26), fill=NAVY)
    hf = font("Bold", 26); d.text((W - M - d.textlength(c["handle"], font=hf), 70), c["handle"], font=hf, fill=OR)
    d.line([(M, 120), (W - M, 120)], fill=NAVY, width=3)
    bf = font("Bold", 30); bw = int(d.textlength(c["badge"], font=bf)) + 64
    d.rounded_rectangle([M, 156, M + bw, 214], radius=29, fill=OR); d.text((M + bw / 2, 185), c["badge"], font=bf, fill="white", anchor="mm")
    # 히어로 숫자
    hero = fit(d, c["hero"], "Black", 120, W - 2 * M - 230, 50)
    d.text((M, 250), c["hero"], font=hero, fill=OR)
    d.text((M, 250 + 128), c["hero_sub"], font=fit(d, c["hero_sub"], "Bold", 32, W - 2 * M - 230, 22), fill=GR)
    p = Image.open(os.path.join(POSES, "a12.png")).convert("RGBA").crop((0, 0, 200, 150)) if False else Image.open(os.path.join(POSES, "a12.png")).convert("RGBA")
    p = p.crop(p.getbbox()); sc = 230 / p.width; p = p.resize((230, int(p.height * sc)), Image.LANCZOS); im.paste(p, (W - M - 230, 235), p)
    y = 440; d.line([(M, y), (W - M, y)], fill=LINE, width=2); y += 30
    hf2 = fit(d, c["headline"], "Black", 52, W - 2 * M, 34); d.text((M, y), c["headline"], font=hf2, fill=NAVY); y += 86
    bfn = font("Medium", 32)
    for ln in wrap(d, c["body"], bfn, W - 2 * M)[:6]:
        d.text((M, y), ln, font=bfn, fill=NAVY); y += 46
    y += 14
    d.text((M, y), c["why_l"], font=font("Bold", 28), fill=OR); y += 44
    for ln in wrap(d, c["why"], font("Bold", 32), W - 2 * M)[:2]:
        d.text((M, y), ln, font=font("Bold", 32), fill=NAVY); y += 44
    y += 24; h = H - y - 150
    d.rounded_rectangle([M, y, W - M, y + h], radius=40, fill=NAVY)
    d.text((M + 40, y + 38), c["head"], font=fit(d, c["head"], "Black", 40, W - 2 * M - 300, 26), fill=(240, 170, 120))
    qw = W - 2 * M - 80 - 190
    for j, ln in enumerate(c["quote"][:2]):
        d.text((M + 40, y + 100 + j * 54), ln, font=fit(d, ln, "Bold", 38, qw, 24), fill="white")
    s = Image.open(os.path.join(POSES, "a00.png")).convert("RGBA"); sc = min(.7, (h - 30) / s.height)
    s = s.resize((int(s.width * sc), int(s.height * sc)), Image.LANCZOS); im.paste(s, (W - M - s.width - 26, y + h - s.height - 12), s)
    ff = font("Medium", 22)
    for i, t in enumerate(c["foot"][:3]):
        d.text((M, H - 118 + i * 30), t, font=fit(d, t, "Medium", 22, W - 2 * M, 15), fill=GR)
    im.save(out, quality=92)


def card3(c: dict, out: str):
    """주간 좋은 뉴스 TOP 3 카드."""
    im = Image.new("RGB", (W, H), CREAM); d = ImageDraw.Draw(im)
    d.text((M, 70), c["top"], font=font("Bold", 26), fill=NAVY)
    hf = font("Bold", 26); d.text((W - M - d.textlength(c["handle"], font=hf), 70), c["handle"], font=hf, fill=OR)
    d.line([(M, 120), (W - M, 120)], fill=NAVY, width=3)
    bf = font("Bold", 30); bw = int(d.textlength(c["badge"], font=bf)) + 64
    d.rounded_rectangle([M, 156, M + bw, 214], radius=29, fill=OR); d.text((M + bw / 2, 185), c["badge"], font=bf, fill="white", anchor="mm")
    d.text((M, 236), c["title"], font=fit(d, c["title"], "Black", 62, W - 2 * M - 200, 36), fill=NAVY)
    p = Image.open(os.path.join(POSES, "a12.png")).convert("RGBA"); p = p.crop(p.getbbox()); sc = 170 / p.width
    p = p.resize((170, int(p.height * sc)), Image.LANCZOS); im.paste(p, (W - M - 170, 150), p)
    y = 330
    for i, it in enumerate(c["items"][:3]):
        d.line([(M, y), (W - M, y)], fill=LINE, width=2)
        d.text((M, y + 20), f"0{i+1}", font=font("Black", 30), fill=OR)
        hx = M + 70
        d.text((hx, y + 12), it["hero"], font=fit(d, it["hero"], "Black", 32, W - hx - M, 24), fill=OR)
        d.text((hx, y + 52), it["head"], font=fit(d, it["head"], "Black", 44, W - hx - M, 34), fill=NAVY)
        f27 = font("Medium", 30); yy = y + 110
        for ln in wrap(d, it["desc"], f27, W - hx - M)[:2]:
            d.text((hx, yy), ln, font=f27, fill=NAVY); yy += 36
        d.text((hx, y + 186), it["src"], font=fit(d, it["src"], "Medium", 21, W - hx - M, 15), fill=GR)
        y += 222
    d.line([(M, y), (W - M, y)], fill=LINE, width=2)
    y += 22; h = H - y - 150
    d.rounded_rectangle([M, y, W - M, y + h], radius=36, fill=NAVY)
    if c.get("author"):
        for j, ln in enumerate(c["quote"][:2]):
            d.text((M + 36, y + 24 + j * 44), ln, font=fit(d, ln, "Bold", 34, W - 2 * M - 80 - 170, 22), fill="white")
        au = "— " + c["author"]; d.text((M + 36, y + 24 + 2 * 44 + 8), au, font=fit(d, au, "Medium", 28, W - 2 * M - 300, 20), fill=(240, 170, 120))
    else:
        d.text((M + 36, y + 18), c["head"], font=fit(d, c["head"], "Black", 34, W - 2 * M - 300, 24), fill=(240, 170, 120))
        for j, ln in enumerate(c["quote"][:2]):
            d.text((M + 36, y + 66 + j * 42), ln, font=fit(d, ln, "Bold", 32, W - 2 * M - 80 - 170, 22), fill="white")
    s = Image.open(os.path.join(POSES, "a00.png")).convert("RGBA"); sc = min(.55, (h - 20) / s.height)
    s = s.resize((int(s.width * sc), int(s.height * sc)), Image.LANCZOS); im.paste(s, (W - M - s.width - 22, y + h - s.height - 8), s)
    for i, t in enumerate(c["foot"][:3]):
        d.text((M, H - 112 + i * 30), t, font=fit(d, t, "Medium", 21, W - 2 * M, 14), fill=GR)
    im.save(out, quality=92)
