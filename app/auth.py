from typing import Optional, List, Tuple
from fastapi import Request, Depends, HTTPException, status
from passlib.context import CryptContext
from sqlmodel import Session, select
from app.database import get_session
from app.models import User

pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_current_user(request: Request, session: Session = Depends(get_session)) -> Optional[User]:
    user_state = getattr(request.state, "user", None)
    if user_state and getattr(user_state, "is_authenticated", False):
        return user_state
    user_id = request.session.get("user_id") if hasattr(request, "session") and "session" in request.scope else None
    if not user_id:
        return None
    user = session.get(User, user_id)
    return user

def require_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    user = get_current_user(request, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/accounts/login"}
        )
    return user

def add_flash_message(request: Request, message: str, category: str = "info"):
    if hasattr(request, "session"):
        messages = request.session.get("_messages", [])
        messages.append({"message": message, "category": category, "tags": category})
        request.session["_messages"] = messages

def get_flash_messages(request: Request) -> List[dict]:
    if hasattr(request, "session"):
        messages = request.session.get("_messages", [])
        request.session["_messages"] = []
        return messages
    return []
