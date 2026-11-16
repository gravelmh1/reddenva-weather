"""미국 파생 브리핑용 자료 수집 (공식 공개 자료 위주). 결과를 out/us_deriv_data.json 에 저장."""
import csv, io, json, re, sys, datetime as dt
import requests
UA = {"User-Agent": "RedDenvaBot/1.0 (https://github.com/gravelmh1/reddenva-weather)"}
out = {"fetched_at": dt.datetime.utcnow().isoformat() + "Z"}
def log(*a): print(*a, flush=True)
# 1) FRED: S&P500, VIX, 미국채 10년
try:
    out["fred"] = {}
    for sid in ("SP500", "VIXCLS", "DGS10"):
        r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": sid, "cosd": "2026-08-15"}, headers=UA, timeout=40); r.raise_for_status()
        log(sid, r.headers.get("content-type"), repr(r.text[:120]))
        rows = [ln.split(",") for ln in r.text.strip().splitlines()[1:]]
        out["fred"][sid] = [[d, v] for d, v in rows if v not in (".", "")]; log(sid, len(rows), out["fred"][sid][-3:])
except Exception as e: log("FRED 실패", e)
# 2) CFTC TFF (금융선물 트레이더 분류) E-mini S&P 500 (code 13874A)
try:
    r = requests.get("https://publicreporting.cftc.gov/resource/gpe5-46if.json", params={"cftc_contract_market_code": "13874A", "$order": "report_date_as_yyyy_mm_dd DESC", "$limit": 20}, headers=UA, timeout=40); r.raise_for_status()
    j = r.json(); keep = ["report_date_as_yyyy_mm_dd", "market_and_exchange_names", "open_interest_all", "dealer_positions_long_all", "dealer_positions_short_all", "asset_mgr_positions_long", "asset_mgr_positions_short", "lev_money_positions_long", "lev_money_positions_short", "other_rept_positions_long", "other_rept_positions_short", "nonrept_positions_long_all", "nonrept_positions_short_all"]
    out["cot"] = [{k: x.get(k) for k in keep + ["change_in_lev_money_long", "change_in_lev_money_short", "change_in_asset_mgr_long", "change_in_asset_mgr_short", "change_in_dealer_long_all", "change_in_dealer_short_all"]} for x in j]; log("COT", len(j), json.dumps(out["cot"][0])[:400])
    if j: log("COT keys", sorted(j[0].keys())[:80])
except Exception as e: log("COT 실패", e)
# 3) ES 선물 (Yahoo 차트, 비공식)
try:
    r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/ES=F", params={"range": "6mo", "interval": "1d"}, headers={"User-Agent": "Mozilla/5.0"}, timeout=40); r.raise_for_status()
    res = r.json()["chart"]["result"][0]; ts = res["timestamp"]; cl = res["indicators"]["quote"][0]["close"]
    out["es"] = [[dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"), c] for t, c in zip(ts, cl)]; log("ES", len(ts), out["es"][-3:])
except Exception as e: log("ES 실패", e)
# 4) FINRA margin statistics
try:
    r = requests.get("https://www.finra.org/rules-guidance/key-topics/margin-accounts/margin-statistics", headers={"User-Agent": "Mozilla/5.0"}, timeout=40); r.raise_for_status()
    import pandas as pd
    t = pd.read_html(io.StringIO(r.text))
    log("FINRA tables", len(t)); 
    if t: df = t[0]; log(df.head(14).to_string()); out["finra"] = df.head(26).astype(str).values.tolist(); out["finra_cols"] = [str(c) for c in df.columns]
except Exception as e: log("FINRA 실패", e)
json.dump(out, open("out/us_deriv_data.json", "w"), ensure_ascii=False, indent=1)
