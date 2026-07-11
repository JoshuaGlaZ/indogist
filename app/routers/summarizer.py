import json
import hashlib
import anyio
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Request, Depends, Form, File, UploadFile, status, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from sqlmodel import Session, select, func, or_, desc, asc

from app.database import get_session
from app.models import User, Summary
from app.auth import get_current_user, require_current_user, add_flash_message
from app.i18n import lang
from app.schemas import (
    parse_uploaded_file_content,
    validate_input_edge_cases,
    validate_text_content
)

from ml.summarization.hybrid import predict_and_summarize
from ml.summarization.traditional import summarize_traditional
from ml.summarization.utils import add_to_indosum_dataset

router = APIRouter(tags=["summarizer"])

# In-memory SHA-256 summary cache
SUMMARY_CACHE = {}

def render_template(request: Request, name: str, context: dict = None):
    return request.app.state.render_template(request, name, context)

@router.get("/", response_class=HTMLResponse)
def home_get(
    request: Request,
    user: Optional[User] = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    recent_summaries = []
    if user:
        statement = select(Summary).where(Summary.user_id == user.id).order_by(desc(Summary.created_at)).limit(5)
        recent_summaries = session.exec(statement).all()
    return render_template(request, "summarizer/home.html", {"recent_summaries": recent_summaries, "user": user})

@router.get("/summarize/", response_class=HTMLResponse)
def summarize_get(request: Request, user: Optional[User] = Depends(get_current_user)):
    return render_template(request, "summarizer/summarize.html", {"form": {}, "user": user})

@router.post("/summarize/")
async def summarize_post(
    request: Request,
    title: Optional[str] = Form(""),
    original_text: Optional[str] = Form(""),
    text: Optional[str] = Form(""),
    compression_ratio: float = Form(0.3),
    method: str = Form("hybrid"),
    file: Optional[UploadFile] = File(None),
    user: Optional[User] = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.headers.get("HX-Request") == "true"
    raw_input = original_text or text or ""

    file_content_str = None
    if file and file.filename:
        try:
            content_bytes = await file.read()
            file_content_str = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            err_msg = lang(request, "Unable to read file. Please ensure it is a valid UTF-8 text file.")
            if is_ajax:
                return JSONResponse({"success": False, "error": err_msg}, status_code=400)
            add_flash_message(request, err_msg, "danger")
            return render_template(request, "summarizer/summarize.html", {"user": user})

    is_valid, err_msg = validate_input_edge_cases(
        title=title or "",
        text=raw_input,
        has_file=bool(file and file.filename),
        file_content=file_content_str
    )
    if not is_valid:
        if is_ajax:
            return HTMLResponse(f'<div class="alert alert-danger card-editorial mb-0">{err_msg}</div>', status_code=400)
        add_flash_message(request, err_msg, "danger")
        return render_template(request, "summarizer/summarize.html", {"user": user})

    final_title = title or ""
    final_text = raw_input

    if file and file.filename and file_content_str:
        try:
            parsed_title, parsed_text = parse_uploaded_file_content(file_content_str)
            final_title = parsed_title
            final_text = parsed_text
        except ValueError as e:
            if is_ajax:
                return HTMLResponse(f'<div class="alert alert-danger card-editorial mb-0">{str(e)}</div>', status_code=400)
            add_flash_message(request, str(e), "danger")
            return render_template(request, "summarizer/summarize.html", {"form": {"title": title or "", "original_text": raw_input}, "user": user})

    try:
        validate_text_content(final_text)
    except ValueError as e:
        if is_ajax:
            return HTMLResponse(f'<div class="alert alert-danger card-editorial mb-0">{str(e)}</div>', status_code=400)

    # Check SHA-256 Cache
    cache_key = hashlib.sha256(f"{final_text}:{method}:{compression_ratio}".encode()).hexdigest()
    if cache_key in SUMMARY_CACHE:
        summary_result = SUMMARY_CACHE[cache_key]
    else:
        if method == "traditional":
            summary_result = summarize_traditional(final_text, ratio=compression_ratio)
        else:
            summary_result = predict_and_summarize(final_title, final_text)
        SUMMARY_CACHE[cache_key] = summary_result

    summary_obj = None
    if user:
        summary_obj = Summary(
            user_id=user.id,
            title=final_title or final_text[:50],
            original_text=final_text,
            summary_text=summary_result,
            method=method,
            compression_ratio=compression_ratio,
            created_at=datetime.utcnow()
        )
        session.add(summary_obj)
        session.commit()
        session.refresh(summary_obj)

    context = {"summary": {"summary_text": summary_result}, "user": user}

    if is_ajax:
        return HTMLResponse(f'''
        <div class="scramble-output" data-text="{summary_result}">
            {summary_result}
        </div>
        ''')

    return render_template(request, "summarizer/summarize.html", context)

@router.get("/history/", response_class=HTMLResponse)
def history_get(
    request: Request,
    q: Optional[str] = Query(""),
    method: Optional[str] = Query(""),
    sort: Optional[str] = Query("-created_at"),
    user: Optional[User] = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    summaries = []
    if user:
        statement = select(Summary).where(Summary.user_id == user.id)
        if q:
            statement = statement.where(or_(Summary.title.contains(q), Summary.summary_text.contains(q)))
        if method:
            statement = statement.where(Summary.method == method)
        if sort == "created_at":
            statement = statement.order_by(asc(Summary.created_at))
        elif sort == "title":
            statement = statement.order_by(asc(Summary.title))
        else:
            statement = statement.order_by(desc(Summary.created_at))
        summaries = session.exec(statement).all()

    return render_template(request, "summarizer/history.html", {
        "summaries": summaries,
        "search_query": q,
        "method_filter": method,
        "sort_by": sort,
        "user": user
    })

@router.get("/charts/", response_class=HTMLResponse)
def charts_get(request: Request, user: Optional[User] = Depends(get_current_user)):
    return render_template(request, "summarizer/charts.html", {"user": user})

@router.get("/comparison/", response_class=HTMLResponse)
@router.post("/comparison/", response_class=HTMLResponse)
def comparison(
    request: Request,
    text: Optional[str] = Form(""),
    user: Optional[User] = Depends(get_current_user)
):
    traditional_summary = ""
    hybrid_summary = ""
    if text:
        traditional_summary = summarize_traditional(text, ratio=0.3)
        hybrid_summary = predict_and_summarize("", text)

    return render_template(request, "summarizer/comparison.html", {
        "source_text": text,
        "traditional_summary": traditional_summary,
        "hybrid_summary": hybrid_summary,
        "user": user
    })
