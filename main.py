import os
import random
import time
from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi_cache import FastAPICache
from fastapi_cache.decorator import cache
from curl_cffi import requests

# Failsafe for Cache Backend Import
try:
    from fastapi_cache.backends.in_memory import InMemoryCacheBackend
except ImportError:
    try:
        from fastapi_cache.backends.inmemory import InMemoryCacheBackend
    except ImportError:
        InMemoryCacheBackend = None

# 1. Rate Limiter Setup
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Stable Instagram API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 2. Cache Initialization with Failsafe
@app.on_event("startup")
async def startup():
    if InMemoryCacheBackend:
        FastAPICache.init(InMemoryCacheBackend())
    else:
        print("Warning: Cache backend not found. API will run without caching.")

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
    return {"status": "API is online", "cache_active": InMemoryCacheBackend is not None}

@app.get("/profile/{username}")
@limiter.limit("5/minute")
@cache(expire=3600)
async def get_instagram_profile(request: Request, username: str):
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

        data = response.json().get("data", {}).get("user")
        if not data:
            return {"error": "Soft Blocked", "msg": "Instagram returned empty data."}

        return {
            "username": data.get("username"),
            "full_name": data.get("full_name"),
            "followers": data.get("edge_followed_by", {}).get("count"),
            "bio": data.get("biography"),
            "dp": data.get("profile_pic_url_hd")
        }

    except Exception as e:
        return {"error": "Request Failed", "details": str(e)}
