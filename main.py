import os
import time
import logging
import asyncio
import random
import base64
from typing import Optional
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from curl_cffi.requests import AsyncSession

# --- 1. SETUP ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("IG_ULTRA_SAFE")

app = FastAPI(title="Image-Proxy IG API")
request_lock = asyncio.Lock()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- 2. CONFIGURATION ---
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

# --- 3. IMAGE PROXY LOGIC ---
@app.get("/proxy-image")
async def proxy_image(url: str):
    """
    Fetches an image from Instagram via proxy and returns it directly.
    This prevents '403 Forbidden' errors on the frontend.
    """
    proxy = random.choice(PROXY_POOL)
    async with AsyncSession(impersonate="chrome120") as session:
        try:
            res = await session.get(url, proxies={"http": proxy, "https": proxy}, timeout=10)
            if res.status_code == 200:
                return Response(content=res.content, media_type="image/jpeg")
        except Exception as e:
            logger.error(f"Image proxy failed: {e}")
    
    return JSONResponse(status_code=404, content={"error": "Image not found"})

# --- 4. PROFILE FETCH LOGIC ---
class ProfileData(BaseModel):
    username: str
    followers: int
    bio: Optional[str]
    dp_url: str      # Original URL
    dp_proxy: str    # Safe Proxy URL for Lovable

async def fetch_with_failover(username: str):
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    active_accounts = [a for a in ACCOUNT_POOL if a["status"] == "healthy"]
    random.shuffle(active_accounts)
    proxies = PROXY_POOL.copy()
    random.shuffle(proxies)

    for i, account in enumerate(active_accounts):
        current_proxy = proxies[i % len(proxies)]
        async with request_lock:
            try:
                await asyncio.sleep(random.uniform(1.8, 3.5))
                async with AsyncSession(impersonate="chrome120") as session:
                    res = await session.get(
                        url,
                        headers={"x-ig-app-id": "936619743392459", "referer": f"https://www.instagram.com/{username}/"},
                        cookies=account["cookies"],
                        proxies={"http": current_proxy, "https": current_proxy},
                        timeout=15
                    )
                    if res.status_code == 200:
                        data = res.json()
                        if data.get("data", {}).get("user"):
                            return {"code": 200, "json": data}
            except Exception as e:
                logger.error(f"Fetch failed: {e}")
                continue
    return {"code": 503, "json": None}

@app.get("/profile/{username}")
@limiter.limit("8/minute")
async def get_profile(request: Request, username: str):
    username = username.strip().lower()
    
    if username in INTERNAL_CACHE:
        data, ts = INTERNAL_CACHE[username]
        if time.time() - ts < 3600:
            return {"success": True, "data": data}

    result = await fetch_with_failover(username)
    
    if result["code"] == 200:
        u = result["json"]["data"]["user"]
        original_dp = u["profile_pic_url_hd"]
        
        # We generate a stable proxy link for the frontend
        # Example: https://your-app.railway.app/proxy-image?url=...
        base_url = str(request.base_url).rstrip("/")
        dp_proxy_url = f"{base_url}/proxy-image?url={original_dp}"

        p = ProfileData(
            username=u["username"],
            followers=u["edge_followed_by"]["count"],
            bio=u["biography"],
            dp_url=original_dp,
            dp_proxy=dp_proxy_url
        )
        INTERNAL_CACHE[username] = (p, time.time())
        return {"success": True, "data": p}

    return JSONResponse(status_code=result["code"], content={"success": False, "error": "API Error"})
