import os
import time
import logging
import asyncio
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from curl_cffi.requests import AsyncSession

# --- 1. LOGGING & SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("IG_API")

app = FastAPI(title="High-Performance IG API", version="3.0")

# Enable CORS for Lovable
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiting (Crucial for 50 users)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- 2. CONFIGURATION ---
PROXY_URL = os.getenv("PROXY_URL", "http://tyzozoto-rotate:6c23wyc9oc1r@p.webshare.io:80")
SESSION_ID = os.getenv("SESSION_ID", "80010991653%3AvmA5lUgf0xOt7T%3A10%3AAYgn1yV_ZHAxNDo2je3EsHExh1F3F9saczllIeSQmg")

COOKIES = {
    "mid": "aWyxUQALAAEXSQj42YOKQ_p8v8dn",
    "ig_did": "84B2CD1D-1165-40DA-8A06-82419391BA7B",
    "csrftoken": "qVLbVtyryQwyHko3V0Ci8Q",
    "ds_user_id": "80010991653",
    "sessionid": SESSION_ID
}

# In-Memory Cache (Fastest option for Railway)
INTERNAL_CACHE = {}
CACHE_TTL = 3600  # 1 hour

# --- 3. RESPONSE MODELS ---
class ProfileData(BaseModel):
    username: str
    full_name: Optional[str] = None
    followers: int
    following: int
    posts: int
    bio: Optional[str] = None
    is_private: bool
    dp_url: str

class ApiResponse(BaseModel):
    success: bool
    source: str
    data: Optional[ProfileData] = None
    error: Optional[str] = None

# --- 4. CORE FETCH FUNCTION (ASYNC) ---
async def fetch_from_instagram(username: str, retries=2) -> dict:
    """
    Fetches data using AsyncSession (Non-blocking).
    Retries automatically if the proxy fails.
    """
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    headers = {
        "x-ig-app-id": "936619743392459",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "referer": f"https://www.instagram.com/{username}/",
        "x-requested-with": "XMLHttpRequest",
    }

    for attempt in range(retries + 1):
        try:
            # AsyncSession is the key to handling 50+ users
            async with AsyncSession(impersonate="chrome120") as session:
                response = await session.get(
                    url,
                    headers=headers,
                    cookies=COOKIES,
                    proxies={"http": PROXY_URL, "https": PROXY_URL},
                    timeout=15
                )

                # Success
                if response.status_code == 200:
                    return {"status": 200, "json": response.json()}
                
                # Handle Rate Limit / Not Found
                if response.status_code in [404, 429]:
                    return {"status": response.status_code, "json": None}

                logger.warning(f"Attempt {attempt+1} failed: {response.status_code}")

        except Exception as e:
            logger.error(f"Network Error on attempt {attempt+1}: {e}")
            if attempt < retries:
                await asyncio.sleep(1) # Wait 1s before retry

    return {"status": 503, "json": None}

# --- 5. ENDPOINTS ---

@app.get("/", tags=["System"])
def system_status():
    return {
        "status": "operational",
        "cache_size": len(INTERNAL_CACHE),
        "proxy": "configured"
    }

@app.get("/profile/{username}", response_model=ApiResponse)
@limiter.limit("15/minute") # Increased limit for active users
async def get_profile(request: Request, username: str):
    username = username.strip().lower()

    # A. Check Cache
    if username in INTERNAL_CACHE:
        data, timestamp = INTERNAL_CACHE[username]
        if time.time() - timestamp < CACHE_TTL:
            return ApiResponse(success=True, source="cache", data=data)
        else:
            del INTERNAL_CACHE[username] # Remove expired

    # B. Fetch Data (Non-Blocking)
    result = await fetch_from_instagram(username)
    status_code = result["status"]
    
    if status_code == 404:
        return JSONResponse(status_code=404, content={"success": False, "source": "live", "error": "User not found"})
    
    if status_code == 429:
        return JSONResponse(status_code=429, content={"success": False, "source": "live", "error": "Rate limited"})
    
    if status_code != 200 or not result["json"]:
        return JSONResponse(status_code=502, content={"success": False, "source": "error", "error": "Proxy/Instagram Error"})

    # C. Parse & Validate
    try:
        user = result["json"].get("data", {}).get("user")
        if not user:
            return JSONResponse(status_code=403, content={"success": False, "source": "live", "error": "Private/Soft Block"})

        profile = ProfileData(
            username=user["username"],
            full_name=user["full_name"],
            followers=user["edge_followed_by"]["count"],
            following=user["edge_follow"]["count"],
            posts=user["edge_owner_to_timeline_media"]["count"],
            bio=user["biography"],
            is_private=user["is_private"],
            dp_url=user["profile_pic_url_hd"]
        )

        # Update Cache
        INTERNAL_CACHE[username] = (profile, time.time())

        return ApiResponse(success=True, source="live", data=profile)

    except KeyError:
        return JSONResponse(status_code=500, content={"success": False, "source": "error", "error": "Data parsing failed"})
