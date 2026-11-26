"""수요일 다트 투자 카드(1080x1350). 이번 주 다트 + 누적 성적(레드덴바 vs 지수) + 지난주 결과."""
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


def money(v, region):
    if region == "kr": return f"{v / 10000:,.0f}만 원"
    return f"${v:,.0f}"


def target(d, cx, cy, r):
    for i, col in enumerate([(214, 56, 40), WHITE, (214, 56, 40), WHITE, (214, 56, 40)]):
        rr = r * (1 - i * .2); d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col, outline=NAVY if i == 0 else None, width=5)
    # 다트 (오른쪽 위에서 날아와 가운데 살짝 옆에 꽂힘)
    hx, hy = cx + r * .12, cy - r * .08; ang = math.radians(-35); L = r * 1.05
    tx, ty = hx + L * math.cos(ang), hy + L * math.sin(ang)
    d.line([(hx, hy), (tx, ty)], fill=NAVY, width=12)
    d.polygon([(hx - 4, hy + 6), (hx + 16, hy - 4), (hx + 6, hy - 14)], fill=(80, 90, 110))
    fx, fy = tx, ty; px, py = -math.sin(ang), math.cos(ang)
    for s in (1, -1):
        d.polygon([(fx, fy), (fx - 52 * math.cos(ang) + s * 30 * px, fy - 52 * math.sin(ang) + s * 30 * py), (fx - 36 * math.cos(ang), fy - 36 * math.sin(ang))], fill=OR)


def card(c: dict, out: str):
    region = c["region"]; ko = region == "kr"; up, dn = colors(region)
    im = Image.new("RGB", (W, H), CREAM); d = ImageDraw.Draw(im)
    cream_header(im, d, {"handle": c["handle"], "top": c["top"], "date": c["day"]}, W, M, NAVY, OR)
    badge = f"레드덴바 다트 투자 · {c['week']}주차" if ko else f"Red Denva's dart portfolio · week {c['week']}"
    bf = font("Bold", 30); bw = int(d.textlength(badge, font=bf)) + 64
    d.rounded_rectangle([M, 160, M + bw, 218], radius=29, fill=OR); d.text((M + bw / 2, 189), badge, font=bf, fill=WHITE, anchor="mm")

    # A. 이번 주 다트
    n = c["new"]; tw = W - 2 * M - 300
    d.text((M, 248), "이번 주 다트가 꽂힌 곳" if ko else "This week the dart hit", font=font("Bold", 32), fill=GR)
    d.text((M, 292), n["name"], font=fit(d, n["name"], "Black", 96, tw, 48), fill=NAVY)
    code = n["sym"].replace(".KS", "")
    sub = " · ".join(x for x in (code, n.get("what", "")) if x)
    d.text((M, 410), sub, font=fit(d, sub, "Bold", 36, tw, 22), fill=NAVY)
    ent = (f"매수가 {n['entry']:,.0f}원 · {money(n['amount'], region)} 가상 투자" if ko else f"Bought at ${n['entry']:,.2f} · {money(n['amount'], region)} in paper money")
    d.text((M, 464), ent, font=fit(d, ent, "Medium", 30, tw, 20), fill=GR)
    q = n.get("quip", "")
    if q:
        qf = fit(d, q, "Bold", 32, tw - 60, 20); qw = int(d.textlength(q, font=qf)) + 56
        d.rounded_rectangle([M, 520, M + qw, 584], radius=32, fill=NAVY); d.text((M + qw / 2, 552), q, font=qf, fill=WHITE, anchor="mm")
    target(d, W - M - 150, 380, 135)
    p = Image.open(os.path.join(POSES, "a00.png")).convert("RGBA"); p = p.crop(p.getbbox()); k = 170 / p.height
    p = p.resize((int(p.width * k), 170), Image.LANCZOS); im.paste(p, (W - M - 300, 448), p)

    # B. 누적 성적
    y = 630; h = 380
    d.rounded_rectangle([M, y, W - M, y + h], radius=40, fill=NAVY)
    t = c.get("tot")
    if not t:
        d.text((M + 44, y + 44), "지금까지 성적" if ko else "Scoreboard", font=font("Bold", 32), fill=(240, 170, 120))
        msg = ["첫 다트.", "성적표는 다음 주부터."] if ko else ["First dart.", "Scores start next week."]
        for i, s in enumerate(msg): d.text((M + 44, y + 120 + i * 84), s, font=font("Black", 64), fill=WHITE)
    else:
        npk = len(c["rows"])
        head = (f"지금까지 {npk}종목 · {money(t['invested'], region)} 넣었으면" if ko else f"So far: {npk} picks · {money(t['invested'], region)} in")
        d.text((M + 44, y + 40), head, font=fit(d, head, "Bold", 32, W - 2 * M - 88, 20), fill=(240, 170, 120))
        lab = [("레드덴바 다트" if ko else "Red Denva's darts", t["ret"], t["value"]), (c["index_name"] + (" 그냥 사기" if ko else " index"), t["ret_idx"], t["value_idx"])]
        mx = max(abs(t["ret"]), abs(t["ret_idx"]), .01); bx0 = M + 44; bw_ = W - 2 * M - 88 - 260
        for i, (nm, r, v) in enumerate(lab):
            yy = y + 110 + i * 112
            d.text((bx0, yy), nm, font=font("Bold", 34), fill=WHITE)
            L = max(10, bw_ * abs(r) / mx); col = up if r >= 0 else dn
            d.rounded_rectangle([bx0, yy + 52, bx0 + L, yy + 84], radius=16, fill=col)
            d.text((W - M - 44, yy + 30), pct(r), font=font("Black", 64), fill=col if r else WHITE, anchor="rm")
        win = t["ret"] - t["ret_idx"]
        verdict = ((f"다트가 {abs(win) * 100:.1f}%p 이기는 중" if win > 0 else f"지수가 {abs(win) * 100:.1f}%p 이기는 중") if ko else
                   (f"Darts ahead by {abs(win) * 100:.1f} pts" if win > 0 else f"Index ahead by {abs(win) * 100:.1f} pts"))
        d.text((M + 44, y + h - 70), verdict, font=font("Black", 40), fill=(240, 170, 120))

    # C. 지난주 다트 결과 + 주간 전적
    y = 1040
    last = c.get("last")
    if last:
        l1 = (f"지난주 다트 {last['name']}" if ko else f"Last week: {last['name']}")
        d.text((M, y), l1, font=fit(d, l1, "Black", 40, W - 2 * M - 260, 24), fill=NAVY)
        col = up if last["ret"] >= 0 else dn
        d.text((W - M, y + 22), pct(last["wk_ret"]), font=font("Black", 48), fill=up if last["wk_ret"] >= 0 else dn, anchor="rm")
        l2 = ((f"같은 1주 {c['index_name']} {pct(last['wk_idx'])} → " + ("무승부" if last.get("draw") else "다트 승" if last["win"] else "지수 승")) if ko else
              (f"{c['index_name']} {pct(last['wk_idx'])} that week → " + ("a draw" if last.get("draw") else "darts win" if last["win"] else "index wins")))
        d.text((M, y + 56), l2, font=font("Bold", 30), fill=GR)
        # 주간 전적: 주차별 승패 칸
        y += 112; t = c["tot"]; rows = c["rows"][-12:]
        dr = t.get("draws", 0)
        rec = (f"주간 전적  다트 {t['wins']}승 {dr and f'{dr}무 ' or ''}{t['losses']}패" if ko else f"Weekly record  Darts {t['wins']}-{t['losses']}" + (f"-{dr}" if dr else ""))
        d.text((M, y + 6), rec, font=font("Black", 34), fill=NAVY)
        x = W - M; cf = font("Black", 26)
        for r in reversed(rows):
            s = ("무" if r.get("draw") else "승" if r["win"] else "패") if ko else ("D" if r.get("draw") else "W" if r["win"] else "L"); x -= 52
            d.rounded_rectangle([x, y, x + 44, y + 52], radius=12, fill=OR if r["win"] else (160, 165, 180) if r.get("draw") else (205, 205, 210))
            d.text((x + 22, y + 26), s, font=cf, fill=WHITE, anchor="mm")
            if x < M + 420: break
    else:
        s = "매주 수요일, 눈 감고 한 종목. 계속 들고 갑니다." if ko else "Every Wednesday, one blindfolded pick. We never sell."
        d.text((M, y + 20), s, font=fit(d, s, "Bold", 36, W - 2 * M, 22), fill=NAVY)
    d.line([(M, H - 84), (W - M, H - 84)], fill=LINE, width=2)
    d.text((M, H - 62), c["foot"], font=fit(d, c["foot"], "Medium", 22, W - 2 * M, 15), fill=GR)
    im.save(out, quality=92)
