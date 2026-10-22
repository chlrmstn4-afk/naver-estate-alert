"""네이버부동산 비공개 API 클라이언트.

주의: 비공개(미문서화) API라 구조가 바뀔 수 있음. 토큰 추출이 실패하면
DEBUG_HTML_DUMP 환경변수를 1로 두고 Actions 로그에서 raw HTML을 확인할 것.
"""
import os
import re
import time
import json
import requests

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
BASE = "https://new.land.naver.com"

TOKEN_PATTERNS = [
    re.compile(r"Bearer\s+([A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+)"),
    re.compile(r'"authorization"\s*:\s*"Bearer\s+([^"]+)"'),
    re.compile(r"NLR_ATK['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]"),
]


class NaverLandError(RuntimeError):
    pass


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9",
    })
    return s


def get_auth_token(session: requests.Session, complex_no: str) -> str:
    url = f"{BASE}/complexes/{complex_no}"
    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    html = resp.text

    for pat in TOKEN_PATTERNS:
        m = pat.search(html)
        if m:
            return m.group(1)

    if os.environ.get("DEBUG_HTML_DUMP") == "1":
        print("---- token not found, dumping first 3000 chars of HTML ----")
        print(html[:3000])

    raise NaverLandError(
        f"complex {complex_no} 페이지에서 인증 토큰을 찾지 못했습니다. "
        "사이트 구조가 바뀌었을 수 있습니다."
    )


def parse_price(raw: str) -> int:
    """'9억 5,000' 같은 문자열을 만원 단위 정수로 변환."""
    if not raw:
        return 0
    s = raw.replace(",", "").strip()
    if "억" in s:
        eok_str, _, rest = s.partition("억")
        eok = int(eok_str.strip()) if eok_str.strip() else 0
        rest = rest.strip()
        man = int(rest) if rest else 0
        return eok * 10000 + man
    return int(s) if s else 0


def fetch_articles(session: requests.Session, token: str, complex_no: str, trade_type: str, max_pages: int = 50):
    """해당 단지/거래유형의 전체 매물을 article_no 기준 dict로 반환."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Referer": f"{BASE}/complexes/{complex_no}",
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
    }
    results = {}
    page = 1
    while page <= max_pages:
        url = f"{BASE}/api/articles/complex/{complex_no}"
        params = {"realEstateType": "APT", "tradeType": trade_type, "page": page}
        resp = session.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 429:
            time.sleep(5)
            continue
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("articleList", []):
            no = str(item.get("articleNo"))
            area2 = item.get("area2") or item.get("spc2") or 0
            area1 = item.get("area1") or item.get("spc1") or 0
            results[no] = {
                "article_no": no,
                "complex_no": complex_no,
                "trade_type": trade_type,
                "price_man": parse_price(item.get("dealOrWarrantPrc", "")),
                "area_exclusive_m2": float(area2) if area2 else 0,
                "area_supply_m2": float(area1) if area1 else 0,
                "floor_info": item.get("floorInfo", ""),
                "direction": item.get("direction", ""),
                "building_name": item.get("buildingName", ""),
                "confirm_date": item.get("articleConfirmYmd", ""),
                "feature_desc": item.get("articleFeatureDesc", ""),
                "tags": item.get("tagList", []),
            }

        if not data.get("isMoreData"):
            break
        page += 1
        time.sleep(1.5)

    return results


def fetch_complex_snapshot(session: requests.Session, token: str, complex_no: str, trade_types):
    snapshot = {}
    for tt in trade_types:
        snapshot.update(fetch_articles(session, token, complex_no, tt))
        time.sleep(1.5)
    return snapshot
