"""수요일 아기 동물 카드(1080x1350). 사진 한 장 크게 + 이름 + 시큰둥한 한 줄."""
import os
from PIL import Image, ImageDraw
from datetile import cream_header
from render import font, fit
from news_render import W, H, M, CREAM, NAVY, OR, GR, POSES


def card(c: dict, out: str):
    im = Image.new("RGB", (W, H), CREAM); d = ImageDraw.Draw(im)
    cream_header(im, d, c, W, M, NAVY, OR)
    # 사진: 가운데(또는 지정 위치) 기준으로 꽉 채워 자르기, 둥근 모서리
    pw, ph = W - 2 * M, 790
    p = Image.open(c["photo"]).convert("RGB"); sc = max(pw / p.width, ph / p.height)
    p = p.resize((int(p.width * sc) + 1, int(p.height * sc) + 1), Image.LANCZOS)
    fx, fy = c.get("focus", (0.5, 0.5))
    x0 = min(max(int(p.width * fx - pw / 2), 0), p.width - pw); y0 = min(max(int(p.height * fy - ph / 2), 0), p.height - ph)
    p = p.crop((x0, y0, x0 + pw, y0 + ph))
    mask = Image.new("L", (pw, ph), 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw, ph], radius=40, fill=255)
    im.paste(p, (M, 150), mask)
    y = 150 + ph + 34
    d.text((M, y), c["badge"], font=font("Black", 30), fill=OR)
    d.text((M, y + 44), c["name"], font=fit(d, c["name"], "Black", 68, W - 2 * M - 250, 40), fill=NAVY)
    for j, ln in enumerate(c["lines"][:2]):
        d.text((M, y + 140 + j * 48), ln, font=fit(d, ln, "Bold" if (j == 0 and c.get("fact")) else "Medium", 36, W - 2 * M - 250, 24), fill=NAVY)
    # 레드덴바 + 한마디
    s = Image.open(os.path.join(POSES, c.get("pose", "a00.png"))).convert("RGBA"); s = s.crop(s.getbbox()); k = 190 / s.height
    s = s.resize((int(s.width * k), 190), Image.LANCZOS); sx = W - M - s.width; sy = y + 62; im.paste(s, (sx, sy), s)
    if c.get("aside"):
        af = fit(d, c["aside"], "Bold", 24, 230, 16); aw = int(d.textlength(c["aside"], font=af)) + 36
        d.rounded_rectangle([W - M - aw, y, W - M, y + 46], radius=23, fill=NAVY); d.text((W - M - aw / 2, y + 23), c["aside"], font=af, fill="white", anchor="mm")
    for i, t in enumerate(c["foot"][:2]):
        d.text((M, H - 92 + i * 30), t, font=fit(d, t, "Medium", 21, W - 2 * M, 14), fill=GR)
    im.save(out, quality=92)
