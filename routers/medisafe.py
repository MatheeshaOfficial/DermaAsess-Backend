from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from deps import get_current_user
from database import supabase_client
from services.gemini_service import ocr_prescription, check_drug_safety
from services.cloudinary_service import upload_image
from services.notification_service import notify_user

router = APIRouter()


@router.post("/scan-prescription")
async def scan_prescription(
    image: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = current_user["user_id"]
        img_bytes = await image.read()
        mime_type = image.content_type
        
        prof_resp = supabase_client.table("profiles").select("*").eq("id", user_id).execute()
        profile = prof_resp.data[0] if prof_resp.data else {}
        
        ocr_result = await ocr_prescription(img_bytes, mime_type)
        medicines = ocr_result.get("medicines", [])
        
        safety_result = await check_drug_safety(medicines, profile)
        
        image_url = upload_image(img_bytes, folder=f"dermaassess/users/{user_id}/prescriptions")
        
        db_data = {
            "user_id": user_id,
            "image_url": image_url,
            "medicines_found": medicines,
            "medicines_count": len(medicines),
            "overall_safety": safety_result.get("overall_safety", "caution"),
            "safety_advice": safety_result.get("advice", ""),
            "interactions": safety_result.get("interactions", []),
            "allergy_alerts": safety_result.get("allergy_alerts", [])
        }
        
        save_resp = supabase_client.table("prescriptions").insert(db_data).execute()
        
        notify_data = {
            "medicines_count": len(medicines),
            "overall_safety": db_data["overall_safety"],
            "safety_advice": db_data["safety_advice"],
            "interactions": db_data["interactions"],
            "allergy_alerts": db_data["allergy_alerts"],
        }
        await notify_user(user_id, "prescription_scan", notify_data)
        
        return save_resp.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
