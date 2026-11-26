"""임시: 선물 투자자별 순매수 과거값 출처 찾기 (3차)."""
import requests
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
B = "https://m.stock.naver.com"
for p in ("/api/index/FUT/trend?bizdate=20261125", "/api/index/FUT/trend?bizdate=20260915", "/api/index/FUT/trend?date=20261125",
          "/api/index/FUT/trend/daily?pageSize=20&page=1", "/api/index/FUT/trend/list?pageSize=20", "/api/index/FUT/trends?pageSize=20",
          "/api/index/KOSPI/trend?bizdate=20261125", "/api/index/FUT/price?pageSize=10&page=1", "/api/index/FUT/integration",
          "/front-api/index/FUT/trend", "/front-api/marketIndex/investorTrend?code=FUT", "/api/index/FUT/investorTrend?pageSize=20",
          "/api/index/KOSPI/trend/daily?pageSize=10", "/front-api/index/investor?code=FUT"):
    try:
        r = requests.get(B + p, headers=H, timeout=20); print("===", p, r.status_code, r.text[:500].replace("\n", " ") if "json" in r.headers.get("content-type", "") else r.headers.get("content-type"))
    except Exception as e: print("===", p, "ERR", e)
