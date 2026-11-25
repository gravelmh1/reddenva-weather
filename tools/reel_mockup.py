"""릴스 시안: 기존 카드 이미지(1080x1350)를 10초짜리 세로 영상(1080x1920, 30fps)으로 바꾼다.
PIL로 프레임을 그리고 ffmpeg로 묶는다. 무료, 외부 API 없음.

  python tools/reel_mockup.py weather out/kr-2026-11-25.jpg reel-weather-kr.mp4
  python tools/reel_mockup.py deriv out/deriv-kr-2026-11-19-1.jpg out/deriv-kr-2026-11-19-2.jpg reel-deriv-kr.mp4

시안이라 훅 문구(숫자)는 아래 HOOK에 적어 두었다. 실제 연결 땐 카드 만드는 스크립트가 넘겨준다.
"""
import subprocess, sys, os
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import font  # 카드와 같은 Noto Sans CJK

W, H, FPS = 1080, 1920, 30
NAVY = (20, 40, 77)
LIGHT = (245, 246, 250)
ORANGE = (217, 130, 43)
RED = (229, 57, 53)
BLUE = (25, 100, 210)
POSES = "assets/poses"


def ease(x):  # ease-in-out cubic
    x = max(0.0, min(1.0, x))
    return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2


def prog(t, a, b):
    return ease((t - a) / (b - a)) if b > a else float(t >= a)


def pop(t, a, d=0.45):
    """0 → 1.12 → 1 튀어나오는 크기"""
    x = (t - a) / d
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    return 1.12 * ease(x / .7) if x < .7 else 1.12 - .12 * ease((x - .7) / .3)


def pose(name, height):
    im = Image.open(f"{POSES}/{name}.png").convert("RGBA")
    return im.resize((round(im.width * height / im.height), height), Image.LANCZOS)


def ctext(d, y, text, fn, fill, alpha=1.0, bg=None):
    w = d.textlength(text, font=fn)
    d.text(((W - w) / 2, y), text, font=fn, fill=fill + (round(255 * alpha),))


def paste_scaled(base, im, cx, cy, s, alpha=1.0):
    if s <= 0.01 or alpha <= 0: return
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    if alpha < 1:
        a = im.getchannel("A").point(lambda v: round(v * alpha)); im.putalpha(a)
    base.alpha_composite(im, (round(cx - im.width / 2), round(cy - im.height / 2)))


def camera(scene, s, cx, cy):
    """scene(1080x1920)을 배율 s로 (cx,cy) 중심 확대"""
    if s <= 1.001: return scene.copy()
    cw, ch = W / s, H / s
    x0 = min(max(cx - cw / 2, 0), W - cw); y0 = min(max(cy - ch / 2, 0), H - ch)
    return scene.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


def card_scene(card, bg, top, bottom, top_color, bottom_color):
    """카드를 세로 화면 가운데에. 아래 430px는 릴스 UI(캡션·버튼) 자리라 비워둔다."""
    sc = Image.new("RGBA", (W, H), bg + (255,))
    cw = 960; c = card.resize((cw, round(card.height * cw / card.width)), Image.LANCZOS)
    y = 290
    sc.paste(c, ((W - cw) // 2, y))
    d = ImageDraw.Draw(sc)
    ctext(d, 150, top, font("Bold", 64), top_color)
    ctext(d, y + c.height + 34, bottom, font("Medium", 38), bottom_color)
    return sc, y, cw / card.width


class Encoder:
    def __init__(self, path):
        self.p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                   "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                                   "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest",
                                   "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                                   "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", path],
                                  stdin=subprocess.PIPE)

    def add(self, im):
        self.p.stdin.write(im.convert("RGB").tobytes())

    def close(self):
        self.p.stdin.close(); self.p.wait()


# ---------------------------------------------------------------- 날씨
def weather(card_path, out, hook):
    card = Image.open(card_path).convert("RGB")
    scene, cy0, k = card_scene(card, NAVY, hook["top"], hook["bottom"], (255, 255, 255), (170, 185, 215))
    ch = pose(hook["pose"], 420)
    enc = Encoder(out)
    N = 10 * FPS
    for i in range(N):
        t = i / FPS
        # 1) 훅 0~2.6초: 어제 → 오늘 숫자가 내려가고, 캐릭터가 튀어나옴
        if t < 3.0:
            f = Image.new("RGBA", (W, H), NAVY + (255,))
            d = ImageDraw.Draw(f, "RGBA")
            fade = 1 - prog(t, 2.5, 3.0)
            ctext(d, 260, hook["where"], font("Medium", 46), (190, 200, 225), fade)
            v = hook["from"] + (hook["to"] - hook["from"]) * prog(t, 0.5, 1.5)
            n = round(v)
            ctext(d, 380, "출근길 아침", font("Medium", 54), (190, 200, 225), fade)
            ctext(d, 450, f"{n}°", font("Black", 300), (255, 255, 255), fade)
            # 변화 알약
            if t > 1.4:
                a = prog(t, 1.4, 1.8) * fade
                txt = hook["delta"]; fn = font("Bold", 78)
                tw = d.textlength(txt, font=fn); x0 = (W - tw) / 2 - 50
                d.rounded_rectangle((x0, 860, x0 + tw + 100, 1000), 36, fill=BLUE + (round(255 * a),))
                d.text((x0 + 50, 870), txt, font=fn, fill=(255, 255, 255, round(255 * a)))
            paste_scaled(f, ch, W / 2, 1290, pop(t, 0.15) * (1 - .0 * fade), fade)
            # 카드가 아래에서 올라옴
            if t >= 2.5:
                y = round(H * (1 - prog(t, 2.5, 3.0)))
                if y < H: f.alpha_composite(scene.crop((0, 0, W, H - y)), (0, y))
            enc.add(f); continue
        # 2) 카드: 3~5.6초 기온 칸 확대 → 6.6초 전체 → 끝까지 아주 천천히 밀기
        zin = prog(t, 3.0, 3.6); zout = prog(t, 5.6, 6.6)
        s = 1 + 0.14 * zin * (1 - zout) + 0.03 * prog(t, 6.6, 10)
        fy = cy0 + 500 * k  # 카드의 '-1° → -3° / ▼2°' 줄
        cy = fy * (1 - zout) + (H / 2) * zout
        f = camera(scene, s, W / 2, cy)
        # 3) 마지막 1.4초 끝인사
        if t > 8.6:
            d = ImageDraw.Draw(f, "RGBA"); a = prog(t, 8.6, 9.1)
            d.rounded_rectangle((90, 1585, W - 90, 1715), 40, fill=(255, 255, 255, round(235 * a)))
            ctext(d, 1612, hook["outro"], font("Bold", 50), NAVY, a)
        enc.add(f)
    enc.close()


# ---------------------------------------------------------------- 파생 브리핑
def deriv(card1, card2, out, hook):
    c1 = Image.open(card1).convert("RGB"); c2 = Image.open(card2).convert("RGB")
    s1, cy0, k = card_scene(c1, LIGHT, hook["top1"], hook["bottom"], NAVY, (110, 120, 140))
    s2, _, _ = card_scene(c2, LIGHT, hook["top2"], hook["bottom"], NAVY, (110, 120, 140))
    ch = pose(hook["pose"], 380)
    enc = Encoder(out)
    for i in range(10 * FPS):
        t = i / FPS
        if t < 2.8:  # 훅: 외국인 vs 기관 숫자 카운트업
            f = Image.new("RGBA", (W, H), NAVY + (255,)); d = ImageDraw.Draw(f, "RGBA")
            fade = 1 - prog(t, 2.4, 2.8)
            ctext(d, 230, hook["kicker"], font("Bold", 44), ORANGE, fade)
            ctext(d, 300, hook["title"], font("Black", 70), (255, 255, 255), fade)
            p = prog(t, 0.4, 1.6)
            for j, (lab, val, col) in enumerate(hook["rows"]):
                y = 520 + j * 300; a = prog(t, 0.3 + j * .25, 0.7 + j * .25) * fade
                ctext(d, y, lab, font("Medium", 52), (190, 200, 225), a)
                ctext(d, y + 70, f"{round(val * p):+,}", font("Black", 150), col, a)
            ctext(d, 1170, hook["unit"], font("Medium", 38), (150, 165, 195), fade)
            paste_scaled(f, ch, W / 2, 1420, pop(t, 0.9), fade)
            if t >= 2.4:
                y = round(H * (1 - prog(t, 2.4, 2.8)))
                if y < H: f.alpha_composite(s1.crop((0, 0, W, H - y)), (0, y))
            enc.add(f); continue
        if t < 6.2:  # 카드1: 위 숫자칸 확대 → 아래 차트로 내려가기
            s = 1.12 - 0.12 * prog(t, 5.2, 6.0)
            cy = cy0 + (300 * k) + (750 - 300) * k * prog(t, 3.6, 5.0)
            f = camera(s1, s, W / 2, cy * (1 - prog(t, 5.2, 6.0)) + H / 2 * prog(t, 5.2, 6.0))
            if t > 5.9:  # 카드2로 밀기
                x = round(W * prog(t, 5.9, 6.2))
                f = f.crop((0, 0, W, H)); g = Image.new("RGBA", (W, H))
                g.alpha_composite(f, (-x, 0)); g.alpha_composite(s2, (W - x, 0)); f = g
            enc.add(f); continue
        # 카드2: 투자자별 누적 순매수 확대 → 신용잔고로
        s = 1 + 0.12 * prog(t, 6.2, 6.8) * (1 - prog(t, 8.4, 9.0))
        cy = (cy0 + 470 * k) * (1 - prog(t, 7.4, 8.2)) + (cy0 + 1040 * k) * prog(t, 7.4, 8.2)
        cy = cy * (1 - prog(t, 8.4, 9.0)) + H / 2 * prog(t, 8.4, 9.0)
        f = camera(s2, s, W / 2, cy)
        if t > 8.9:
            d = ImageDraw.Draw(f, "RGBA"); a = prog(t, 8.9, 9.3)
            d.rounded_rectangle((90, 1585, W - 90, 1715), 40, fill=NAVY + (round(240 * a),))
            ctext(d, 1612, hook["outro"], font("Bold", 50), (255, 255, 255), a)
        enc.add(f)
    enc.close()


if __name__ == "__main__":
    kind = sys.argv[1]
    if kind == "weather":
        weather(sys.argv[2], sys.argv[3], dict(
            where="서울 · 11월 25일 수요일", **{"from": -1, "to": -3}, delta="▼ 어제보다 2° 추워요",
            pose="w14", top="오늘 서울 날씨", bottom="@reddenva.kr · 매일 아침 6시",
            outro="내일 아침 6시에 또 올게요"))
    else:
        deriv(sys.argv[2], sys.argv[3], sys.argv[4], dict(
            kicker="목요일 파생 브리핑 · 11/18 마감", title="외국인은 사고, 기관은 팔았다",
            rows=[("외국인 선물 누적", 31709, RED), ("기관 선물 누적", -30160, (90, 150, 255))],
            unit="9월 만기 이후 · 단위 계약", pose="a08",
            top1="이번 주 파생 숫자", top2="누가 사고 누가 팔았나", bottom="@reddenva.kr · 매주 목요일 · 투자 권유 아님",
            outro="다음 주 목요일에 또 봐요"))
