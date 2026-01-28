from fastapi import Depends, HTTPException, Security
from fastapi.security import OAuth2PasswordBearer
from firebase_admin import auth
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

async def get_current_user_id(token: str = Security(oauth2_scheme)) -> str:
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token["uid"]
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
