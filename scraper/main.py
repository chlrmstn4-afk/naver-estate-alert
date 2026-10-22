import os
import json
from pathlib import Path
from datetime import date

from naver_client import get_session, get_auth_token, fetch_complex_snapshot
from diff import diff_snapshot, build_summary_lines
import kakao_notify

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
DATA_DIR = ROOT / "docs" / "data"
REFRESH_TOKEN_PATH = ROOT / "state" / "kakao_refresh_token.txt"

TODAY = date.today().isoformat()


def to_pyeong(m2: float) -> float:
    return round(m2 / 3.3058, 1)


def load_json(path: Path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def build_history_entry(snapshot: dict):
    by_area = {}
    for item in snapshot.values():
        key = str(int(round(to_pyeong(item["area_exclusive_m2"]))))
        bucket = by_area.setdefault(key, {"count": 0, "prices": []})
        bucket["count"] += 1
        bucket["prices"].append(item["price_man"])

    for b in by_area.values():
        prices = b.pop("prices")
        b["avg_price_man"] = round(sum(prices) / len(prices)) if prices else 0
        b["min_price_man"] = min(prices) if prices else 0
        b["max_price_man"] = max(prices) if prices else 0

    return {"date": TODAY, "total_count": len(snapshot), "by_area": by_area}


def append_events(events_path: Path, complex_no: str, new, changed, closed):
    events = load_json(events_path, [])
    for x in new:
        events.append({"date": TODAY, "type": "new", "complex_no": complex_no, **x})
    for x in changed:
        events.append({
            "date": TODAY, "type": "changed", "complex_no": complex_no,
            "article_no": x["article_no"],
            "old_price_man": x["old_price_man"],
            "new_price_man": x["new_price_man"],
            "area_exclusive_m2": x["item"]["area_exclusive_m2"],
        })
    for x in closed:
        events.append({"date": TODAY, "type": "closed", "complex_no": complex_no, **x})
    events = events[-500:]
    save_json(events_path, events)


def main():
    config = load_json(CONFIG_PATH, {"complexes": [], "trade_types": ["A1"], "watched_areas": {}})
    trade_types = config.get("trade_types", ["A1"])
    watched_areas_cfg = config.get("watched_areas", {})

    session = get_session()
    summaries = []

    for c in config.get("complexes", []):
        no = c["complex_no"]
        name = c.get("name", no)
        print(f"[{name}] 수집 시작 (complex_no={no})")

        token = get_auth_token(session, no)
        today_snapshot = fetch_complex_snapshot(session, token, no, trade_types)
        print(f"[{name}] 오늘 매물 수: {len(today_snapshot)}")

        complex_dir = DATA_DIR / no
        latest_path = complex_dir / "latest.json"
        history_path = complex_dir / "history.json"
        events_path = complex_dir / "events.json"
        meta_path = complex_dir / "meta.json"

        prev_snapshot = load_json(latest_path, {})
        new, changed, closed = diff_snapshot(prev_snapshot, today_snapshot)
        print(f"[{name}] 신규 {len(new)} / 가격변동 {len(changed)} / 소멸 {len(closed)}")

        save_json(latest_path, today_snapshot)
        save_json(meta_path, {"complex_no": no, "name": name, "updated": TODAY})

        history = load_json(history_path, [])
        history = [h for h in history if h["date"] != TODAY]
        history.append(build_history_entry(today_snapshot))
        history = history[-365:]
        save_json(history_path, history)

        append_events(events_path, no, new, changed, closed)

        watched_raw = watched_areas_cfg.get(no)
        watched_ranges = [tuple(r) for r in watched_raw] if watched_raw else None
        summary = build_summary_lines(name, new, changed, closed, watched_ranges)
        if summary:
            summaries.append(summary)

    manifest = [
        {"complex_no": c["complex_no"], "name": c.get("name", c["complex_no"]), "role": c.get("role", "watch")}
        for c in config.get("complexes", [])
    ]
    save_json(DATA_DIR / "manifest.json", manifest)

    if summaries:
        text = "\n\n".join(summaries)
        print("---- 카카오 알림 전송 ----")
        print(text)
        send_kakao(text)
    else:
        print("알림 대상 변동 없음")


def send_kakao(text: str):
    client_id = os.environ["KAKAO_REST_API_KEY"]
    client_secret = os.environ["KAKAO_CLIENT_SECRET"]
    refresh_token = REFRESH_TOKEN_PATH.read_text(encoding="utf-8").strip()

    token_data = kakao_notify.refresh_access_token(client_id, client_secret, refresh_token)
    access_token = token_data["access_token"]

    new_refresh = token_data.get("refresh_token")
    if new_refresh and new_refresh != refresh_token:
        REFRESH_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        REFRESH_TOKEN_PATH.write_text(new_refresh, encoding="utf-8")
        print("refresh_token 갱신됨 (커밋 필요)")

    kakao_notify.send_text_memo(access_token, text)


if __name__ == "__main__":
    main()
