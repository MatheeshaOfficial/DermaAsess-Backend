<<<<<<< HEAD
from fastapi import APIRouter, Depends, HTTPException
from deps import get_current_user
from database import supabase_client
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    notification_channel: Optional[str] = None
    age: Optional[int] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    allergies: Optional[List[str]] = None
    chronic_conditions: Optional[List[str]] = None


@router.put("/me")
async def update_profile(
    update_data: ProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    try:
        data = update_data.model_dump(exclude_unset=True)

        if not data:
            raise HTTPException(status_code=400, detail="No data provided")

        resp = supabase_client.table("profiles") \
            .update(data) \
            .eq("id", current_user["user_id"]) \
            .execute()

        if not resp.data:
            raise HTTPException(status_code=404, detail="Profile not found")

        return {
            "success": True,
            "message": "Profile updated successfully",
            "profile": resp.data[0]
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me")
async def get_profile(current_user: dict = Depends(get_current_user)):
    try:
        resp = supabase_client.table("profiles") \
            .select("*") \
            .eq("id", current_user["user_id"]) \
            .execute()

        if not resp.data:
            raise HTTPException(status_code=404, detail="Profile not found")

        return resp.data[0]

    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
=======
from fastapi import APIRouter, Depends, HTTPException
from deps import get_current_user
from database import supabase_client
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    notification_channel: Optional[str] = None
    age: Optional[int] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    allergies: Optional[List[str]] = None
    chronic_conditions: Optional[List[str]] = None


@router.put("/me")
async def update_profile(
    update_data: ProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    try:
        data = update_data.model_dump(exclude_unset=True)

        if not data:
            raise HTTPException(status_code=400, detail="No data provided")

        resp = supabase_client.table("profiles") \
            .update(data) \
            .eq("id", current_user["user_id"]) \
            .execute()

        if not resp.data:
            raise HTTPException(status_code=404, detail="Profile not found")

        return {
            "success": True,
            "message": "Profile updated successfully",
            "profile": resp.data[0]
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me")
async def get_profile(current_user: dict = Depends(get_current_user)):
    try:
        resp = supabase_client.table("profiles") \
            .select("*") \
            .eq("id", current_user["user_id"]) \
            .execute()

        if not resp.data:
            raise HTTPException(status_code=404, detail="Profile not found")

        return resp.data[0]

    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
>>>>>>> 3efa2a2850a1b0535bb86f92f3a35fd5c8ece0cc
        raise HTTPException(status_code=500, detail=str(e))