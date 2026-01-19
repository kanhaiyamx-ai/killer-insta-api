import os
import time
import logging
import asyncio
import random
from typing import Optional, List
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from curl_cffi.requests import AsyncSession

# --- 1. PRO-LEVEL LOGGING ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("IG_ULTRA_SAFE")

app = FastAPI(title="Ultra-Safe IG API")
request_lock = asyncio.Lock()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- 2. FAIL-SAFE CONFIGURATION ---
PROXY_POOL = [
    "http://tyzozoto-rotate:6c23wyc9oc1r@p.webshare.io:80",
    "http://nqkbjqmr-rotate:zesrjh0nfnr4@p.webshare.io:80",
    "http://qufokusu-rotate:2wnp08o44k6a@p.webshare.io:80",
    "http://bjuzswey-rotate:rdh7z9ajetu4@p.webshare.io:80"
]

ACCOUNT_POOL = [
    {
        "id": "ACC_PRIMARY",
        "status": "healthy",
        "cookies": {
            "mid": "aW5VQQALAAF3Sj_dJkMRaTSD3iWj",
            "ig_did": "5B27679A-AC1A-4E2A-BE11-C4D1C43C9211",
            "csrftoken": "fkqtzKpZHZNUA9Y4E2v0iQ",
            "ds_user_id": "80409252334",
            "sessionid": "80409252334%3AHRYCzC2HkUJ3Eg%3A7%3AAYipb5jIR-waUckVycYS6o2v1oARtyjLc65ncXckmw"
        }
    },
    {
        "id": "ACC_SECONDARY",
        "status": "healthy",
        "cookies": {
            "mid": "aW4nQwALAAGpPxvGsX2SJtmNQPqH",
            "ig_did": "38AA571B-E4A8-4CF8-A5C6-56EE1ED490E7",
            "csrftoken": "7L-zwQQPpr6ohqm9-XTctF",
            "ds_user_id": "80062988095",
            "sessionid": "80062988095%3AsoQ4CkWt17Md8Q%3A13%3AAYjHG1Sn0vhkBk-8jmbiUBB_NXXLs1oQCS0NIXATYg"
        }
    }
]

INTERNAL_CACHE = {}

# --- 3. ERROR-HANDLING MODELS ---
class ProfileData(BaseModel):
    username: str
    followers: int
    bio: Optional[str]
    dp_url: str

class ApiResponse(BaseModel):
    success: bool
    data: Optional[ProfileData] = None
    error: Optional[str] = None
    code: int

# --- 4. THE INDESTRUCTIBLE FETCH LOGIC ---
async def fetch_with_failover(username: str):
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    
    # 1. Filter only healthy accounts
    active_accounts = [a for a in ACCOUNT_POOL if a["status"] == "healthy"]
    if not active_accounts:
        # Reset health if all are down (aggressive recovery)
        for a in ACCOUNT_POOL: a["status"] = "healthy"
        active_accounts = ACCOUNT_POOL
        
    random.shuffle(active_accounts)
    proxies = PROXY_POOL.copy()
    random.shuffle(proxies)

    for i, account in enumerate(active_accounts):
        current_proxy = proxies[i % len(proxies)]
        
        async with request_lock:
            try:
                # Anti-Detection: Dynamic Jitter
                await asyncio.sleep(random.uniform(1.8, 3.5))
                
                async with AsyncSession(impersonate="chrome120") as session:
                    res = await session.get(
                        url,
                        headers={
                            "x-ig-app-id": "936619743392459",
                            "referer": f"https://www.instagram.com/{username}/",
                            "accept": "*/*"
                        },
                        cookies=account["cookies"],
                        proxies={"http": current_proxy, "https": current_proxy},
                        timeout=15
                    )

                    # --- ERROR HANDLING LOGIC ---
                    if res.status_code == 200:
                        data = res.json()
                        if data.get("data", {}).get("user"):
                            return {"code": 200, "json": data}
                        # Soft Block Detected
                        logger.warning(f"Soft block on {account['id']}. Marking account as degraded.")
                        account["status"] = "degraded"
                        continue

                    if res.status_code == 404:
                        return {"code": 404, "json": None}

                    if res.status_code == 429:
                        logger.error(f"Rate limited on {account['id']}. Cooling down.")
                        account["status"] = "cooldown"
                        continue

            except Exception as e:
                logger.error(f"Connection failed: {str(e)}")
                continue

    return {"code": 503, "json": None}

@app.get("/profile/{username}", response_model=ApiResponse)
@limiter.limit("8/minute")
async def get_profile(request: Request, username: str):
    username = username.strip().lower()

    # 1. Ultra-Fast Cache Check
    if username in INTERNAL_CACHE:
        data, ts = INTERNAL_CACHE[username]
        if time.time() - ts < 3600:
            return ApiResponse(success=True, data=data, code=200)

    # 2. Resilient Fetch
    result = await fetch_with_failover(username)
    
    if result["code"] == 200:
        u = result["json"]["data"]["user"]
        p = ProfileData(
            username=u["username"],
            followers=u["edge_followed_by"]["count"],
            bio=u["biography"],
            dp_url=u["profile_pic_url_hd"]
        )
        INTERNAL_CACHE[username] = (p, time.time())
        return ApiResponse(success=True, data=p, code=200)

    if result["code"] == 404:
        return ApiResponse(success=False, error="User not found", code=404)

    return ApiResponse(success=False, error="Service temporarily overloaded. Please retry in 60s.", code=503)
