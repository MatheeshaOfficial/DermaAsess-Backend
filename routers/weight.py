from fastapi import APIRouter, Depends, HTTPException, Form
from deps import get_current_user
from database import supabase_client
from services.gemini_service import generate_fat_loss_advice
from services.notification_service import notify_user

router = APIRouter()


@router.post("/log")
async def log_weight(
    weight_kg: float = Form(...),
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = current_user["user_id"]
        record = {
            "user_id": user_id,
            "weight_kg": weight_kg
        }
        
        save_resp = supabase_client.table("weight_logs").insert(record).execute()
        supabase_client.table("profiles").update({"weight": weight_kg}).eq("id", user_id).execute()
        
        notify_data = {
            "weight_kg": weight_kg
        }
        await notify_user(user_id, "weight_logged", notify_data)
        
        return save_resp.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_history(current_user: dict = Depends(get_current_user)):
    try:
        resp = supabase_client.table("weight_logs") \
            .select("*") \
            .eq("user_id", current_user["user_id"]) \
            .order("created_at", desc=True) \
            .execute()
        return resp.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fat-loss-advice")
async def get_fat_loss_advice(current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        prof_resp = supabase_client.table("profiles").select("*").eq("id", user_id).execute()
        profile = prof_resp.data[0] if prof_resp.data else {}
        
        hist_resp = supabase_client.table("weight_logs").select("weight_kg, created_at").eq("user_id", user_id).order("created_at", desc=True).limit(14).execute()
        history = list(reversed(hist_resp.data)) if hist_resp.data else []
        
        advice = await generate_fat_loss_advice(history, profile)
        return advice
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
