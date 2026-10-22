import json
import requests

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def send_text_memo(access_token: str, text: str, link_url: str = "https://new.land.naver.com") -> dict:
    template = {
        "object_type": "text",
        "text": text[:195],
        "link": {"web_url": link_url, "mobile_web_url": link_url},
        "button_title": "네이버부동산 보기",
    }
    resp = requests.post(
        MEMO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps(template, ensure_ascii=False)},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()
