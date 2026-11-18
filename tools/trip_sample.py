"""주말 여행 시안용: 후보 장소 사진(Wikimedia Commons, CC/퍼블릭 도메인)과 주말 날씨를 받아 samples/trip 에 저장."""
import json, os, re, requests, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from animals import commons, UA
SPOTS = {
    "kr": [("덕수궁 돌담길", "Deoksugung Doldam-gil", 37.5658, 126.9752), ("서울숲", "Seoul Forest", 37.5444, 127.0374),
           ("북촌 한옥마을", "Bukchon Hanok Village", 37.5826, 126.9830), ("창경궁", "Changgyeonggung", 37.5794, 126.9948), ("낙산공원", "Naksan Park Seoul", 37.5806, 127.0076), ("석촌호수", "Seokchon Lake", 37.5096, 127.1036)],
    "us": [("Descanso Gardens", "Descanso Gardens", 34.2015, -118.2104), ("Joshua Tree", "Joshua Tree National Park", 33.8734, -115.9010),
           ("Ojai", "Ojai Valley", 34.4480, -119.2429), ("Huntington Library", "Huntington Library gardens", 34.1290, -118.1145)],
}
os.makedirs("samples/trip", exist_ok=True); meta = {}
for reg, spots in SPOTS.items():
    for name, q, lat, lon in spots:
        try: cands = commons(q)[:4]
        except Exception as e: print("검색 실패", q, e); cands = []
        files = []
        for i, c in enumerate(cands):
            r = requests.get(c["url"], headers=UA, timeout=40)
            if r.ok:
                fn = f"samples/trip/{reg}_{re.sub(r'\\W+', '_', name)}_{i}.jpg"; open(fn, "wb").write(r.content); files.append(dict(c, file=fn))
        unit = "celsius" if reg == "kr" else "fahrenheit"
        try: w = requests.get("https://api.open-meteo.com/v1/forecast", timeout=30, params={"latitude": lat, "longitude": lon, "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code", "timezone": "auto", "forecast_days": 7, "temperature_unit": unit}).json().get("daily")
        except Exception as e: print("날씨 실패", e); w = None
        meta[f"{reg}|{name}"] = dict(files=files, weather=w)
        print(reg, name, len(files))
json.dump(meta, open("samples/trip/meta.json", "w"), ensure_ascii=False, indent=1)
