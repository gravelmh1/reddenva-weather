"""숫자를 날씨 전문가 톤의 문구와 캐릭터 포즈로 바꾼다. (LLM 없이 규칙으로 동작 = 토큰 0)"""
import datetime as dt
from weather import to_c

WD_KO = "월화수목금토일"
WD_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WD_EN_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _group(code: int) -> str:
    if code >= 95: return "thunder"
    if 71 <= code <= 77 or code in (85, 86): return "snow"
    if 51 <= code <= 67 or 80 <= code <= 82: return "rain"
    if code in (45, 48): return "fog"
    return "clear"


def features(p: dict, unit: str) -> dict:
    days, hourly = p["days"], p["hourly"]
    today, tom = days[0], days[1]
    hrs = hourly[today["date"]]
    morning = round(sum(hrs[h]["t"] for h in (7, 8, 9)) / 3)
    evening = round(hrs[18]["t"])
    day_hours = [hrs[h] for h in range(6, 23)]
    rain_day = max(x["rain"] for x in day_hours)
    order = ["clear", "fog", "rain", "snow", "thunder"]
    grp = max((_group(x["code"]) for x in day_hours), key=order.index)
    c = lambda v: to_c(v, unit)
    return dict(today=today, tom=tom, days=days, morning=morning, evening=evening, rain_day=rain_day, grp=grp,
                swing_c=round(c(today["hi"]) - c(today["lo"])), hi_c=c(today["hi"]), lo_c=c(today["lo"]),
                wind_hi=today["wind"], unit=unit, c=c)


def _outfit(cv: float, lang: str) -> str:
    bands = [(0, "패딩", "puffer jacket"), (5, "두꺼운 코트", "a heavy coat"), (11, "코트", "a coat"),
             (16, "자켓", "a light jacket"), (20, "가디건", "a cardigan"), (25, "긴팔 셔츠", "long sleeves")]
    for lim, ko, en in bands:
        if cv <= lim:
            return ko if lang == "ko" else en
    return "반팔" if lang == "ko" else "a T-shirt"


def _pick(options, seed):
    return options[seed % len(options)]


def build(f: dict, region: str, city: str, now: dt.datetime) -> dict:
    lang = "ko" if region == "kr" else "en"
    seed = now.timetuple().tm_yday
    c, unit = f["c"], f["unit"]
    t, tom = f["today"], f["tom"]
    wd_tom_i = dt.date.fromisoformat(tom["date"]).weekday()

    # ---- 헤드라인
    big_wind = (f["wind_hi"] >= 35) if unit == "C" else (f["wind_hi"] >= 22)
    if lang == "ko":
        if f["grp"] == "thunder": head = _pick(["천둥번개 예보, 오늘은 집이 최고예요", "번개 치는 날, 우산도 믿지 마세요"], seed)
        elif f["grp"] == "snow": head = _pick(["눈 예보, 걸음은 반 보폭으로 걸어요", "출근길 눈 소식, 10분 일찍 나서요"], seed)
        elif f["rain_day"] >= 60: head = _pick([f"비 올 확률 {f['rain_day']}%, 우산 없이 나가면 도박이에요", f"비 {f['rain_day']}%, 오늘 신발은 방수로 가요"], seed)
        elif f["rain_day"] >= 40: head = f"비 올 확률 {f['rain_day']}%, 접이식 우산은 가방 속에"
        elif f["swing_c"] >= 8: head = _pick([f"일교차 {f['swing_c']}도, 겉옷은 벗을 수 있게 입는 날", f"아침과 낮이 {f['swing_c']}도 차이, 양파처럼 껴입어요"], seed)
        elif f["hi_c"] >= 30: head = f"최고 {t['hi']}도, 오늘은 그늘이 명당이에요"
        elif f["lo_c"] <= 0: head = _pick([f"최저 {t['lo']}도, 장갑 챙긴 사람이 승자예요", f"영하 {abs(t['lo'])}도, 이불 밖은 위험해요"], seed)
        elif big_wind: head = f"바람 최고 시속 {t['wind']}km, 머리 스타일은 포기해요"
        else: head = _pick(["무난한 하루, 그래도 겉옷 하나는 챙겨요", "오늘 날씨는 얌전해요. 기분은 알아서!"], seed)
    else:
        if f["grp"] == "thunder": head = _pick(["Thunderstorms today: stay in if you can", "Lightning in the forecast. Skip the golf."], seed)
        elif f["grp"] == "snow": head = "Snow in the forecast: leave 10 minutes early"
        elif f["rain_day"] >= 60: head = _pick([f"{f['rain_day']}% chance of rain: umbrella day", f"Rain odds {f['rain_day']}%. Waterproof shoes, please."], seed)
        elif f["rain_day"] >= 40: head = f"{f['rain_day']}% rain chance: pack a compact umbrella"
        elif f["swing_c"] >= 8:
            head = f"{f['morning']}° at breakfast, {t['hi']}° at lunch" if f["morning"] != t["hi"] else "Big swing today: dress in layers"
        elif f["hi_c"] >= 30: head = f"High of {t['hi']}°: find the shade"
        elif f["lo_c"] <= 0: head = f"Low of {t['lo']}°: gloves are non-negotiable"
        elif big_wind: head = f"Gusts up to {t['wind']} mph: hold onto your hat"
        else: head = _pick(["A calm one today, but a light layer never hurts", "Weather is behaving today. Enjoy it."], seed)

    # ---- 줄 1: 우산
    p = f["rain_day"]
    if lang == "ko":
        if f["grp"] == "snow": umb = "눈 예보, 미끄럼 주의"
        elif p >= 50: umb = f"꼭 챙기세요 (강수 {p}%)"
        elif p >= 20: umb = f"챙기면 마음 편해요 ({p}%)"
        else: umb = f"필요 없어요 (강수 {p}%)"
    else:
        if f["grp"] == "snow": umb = "Snow expected, watch your step"
        elif p >= 50: umb = f"Yes, bring one ({p}%)"
        elif p >= 20: umb = f"Maybe, to be safe ({p}%)"
        else: umb = f"Not needed ({p}%)"

    # ---- 줄 2: 옷차림
    om, oa = _outfit(c(f["morning"]), lang), _outfit(c(t["hi"]), lang)
    if lang == "ko":
        wear = f"종일 {oa} 차림이면 충분해요" if om == oa else f"아침 {f['morning']}도엔 {om}, 낮 {t['hi']}도엔 {oa}"
    else:
        wear = f"{oa[0].upper()+oa[1:]} all day will do" if om == oa else f"{om[0].upper()+om[1:]} now, {oa} by noon"

    # ---- 줄 3: 미리보기
    third = None
    for d in f["days"][1:]:
        if c(d["lo"]) <= 0 and c(t["lo"]) > 0:
            i = dt.date.fromisoformat(d["date"]).weekday()
            third = (("주의", f"{WD_KO[i]}요일 최저 {d['lo']}도, 영하로 내려가요") if lang == "ko"
                     else ("Heads up", f"{WD_EN_FULL[i]} dips to {d['lo']}°, freezing")); break
    if not third:
        dh = tom["hi"] - t["hi"]
        if c(tom["hi"]) - c(t["hi"]) <= -5:
            third = (("내일", f"최고 {tom['hi']}도, 오늘보다 {abs(dh)}도 낮아요") if lang == "ko"
                     else ("Tomorrow", f"high drops {abs(dh)}° to {tom['hi']}°"))
        elif tom["rain"] >= 60:
            third = (("내일", f"비 {tom['rain']}% 예보") if lang == "ko" else ("Tomorrow", f"rain, {tom['rain']}% chance"))
        elif c(tom["hi"]) - c(t["hi"]) >= 5:
            third = (("내일", f"최고 {tom['hi']}도, 오늘보다 {dh}도 올라요") if lang == "ko"
                     else ("Tomorrow", f"warms up {dh}° to {tom['hi']}°"))
        else:
            dd = f["evening"] - f["morning"]
            third = ((("퇴근길", f"{f['evening']}도, 아침보다 {abs(dd)}도 {'높아요' if dd >= 0 else '낮아요'}")) if lang == "ko"
                     else ("Evening", f"{f['evening']}°, {abs(dd)}° {'warmer' if dd >= 0 else 'cooler'} than morning"))
    rows = [("우산" if lang == "ko" else "Umbrella", umb), ("옷차림" if lang == "ko" else "Wear", wear), third]

    # ---- 포즈
    if f["grp"] in ("thunder", "snow") or f["rain_day"] >= 50: pose = "a10"
    elif f["lo_c"] <= 3: pose = "a18"
    elif f["hi_c"] >= 24: pose = "a16"
    elif f["swing_c"] >= 8: pose = "a05"
    elif big_wind: pose = "a09"
    else: pose = "a00"

    # ---- 캡션 (Instagram과 Threads 공통)
    if lang == "ko":
        wd = WD_KO[now.weekday()]
        top = f"{city} {now.month}/{now.day}({wd}) 최고 {t['hi']}° · 최저 {t['lo']}°"
        tags = "#서울날씨 #출근길날씨 #오늘의날씨 #날씨 #레드덴바"
    else:
        wd = WD_EN[now.weekday()]
        top = f"{city} {wd} {now.month}/{now.day}: high {t['hi']}° · low {t['lo']}°"
        tags = "#LAWeather #LosAngeles #MorningCommute #TodayWeather #RedDenva"
    body = "\n".join(["· " + (f"{a}: {b}") for a, b in rows])
    caption = f"{top}\n{head}\n{body}\n\n{tags}"
    return dict(headline=head, rows=rows, pose=pose, caption=caption, lang=lang)
