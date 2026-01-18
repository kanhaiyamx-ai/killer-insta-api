import time
import random
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from curl_cffi import requests

# 1. Setup Rate Limiter (Prevents one user from breaking your API)
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Lovable Backend API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 2. Enable CORS (Required for Lovable/Frontend to work)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace "*" with your Lovable site URL
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. High-Speed Memory Cache
INTERNAL_CACHE = {}
CACHE_TIME = 3600  # Data stays fresh for 1 hour

# --- CONFIGURATION ---
PROXY_URL = "http://tyzozoto-rotate:6c23wyc9oc1r@p.webshare.io:80"
COOKIES = {
    "mid": "aWyxUQALAAEXSQj42YOKQ_p8v8dn",
    "ig_did": "84B2CD1D-1165-40DA-8A06-82419391BA7B",
    "csrftoken": "qVLbVtyryQwyHko3V0Ci8Q",
    "ds_user_id": "80010991653",
    "sessionid": "80010991653%3AvmA5lUgf0xOt7T%3A10%3AAYgn1yV_ZHAxNDo2je3EsHExh1F3F9saczllIeSQmg"
}

@app.get("/profile/{username}")
@limiter.limit("10/minute") # Each visitor can search 10 times per minute
async def get_profile(request: Request, username: str):
    user_key = username.lower().strip()

    # Check Cache first (Saves your proxy & account from extra load)
    if user_key in INTERNAL_CACHE:
        data, expiry = INTERNAL_CACHE[user_key]
        if time.time() < expiry:
            return {"source": "cache", "data": data}

    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={user_key}"
    
    headers = {
        "x-ig-app-id": "936619743392459",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "referer": "https://www.instagram.com/",
        "x-requested-with": "XMLHttpRequest",
    }

    try:
        # Chrome 120 Impersonation (Best for bypassing blocks)
        response = requests.get(
            url,
            headers=headers,
            cookies=COOKIES,
            proxies={"http": PROXY_URL, "https": PROXY_URL},
            impersonate="chrome120",
            timeout=20
        )

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Instagram block")

        raw_data = response.json().get("data", {}).get("user")
        if not raw_data:
            return {"error": "Account not found or private info hidden"}

        # Prepare clean data for your Lovable site
        clean_data = {
            "username": raw_data.get("username"),
            "full_name": raw_data.get("full_name"),
            "followers": raw_data.get("edge_followed_by", {}).get("count"),
            "bio": raw_data.get("biography"),
            "profile_pic": raw_data.get("profile_pic_url_hd"),
            "is_private": raw_data.get("is_private")
        }

        # Save to cache
        INTERNAL_CACHE[user_key] = (clean_data, time.time() + CACHE_TIME)
        
        return {"source": "live", "data": clean_data}

    except Exception as e:
        return {"error": "Connection issue", "details": str(e)}
