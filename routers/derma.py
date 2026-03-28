from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from deps import get_current_user
from database import supabase_client, get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from services.gemini_service import analyze_skin_image
import json
from services.cloudinary_service import upload_image
from services.notification_service import notify_user
import urllib.parse

router = APIRouter()


@router.post("/assess")
async def assess_skin(
    image: UploadFile = File(...),
    symptoms: str = Form("No symptoms described"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        user_id = current_user["user_id"]
        img_bytes = await image.read()
        mime_type = image.content_type
        
        prof_resp = supabase_client.table("profiles").select("*").eq("id", user_id).execute()
        profile = prof_resp.data[0] if prof_resp.data else {}
        
        result = await analyze_skin_image(img_bytes, mime_type, symptoms, profile)
        
        image_url = upload_image(img_bytes, folder=f"dermaassess/users/{user_id}/skin")
        
        query = text("""
            INSERT INTO skin_assessments (user_id, image_url, severity_score, contagion_risk, recommended_action, diagnosis, possible_conditions, advice, symptoms)
            VALUES (:user_id, :image_url, :severity_score, :contagion_risk, :recommended_action, :diagnosis, :possible_conditions, :advice, :symptoms)
            RETURNING *
        """)
        params = {
            "user_id": user_id,
            "image_url": image_url,
            "severity_score": result.get("severity", 5),
            "contagion_risk": result.get("contagion_risk", "low"),
            "recommended_action": result.get("recommended_action", "clinic"),
            "diagnosis": result.get("diagnosis", ""),
            "possible_conditions": json.dumps(result.get("possible_conditions", [])),
            "advice": result.get("advice", ""),
            "symptoms": symptoms
        }
        res = db.execute(query, params).fetchone()
        db.commit()
        saved_record = dict(res._mapping) if res else {}
        
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
        
        event_type = "emergency" if db_data["severity_score"] >= 7 else "skin_assessment"
        await notify_user(user_id, event_type, db_data)
        
        return saved_record
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_history(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
         query = text("""
             SELECT * FROM skin_assessments 
             WHERE user_id = :uid 
             ORDER BY created_at DESC
         """)
         rows = db.execute(query, {"uid": current_user["user_id"]}).fetchall()
         return [dict(r._mapping) for r in rows]
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))
