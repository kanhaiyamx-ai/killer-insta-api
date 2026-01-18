from fastapi import FastAPI, HTTPException, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryCacheBackend
from fastapi_cache.decorator import cache
from curl_cffi import requests
import random
import time
import asyncio

# 1. Setup Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Pro IG Scraper API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 2. Setup In-Memory Cache (Simple for Railway)
@app.on_event("startup")
async def startup():
    FastAPICache.init(InMemoryCacheBackend())

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
    return {"status": "Pro API Online", "endpoints": ["/profile/{username}"]}

@app.get("/profile/{username}")
@limiter.limit("5/minute")  # Limits each IP to 5 searches per minute
@cache(expire=3600)         # Saves results for 1 hour (3600 seconds)
async def get_instagram_profile(request: Request, username: str):
    """
    Fetches Instagram data with caching and rate limiting.
    The @cache decorator ensures that repeat searches are instant.
    """
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
        # Mimic real browser TLS handshake
        response = requests.get(
            url,
            headers=headers,
            cookies=COOKIES,
            proxies={"http": PROXY_URL, "https": PROXY_URL},
            impersonate="chrome120",
            timeout=25
        )

        if response.status_code != 200:
            return {"error": f"Instagram Error {response.status_code}", "msg": "Session or Proxy issue"}

        data = response.json().get("data", {}).get("user")
        if not data:
            return {"error": "Soft Block", "msg": "Instagram returned empty data."}

        # Success Response
        return {
            "cached_at": time.ctime(),
            "username": data.get("username"),
            "full_name": data.get("full_name"),
            "followers": data.get("edge_followed_by", {}).get("count"),
            "following": data.get("edge_follow", {}).get("count"),
            "posts": data.get("edge_owner_to_timeline_media", {}).get("count"),
            "bio": data.get("biography"),
            "is_private": data.get("is_private"),
            "dp": data.get("profile_pic_url_hd")
        }

    except Exception as e:
        return {"error": "Server Error", "details": str(e)}
