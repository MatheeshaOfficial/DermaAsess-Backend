from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
from deps import get_current_user
from database import supabase_client
from services.gemini_service import chat_with_dermabot

router = APIRouter()

@router.post("/message")
async def chat(
    message: str = Form(...),
    session_id: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = current_user["user_id"]
        session_id_val = session_id if session_id else f"web_{user_id}"
        
        prof_resp = supabase_client.table("profiles").select("*").eq("id", user_id).execute()
        profile = prof_resp.data[0] if prof_resp.data else {}
        
        hist_resp = supabase_client.table("chat_messages").select("role, content").eq("session_id", session_id_val).order("created_at", desc=False).limit(10).execute()
        history = hist_resp.data if hist_resp.data else []
        
        img_bytes = None
        mime_type = None
        if image:
            img_bytes = await image.read()
            mime_type = image.content_type
            
        reply_text = await chat_with_dermabot(message, img_bytes, mime_type, history, profile, "")
        
        supabase_client.table("chat_messages").insert({"session_id": session_id_val, "user_id": user_id, "role": "user", "content": message}).execute()
        supabase_client.table("chat_messages").insert({"session_id": session_id_val, "user_id": user_id, "role": "assistant", "content": reply_text}).execute()
        
        return {"reply": reply_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
