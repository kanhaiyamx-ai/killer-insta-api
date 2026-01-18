from fastapi import FastAPI
from curl_cffi import requests
import random
import time

app = FastAPI()

# Proxy and Cookies
PROXY_URL = "http://tyzozoto-rotate:6c23wyc9oc1r@p.webshare.io:80"
COOKIE_DICT = {
    "mid": "aWyxUQALAAEXSQj42YOKQ_p8v8dn",
    "ig_did": "84B2CD1D-1165-40DA-8A06-82419391BA7B",
    "csrftoken": "qVLbVtyryQwyHko3V0Ci8Q",
    "ds_user_id": "80010991653",
    "sessionid": "80010991653%3AvmA5lUgf0xOt7T%3A10%3AAYgn1yV_ZHAxNDo2je3EsHExh1F3F9saczllIeSQmg"
}

HEADERS = {
    "authority": "www.instagram.com",
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "x-ig-app-id": "936619743392459",
    "x-requested-with": "XMLHttpRequest",
    "referer": "https://www.instagram.com/",
}

@app.get("/profile/{username}")
def get_instagram_profile(username: str):
    # Using 'impersonate' makes the TLS fingerprint look exactly like Chrome 120
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    
    try:
        response = requests.get(
            url, 
            headers=HEADERS, 
            cookies=COOKIE_DICT,
            proxies={"http": PROXY_URL, "https": PROXY_URL},
            impersonate="chrome120",
            timeout=30
        )

        if response.status_code != 200:
            return {"error": f"Status {response.status_code}", "text": response.text[:200]}

        data = response.json()
        user = data.get("data", {}).get("user")

        if not user:
            return {
                "error": "Soft Blocked",
                "info": "Instagram detected the proxy. Try logging into the account on your PC and searching for a user to 'unlock' the session.",
                "raw_response": data
            }

        return {
            "username": user.get("username"),
            "followers": user.get("edge_followed_by", {}).get("count"),
            "bio": user.get("biography"),
            "pic": user.get("profile_pic_url_hd")
        }

    except Exception as e:
        return {"error": "Connection Failed", "details": str(e)}
