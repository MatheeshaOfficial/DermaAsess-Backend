from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
from deps import get_current_user
from database import supabase_client, get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from services.gemini_service import chat_with_dermabot

router = APIRouter()

@router.post("/message")
async def chat(
    message: str = Form(...),
    session_id: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        user_id = current_user["user_id"]
        session_id_val = session_id if session_id else f"web_{user_id}"
        
        prof_resp = supabase_client.table("profiles").select("*").eq("id", user_id).execute()
        profile = prof_resp.data[0] if prof_resp.data else {}
        
        query_hist = text("""
            SELECT role, content FROM chat_messages 
            WHERE session_id = :session_id 
            ORDER BY created_at ASC LIMIT 10
        """)
        hist_rows = db.execute(query_hist, {"session_id": session_id_val}).fetchall()
        history = [{"role": r[0], "content": r[1]} for r in hist_rows]
        
        img_bytes = None
        mime_type = None
        if image:
            img_bytes = await image.read()
            mime_type = image.content_type
            
        reply_text = await chat_with_dermabot(message, img_bytes, mime_type, history, profile, "")
        
        insert_msg = text("""
            INSERT INTO chat_messages (session_id, user_id, role, content)
            VALUES (:session_id, :user_id, :role, :content)
        """)
        db.execute(insert_msg, {
            "session_id": session_id_val, 
            "user_id": user_id, 
            "role": "user", 
            "content": message
        })
        db.execute(insert_msg, {
            "session_id": session_id_val, 
            "user_id": user_id, 
            "role": "assistant", 
            "content": reply_text
        })
        db.commit()
        
        return {"reply": reply_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
