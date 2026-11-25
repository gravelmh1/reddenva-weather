"""일요일 넷플릭스 카드(1080x1350). 포스터 없이 우리 디자인: 1위 큰 패널 + 2~5위 목록 + 영화 1위."""
import os
from PIL import Image, ImageDraw
from datetile import cream_header
from render import font, fit
from news_render import W, H, M, CREAM, NAVY, OR, GR, LINE, POSES

RED = (229, 9, 20)


def wrap(d, text, f, width, max_lines=2):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= width: cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]; lines[-1] = lines[-1].rstrip(".,") + "…"
    return lines


def card(c: dict, out: str):
    im = Image.new("RGB", (W, H), CREAM); d = ImageDraw.Draw(im)
    cream_header(im, d, c, W, M, NAVY, OR)
    # 1위 패널
    x0, y0, x1, y1 = M, 168, W - M, 790
    d.rounded_rectangle([x0, y0, x1, y1], radius=40, fill=NAVY)
    d.rounded_rectangle([x0 + 44, y0 + 44, x0 + 44 + 132, y0 + 44 + 132], radius=28, fill=RED)
    d.text((x0 + 110, y0 + 112), "1", font=font("Black", 104), fill="white", anchor="mm")
    kx = x0 + 44 + 132 + 30
    d.text((kx, y0 + 52), c["kicker"], font=fit(d, c["kicker"], "Bold", 27, x1 - 44 - kx, 18), fill=(255, 196, 150))
    tf = fit(d, c["title"], "Black", 78, x1 - 44 - kx, 46)
    tl = wrap(d, c["title"], tf, x1 - 44 - kx, 2) if d.textlength(c["title"], font=tf) > x1 - 44 - kx else [c["title"]]
    ty = y0 + 92
    for ln in tl:
        d.text((kx, ty), ln, font=tf, fill="white"); ty += int(tf.size * 1.12)
    if c.get("season"):
        d.text((kx, ty + 4), c["season"], font=font("Bold", 32), fill=(255, 196, 150)); ty += 46
    # 칩: 장르 · 몇 주째
    cy = max(ty + 26, y0 + 230); cx = x0 + 44
    for txt, bg, fg in ((c.get("genre"), (255, 255, 255), NAVY), (c["weeks"], RED, (255, 255, 255))):
        if not txt: continue
        cf = font("Bold", 28); w = int(d.textlength(txt, font=cf)) + 44
        d.rounded_rectangle([cx, cy, cx + w, cy + 54], radius=27, fill=bg); d.text((cx + w / 2, cy + 27), txt, font=cf, fill=fg, anchor="mm"); cx += w + 14
    # 소개 + 추천 대상 (왼쪽), 레드덴바 (오른쪽 아래)
    s = Image.open(os.path.join(POSES, "a18.png")).convert("RGBA"); s = s.crop(s.getbbox()); k = 250 / s.height
    s = s.resize((int(s.width * k), 250), Image.LANCZOS); im.paste(s, (x1 - 30 - s.width, y1 - 24 - s.height), s)
    tw = x1 - 44 - s.width - 40 - (x0 + 44); ly = cy + 86
    if c.get("line"):
        lf = font("Medium", 36)
        for ln in wrap(d, c["line"], lf, tw, 3):
            d.text((x0 + 44, ly), ln, font=lf, fill="white"); ly += 50
    if c.get("who"):
        wt = c["who_label"] + c["who"]; d.text((x0 + 44, ly + 14), wt, font=fit(d, wt, "Bold", 28, tw, 18), fill=(255, 196, 150))
    # 2~5위
    y = y1 + 34
    d.text((M, y), c["list_title"], font=font("Black", 30), fill=OR); y += 50
    rf = font("Black", 40)
    for rank, t, se in c["rest"]:
        d.text((M, y), str(rank), font=rf, fill=OR)
        name = t + (f"  {se}" if se else "")
        d.text((M + 64, y + 4), name, font=fit(d, name, "Bold", 36, W - 2 * M - 64, 22), fill=NAVY)
        y += 58; d.line([(M, y - 8), (W - M, y - 8)], fill=LINE, width=2)
    if c.get("film"):
        y += 6; lab = c["film_label"]; lf = font("Black", 28); lw = int(d.textlength(lab, font=lf)) + 36
        d.rounded_rectangle([M, y, M + lw, y + 46], radius=23, fill=NAVY); d.text((M + lw / 2, y + 23), lab, font=lf, fill="white", anchor="mm")
        d.text((M + lw + 18, y + 4), c["film"], font=fit(d, c["film"], "Bold", 34, W - 2 * M - lw - 18, 20), fill=NAVY)
    for i, t in enumerate(c["foot"][:2]):
        d.text((M, H - 92 + i * 30), t, font=fit(d, t, "Medium", 21, W - 2 * M, 14), fill=GR)
    im.save(out, quality=92)
