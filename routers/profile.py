from fastapi import APIRouter, Depends, HTTPException
from deps import get_current_user
import supabase
import os
from pydantic import BaseModel

router = APIRouter()

supabase_client = supabase.create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_KEY", "")
)

class ProfileUpdate(BaseModel):
    email: str = None
    notification_channel: str = None

@router.put("/")
async def update_profile(update_data: ProfileUpdate, current_user: dict = Depends(get_current_user)):
    try:
        data = update_data.model_dump(exclude_unset=True)
        resp = supabase_client.table("profiles").update(data).eq("id", current_user["user_id"]).execute()
        return resp.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
