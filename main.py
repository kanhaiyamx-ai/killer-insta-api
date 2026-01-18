from fastapi import FastAPI, HTTPException
import httpx # You will need to add httpx to requirements.txt

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
    "accept-language": "en-US,en;q=0.9",
    "cookie": COOKIE_STRING,
    "referer": "https://www.instagram.com/",
    "x-requested-with": "XMLHttpRequest" # Helps mimic a real web app request
}

@app.get("/")
def home():
    return {"status": "API is online", "usage": "/profile/{username}"}

@app.get("/profile/{username}")
async def get_instagram_profile(username: str):
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    
    async with httpx.AsyncClient(http2=True) as client: # Use HTTP/2 to look more like a browser
        try:
            response = await client.get(url, headers=HEADERS, timeout=15.0)
            
            if response.status_code != 200:
                return {"error": f"Instagram returned {response.status_code}", "raw": response.text}

            data = response.json()
            
            # Instagram sometimes returns {"status": "ok"} but no data if you are flagged
            if "data" not in data or not data["data"].get("user"):
                return {
                    "error": "Soft Block: Instagram returned status OK but hidden data.",
                    "suggestion": "Log into your account on a browser and search for this user manually once to 'warm up' the session.",
                    "raw_response": data
                }

            user = data["data"]["user"]
            return {
                "username": user.get("username"),
                "followers": user.get("edge_followed_by", {}).get("count"),
                "bio": user.get("biography"),
                "profile_pic": user.get("profile_pic_url_hd")
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
