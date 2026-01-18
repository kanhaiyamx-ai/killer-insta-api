from fastapi import FastAPI, HTTPException
import httpx
import logging

# Setup logging to help you see errors in Railway logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

COOKIE_STRING = (
    "mid=aWyxUQALAAEXSQj42YOKQ_p8v8dn; "
    "ig_did=84B2CD1D-1165-40DA-8A06-82419391BA7B; "
    "csrftoken=qVLbVtyryQwyHko3V0Ci8Q; "
    "ds_user_id=80010991653; "
    "sessionid=80010991653%3AvmA5lUgf0xOt7T%3A10%3AAYgn1yV_ZHAxNDo2je3EsHExh1F3F9saczllIeSQmg"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "x-ig-app-id": "936619743392459",
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "cookie": COOKIE_STRING,
    "referer": "https://www.instagram.com/",
    "x-requested-with": "XMLHttpRequest"
}

@app.get("/")
def home():
    return {"status": "API is online", "usage": "/profile/{username}"}

@app.get("/profile/{username}")
async def get_instagram_profile(username: str):
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    
    try:
        async with httpx.AsyncClient(http2=True, follow_redirects=True) as client:
            response = await client.get(url, headers=HEADERS, timeout=20.0)
            
            if response.status_code != 200:
                logger.error(f"Instagram Error: {response.status_code}")
                return {"error": f"Instagram returned {response.status_code}", "body": response.text[:200]}

            data = response.json()
            user = data.get("data", {}).get("user")
            
            if not user:
                return {"error": "User data missing from response", "raw": data}

            return {
                "username": user.get("username"),
                "full_name": user.get("full_name"),
                "followers": user.get("edge_followed_by", {}).get("count"),
                "following": user.get("edge_follow", {}).get("count"),
                "bio": user.get("biography"),
                "profile_pic": user.get("profile_pic_url_hd"),
                "is_private": user.get("is_private")
            }

    except Exception as e:
        logger.exception("Application Crash:")
        return {"error": "Internal Server Error", "message": str(e)}
