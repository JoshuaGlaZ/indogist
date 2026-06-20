from typing import Optional
from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select, func

from app.database import get_session
from app.models import User, Summary
from app.auth import (
    hash_password,
    verify_password,
    get_current_user,
    require_current_user,
    add_flash_message
)
from app.i18n import lang

router = APIRouter(prefix="/accounts", tags=["accounts"])

def render_template(request: Request, name: str, context: dict = None):
    return request.app.state.render_template(request, name, context)

@router.get("/register", response_class=HTMLResponse)
def register_get(request: Request, user: Optional[User] = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return render_template(request, "accounts/register.html", {"form": {}})

@router.post("/register", response_class=HTMLResponse)
def register_post(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(..., alias="password1"),
    confirm_password: str = Form(..., alias="password2"),
    session: Session = Depends(get_session)
):
    form_data = {"username": username, "email": email}

    if password != confirm_password:
        add_flash_message(request, lang("Passwords do not match."), "danger")
        return render_template(request, "accounts/register.html", {"form": form_data})

    existing_user = session.exec(select(User).where(User.username == username)).first()
    if existing_user:
        add_flash_message(request, lang("Username is already taken."), "danger")
        return render_template(request, "accounts/register.html", {"form": form_data})

    existing_email = session.exec(select(User).where(User.email == email)).first()
    if existing_email:
        add_flash_message(request, lang("Email address is already registered."), "danger")
        return render_template(request, "accounts/register.html", {"form": form_data})

    new_user = User(
        username=username.strip(),
        email=email.strip().lower(),
        hashed_password=hash_password(password)
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    request.session["user_id"] = new_user.id
    add_flash_message(request, lang(f"Account created for {new_user.username}! You are now logged in."), "success")
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

@router.get("/login", response_class=HTMLResponse)
def login_get(request: Request, user: Optional[User] = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return render_template(request, "accounts/login.html", {"form": {}})

@router.post("/login", response_class=HTMLResponse)
def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session)
):
    user = session.exec(select(User).where(User.username == username)).first()

    if not user or not verify_password(password, user.hashed_password):
        add_flash_message(request, lang("Invalid username or password."), "danger")
        return render_template(request, "accounts/login.html", {"form": {"username": username}})

    request.session["user_id"] = user.id
    add_flash_message(request, lang(f"Welcome back, {user.username}!"), "success")
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    add_flash_message(request, lang("You have been logged out."), "info")
    return RedirectResponse(url="/accounts/login", status_code=status.HTTP_302_FOUND)

@router.post("/logout")
def logout_post(request: Request):
    return logout(request)

@router.get("/profile", response_class=HTMLResponse)
def profile_get(
    request: Request,
    current_user: User = Depends(require_current_user),
    session: Session = Depends(get_session)
):
    total_summaries = session.exec(
        select(func.count(Summary.id)).where(Summary.user_id == current_user.id)
    ).one() or 0

    return render_template(
        request,
        "accounts/profile.html",
        {
            "user": current_user,
            "total_summaries": total_summaries,
            "u_form": current_user
        }
    )

@router.post("/profile", response_class=HTMLResponse)
def profile_post(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    current_user: User = Depends(require_current_user),
    session: Session = Depends(get_session)
):
    existing_email = session.exec(
        select(User).where(User.email == email, User.id != current_user.id)
    ).first()

    if existing_email:
        add_flash_message(request, lang("Email is already in use."), "danger")
    else:
        current_user.username = username.strip()
        current_user.email = email.strip().lower()
        session.add(current_user)
        session.commit()
        session.refresh(current_user)
        add_flash_message(request, lang("Your profile has been updated!"), "success")

    total_summaries = session.exec(
        select(func.count(Summary.id)).where(Summary.user_id == current_user.id)
    ).one() or 0

    return render_template(
        request,
        "accounts/profile.html",
        {
            "user": current_user,
            "total_summaries": total_summaries,
            "u_form": current_user
        }
    )
