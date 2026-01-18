from fastapi import FastAPI, HTTPException
import requests

app = FastAPI()

# Your Hardcoded Session Data
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
    "cookie": COOKIE_STRING,
    "referer": "https://www.instagram.com/"
}

@app.get("/")
def home():
    return {"status": "API is online", "usage": "/profile/{username}"}

@app.get("/profile/{username}")
def get_instagram_profile(username: str):
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        
        if response.status_code != 200:
            return {"error": f"Instagram returned {response.status_code}", "detail": "Check cookies"}

        raw_data = response.json()
        
        # Safe navigation of the JSON tree
        data = raw_data.get('data', {})
        if not data:
            return {"error": "No data key found", "raw": raw_data}
            
        user = data.get('user', {})
        if not user:
            return {"error": "User not found or profile is restricted", "raw": raw_data}

        # Success! Return the clean data
        return {
            "username": user.get("username"),
            "full_name": user.get("full_name"),
            "followers": user.get("edge_followed_by", {}).get("count"),
            "following": user.get("edge_follow", {}).get("count"),
            "posts": user.get("edge_owner_to_timeline_media", {}).get("count"),
            "bio": user.get("biography"),
            "profile_pic": user.get("profile_pic_url_hd"),
            "is_private": user.get("is_private"),
            "is_verified": user.get("is_verified")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
