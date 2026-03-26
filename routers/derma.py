from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from deps import get_current_user
import supabase
import os
from services.gemini_service import analyze_skin_image
from services.cloudinary_service import upload_image
from services.notification_service import notify_user
import urllib.parse

router = APIRouter()

supabase_client = supabase.create_client(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_SERVICE_KEY", ""))

@router.post("/assess")
async def assess_skin(
    image: UploadFile = File(...),
    symptoms: str = Form("No symptoms described"),
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = current_user["user_id"]
        img_bytes = await image.read()
        mime_type = image.content_type
        
        prof_resp = supabase_client.table("profiles").select("*").eq("id", user_id).execute()
        profile = prof_resp.data[0] if prof_resp.data else {}
        
        result = await analyze_skin_image(img_bytes, mime_type, symptoms, profile)
        
        image_url = upload_image(img_bytes, folder=f"dermaassess/users/{user_id}/skin")
        
        db_data = {
            "user_id": user_id,
            "image_url": image_url,
            "severity_score": result.get("severity", 5),
            "contagion_risk": result.get("contagion_risk", "low"),
            "recommended_action": result.get("recommended_action", "clinic"),
            "diagnosis": result.get("diagnosis", ""),
            "possible_conditions": result.get("possible_conditions", []),
            "advice": result.get("advice", ""),
            "symptoms": symptoms
        }
        
        save_resp = supabase_client.table("skin_assessments").insert(db_data).execute()
        
        event_type = "emergency" if db_data["severity_score"] >= 7 else "skin_assessment"
        await notify_user(user_id, event_type, db_data)
        
        return save_resp.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_history(current_user: dict = Depends(get_current_user)):
    try:
         resp = supabase_client.table("skin_assessments").select("*").eq("user_id", current_user["user_id"]).order("created_at", desc=True).execute()
         return resp.data
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))
