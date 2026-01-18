import time
import random
import logging
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from curl_cffi import requests

# 1. Setup Logging (Essential for debugging on Railway)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Setup Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Lovable Production API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 3. Enable CORS for Lovable
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Memory Cache
INTERNAL_CACHE = {}
CACHE_EXPIRY = 3600 

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
@limiter.limit("10/minute")
async def get_instagram_profile(request: Request, username: str):
    user_key = username.lower().strip()

    # --- CACHE CHECK ---
    if user_key in INTERNAL_CACHE:
        data, timestamp = INTERNAL_CACHE[user_key]
        if time.time() - timestamp < CACHE_EXPIRY:
            return {"status": "success", "source": "cache", "data": data}

    # --- API REQUEST ---
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={user_key}"
    headers = {
        "x-ig-app-id": "936619743392459",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "referer": "https://www.instagram.com/",
        "x-requested-with": "XMLHttpRequest",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            cookies=COOKIES,
            proxies={"http": PROXY_URL, "https": PROXY_URL},
            impersonate="chrome120",
            timeout=15
        )

        # Handle HTTP Errors
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Instagram user not found.")
        
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="Rate limit reached on Instagram. Please wait.")

        if response.status_code != 200:
            logger.error(f"IG Error: {response.status_code} - {response.text[:100]}")
            raise HTTPException(status_code=502, detail="Instagram service unavailable.")

        # Parse Data
        json_data = response.json()
        user = json_data.get("data", {}).get("user")
        
        if not user:
            # This is the "Soft Block" - Status 200 but empty data
            raise HTTPException(status_code=403, detail="Access denied by Instagram (Soft Block).")

        profile_data = {
            "username": user.get("username"),
            "full_name": user.get("full_name"),
            "followers": user.get("edge_followed_by", {}).get("count"),
            "is_private": user.get("is_private"),
            "bio": user.get("biography"),
            "dp": user.get("profile_pic_url_hd")
        }

        # Save to Cache
        INTERNAL_CACHE[user_key] = (profile_data, time.time())
        
        return {"status": "success", "source": "live", "data": profile_data}

    except requests.exceptions.RequestError as e:
        logger.error(f"Proxy/Network Error: {str(e)}")
        raise HTTPException(status_code=503, detail="Proxy connection failed.")
    
    except Exception as e:
        logger.exception("Unexpected Crash")
        raise HTTPException(status_code=500, detail="Internal server error.")

# Global Error Handler for cleaner Frontend responses
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.detail},
    )
