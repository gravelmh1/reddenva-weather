"""네트워크 없이 테스트하기 위한 가짜 예보 (실제 예보 아님)."""
import datetime as dt
import math

SCENARIOS = {
    "live": dict(unit="C", hi=[15, 12, 16, 17, 16, 12, 6], lo=[8, 9, 7, 6, 8, 0, -1], rain=[16, 78, 0, 0, 98, 96, 0], code=0, yhi=14, ylo=6),
    "kr_mild": dict(unit="C", hi=[18, 14, 16, 15, 14, 10, 6], lo=[9, 10, 9, 9, 10, 2, -1], rain=[0] * 7, code=0),
    "us_warm": dict(unit="F", hi=[78, 67, 71, 73, 68, 68, 67], lo=[60, 57, 57, 58, 57, 52, 53], rain=[5, 75, 10, 10, 30, 15, 15], code=0),
    "rain": dict(unit="C", hi=[14, 12, 15, 16, 17, 15, 14], lo=[9, 8, 9, 10, 11, 9, 8], rain=[80, 60, 20, 10, 10, 30, 20], code=61),
    "cold": dict(unit="C", hi=[3, 2, 5, 7, 6, 4, 3], lo=[-5, -6, -3, -2, -1, -4, -5], rain=[0] * 7, code=0),
    "hot": dict(unit="F", hi=[96, 94, 91, 88, 85, 84, 86], lo=[70, 69, 68, 66, 64, 63, 65], rain=[0] * 7, code=0),
}


def make(name: str, start: dt.date) -> dict:
    s = dict(SCENARIOS[name])
    # 어제 값(비교용): 시나리오에 없으면 오늘보다 조금 낮게
    s["hi"] = [s.get("yhi", s["hi"][0] - 4)] + s["hi"]
    s["lo"] = [s.get("ylo", s["lo"][0] - 3)] + s["lo"]
    s["rain"] = [0] + s["rain"]
    N = 8
    daily = dict(time=[], temperature_2m_max=s["hi"], temperature_2m_min=s["lo"], precipitation_probability_max=s["rain"],
                 weather_code=[s["code"]] * N, wind_speed_10m_max=[12] * N)
    hourly = dict(time=[], temperature_2m=[], apparent_temperature=[], precipitation_probability=[], weather_code=[], wind_speed_10m=[])
    for i in range(N):
        day = start + dt.timedelta(days=i - 1)
        daily["time"].append(day.isoformat())
        for h in range(24):
            t = s["lo"][i] + (s["hi"][i] - s["lo"][i]) * (0.5 - 0.5 * math.cos(2 * math.pi * (h - 3) / 24))
            hourly["time"].append(f"{day.isoformat()}T{h:02d}:00")
            hourly["temperature_2m"].append(t); hourly["apparent_temperature"].append(t)
            hourly["precipitation_probability"].append(s["rain"][i]); hourly["weather_code"].append(s["code"]); hourly["wind_speed_10m"].append(12)
    return dict(daily=daily, hourly=hourly)
