import os
import random
import time
from fastapi import FastAPI, Request, HTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from curl_cffi import requests

# 1. Setup Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Stable Instagram API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 2. Simple Manual Cache (Dictionary)
# This replaces the unreliable fastapi-cache library
INTERNAL_CACHE = {}
CACHE_EXPIRATION = 3600 # 1 hour

# --- CONFIGURATION ---
PROXY_URL = "http://tyzozoto-rotate:6c23wyc9oc1r@p.webshare.io:80"
COOKIES = {
    "mid": "aWyxUQALAAEXSQj42YOKQ_p8v8dn",
    "ig_did": "84B2CD1D-1165-40DA-8A06-82419391BA7B",
    "csrftoken": "qVLbVtyryQwyHko3V0Ci8Q",
    "ds_user_id": "80010991653",
    "sessionid": "80010991653%3AvmA5lUgf0xOt7T%3A10%3AAYgn1yV_ZHAxNDo2je3EsHExh1F3F9saczllIeSQmg"
}

@app.get("/")
def home():
    return {"status": "API Online", "cache_size": len(INTERNAL_CACHE)}

@app.get("/profile/{username}")
@limiter.limit("10/minute")
async def get_instagram_profile(request: Request, username: str):
    username = username.lower().strip()
    
    # Check Manual Cache
    if username in INTERNAL_CACHE:
        cached_data, timestamp = INTERNAL_CACHE[username]
        if time.time() - timestamp < CACHE_EXPIRATION:
            cached_data["source"] = "cache"
            return cached_data

    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    
    headers = {
        "x-ig-app-id": "936619743392459",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "referer": f"https://www.instagram.com/{username}/",
        "x-requested-with": "XMLHttpRequest",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            cookies=COOKIES,
            proxies={"http": PROXY_URL, "https": PROXY_URL},
            impersonate="chrome120",
            timeout=25
        )

        if response.status_code != 200:
            return {"error": f"Instagram Error {response.status_code}"}

        json_data = response.json()
        user = json_data.get("data", {}).get("user")
        
        if not user:
            return {"error": "Soft Blocked", "msg": "Instagram returned empty data."}

        profile_data = {
            "source": "live",
            "username": user.get("username"),
            "full_name": user.get("full_name"),
            "followers": user.get("edge_followed_by", {}).get("count"),
            "following": user.get("edge_follow", {}).get("count"),
            "posts": user.get("edge_owner_to_timeline_media", {}).get("count"),
            "bio": user.get("biography"),
            "dp": user.get("profile_pic_url_hd")
        }

        # Save to Manual Cache
        INTERNAL_CACHE[username] = (profile_data, time.time())
        
        return profile_data

    except Exception as e:
        return {"error": "Request Failed", "details": str(e)}
