from fastapi import FastAPI, HTTPException
import httpx
import random
import asyncio

app = FastAPI()

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
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "x-asbd-id": "129477", # Important internal ID
    "x-ig-app-id": "936619743392459",
    "x-ig-www-claim": "0",
    "x-requested-with": "XMLHttpRequest"
}

@app.get("/profile/{username}")
async def get_instagram_profile(username: str):
    # Mimic human delay to reduce "Soft Block" probability
    await asyncio.sleep(random.uniform(1.5, 3.0))
    
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    
    async with httpx.AsyncClient(http2=True, follow_redirects=True) as client:
        try:
            response = await client.get(url, headers=HEADERS, timeout=20.0)
            
            # If we get 'status ok' but no data, it's a soft block
            data = response.json()
            if data.get("status") == "ok" and not data.get("data"):
                return {
                    "error": "Soft Blocked by Instagram",
                    "reason": "Railway IP detected as bot",
                    "suggestion": "Login to your account on a browser and search for a profile once to 'unfreeze' the session."
                }

            user = data.get("data", {}).get("user")
            if not user:
                 return {"error": "User data not found", "raw": data}

            return {
                "username": user.get("username"),
                "followers": user.get("edge_followed_by", {}).get("count"),
                "bio": user.get("biography"),
                "pic": user.get("profile_pic_url_hd")
            }

        except Exception as e:
            return {"error": "Server Crash", "message": str(e)}
