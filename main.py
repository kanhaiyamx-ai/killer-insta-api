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
    "x-ig-app-id": "936619743392459",  # Static ID for Instagram Web App
    "accept": "*/*",
    "cookie": COOKIE_STRING
}

@app.get("/")
def home():
    return {"status": "API is running", "endpoint": "/profile/{username}"}

@app.get("/profile/{username}")
def get_instagram_profile(username: str):
    # Instagram internal API endpoint for profile info
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Username not found.")
        
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="Rate limited by Instagram. Slow down!")

        if response.status_code != 200:
            return {
                "error": f"Failed to fetch. Status code: {response.status_code}",
                "message": "Cookies might be expired or account is flagged."
            }

        data = response.json().get('data', {}).get('user', {})
        
        if not data:
            return {"error": "Invalid response structure from Instagram."}

        # Parsing the specific data you requested
        return {
            "username": data.get("username"),
            "full_name": data.get("full_name"),
            "followers": data.get("edge_followed_by", {}).get("count"),
            "following": data.get("edge_follow", {}).get("count"),
            "posts_count": data.get("edge_owner_to_timeline_media", {}).get("count"),
            "bio": data.get("biography"),
            "profile_pic": data.get("profile_pic_url_hd"),
            "is_private": data.get("is_private"),
            "external_url": data.get("external_url")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")
