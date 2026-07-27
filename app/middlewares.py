from fastapi import Request
from sqlmodel import Session

import app.database as app_db
from app.i18n import get_translations, negotiate_locale
from app.models import User


class AnonymousUser:
    is_authenticated = False
    username = ""
    email = ""
    id = None


async def locale_middleware(request: Request, call_next):
    locale = negotiate_locale(request)
    request.state.locale = locale
    request.state.translations = get_translations(locale)
    response = await call_next(request)
    response.headers["Content-Language"] = locale
    return response


async def user_and_messages_middleware(request: Request, call_next):
    if request.url.path.startswith("/static") or request.url.path in (
        "/health",
        "/favicon.ico",
    ):
        request.state.user = AnonymousUser()
        request.scope["user"] = AnonymousUser()
        return await call_next(request)

    user_id = request.session.get("user_id") if "session" in request.scope else None
    user_obj = AnonymousUser()
    if user_id:
        with Session(app_db.engine) as db_session:
            user = db_session.get(User, user_id)
            if user:
                user_obj = user
            else:
                if "session" in request.scope:
                    request.session.pop("user_id", None)
    request.state.user = user_obj
    request.scope["user"] = user_obj
    response = await call_next(request)
    return response
