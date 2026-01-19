import os
import time
import logging
import asyncio
import random
from typing import Optional
from fastapi import FastAPI, Request
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

app = FastAPI(title="Multi-Account IG API", version="4.0")

# Enable CORS for Lovable
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- 2. CONFIGURATION ---
PROXY_URL = os.getenv("PROXY_URL", "http://tyzozoto-rotate:6c23wyc9oc1r@p.webshare.io:80")

# --- ACCOUNT POOL (Rotation System) ---
ACCOUNT_POOL = [
    # Account 1 (Original)
    {
        "mid": "aWyxUQALAAEXSQj42YOKQ_p8v8dn",
        "ig_did": "84B2CD1D-1165-40DA-8A06-82419391BA7B",
        "csrftoken": "qVLbVtyryQwyHko3V0Ci8Q",
        "ds_user_id": "80010991653",
        "sessionid": "80010991653%3AvmA5lUgf0xOt7T%3A10%3AAYgn1yV_ZHAxNDo2je3EsHExh1F3F9saczllIeSQmg"
    },
    # Account 2 (New)
    {
        "mid": "aW4nQwALAAGpPxvGsX2SJtmNQPqH",
        "ig_did": "38AA571B-E4A8-4CF8-A5C6-56EE1ED490E7",
        "csrftoken": "7L-zwQQPpr6ohqm9-XTctF",
        "ds_user_id": "80062988095",
        "sessionid": "80062988095%3AsoQ4CkWt17Md8Q%3A13%3AAYjHG1Sn0vhkBk-8jmbiUBB_NXXLs1oQCS0NIXATYg"
    }
]

# In-Memory Cache
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

# --- 4. CORE FETCH FUNCTION ---
async def fetch_from_instagram(username: str, retries=2) -> dict:
    """
    Fetches data using random account rotation.
    """
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    
    headers = {
        "x-ig-app-id": "936619743392459",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "referer": f"https://www.instagram.com/{username}/",
        "x-requested-with": "XMLHttpRequest",
    }

    for attempt in range(retries + 1):
        # ROTATION LOGIC: Pick a random account for each attempt
        current_account = random.choice(ACCOUNT_POOL)
        account_id = current_account.get("ds_user_id", "unknown")
        
        try:
            logger.info(f"Fetching {username} using Account: {account_id}")
            
            async with AsyncSession(impersonate="chrome120") as session:
                response = await session.get(
                    url,
                    headers=headers,
                    cookies=current_account, # Use the selected account's cookies
                    proxies={"http": PROXY_URL, "https": PROXY_URL},
                    timeout=15
                )

                if response.status_code == 200:
                    return {"status": 200, "json": response.json()}
                
                if response.status_code == 404:
                    return {"status": 404, "json": None}

                # If blocked (429/Challenge), log it and retry with (likely) the other account
                logger.warning(f"Account {account_id} failed with {response.status_code}. Retrying...")

        except Exception as e:
            logger.error(f"Network Error: {e}")
            if attempt < retries:
                await asyncio.sleep(0.5)

    return {"status": 503, "json": None}

# --- 5. ENDPOINTS ---

@app.get("/", tags=["System"])
def system_status():
    return {
        "status": "operational",
        "accounts_loaded": len(ACCOUNT_POOL),
        "cache_size": len(INTERNAL_CACHE)
    }

@app.get("/profile/{username}", response_model=ApiResponse)
@limiter.limit("20/minute") # Higher limit now that we have 2 accounts
async def get_profile(request: Request, username: str):
    username = username.strip().lower()

    # A. Check Cache
    if username in INTERNAL_CACHE:
        data, timestamp = INTERNAL_CACHE[username]
        if time.time() - timestamp < CACHE_TTL:
            return ApiResponse(success=True, source="cache", data=data)
        else:
            del INTERNAL_CACHE[username]

    # B. Fetch Data (Rotated)
    result = await fetch_from_instagram(username)
    status_code = result["status"]
    
    if status_code == 404:
        return JSONResponse(status_code=404, content={"success": False, "source": "live", "error": "User not found"})
    
    if status_code != 200 or not result["json"]:
        return JSONResponse(status_code=502, content={"success": False, "source": "error", "error": "Instagram unavailable"})

    # C. Parse
    try:
        user = result["json"].get("data", {}).get("user")
        if not user:
            return JSONResponse(status_code=403, content={"success": False, "source": "live", "error": "Soft Block"})

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

        INTERNAL_CACHE[username] = (profile, time.time())
        return ApiResponse(success=True, source="live", data=profile)

    except Exception:
        return JSONResponse(status_code=500, content={"success": False, "source": "error", "error": "Data parsing failed"})
