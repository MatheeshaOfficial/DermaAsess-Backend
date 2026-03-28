from fastapi import APIRouter, Depends, HTTPException
from deps import get_current_user
from database import supabase_client, get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
import json
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
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        data = update_data.model_dump(exclude_unset=True)

        if not data:
            raise HTTPException(status_code=400, detail="No data provided")

        user_id = current_user["user_id"]
        
        if "allergies" in data and data["allergies"] is not None:
            data["allergies"] = json.dumps(data["allergies"])
        if "chronic_conditions" in data and data["chronic_conditions"] is not None:
            data["chronic_conditions"] = json.dumps(data["chronic_conditions"])
            
        set_clauses = [f"{k} = :{k}" for k in data.keys()]
        set_str = ", ".join(set_clauses)
        
        query = text(f"""
            UPDATE profiles 
            SET {set_str} 
            WHERE id = :id 
            RETURNING *
        """)
        
        data["id"] = user_id
        res = db.execute(query, data).fetchone()
        db.commit()

        if not res:
            raise HTTPException(status_code=404, detail="Profile not found")

        profile_data = dict(res._mapping)
        if isinstance(profile_data.get("allergies"), str):
            try: profile_data["allergies"] = json.loads(profile_data["allergies"])
            except: pass
        if isinstance(profile_data.get("chronic_conditions"), str):
            try: profile_data["chronic_conditions"] = json.loads(profile_data["chronic_conditions"])
            except: pass

        return {
            "success": True,
            "message": "Profile updated successfully",
            "profile": profile_data
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me")
async def get_profile(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        query = text("SELECT * FROM profiles WHERE id = :id")
        res = db.execute(query, {"id": current_user["user_id"]}).fetchone()

        if not res:
            raise HTTPException(status_code=404, detail="Profile not found")

        profile_data = dict(res._mapping)
        if isinstance(profile_data.get("allergies"), str):
            try: profile_data["allergies"] = json.loads(profile_data["allergies"])
            except: pass
        if isinstance(profile_data.get("chronic_conditions"), str):
            try: profile_data["chronic_conditions"] = json.loads(profile_data["chronic_conditions"])
            except: pass

        return profile_data

    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))