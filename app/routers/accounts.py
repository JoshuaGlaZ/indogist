import os

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app.auth import (
    add_flash_message,
    get_current_user,
    hash_password,
    require_current_user,
    verify_password,
)
from app.database import get_session
from app.i18n import lang
from app.models import Summary, User

router = APIRouter(prefix="/accounts", tags=["accounts"])


limiter = Limiter(
    key_func=get_remote_address,
    enabled=os.getenv("TESTING", "False").lower() not in ("true", "1"),
)


def render_template(request: Request, name: str, context: dict | None = None):
    return request.app.state.render_template(request, name, context)


@router.get("/register", response_class=HTMLResponse)
def register_get(request: Request, user: User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return render_template(request, "accounts/register.html", {"form": {}})


@router.post("/register", response_class=HTMLResponse)
@limiter.limit("5/minute")
def register_post(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(..., alias="password1"),
    confirm_password: str = Form(..., alias="password2"),
    session: Session = Depends(get_session),
):
    form_data = {"username": username, "email": email}

    if password != confirm_password:
        add_flash_message(request, lang(request, "Passwords do not match."), "danger")
        return render_template(request, "accounts/register.html", {"form": form_data})

    existing_user = session.exec(select(User).where(User.username == username)).first()
    if existing_user:
        add_flash_message(request, lang(request, "Username is already taken."), "danger")
        return render_template(request, "accounts/register.html", {"form": form_data})

    existing_email = session.exec(select(User).where(User.email == email)).first()
    if existing_email:
        add_flash_message(request, lang(request, "Email address is already registered."), "danger")
        return render_template(request, "accounts/register.html", {"form": form_data})

    new_user = User(
        username=username.strip(),
        email=email.strip().lower(),
        hashed_password=hash_password(password),
    )
    try:
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
    except IntegrityError:
        session.rollback()
        add_flash_message(request, lang(request, "Username is already taken."), "danger")
        return render_template(
            request,
            "accounts/register.html",
            {"form": form_data},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    request.session["user_id"] = new_user.id
    add_flash_message(
        request,
        lang(request, "Account created for %(username)s! You are now logged in.")
        % {"username": new_user.username},
        "success",
    )
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)


@router.get("/login", response_class=HTMLResponse)
def login_get(request: Request, user: User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return render_template(request, "accounts/login.html", {"form": {}})


@router.post("/login", response_class=HTMLResponse)
@limiter.limit("10/minute")
def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.username == username)).first()

    if not user or not verify_password(password, user.hashed_password):
        add_flash_message(request, lang(request, "Invalid username or password."), "danger")
        return render_template(request, "accounts/login.html", {"form": {"username": username}})

    request.session["user_id"] = user.id
    add_flash_message(
        request,
        lang(request, "Welcome back, %(username)s!") % {"username": user.username},
        "success",
    )
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    add_flash_message(request, lang(request, "You have been logged out."), "info")
    return RedirectResponse(url="/accounts/login", status_code=status.HTTP_302_FOUND)


@router.post("/logout")
def logout_post(request: Request):
    request.session.clear()
    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        return Response(status_code=200, headers={"HX-Redirect": "/accounts/login"})
    return RedirectResponse(url="/accounts/login", status_code=status.HTTP_302_FOUND)


@router.get("/profile", response_class=HTMLResponse)
def profile_get(
    request: Request,
    current_user: User = Depends(require_current_user),
    session: Session = Depends(get_session),
):
    try:
        res = session.exec(
            select(func.count(Summary.id)).where(Summary.user_id == current_user.id)
        ).first()
        if isinstance(res, (int, float)):
            total_summaries = int(res)
        elif res and isinstance(res, (tuple, list)) and len(res) > 0:
            total_summaries = int(res[0])
        else:
            total_summaries = 0
    except (Exception, IndexError):
        total_summaries = 0

    return render_template(
        request,
        "accounts/profile.html",
        {
            "user": current_user,
            "total_summaries": total_summaries,
            "u_form": current_user,
        },
    )


@router.post("/profile", response_class=HTMLResponse)
def profile_post(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    current_user: User = Depends(require_current_user),
    session: Session = Depends(get_session),
):
    clean_username = username.strip()
    clean_email = email.strip().lower()

    existing_username = session.exec(
        select(User).where(
            func.lower(User.username) == clean_username.lower(),
            User.id != current_user.id,
        )
    ).first()

    existing_email = session.exec(
        select(User).where(
            func.lower(User.email) == clean_email.lower(),
            User.id != current_user.id,
        )
    ).first()

    if existing_username:
        add_flash_message(request, lang(request, "Username is already taken."), "danger")
    elif existing_email:
        add_flash_message(request, lang(request, "Email is already in use."), "danger")
    else:
        try:
            current_user.username = clean_username
            current_user.email = clean_email
            session.add(current_user)
            session.commit()
            session.refresh(current_user)
            add_flash_message(request, lang(request, "Your profile has been updated!"), "success")
        except IntegrityError:
            session.rollback()
            add_flash_message(
                request, lang(request, "Username or email is already taken."), "danger"
            )

    try:
        res = session.exec(
            select(func.count(Summary.id)).where(Summary.user_id == current_user.id)
        ).first()
        if isinstance(res, (int, float)):
            total_summaries = int(res)
        elif res and isinstance(res, (tuple, list)) and len(res) > 0:
            total_summaries = int(res[0])
        else:
            total_summaries = 0
    except (Exception, IndexError):
        total_summaries = 0

    return render_template(
        request,
        "accounts/profile.html",
        {
            "user": current_user,
            "total_summaries": total_summaries,
            "u_form": current_user,
        },
    )
