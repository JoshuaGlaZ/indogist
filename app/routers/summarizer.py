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
    hybrid_variant: str = Form("pos_ner"),
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
            return HTMLResponse(f'<div class="alert alert-danger mb-0">{err_msg}</div>', status_code=400)
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
                return HTMLResponse(f'<div class="alert alert-danger mb-0">{str(e)}</div>', status_code=400)
            add_flash_message(request, str(e), "danger")
            return render_template(request, "summarizer/summarize.html", {"form": {"title": title or "", "original_text": raw_input}, "user": user})

    try:
        validate_text_content(final_text)
    except ValueError as e:
        if is_ajax:
            return HTMLResponse(f'<div class="alert alert-danger mb-0">{str(e)}</div>', status_code=400)

    # Check SHA-256 Cache
    cache_key = hashlib.sha256(f"{final_text}:{method}:{hybrid_variant}:{compression_ratio}".encode()).hexdigest()
    entities_list = []
    if cache_key in SUMMARY_CACHE:
        cached = SUMMARY_CACHE[cache_key]
        summary_result = cached["summary"]
        entities_list = cached.get("entities", [])
    else:
        if method == "traditional":
            summary_result = summarize_traditional(final_text, ratio=compression_ratio)
        else:
            # Run POS/NER Hybrid model
            res = predict_and_summarize(final_text, title=final_title, compression_ratio=compression_ratio)
            if isinstance(res, dict):
                summary_result = res.get("summary", "")
                entities_list = res.get("entities", [])
            else:
                summary_result = res
        
        SUMMARY_CACHE[cache_key] = {"summary": summary_result, "entities": entities_list}

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

    if is_ajax:
        # Build Out-Of-Band entity chip HTML for HTMX
        entity_chips_html = ""
        if entities_list:
            for ent in entities_list:
                score = ent.get("confidence_percent", round(ent.get("score", 0.9) * 100))
                entity_chips_html += f'''
                <span class="entity-chip show">
                  <span>{ent.get("text", "")}</span>
                  <span class="e-type">{ent.get("label", "ENTITY")}</span>
                  <span class="e-score">{score}%</span>
                </span>
                '''
        else:
            entity_chips_html = f'<span class="output-placeholder">{lang(request, "No named entities detected in this text.")}</span>'

        return HTMLResponse(f'''
        <div class="summary-output-text">{summary_result}</div>
        <div id="entityWrap" hx-swap-oob="true">
            {entity_chips_html}
        </div>
        ''')

    context = {"summary": {"summary_text": summary_result}, "entities_list": entities_list, "user": user}
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
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.headers.get("HX-Request") == "true"
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

    context = {
        "summaries": summaries,
        "search_query": q,
        "method_filter": method,
        "sort_by": sort,
        "user": user
    }

    if is_ajax:
        return render_template(request, "summarizer/history_list.html", context)

    return render_template(request, "summarizer/history.html", context)

@router.get("/charts/", response_class=HTMLResponse)
def charts_get(request: Request, user: Optional[User] = Depends(get_current_user)):
    return render_template(request, "summarizer/charts.html", {"user": user})

@router.get("/comparison/", response_class=HTMLResponse)
@router.post("/comparison/", response_class=HTMLResponse)
def comparison(
    request: Request,
    text: Optional[str] = Form(""),
    model_a: Optional[str] = Form("traditional"),
    model_b: Optional[str] = Form("hybrid"),
    user: Optional[User] = Depends(get_current_user)
):
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.headers.get("HX-Request") == "true"
    summary_a = ""
    summary_b = ""
    if text:
        if model_a == "traditional":
            summary_a = summarize_traditional(text, ratio=0.3)
        else:
            res_a = predict_and_summarize(text, title="")
            summary_a = res_a.get("summary", "") if isinstance(res_a, dict) else res_a

        if model_b == "traditional":
            summary_b = summarize_traditional(text, ratio=0.3)
        else:
            res_b = predict_and_summarize(text, title="")
            summary_b = res_b.get("summary", "") if isinstance(res_b, dict) else res_b

    context = {
        "source_text": text,
        "traditional_summary": summary_a,
        "hybrid_summary": summary_b,
        "model_a": model_a,
        "model_b": model_b,
        "user": user
    }

    if is_ajax and text:
        return HTMLResponse(f'''
        <div class="card">
          <div class="card-head">
            <p class="card-title">Model A ({model_a|upper})</p>
            <span class="badge {model_a}">{model_a}</span>
          </div>
          <div class="card-body">
            <div class="output-area">{summary_a}</div>
            <div class="stats-grid" style="margin-top: 12px;">
              <div class="stat-card"><span class="s-label">Words</span><span class="s-value">{len(summary_a.split()) if summary_a else 0}</span></div>
              <div class="stat-card accent"><span class="s-label">Sentences</span><span class="s-value">{len(summary_a.split('.')) if summary_a else 0}</span></div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-head">
            <p class="card-title">Model B ({model_b|upper})</p>
            <span class="badge {model_b}">{model_b}</span>
          </div>
          <div class="card-body">
            <div class="output-area">{summary_b}</div>
            <div class="stats-grid" style="margin-top: 12px;">
              <div class="stat-card"><span class="s-label">Words</span><span class="s-value">{len(summary_b.split()) if summary_b else 0}</span></div>
              <div class="stat-card accent"><span class="s-label">Sentences</span><span class="s-value">{len(summary_b.split('.')) if summary_b else 0}</span></div>
            </div>
          </div>
        </div>
        ''')

    return render_template(request, "summarizer/comparison.html", context)
