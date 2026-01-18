from fastapi import FastAPI, HTTPException
import httpx
import random
import asyncio

app = FastAPI()

# 1. YOUR UPDATED PROXY (WebShare)
# Format: http://username:password@host:port
PROXY_URL = "http://tyzozoto-rotate:6c23wyc9oc1r@p.webshare.io:80"

# 2. YOUR COOKIES
COOKIE_STRING = (
    "mid=aWyxUQALAAEXSQj42YOKQ_p8v8dn; "
    "ig_did=84B2CD1D-1165-40DA-8A06-82419391BA7B; "
    "csrftoken=qVLbVtyryQwyHko3V0Ci8Q; "
    "ds_user_id=80010991653; "
    "sessionid=80010991653%3AvmA5lUgf0xOt7T%3A10%3AAYgn1yV_ZHAxNDo2je3EsHExh1F3F9saczllIeSQmg"
)

HEADERS = {
    "authority": "www.instagram.com",
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "cookie": COOKIE_STRING,
    "referer": "https://www.instagram.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "x-ig-app-id": "936619743392459",
    "x-requested-with": "XMLHttpRequest"
}

@app.get("/")
def home():
    return {"status": "API with Proxy is running"}

@app.get("/profile/{username}")
async def get_instagram_profile(username: str):
    # Small delay to keep it human-like
    await asyncio.sleep(random.uniform(1, 2))
    
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    
    # Passing the proxy to the AsyncClient
    async with httpx.AsyncClient(proxy=PROXY_URL, http2=True, follow_redirects=True) as client:
        try:
            response = await client.get(url, headers=HEADERS, timeout=30.0)
            
            if response.status_code != 200:
                return {"error": f"Instagram Error {response.status_code}", "msg": "Check if proxy is active"}

            data = response.json()
            user = data.get("data", {}).get("user")
            
            if not user:
                return {"error": "Soft Blocked despite proxy", "raw": data}

            return {
                "username": user.get("username"),
                "followers": user.get("edge_followed_by", {}).get("count"),
                "following": user.get("edge_follow", {}).get("count"),
                "bio": user.get("biography"),
                "pic": user.get("profile_pic_url_hd")
            }

        except Exception as e:
            return {"error": "Proxy or Connection Error", "message": str(e)}
