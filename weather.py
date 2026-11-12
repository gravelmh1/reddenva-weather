"""Open-Meteo에서 예보를 가져오고 필요한 값으로 정리한다."""
import os
import requests

REGIONS = {
    "kr": dict(city="서울", lat=37.5665, lon=126.9780, tz="Asia/Seoul", unit="C", lang="ko"),
    "us": dict(city="Los Angeles", lat=34.0522, lon=-118.2437, tz="America/Los_Angeles", unit="F", lang="en"),
}


def fetch(region: str) -> dict:
    r = REGIONS[region]
    key = os.environ.get("OPEN_METEO_API_KEY", "").strip()
    host = "https://customer-api.open-meteo.com" if key else "https://api.open-meteo.com"
    params = {
        "latitude": r["lat"], "longitude": r["lon"], "timezone": r["tz"], "forecast_days": 7,
        "temperature_unit": "celsius" if r["unit"] == "C" else "fahrenheit",
        "wind_speed_unit": "kmh" if r["unit"] == "C" else "mph",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code,wind_speed_10m_max",
        "hourly": "temperature_2m,apparent_temperature,precipitation_probability,weather_code,wind_speed_10m",
    }
    if key:
        params["apikey"] = key
    resp = requests.get(f"{host}/v1/forecast", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def to_c(v: float, unit: str) -> float:
    return v if unit == "C" else (v - 32) / 1.8


def parse(data: dict) -> dict:
    d = data["daily"]
    days = []
    for i, date in enumerate(d["time"]):
        days.append(dict(date=date, hi=round(d["temperature_2m_max"][i]), lo=round(d["temperature_2m_min"][i]),
                         rain=int(d["precipitation_probability_max"][i] or 0), code=int(d["weather_code"][i] or 0),
                         wind=round(d["wind_speed_10m_max"][i])))
    h = data["hourly"]
    hourly = {}
    for i, t in enumerate(h["time"]):
        date, hh = t.split("T")
        hourly.setdefault(date, {})[int(hh[:2])] = dict(
            t=h["temperature_2m"][i], feel=h["apparent_temperature"][i],
            rain=int(h["precipitation_probability"][i] or 0), code=int(h["weather_code"][i] or 0))
    return dict(days=days, hourly=hourly)
