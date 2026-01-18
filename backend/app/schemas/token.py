from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime

class TokenPayload(BaseModel):
    sub: Optional[int] = None
    exp: Optional[int] = None
    iat: Optional[int] = None
    
class RefreshTokenCreate(BaseModel):
    token: str
    expires_at: datetime
    user_id: int

class RefreshTokenResponse(RefreshTokenCreate):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class TokenData(BaseModel):
    email: Optional[EmailStr] = None
