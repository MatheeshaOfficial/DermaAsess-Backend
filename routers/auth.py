import time
import hashlib
import hmac
import os
import httpx
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from database import supabase_client
from config import BOT_TOKEN, GOOGLE_CLIENT_ID
from deps import create_jwt, get_current_user

router = APIRouter()
BOT_TOKEN = BOT_TOKEN
GOOGLE_CLIENT_ID = GOOGLE_CLIENT_ID

class TelegramAuthData(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str

class GoogleAuthData(BaseModel):
    credential: str

@router.post("/telegram-login")
async def telegram_login(data: TelegramAuthData):
    data_dict = data.model_dump()
    received_hash = data_dict.pop("hash")
    
    sorted_items = sorted(data_dict.items(), key=lambda x: x[0])
    check_string = "\n".join([f"{k}={v}" for k, v in sorted_items if v is not None])
    
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(status_code=401, detail="Invalid Telegram authentication data")
        
    if abs(time.time() - data.auth_date) > 86400: # 24 hours
        raise HTTPException(status_code=401, detail="Authentication data expired")
        
    try:
        # Check bot_users
        response = supabase_client.table("bot_users").select("profile_id").eq("telegram_id", data.id).execute()
        is_new_user = False
        profile_id = None
        
        if response.data and response.data[0].get("profile_id"):
            profile_id = response.data[0]["profile_id"]
        else:
            is_new_user = True
            prof_resp = supabase_client.table("profiles").insert({
                "telegram_id": data.id,
                "telegram_username": data.username,
                "notification_channel": "telegram",
                "login_method": "telegram"
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
                
        # Get full profile
        prof_check = supabase_client.table("profiles").select("*").eq("id", profile_id).execute()
        profile = prof_check.data[0]
        
        # Determine login_method
        has_telegram = bool(profile.get("telegram_id"))
        has_email = bool(profile.get("email"))
        if has_telegram and has_email:
            login_method = "both"
            notification_channel = "telegram"
        elif has_email:
            login_method = "google"
            notification_channel = "email"
        else:
            login_method = "telegram"
            notification_channel = "telegram"
            
        update_data = {}
        if profile.get("login_method") != login_method:
            update_data["login_method"] = login_method
        if profile.get("notification_channel") != notification_channel:
            update_data["notification_channel"] = notification_channel
            
        if update_data:
            supabase_client.table("profiles").update(update_data).eq("id", profile_id).execute()
            
        jwt_token = create_jwt(str(profile_id), profile.get("telegram_id"), profile.get("email"), login_method)
        profile_complete = profile.get("age") is not None
            
        return {
            "access_token": jwt_token,
            "token_type": "bearer",
            "user_id": profile_id,
            "first_name": profile.get("first_name", data.first_name),
            "email": profile.get("email"),
            "telegram_id": data.id,
            "login_method": login_method,
            "is_new_user": is_new_user,
            "profile_complete": profile_complete,
            "notification_channel": notification_channel
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/google-login")
async def google_login(data: GoogleAuthData):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": data.credential}
            )
            
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid Google token")
            
        token_info = resp.json()
        
        if token_info.get("aud") != GOOGLE_CLIENT_ID:
            raise HTTPException(status_code=401, detail="Token audience mismatch")
            
        email = token_info.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Google")
            
        # Check profiles table
        prof_check = supabase_client.table("profiles").select("*").eq("email", email).execute()
        is_new_user = False
        if prof_check.data:
            profile = prof_check.data[0]
            profile_id = profile["id"]
        else:
            is_new_user = True
            prof_resp = supabase_client.table("profiles").insert({
                "email": email,
                "first_name": token_info.get("given_name", token_info.get("name")),
                "last_name": token_info.get("family_name"),
                "notification_channel": "email",
                "login_method": "google"
            }).execute()
            profile = prof_resp.data[0]
            profile_id = profile["id"]
            
        # Determine login_method
        has_telegram = bool(profile.get("telegram_id"))
        has_email = bool(profile.get("email"))
        if has_telegram and has_email:
            login_method = "both"
            notification_channel = "telegram"
        elif has_email:
            login_method = "google"
            notification_channel = "email"
        else:
            login_method = "telegram"
            notification_channel = "telegram"
            
        update_data = {}
        if profile.get("login_method") != login_method:
            update_data["login_method"] = login_method
        if profile.get("notification_channel") != notification_channel:
            update_data["notification_channel"] = notification_channel
            
        if update_data:
            supabase_client.table("profiles").update(update_data).eq("id", profile_id).execute()
            
        jwt_token = create_jwt(str(profile_id), profile.get("telegram_id"), profile.get("email"), login_method)
        profile_complete = profile.get("age") is not None
        
        return {
            "access_token": jwt_token,
            "token_type": "bearer",
            "user_id": profile_id,
            "first_name": profile.get("first_name"),
            "email": profile.get("email"),
            "telegram_id": profile.get("telegram_id"),
            "login_method": login_method,
            "is_new_user": is_new_user,
            "profile_complete": profile_complete,
            "notification_channel": notification_channel
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/link-telegram")
async def link_telegram(data: TelegramAuthData, current_user: dict = Depends(get_current_user)):
    data_dict = data.model_dump()
    received_hash = data_dict.pop("hash")
    
    sorted_items = sorted(data_dict.items(), key=lambda x: x[0])
    check_string = "\n".join([f"{k}={v}" for k, v in sorted_items if v is not None])
    
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(status_code=401, detail="Invalid Telegram authentication data")
        
    if abs(time.time() - data.auth_date) > 86400:
        raise HTTPException(status_code=401, detail="Authentication data expired")
        
    try:
        user_id = current_user["user_id"]
        
        # Check if telegram_id exists in other accounts
        dup_check = supabase_client.table("profiles").select("id").eq("telegram_id", data.id).neq("id", user_id).execute()
        if dup_check.data:
            raise HTTPException(status_code=400, detail="This Telegram account is already linked to another DermaAssess account")
            
        # update bot_users
        bot_check = supabase_client.table("bot_users").select("*").eq("telegram_id", data.id).execute()
        if not bot_check.data:
            supabase_client.table("bot_users").insert({
                "telegram_id": data.id,
                "first_name": data.first_name,
                "telegram_username": data.username,
                "profile_id": user_id,
                "onboarded": True,
                "current_state": "idle"
            }).execute()
        else:
            supabase_client.table("bot_users").update({"profile_id": user_id, "onboarded": True}).eq("telegram_id", data.id).execute()
            
        supabase_client.table("profiles").update({
            "telegram_id": data.id,
            "telegram_username": data.username,
            "notification_channel": "telegram",
            "login_method": "both"
        }).eq("id", user_id).execute()
        
        return {
            "success": True,
            "message": "Telegram linked successfully",
            "notification_channel": "telegram"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/link-google")
async def link_google(data: GoogleAuthData, current_user: dict = Depends(get_current_user)):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": data.credential}
            )
            
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid Google token")
            
        token_info = resp.json()
        
        if token_info.get("aud") != GOOGLE_CLIENT_ID:
            raise HTTPException(status_code=401, detail="Token audience mismatch")
            
        email = token_info.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Google")
            
        user_id = current_user["user_id"]
        
        dup_check = supabase_client.table("profiles").select("id").eq("email", email).neq("id", user_id).execute()
        if dup_check.data:
            raise HTTPException(status_code=400, detail="This Google account is already linked to another DermaAssess account")
            
        supabase_client.table("profiles").update({
            "email": email,
            "login_method": "both"
        }).eq("id", user_id).execute()
        
        return {
            "success": True,
            "message": "Google account linked",
            "notification_channel": "telegram"
        }
    except HTTPException:
        raise
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
