import time
import os
import secrets
import httpx
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from database import supabase_client
from config import GOOGLE_CLIENT_ID, BOT_USERNAME
from deps import create_jwt, get_current_user

router = APIRouter()


class TelegramCompleteData(BaseModel):
    session_token: str
    telegram_id: int
    first_name: str
    username: Optional[str] = None


class GoogleAuthData(BaseModel):
    credential: str


def determine_login_method(has_telegram: bool, has_email: bool):
    """Return login_method and notification_channel tuple."""
    if has_telegram and has_email:
        return "both", "telegram"
    elif has_telegram:
        return "telegram", "telegram"
    else:
        return "google", "email"


@router.post("/telegram-start")
async def telegram_start(request: Request):
    try:
        session_token = secrets.token_urlsafe(32)
        
        # Check for optional auth token to support linking
        auth_header = request.headers.get("Authorization")
        user_id = None
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                import jwt
                from config import JWT_SECRET
                payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
                user_id = payload.get("sub")
            except Exception:
                pass

        insert_data = {"session_token": session_token}
        if user_id:
            insert_data["profile_id"] = user_id

        supabase_client.table("telegram_login_sessions").insert(insert_data).execute()
        
        bot_link = f"https://t.me/{BOT_USERNAME}?start=login_{session_token}"
        
        return {
            "success": True,
            "session_token": session_token,
            "bot_link": bot_link
        }
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/telegram-complete")
async def telegram_complete(data: TelegramCompleteData):
    try:
        # ── Verify session ─────────────────────────────────────────
        session_resp = supabase_client.table("telegram_login_sessions") \
            .select("*") \
            .eq("session_token", data.session_token) \
            .eq("status", "pending") \
            .execute()
            
        if not session_resp.data:
            raise HTTPException(status_code=400, detail="Invalid or expired session")
            
        session_id = session_resp.data[0]["id"]
        linked_profile_id = session_resp.data[0].get("profile_id")
        
        # ── Handle Linking or Login ───────────────────────────
        is_new_user = False
        profile_id = None

        if linked_profile_id:
            profile_id = linked_profile_id
            
            # Update only telegram aspects of profile
            supabase_client.table("profiles").update({
                "telegram_id": data.telegram_id,
                "telegram_username": data.username
            }).eq("id", profile_id).execute()
            
            bot_resp = supabase_client.table("bot_users").select("*").eq("telegram_id", data.telegram_id).execute()
            if not bot_resp.data:
                supabase_client.table("bot_users").insert({
                    "telegram_id": data.telegram_id,
                    "first_name": data.first_name,
                    "telegram_username": data.username,
                    "profile_id": profile_id,
                    "onboarded": False,
                    "current_state": "idle"
                }).execute()
            else:
                supabase_client.table("bot_users").update({"profile_id": profile_id}).eq("telegram_id", data.telegram_id).execute()
                
        else:
            bot_resp = supabase_client.table("bot_users") \
                .select("profile_id") \
                .eq("telegram_id", data.telegram_id) \
                .execute()

        if bot_resp.data and bot_resp.data[0].get("profile_id"):
            profile_id = bot_resp.data[0]["profile_id"]
        else:
            is_new_user = True
            prof_resp = supabase_client.table("profiles").insert({
                "full_name": data.first_name,
                "telegram_id": data.telegram_id,
                "telegram_username": data.username,
                "notification_channel": "telegram",
                "login_method": "telegram"
            }).execute()
            profile_id = prof_resp.data[0]["id"]

            if not bot_resp.data:
                supabase_client.table("bot_users").insert({
                    "telegram_id": data.telegram_id,
                    "first_name": data.first_name,
                    "telegram_username": data.username,
                    "profile_id": profile_id,
                    "onboarded": False,
                    "current_state": "idle"
                }).execute()
            else:
                supabase_client.table("bot_users") \
                    .update({"profile_id": profile_id}) \
                    .eq("telegram_id", data.telegram_id) \
                    .execute()

        # ── Get full profile ──────────────────────────────────
        prof_check = supabase_client.table("profiles") \
            .select("*") \
            .eq("id", profile_id) \
            .execute()
        profile = prof_check.data[0]

        # ── Determine method + channel ────────────────────────
        login_method, notification_channel = determine_login_method(
            has_telegram=bool(profile.get("telegram_id")),
            has_email=bool(profile.get("email"))
        )

        update_data = {}
        if profile.get("login_method") != login_method:
            update_data["login_method"] = login_method
        if profile.get("notification_channel") != notification_channel:
            update_data["notification_channel"] = notification_channel
        if update_data:
            supabase_client.table("profiles") \
                .update(update_data) \
                .eq("id", profile_id) \
                .execute()

        jwt_token = create_jwt(
            str(profile_id),
            profile.get("telegram_id"),
            profile.get("email"),
            login_method
        )
        
        # ── Mark session completed ────────────────────────────
        supabase_client.table("telegram_login_sessions") \
            .update({
                "status": "completed",
                "jwt_token": jwt_token,
                "telegram_id": data.telegram_id,
                "first_name": data.first_name,
                "username": data.username,
                "profile_id": profile_id
            }) \
            .eq("id", session_id) \
            .execute()

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/telegram-status/{session_token}")
async def telegram_status(session_token: str):
    try:
        session_resp = supabase_client.table("telegram_login_sessions") \
            .select("*") \
            .eq("session_token", session_token) \
            .execute()
            
        if not session_resp.data:
            raise HTTPException(status_code=404, detail="Session not found")
            
        session_data = session_resp.data[0]
        
        if session_data["status"] == "pending":
            return {"success": True, "status": "pending"}
        elif session_data["status"] == "completed":
            return {
                "success": True,
                "status": "completed",
                "access_token": session_data["jwt_token"],
                "token_type": "bearer"
            }
        else:
            raise HTTPException(status_code=400, detail=f"Session state {session_data['status']}")
            
    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/google-login")
async def google_login(data: GoogleAuthData):
    try:
        # ── Verify Google ID token ────────────────────────────
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

        # ── Build full_name from Google token ─────────────────
        # Google gives: name (full), given_name, family_name
        full_name = (
            token_info.get("name")              # "John Smith"
            or token_info.get("given_name", "") # fallback to first name
        ).strip() or None

        # ── Find or create profile ────────────────────────────
        prof_check = supabase_client.table("profiles") \
            .select("*") \
            .eq("email", email) \
            .execute()

        is_new_user = False

        if prof_check.data:
            profile = prof_check.data[0]
            profile_id = profile["id"]
        else:
            is_new_user = True
            prof_resp = supabase_client.table("profiles").insert({
                "full_name": full_name,          # ← fixed: was first_name/last_name
                "email": email,
                "notification_channel": "email",
                "login_method": "google"
            }).execute()
            profile = prof_resp.data[0]
            profile_id = profile["id"]

        # ── Determine method + channel ────────────────────────
        login_method, notification_channel = determine_login_method(
            has_telegram=bool(profile.get("telegram_id")),
            has_email=bool(profile.get("email"))
        )

        update_data = {}
        if profile.get("login_method") != login_method:
            update_data["login_method"] = login_method
        if profile.get("notification_channel") != notification_channel:
            update_data["notification_channel"] = notification_channel
        if update_data:
            supabase_client.table("profiles") \
                .update(update_data) \
                .eq("id", profile_id) \
                .execute()

        jwt_token = create_jwt(
            str(profile_id),
            profile.get("telegram_id"),
            email,
            login_method
        )

        return {
            "access_token": jwt_token,
            "token_type": "bearer",
            "user_id": profile_id,
            "first_name": token_info.get("given_name") or full_name,
            "email": email,
            "telegram_id": profile.get("telegram_id"),
            "login_method": login_method,
            "is_new_user": is_new_user,
            "profile_complete": profile.get("age") is not None,
            "notification_channel": notification_channel
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/link-google")
async def link_google(
    data: GoogleAuthData,
    current_user: dict = Depends(get_current_user)
):
    try:
        # ── Verify Google ID token ────────────────────────────
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

        # ── Check for duplicate ───────────────────────────────
        dup_check = supabase_client.table("profiles") \
            .select("id") \
            .eq("email", email) \
            .neq("id", user_id) \
            .execute()
        if dup_check.data:
            raise HTTPException(
                status_code=400,
                detail="This Google account is already linked to another DermaAssess account"
            )

        # ── Update profile ────────────────────────────────────
        supabase_client.table("profiles").update({
            "email": email,
            "login_method": "both"
            # notification_channel stays "telegram" — already has telegram
        }).eq("id", user_id).execute()

        return {
            "success": True,
            "message": "Google account linked",
            "notification_channel": "telegram"
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    try:
        response = supabase_client.table("profiles") \
            .select("*") \
            .eq("id", current_user["user_id"]) \
            .execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Profile not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))