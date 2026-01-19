from fastapi import Request, HTTPException, status
from firebase_admin import auth
import firebase_admin

# Initialize Firebase Admin if not already done
if not firebase_admin._apps:
    firebase_admin.initialize_app()

async def verify_firebase_token(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header"
        )

    token = auth_header.split(" ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        # Add user to request state
        request.state.user = decoded_token
        return decoded_token # Contains 'uid', 'email', etc.
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {str(e)}"
        )
