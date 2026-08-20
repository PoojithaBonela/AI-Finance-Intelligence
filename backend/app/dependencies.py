from fastapi import HTTPException, status, Header
from typing import Optional
from .database import supabase_client
import logging

logger = logging.getLogger(__name__)

async def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """
    Extracts the Bearer token from the Authorization header,
    verifies it with Supabase, and returns the authenticated user's ID.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.split(" ")[1]
    
    if not supabase_client:
        logger.error("Supabase client is not initialized in dependencies")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection is not initialized"
        )
        
    try:
        response = supabase_client.auth.get_user(token)
        user = response.user
        if not user:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user.id
    except Exception as e:
        logger.error(f"Error validating token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
