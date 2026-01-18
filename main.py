from fastapi import FastAPI, HTTPException, Request
from curl_cffi import requests
import random
import time
import logging

# Initialize Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Professional Instagram Data API")

# --- CONFIGURATION ---
PROXY_URL = "http://tyzozoto-rotate:6c23wyc9oc1r@p.webshare.io:80"
# Using a dict is safer for curl_cffi than a string
COOKIES = {
    "mid": "aWyxUQALAAEXSQj42YOKQ_p8v8dn",
    "ig_did": "84B2CD1D-1165-40DA-8A06-82419391BA7B",
    "csrftoken": "qVLbVtyryQwyHko3V0Ci8Q",
    "ds_user_id": "80010991653",
    "sessionid": "80010991653%3AvmA5lUgf0xOt7T%3A10%3AAYgn1yV_ZHAxNDo2je3EsHExh1F3F9saczllIeSQmg"
}

# High-trust browser headers
HEADERS = {
    "authority": "www.instagram.com",
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "x-ig-app-id": "936619743392459",
    "x-asbd-id": "129477",
    "x-requested-with": "XMLHttpRequest",
    "referer": "https://www.instagram.com/",
}

@app.get("/")
def health_check():
    return {"status": "online", "message": "High-Performance IG API is ready"}

@app.get("/profile/{username}")
def fetch_data(username: str):
    # 1. Anti-Spam Random Delay (Simulates human reading time)
    time.sleep(random.uniform(0.5, 1.5))
    
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    
    try:
        # 2. Impersonate Chrome 120 (Mimics real browser TLS handshake)
        response = requests.get(
            url,
            headers=HEADERS,
            cookies=COOKIES,
            proxies={"http": PROXY_URL, "https": PROXY_URL},
            impersonate="chrome120",
            timeout=25
        )

        if response.status_code == 429:
            return {"error": "Rate Limit", "message": "Instagram is asking us to slow down."}
        
        if response.status_code != 200:
            logger.error(f"Failed for {username}: {response.status_code}")
            return {"error": "Failed", "status": response.status_code}

        json_response = response.json()
        user_data = json_response.get("data", {}).get("user")

        if not user_data:
            return {
                "error": "Soft Block", 
                "message": "Instagram returned an empty response. Try visiting the profile in your browser once."
            }

        # 3. Clean Output
        return {
            "status": "success",
            "data": {
                "username": user_data.get("username"),
                "full_name": user_data.get("full_name"),
                "is_private": user_data.get("is_private"),
                "is_verified": user_data.get("is_verified"),
                "followers": user_data.get("edge_followed_by", {}).get("count"),
                "following": user_data.get("edge_follow", {}).get("count"),
                "posts": user_data.get("edge_owner_to_timeline_media", {}).get("count"),
                "bio": user_data.get("biography"),
                "profile_pic": user_data.get("profile_pic_url_hd"),
                "external_url": user_data.get("external_url")
            }
        }

    except Exception as e:
        logger.exception("API Crash")
        return {"error": "Server Error", "details": str(e)}
