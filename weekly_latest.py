"""오늘 만든 주간 카드(책/뉴스) 중 하나를 out/weekly-{region}-latest.json 으로 복사한다. (Make가 이 파일 하나만 읽도록)"""
import datetime as dt, json, os, shutil, sys
from zoneinfo import ZoneInfo
import weather

region = sys.argv[1]; day = dt.datetime.now(ZoneInfo(weather.REGIONS[region]["tz"])).date().isoformat()
for kind in ("books", "news"):
    p = f"out/{kind}-{region}-latest.json"
    if os.path.exists(p) and json.load(open(p, encoding="utf-8")).get("date") == day:
        shutil.copy(p, f"out/weekly-{region}-latest.json"); print("weekly latest ←", kind); break
else:
    print("오늘 만든 주간 카드 없음")
