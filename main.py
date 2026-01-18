import os
import random
import time
from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi_cache import FastAPICache
from fastapi_cache.backends.in_memory import InMemoryCacheBackend # Fixed Import Path
from fastapi_cache.decorator import cache
from curl_cffi import requests

# 1. Rate Limiter Setup
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Pro Instagram API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 2. Cache Initialization (Fixed Backend)
@app.on_event("startup")
async def startup():
    FastAPICache.init(InMemoryCacheBackend())

# --- CONFIGURATION (Safe approach) ---
# It's better to set these in Railway "Variables" tab, 
# but I have kept your values here for immediate use.
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
    return {"status": "API Online", "docs": "/docs"}

@app.get("/profile/{username}")
@limiter.limit("5/minute")  # Prevent spamming
@cache(expire=3600)         # Cache results for 1 hour
async def get_instagram_profile(request: Request, username: str):
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    
    headers = {
        "authority": "www.instagram.com",
        "accept": "*/*",
        "x-ig-app-id": "936619743392459",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "referer": f"https://www.instagram.com/{username}/",
        "x-requested-with": "XMLHttpRequest",
    }

    try:
        # Using curl_cffi for advanced TLS impersonation
        response = requests.get(
            url,
            headers=headers,
            cookies=COOKIES,
            proxies={"http": PROXY_URL, "https": PROXY_URL},
            impersonate="chrome120",
            timeout=25
        )

        if response.status_code != 200:
            return {"error": f"Instagram Error {response.status_code}", "msg": "Check proxy/session"}

        data = response.json().get("data", {}).get("user")
        if not data:
            return {"error": "Soft Blocked", "msg": "Empty data returned from Instagram"}

        return {
            "cached_at": time.ctime(),
            "username": data.get("username"),
            "full_name": data.get("full_name"),
            "followers": data.get("edge_followed_by", {}).get("count"),
            "following": data.get("edge_follow", {}).get("count"),
            "bio": data.get("biography"),
            "is_private": data.get("is_private"),
            "profile_pic": data.get("profile_pic_url_hd")
        }

    except Exception as e:
        return {"error": "Request Failed", "details": str(e)}
