import time
import os
import secrets
import httpx
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from config import GOOGLE_CLIENT_ID, BOT_USERNAME
from deps import create_jwt, get_current_user
import json

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
        
        # ── Verify session in PostgreSQL ─────────────────────────────
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

        # ── Handle Linking or Login ───────────────────────────
        is_new_user = False
        profile_id = None

        if linked_profile_id:
            profile_id = str(linked_profile_id)
            
            # Update only telegram aspects of profile
            db.execute(text("UPDATE profiles SET telegram_id = :tid, telegram_username = :uname WHERE id = :id"), 
                       {"tid": data.telegram_id, "uname": data.username, "id": profile_id})
            
            bot_row = db.execute(text("SELECT * FROM bot_users WHERE telegram_id = :tid"), {"tid": data.telegram_id}).fetchone()
            if not bot_row:
                db.execute(text("""
                    INSERT INTO bot_users (telegram_id, first_name, telegram_username, profile_id, onboarded, current_state)
                    VALUES (:tid, :fname, :uname, :pid, FALSE, 'idle')
                """), {"tid": data.telegram_id, "fname": data.first_name, "uname": data.username, "pid": profile_id})
            else:
                db.execute(text("UPDATE bot_users SET profile_id = :pid WHERE telegram_id = :tid"), 
                           {"pid": profile_id, "tid": data.telegram_id})
                
        else:
            bot_row = db.execute(text("SELECT profile_id FROM bot_users WHERE telegram_id = :tid"), {"tid": data.telegram_id}).fetchone()

            if bot_row and bot_row[0]:
                profile_id = str(bot_row[0])
            else:
                is_new_user = True
                prof_res = db.execute(text("""
                    INSERT INTO profiles (full_name, telegram_id, telegram_username, notification_channel, login_method)
                    VALUES (:fname, :tid, :uname, 'telegram', 'telegram')
                    RETURNING id
                """), {"fname": data.first_name, "tid": data.telegram_id, "uname": data.username}).fetchone()
                profile_id = str(prof_res[0])

                if not bot_row:
                    db.execute(text("""
                        INSERT INTO bot_users (telegram_id, first_name, telegram_username, profile_id, onboarded, current_state)
                        VALUES (:tid, :fname, :uname, :pid, FALSE, 'idle')
                    """), {"tid": data.telegram_id, "fname": data.first_name, "uname": data.username, "pid": profile_id})
                else:
                    db.execute(text("UPDATE bot_users SET profile_id = :pid WHERE telegram_id = :tid"), 
                               {"pid": profile_id, "tid": data.telegram_id})
        db.commit()

        # ── Get full profile ──────────────────────────────────
        prof_check = db.execute(text("SELECT telegram_id, email, login_method, notification_channel FROM profiles WHERE id = :id"), {"id": profile_id}).fetchone()
        profile = dict(prof_check._mapping) if prof_check else {}

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
            set_clauses = [f"{k} = :{k}" for k in update_data.keys()]
            set_str = ", ".join(set_clauses)
            update_data["id"] = profile_id
            db.execute(text(f"UPDATE profiles SET {set_str} WHERE id = :id"), update_data)
            db.commit()

        jwt_token = create_jwt(
            str(profile_id),
            profile.get("telegram_id"),
            profile.get("email"),
            login_method
        )
        
        # ── Mark session completed in PostgreSQL ───────────────────
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
            "redirect_url": "/"
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
async def google_login(data: GoogleAuthData, db: Session = Depends(get_db)):
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
        full_name = (
            token_info.get("name")              # "John Smith"
            or token_info.get("given_name", "") # fallback to first name
        ).strip() or None

        # ── Find or create profile ────────────────────────────
        prof_check = db.execute(text("SELECT id, telegram_id, email, login_method, notification_channel, age FROM profiles WHERE email = :email"), {"email": email}).fetchone()

        is_new_user = False

        if prof_check:
            profile = dict(prof_check._mapping)
            profile_id = str(profile["id"])
        else:
            is_new_user = True
            prof_res = db.execute(text("""
                INSERT INTO profiles (full_name, email, notification_channel, login_method)
                VALUES (:fname, :email, 'email', 'google')
                RETURNING id, telegram_id, email, login_method, notification_channel, age
            """), {"fname": full_name, "email": email}).fetchone()
            db.commit()
            profile = dict(prof_res._mapping)
            profile_id = str(profile["id"])

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
            set_clauses = [f"{k} = :{k}" for k in update_data.keys()]
            set_str = ", ".join(set_clauses)
            update_data["id"] = profile_id
            db.execute(text(f"UPDATE profiles SET {set_str} WHERE id = :id"), update_data)
            db.commit()

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
        db.rollback()
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/link-google")
async def link_google(
    data: GoogleAuthData,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
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
        dup_check = db.execute(text("SELECT id FROM profiles WHERE email = :email AND id != :uid"), {"email": email, "uid": user_id}).fetchone()
        
        if dup_check:
            raise HTTPException(
                status_code=400,
                detail="This Google account is already linked to another DermaAssess account"
            )

        # ── Update profile ────────────────────────────────────
        db.execute(text("UPDATE profiles SET email = :email, login_method = 'both' WHERE id = :uid"), {"email": email, "uid": user_id})
        db.commit()

        return {
            "success": True,
            "message": "Google account linked",
            "notification_channel": "telegram"
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        response = db.execute(text("SELECT * FROM profiles WHERE id = :uid"), {"uid": current_user["user_id"]}).fetchone()
        if not response:
            raise HTTPException(status_code=404, detail="Profile not found")
            
        profile_data = dict(response._mapping)
        if isinstance(profile_data.get("allergies"), str):
            try: profile_data["allergies"] = json.loads(profile_data["allergies"])
            except: pass
        if isinstance(profile_data.get("chronic_conditions"), str):
            try: profile_data["chronic_conditions"] = json.loads(profile_data["chronic_conditions"])
            except: pass
            
        return profile_data
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
