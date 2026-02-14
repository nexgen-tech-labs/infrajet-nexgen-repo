from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, Security, Header
from fastapi.security import OAuth2PasswordBearer
from firebase_admin import auth
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)

# Type alias for backward compatibility with Supabase code
SupabaseUser = Dict[str, Any]


class FirebaseJWTValidator:
    """Validates Firebase JWT tokens"""

    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        """Verify Firebase ID token and return decoded claims"""
        try:
            decoded_token = auth.verify_id_token(token)
            return decoded_token
        except auth.ExpiredIdTokenError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except auth.InvalidIdTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


# Alias for backward compatibility
SupabaseJWTValidator = FirebaseJWTValidator


async def get_current_user_id(token: str = Security(oauth2_scheme)) -> str:
    """Get current user ID from Firebase token (required)"""
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token["uid"]
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


async def get_current_user_id_optional(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Security(oauth2_scheme)
) -> Optional[str]:
    """Get current user ID from Firebase token (optional, returns None if not authenticated)"""
    # Try to get token from Authorization header first
    token_to_use = None
    if authorization and authorization.startswith("Bearer "):
        token_to_use = authorization.split(" ")[1]
    elif token:
        token_to_use = token

    if not token_to_use:
        return None

    try:
        decoded_token = auth.verify_id_token(token_to_use)
        return decoded_token["uid"]
    except Exception:
        # Return None for optional auth instead of raising exception
        return None


async def get_current_user(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)) -> User:
    """Get current user from database (required)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
