import jwt
from datetime import datetime, timedelta
from fastapi import Header, HTTPException, status
from config import JWT_SECRET


JWT_SECRET = JWT_SECRET

def create_jwt(user_id: str, telegram_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "telegram_id": telegram_id,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def get_current_user(authorization: str = Header(...)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    
    try:
        decoded_payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return {
            "user_id": decoded_payload.get("sub"),
            "telegram_id": decoded_payload.get("telegram_id")
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
