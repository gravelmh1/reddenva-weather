"""날짜 달력 아이콘(월 띠 + 큰 날짜). 날씨 카드에서 잘 보였던 모양을 모든 Red Denva 콘텐츠에 쓴다."""
import datetime as dt
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw
from render import font, fit

ACCENT = (214, 66, 26)
INK = (18, 30, 52)
TZ = {"kr": "Asia/Seoul", "us": "America/Los_Angeles"}
KO_DAYS = "월화수목금토일"


def region_of(handle_or_region: str) -> str:
    return "kr" if str(handle_or_region).endswith("kr") else "us"


def today(handle_or_region: str) -> dt.date:
    return dt.datetime.now(ZoneInfo(TZ[region_of(handle_or_region)])).date()


def tile(d: ImageDraw.ImageDraw, x: int, y: int, size: int, day: dt.date, ko: bool, accent=ACCENT, ink=INK):
    """흰 달력 칸. 위에 색 띠(월), 아래 큰 날짜."""
    r = max(8, int(size * .16)); band = int(size * .3)
    d.rounded_rectangle([x, y, x + size, y + size], radius=r, fill="white", outline=(214, 218, 226), width=2)
    d.rounded_rectangle([x, y, x + size, y + band + r], radius=r, fill=accent)
    d.rectangle([x, y + band, x + size, y + band + r], fill="white")
    mon = f"{day.month}월 {KO_DAYS[day.weekday()]}" if ko else day.strftime("%b %a").upper()
    d.text((x + size / 2, y + band / 2 + 1), mon, font=fit(d, mon, "Bold", int(size * .2), size - 12, 12), fill="white", anchor="mm")
    d.text((x + size / 2, y + band + (size - band) / 2 + 2), str(day.day), font=font("Black", int(size * .5)), fill=ink, anchor="mm")


def date_text(day: dt.date, ko: bool) -> str:
    return f"{day.month}월 {day.day}일 {KO_DAYS[day.weekday()]}요일" if ko else day.strftime("%A, %b ") + str(day.day)


def cream_header(im, d, c: dict, W: int, M: int, navy, orange):
    """책·좋은 뉴스·아기 동물 카드 머리: 달력 아이콘 + 시리즈 이름 + 큰 날짜(요일) + 계정. 구분선은 y=140."""
    ko = region_of(c["handle"]) == "kr"
    day = c.get("date") or today(c["handle"])
    if isinstance(day, str):
        day = dt.date.fromisoformat(day)
    tile(d, M, 22, 104, day, ko)
    label = c["top"].split(" · ")[0]
    x = M + 128
    hf = font("Bold", 26); hw = d.textlength(c["handle"], font=hf)
    d.text((x, 30), label, font=fit(d, label, "Bold", 26, W - M - hw - 30 - x, 18), fill=orange)
    dtx = date_text(day, ko)
    d.text((x, 66), dtx, font=fit(d, dtx, "Black", 44, W - M - x, 28), fill=navy)
    d.text((W - M - hw, 30), c["handle"], font=hf, fill=orange)
    d.line([(M, 140), (W - M, 140)], fill=navy, width=3)


def stamp_png(path: str, region: str, x: int = 59, y: int = 34, size: int = 118):
    """matplotlib로 만든 카드(파생 브리핑)에 나중에 달력 아이콘을 찍는다."""
    im = Image.open(path).convert("RGB"); d = ImageDraw.Draw(im)
    tile(d, x, y, size, today(region), region == "kr")
    im.save(path)
