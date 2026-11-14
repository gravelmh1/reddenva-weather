"""주간 책 카드(1080x1350)를 그린다. 한국판/미국판 공용."""
import os
from PIL import Image, ImageDraw
from render import font, wrap, fit

W, H, M = 1080, 1350, 84
CREAM = (247, 242, 234); NAVY = (15, 34, 64); OR = (205, 92, 40); GR = (125, 128, 138); LINE = (222, 214, 201)
HERE = os.path.dirname(os.path.abspath(__file__))
POSES = os.path.join(HERE, "assets", "poses")


def card(c: dict, out: str):
    im = Image.new("RGB", (W, H), CREAM); d = ImageDraw.Draw(im)
    d.text((M, 70), c["top"], font=font("Bold", 26), fill=NAVY)
    hf = font("Bold", 26); d.text((W - M - d.textlength(c["handle"], font=hf), 70), c["handle"], font=hf, fill=OR)
    d.line([(M, 120), (W - M, 120)], fill=NAVY, width=3)
    bf = font("Bold", 30); bw = int(d.textlength(c["badge"], font=bf)) + 64
    d.rounded_rectangle([M, 156, M + bw, 214], radius=29, fill=OR)
    d.text((M + bw / 2, 185), c["badge"], font=bf, fill="white", anchor="mm")
    sf = fit(d, c["src"], "Medium", 24, W - 2 * M - bw - 22 - 190, 18)
    d.text((M + bw + 22, 185), c["src"], font=sf, fill=GR, anchor="lm")
    tf = fit(d, c["title"], "Black", 70, W - 2 * M - 210, 36)
    d.text((M, 250), c["title"], font=tf, fill=NAVY)
    af = font("Medium", 32); d.text((M, 342), c["author"], font=af, fill=GR)
    ax = M + d.textlength(c["author"], font=af) + 30
    gf = fit(d, "|  " + c["tag"], "Bold", 32, W - ax - M - 160, 22)
    d.text((ax, 342), "|  " + c["tag"], font=gf, fill=OR)
    p = Image.open(os.path.join(POSES, "a19.png")).convert("RGBA").crop((9, 0, 225, 259))
    p = p.resize((int(p.width * .62), int(p.height * .62)), Image.LANCZOS); im.paste(p, (W - M - p.width, 222), p)
    y = 430
    d.text((M, y), c["l1"], font=font("Bold", 28), fill=OR)
    f3 = font("Medium", 33); lines = wrap(d, c["plot"], f3, W - 2 * M)[:4]
    for j, ln in enumerate(lines): d.text((M, y + 46 + j * 46), ln, font=f3, fill=NAVY)
    y += 46 + len(lines) * 46 + 30
    d.text((M, y), c["l2"], font=font("Bold", 28), fill=OR); y += 44
    for i, t in enumerate(c["keys"][:3]):
        d.line([(M, y), (W - M, y)], fill=LINE, width=2)
        d.text((M, y + 33), f"0{i+1}", font=font("Black", 32), fill=OR, anchor="lm")
        d.text((M + 86, y + 33), t, font=fit(d, t, "Bold", 33, W - 2 * M - 86, 22), fill=NAVY, anchor="lm")
        y += 66
    d.line([(M, y), (W - M, y)], fill=LINE, width=2)
    y += 36; h = H - y - 110
    d.rounded_rectangle([M, y, W - M, y + h], radius=40, fill=NAVY)
    hdf = fit(d, c["head"], "Black", 46, W - 2 * M - 80 - (110 if c.get("headsub") else 0), 28)
    d.text((M + 40, y + 40), c["head"], font=hdf, fill=(240, 170, 120))
    if c.get("headsub"):
        d.text((M + 40 + d.textlength(c["head"], font=hdf) + 12, y + 54), c["headsub"], font=font("Bold", 28), fill=(200, 205, 215))
    qw = W - 2 * M - 80 - 200
    for j, ln in enumerate(c["quote"][:2]):
        d.text((M + 40, y + 112 + j * 58), ln, font=fit(d, ln, "Bold", 40, qw, 24), fill="white")
    s = Image.open(os.path.join(POSES, "a16.png")).convert("RGBA"); sc = min(.8, (h - 30) / s.height)
    s = s.resize((int(s.width * sc), int(s.height * sc)), Image.LANCZOS); im.paste(s, (W - M - s.width - 26, y + h - s.height - 12), s)
    d.text((M, H - 84), c["foot1"], font=fit(d, c["foot1"], "Medium", 23, W - 2 * M, 16), fill=GR)
    d.text((M, H - 50), c["foot2"], font=font("Medium", 23), fill=GR)
    im.save(out, quality=92)
