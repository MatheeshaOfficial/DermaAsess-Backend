import time
import os
import secrets
import httpx
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import supabase_client, get_db
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
async def telegram_start(request: Request, db: Session = Depends(get_db)):
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

        print(f"DEBUG: Generating telegram auth session. token={session_token[:8]}..., user_id={user_id}")
        
        insert_query = text("""
            INSERT INTO telegram_login_sessions (session_token, profile_id, status)
            VALUES (:session_token, :profile_id, 'pending')
        """)
        
        params = {
            "session_token": session_token,
            "profile_id": user_id
        }
        
        db.execute(insert_query, params)
        db.commit()
        
        # Verify it was inserted
        verify = db.execute(text("SELECT id FROM telegram_login_sessions WHERE session_token = :t"), {"t": session_token}).fetchone()
        if not verify:
            raise Exception("Failed to verify insertion of session_token")
            
        print(f"DEBUG: Session row inserted successfully, id={verify[0]}")
        
        bot_link = f"https://t.me/{BOT_USERNAME}?start=login_{session_token}"
        
        return {
            "success": True,
            "session_token": session_token,
            "bot_link": bot_link,
            "auth_link": bot_link
        }
    except Exception as e:
        import traceback; traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/telegram-complete")
async def telegram_complete(data: TelegramCompleteData, db: Session = Depends(get_db)):
    try:
        print(f"DEBUG: telegram_complete called for session={data.session_token[:8]}...")
        
        # â”€â”€ Verify session in PostgreSQL â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        query = text("""
            SELECT id, profile_id, status, expires_at 
            FROM telegram_login_sessions 
            WHERE session_token = :token
        """)
        session_row = db.execute(query, {"token": data.session_token}).fetchone()
        
        if not session_row:
            raise HTTPException(status_code=400, detail="Invalid or expired login session")
            
        session_id = session_row[0]
        linked_profile_id = session_row[1]
        status = session_row[2]
        expires_at = session_row[3]
        
        if expires_at.tzinfo is None:
            from datetime import timezone
            expires_at = expires_at.replace(tzinfo=timezone.utc)
            
        if status != 'pending':
            raise HTTPException(status_code=400, detail=f"Session is already {status}")
            
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        
        if expires_at < now:
            print(f"DEBUG: Session {session_id} expired.")
            db.execute(text("UPDATE telegram_login_sessions SET status = 'expired' WHERE id = :id"), {"id": session_id})
            db.commit()
            raise HTTPException(status_code=400, detail="Invalid or expired login session")

        # â”€â”€ Handle Linking or Login â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        is_new_user = False
        profile_id = None

        if linked_profile_id:
            profile_id = str(linked_profile_id)
            
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

        # â”€â”€ Get full profile â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        prof_check = supabase_client.table("profiles") \
            .select("*") \
            .eq("id", profile_id) \
            .execute()
        profile = prof_check.data[0]

        # â”€â”€ Determine method + channel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
        
        # â”€â”€ Mark session completed in PostgreSQL â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        update_query = text("""
            UPDATE telegram_login_sessions 
            SET status = 'completed',
                jwt_token = :jwt_token,
                telegram_id = :telegram_id,
                telegram_username = :telegram_username,
                telegram_name = :telegram_name,
                profile_id = :profile_id,
                completed_at = now()
            WHERE id = :id
        """)
        db.execute(update_query, {
            "jwt_token": jwt_token,
            "telegram_id": data.telegram_id,
            "telegram_username": data.username,
            "telegram_name": data.first_name,
            "profile_id": profile_id,
            "id": session_id
        })
        db.commit()
        print(f"DEBUG: Session {session_id} marked as completed for profile {profile_id}")

        return {
            "success": True,
            "token": jwt_token,
            "redirect_url": "/" # Required by prompt: "<frontend url if your project uses one, otherwise omit>"
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/telegram-status/{session_token}")
async def telegram_status(session_token: str, db: Session = Depends(get_db)):
    try:
        print(f"DEBUG: telegram_status polled for session={session_token[:8]}...")
        query = text("""
            SELECT id, status, jwt_token, expires_at 
            FROM telegram_login_sessions 
            WHERE session_token = :token
        """)
        session_row = db.execute(query, {"token": session_token}).fetchone()
        
        if not session_row:
            raise HTTPException(status_code=404, detail="Session not found")
            
        session_id = session_row[0]
        status = session_row[1]
        jwt_token = session_row[2]
        expires_at = session_row[3]
        
        if expires_at.tzinfo is None:
            from datetime import timezone
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        
        if status == 'pending':
            if expires_at < now:
                db.execute(text("UPDATE telegram_login_sessions SET status = 'expired' WHERE id = :id"), {"id": session_id})
                db.commit()
                return {"success": False, "status": "expired"}
            return {"success": True, "status": "pending"}
            
        elif status == 'completed':
            return {
                "success": True,
                "status": "completed",
                "token": jwt_token,
                "access_token": jwt_token,
                "token_type": "bearer"
            }
        else:
            return {"success": False, "status": "expired"}
            
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/google-login")
async def google_login(data: GoogleAuthData):
    try:
        # â”€â”€ Verify Google ID token â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

        # â”€â”€ Build full_name from Google token â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # Google gives: name (full), given_name, family_name
        full_name = (
            token_info.get("name")              # "John Smith"
            or token_info.get("given_name", "") # fallback to first name
        ).strip() or None

        # â”€â”€ Find or create profile â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
                "full_name": full_name,          # â† fixed: was first_name/last_name
                "email": email,
                "notification_channel": "email",
                "login_method": "google"
            }).execute()
            profile = prof_resp.data[0]
            profile_id = profile["id"]

        # â”€â”€ Determine method + channel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
        # â”€â”€ Verify Google ID token â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

        # â”€â”€ Check for duplicate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

        # â”€â”€ Update profile â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        supabase_client.table("profiles").update({
            "email": email,
            "login_method": "both"
            # notification_channel stays "telegram" â€” already has telegram
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
