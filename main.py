import os
import time
import logging
from typing import Optional, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from curl_cffi import requests

# --- 1. LOGGING & CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("IG_API")

# Use Environment Variables for security (with fallbacks for your current setup)
PROXY_URL = os.getenv("PROXY_URL", "http://tyzozoto-rotate:6c23wyc9oc1r@p.webshare.io:80")
SESSION_ID = os.getenv("SESSION_ID", "80010991653%3AvmA5lUgf0xOt7T%3A10%3AAYgn1yV_ZHAxNDo2je3EsHExh1F3F9saczllIeSQmg")

COOKIES = {
    "mid": "aWyxUQALAAEXSQj42YOKQ_p8v8dn",
    "ig_did": "84B2CD1D-1165-40DA-8A06-82419391BA7B",
    "csrftoken": "qVLbVtyryQwyHko3V0Ci8Q",
    "ds_user_id": "80010991653",
    "sessionid": SESSION_ID
}

# --- 2. DATA MODELS (For cleaner documentation) ---
class ProfileData(BaseModel):
    username: str
    full_name: Optional[str] = None
    followers: int = 0
    following: int = 0
    posts: int = 0
    bio: Optional[str] = None
    is_private: bool = False
    dp_url: str

class ApiResponse(BaseModel):
    success: bool
    source: str  # "cache" or "live"
    data: Optional[ProfileData] = None
    error: Optional[str] = None

# --- 3. APP SETUP ---
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Lovable Instagram API", version="2.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple In-Memory Cache
INTERNAL_CACHE = {}
CACHE_TTL = 3600  # 1 hour

# --- 4. HELPER FUNCTIONS ---
def get_headers(username: str):
    return {
        "x-ig-app-id": "936619743392459",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "referer": f"https://www.instagram.com/{username}/",
        "x-requested-with": "XMLHttpRequest",
    }

# --- 5. ENDPOINTS ---

@app.get("/", tags=["Health"])
def health_check():
    """Checks API status and cache size."""
    return {
        "status": "online",
        "cache_items": len(INTERNAL_CACHE),
        "proxy_configured": bool(PROXY_URL)
    }

@app.get("/profile/{username}", response_model=ApiResponse, tags=["Instagram"])
@limiter.limit("10/minute")
async def fetch_profile(request: Request, username: str):
    username = username.strip().lower()

    # A. CACHE CHECK
    if username in INTERNAL_CACHE:
        data, timestamp = INTERNAL_CACHE[username]
        if time.time() - timestamp < CACHE_TTL:
            logger.info(f"Cache hit for {username}")
            return ApiResponse(success=True, source="cache", data=data)
        else:
            del INTERNAL_CACHE[username]  # Expired

    # B. LIVE FETCH
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    
    try:
        logger.info(f"Fetching live data for {username}...")
        response = requests.get(
            url,
            headers=get_headers(username),
            cookies=COOKIES,
            proxies={"http": PROXY_URL, "https": PROXY_URL},
            impersonate="chrome120",
            timeout=20
        )

        # Handle Standard Errors
        if response.status_code == 404:
            return JSONResponse(
                status_code=404,
                content={"success": False, "source": "live", "error": "User not found"}
            )
        
        if response.status_code == 429:
            logger.warning(f"Rate limit hit for {username}")
            return JSONResponse(
                status_code=429,
                content={"success": False, "source": "live", "error": "Rate limit exceeded. Try again later."}
            )

        if response.status_code != 200:
            logger.error(f"IG Error {response.status_code}: {response.text[:100]}")
            return JSONResponse(
                status_code=502,
                content={"success": False, "source": "live", "error": f"Instagram returned {response.status_code}"}
            )

        # C. PARSE DATA
        json_data = response.json()
        user = json_data.get("data", {}).get("user")

        if not user:
            logger.warning(f"Soft block detected for {username}")
            return JSONResponse(
                status_code=403,
                content={"success": False, "source": "live", "error": "Instagram Soft Block (Empty Data)"}
            )

        clean_data = ProfileData(
            username=user.get("username"),
            full_name=user.get("full_name"),
            followers=user.get("edge_followed_by", {}).get("count", 0),
            following=user.get("edge_follow", {}).get("count", 0),
            posts=user.get("edge_owner_to_timeline_media", {}).get("count", 0),
            bio=user.get("biography"),
            is_private=user.get("is_private", False),
            dp_url=user.get("profile_pic_url_hd")
        )

        # D. SAVE TO CACHE
        INTERNAL_CACHE[username] = (clean_data, time.time())

        return ApiResponse(success=True, source="live", data=clean_data)

    except requests.RequestsError as e:
        logger.error(f"Network error: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={"success": False, "source": "error", "error": "Proxy Connection Failed"}
        )
    except Exception as e:
        logger.exception(f"Unexpected error for {username}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "source": "error", "error": "Internal Server Error"}
        )

# Global Exception Handler ensures standardized JSON even on crash
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": f"Critical Server Failure: {str(exc)}"}
    )
