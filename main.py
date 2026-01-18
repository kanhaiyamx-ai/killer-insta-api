from fastapi import FastAPI, HTTPException
import requests

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
    "cookie": COOKIE_STRING,
    "referer": "https://www.instagram.com/"
}

@app.get("/test")
def test_connection():
    # This checks if your session is actually valid
    url = "https://www.instagram.com/api/v1/users/web_profile_info/?username=cristiano"
    response = requests.get(url, headers=HEADERS)
    return {
        "status_code": response.status_code,
        "response_preview": response.text[:500] # Shows the first 500 characters of the error
    }

@app.get("/profile/{username}")
def get_instagram_profile(username: str):
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        
        if response.status_code != 200:
            return {"error": f"Instagram returned status {response.status_code}", "debug": "/test"}

        json_data = response.json()
        user_data = json_data.get('data', {}).get('user')
        
        if not user_data:
            return {
                "error": "Invalid response structure",
                "full_response": json_data # This helps us see what Instagram actually sent
            }

        return {
            "username": user_data.get("username"),
            "followers": user_data.get("edge_followed_by", {}).get("count"),
            "bio": user_data.get("biography")
        }

    except Exception as e:
        return {"error": str(e)}
