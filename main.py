from fastapi import FastAPI, HTTPException
from curl_cffi import requests
import random
import time
import logging

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Ultra Instagram API 2026")

# --- CONFIGURATION ---
PROXY_URL = "http://tyzozoto-rotate:6c23wyc9oc1r@p.webshare.io:80"
COOKIES = {
    "mid": "aWyxUQALAAEXSQj42YOKQ_p8v8dn",
    "ig_did": "84B2CD1D-1165-40DA-8A06-82419391BA7B",
    "csrftoken": "qVLbVtyryQwyHko3V0Ci8Q",
    "ds_user_id": "80010991653",
    "sessionid": "80010991653%3AvmA5lUgf0xOt7T%3A10%3AAYgn1yV_ZHAxNDo2je3EsHExh1F3F9saczllIeSQmg"
}

# List of modern User-Agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

def fetch_with_retry(username, retries=3):
    """Helper function to retry requests if they fail"""
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    
    for i in range(retries):
        try:
            headers = {
                "authority": "www.instagram.com",
                "accept": "*/*",
                "x-ig-app-id": "936619743392459",
                "x-asbd-id": "129477",
                "user-agent": random.choice(USER_AGENTS),
                "referer": f"https://www.instagram.com/{username}/",
                "x-requested-with": "XMLHttpRequest",
            }

            response = requests.get(
                url,
                headers=headers,
                cookies=COOKIES,
                proxies={"http": PROXY_URL, "https": PROXY_URL},
                impersonate="chrome110",
                timeout=20
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("data", {}).get("user"):
                    return data
            
            # If we get a 429 or empty data, wait and retry
            logger.warning(f"Retry {i+1}/{retries} for {username}. Status: {response.status_code}")
            time.sleep(random.uniform(2, 4))
            
        except Exception as e:
            logger.error(f"Attempt {i+1} failed: {e}")
            time.sleep(2)
            
    return None

@app.get("/profile/{username}")
async def get_profile(username: str):
    result = fetch_with_retry(username)
    
    if not result:
        raise HTTPException(status_code=500, detail="Failed to fetch data after multiple attempts. Instagram might be blocking the session.")

    user = result["data"]["user"]
    return {
        "account": {
            "id": user.get("id"),
            "username": user.get("username"),
            "full_name": user.get("full_name"),
            "verified": user.get("is_verified"),
            "private": user.get("is_private"),
        },
        "stats": {
            "followers": user.get("edge_followed_by", {}).get("count"),
            "following": user.get("edge_follow", {}).get("count"),
            "posts": user.get("edge_owner_to_timeline_media", {}).get("count"),
        },
        "content": {
            "bio": user.get("biography"),
            "profile_pic": user.get("profile_pic_url_hd"),
            "external_link": user.get("external_url"),
        }
    }
