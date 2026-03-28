from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from deps import get_current_user
from database import supabase_client, get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from services.gemini_service import analyze_meal
from services.cloudinary_service import upload_image
from services.notification_service import notify_user

router = APIRouter()


@router.post("/log")
async def log_weight(
    weight_kg: float = Form(...),
    meal_image: UploadFile = File(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
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
            
        # Save to PostgreSQL
        query = text("""
            INSERT INTO weight_logs (user_id, weight_kg, meal_description, calories_estimate, protein_g, carbs_g, fat_g, meal_image_url)
            VALUES (:user_id, :weight_kg, :meal_description, :calories_estimate, :protein_g, :carbs_g, :fat_g, :meal_image_url)
            RETURNING *
        """)
        params = {
            "user_id": user_id,
            "weight_kg": weight_kg,
            "meal_description": record.get("meal_description"),
            "calories_estimate": record.get("calories_estimate"),
            "protein_g": record.get("protein_g"),
            "carbs_g": record.get("carbs_g"),
            "fat_g": record.get("fat_g"),
            "meal_image_url": record.get("meal_image_url")
        }
        res = db.execute(query, params).fetchone()
        
        # Update Profiles table in PostgreSQL
        db.execute(text("UPDATE profiles SET weight_kg = :w WHERE id = :uid"), {"w": weight_kg, "uid": user_id})
        db.commit()
        
        saved_record = dict(res._mapping) if res else {}
        
        notify_data = {
            "weight_kg": weight_kg,
            "meal_description": record.get("meal_description"),
            "calories": record.get("calories_estimate"),
            "ai_advice": meal_analysis.get("advice", "Keep it up!"),
        }
        await notify_user(user_id, "weight_logged", notify_data)
        
        return saved_record
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_history(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        query = text("""
            SELECT * FROM weight_logs 
            WHERE user_id = :uid 
            ORDER BY logged_at DESC
        """)
        rows = db.execute(query, {"uid": current_user["user_id"]}).fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
