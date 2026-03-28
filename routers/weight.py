from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from deps import get_current_user
from database import supabase_client
from services.gemini_service import analyze_meal
from services.cloudinary_service import upload_image
from services.notification_service import notify_user

router = APIRouter()


@router.post("/log")
async def log_weight(
    weight_kg: float = Form(...),
    meal_image: UploadFile = File(None),
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = current_user["user_id"]
        record = {
            "user_id": user_id,
            "weight_kg": weight_kg
        }
        
        meal_analysis = {}
        
        if meal_image:
            img_bytes = await meal_image.read()
            mime_type = meal_image.content_type
            meal_analysis = await analyze_meal(img_bytes, mime_type)
            record["meal_description"] = ", ".join(meal_analysis.get("food_items", []))
            record["calories_estimate"] = meal_analysis.get("calories_estimate", 0)
            record["protein_g"] = meal_analysis.get("protein_g", 0)
            record["carbs_g"] = meal_analysis.get("carbs_g", 0)
            record["fat_g"] = meal_analysis.get("fat_g", 0)
            record["meal_image_url"] = upload_image(img_bytes, folder=f"dermaassess/users/{user_id}/meals")
            
        save_resp = supabase_client.table("weight_logs").insert(record).execute()
        supabase_client.table("profiles").update({"weight": weight_kg}).eq("id", user_id).execute()
        
        notify_data = {
            "weight_kg": weight_kg,
            "meal_description": record.get("meal_description"),
            "calories": record.get("calories_estimate"),
            "ai_advice": meal_analysis.get("advice", "Keep it up!"),
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
            .order("logged_at", desc=True) \
            .execute()
        return resp.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
