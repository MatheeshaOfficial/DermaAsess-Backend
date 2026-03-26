from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from deps import get_current_user
import supabase
import os
from services.gemini_service import chat_with_dermabot

router = APIRouter()

supabase_client = supabase.create_client(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_SERVICE_KEY", ""))

class ChatMessage(BaseModel):
    message: str

@router.post("/")
async def chat(data: ChatMessage, current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        session_id = f"web_{user_id}"
        
        prof_resp = supabase_client.table("profiles").select("*").eq("id", user_id).execute()
        profile = prof_resp.data[0] if prof_resp.data else {}
        
        hist_resp = supabase_client.table("chat_messages").select("role, content").eq("session_id", session_id).order("created_at", desc=False).limit(10).execute()
        history = hist_resp.data if hist_resp.data else []
        
        reply_text = await chat_with_dermabot(data.message, None, None, history, profile, "")
        
        supabase_client.table("chat_messages").insert({"session_id": session_id, "user_id": user_id, "role": "user", "content": data.message}).execute()
        supabase_client.table("chat_messages").insert({"session_id": session_id, "user_id": user_id, "role": "assistant", "content": reply_text}).execute()
        
        return {"reply": reply_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
