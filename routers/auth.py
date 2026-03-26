import os
import hashlib
import hmac
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import supabase
from dotenv import load_dotenv
from deps import create_jwt, get_current_user

load_dotenv()

router = APIRouter()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

supabase_client = supabase.create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_KEY", "")
)

class TelegramAuthData(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str

@router.post("/telegram-login")
async def telegram_login(data: TelegramAuthData):
    data_dict = data.model_dump()
    received_hash = data_dict.pop("hash")
    
    sorted_items = sorted(data_dict.items(), key=lambda x: x[0])
    check_string = "\n".join([f"{k}={v}" for k, v in sorted_items if v is not None])
    
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    
    if expected_hash != received_hash:
        raise HTTPException(status_code=401, detail="Invalid Telegram authentication data")
        
    import time
    if time.time() - data.auth_date > 86400: # 24 hours
        raise HTTPException(status_code=401, detail="Authentication data expired")
        
    try:
        response = supabase_client.table("bot_users").select("profile_id").eq("telegram_id", data.id).execute()
        is_new_user = False
        profile_id = None
        
        if response.data and response.data[0].get("profile_id"):
            profile_id = response.data[0]["profile_id"]
        else:
            is_new_user = True
            prof_resp = supabase_client.table("profiles").insert({
                "telegram_id": data.id,
                "notification_channel": "telegram"
            }).execute()
            profile_id = prof_resp.data[0]["id"]
            
            if not response.data:
                supabase_client.table("bot_users").insert({
                    "telegram_id": data.id,
                    "first_name": data.first_name,
                    "telegram_username": data.username,
                    "profile_id": profile_id,
                    "onboarded": False,
                    "current_state": "idle"
                }).execute()
            else:
                supabase_client.table("bot_users").update({"profile_id": profile_id}).eq("telegram_id", data.id).execute()
                
        jwt_token = create_jwt(str(profile_id), data.id)
        
        prof_check = supabase_client.table("profiles").select("age").eq("id", profile_id).execute()
        profile_complete = False
        if prof_check.data and prof_check.data[0].get("age"):
            profile_complete = True
            
        return {
            "access_token": jwt_token,
            "token_type": "bearer",
            "user_id": profile_id,
            "telegram_id": data.id,
            "first_name": data.first_name,
            "is_new_user": is_new_user,
            "profile_complete": profile_complete
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    try:
        response = supabase_client.table("profiles").select("*").eq("id", current_user["user_id"]).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Profile not found")
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
