import json
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

def render_template(request: Request, name: str, context: dict = None):
    return request.app.state.render_template(request, name, context)

@router.get("/", response_class=HTMLResponse)
def home(request: Request, user: Optional[User] = Depends(get_current_user), session: Session = Depends(get_session)):
    recent_summaries = []
    if user:
        statement = (
            select(Summary)
            .where(Summary.user_id == user.id)
            .order_by(desc(Summary.created_at))
            .limit(5)
        )
        recent_summaries = session.exec(statement).all()
    return render_template(request, "summarizer/home.html", {"recent_summaries": recent_summaries, "user": user})

@router.get("/summarize", response_class=HTMLResponse)
def summarize_get(request: Request, user: Optional[User] = Depends(get_current_user)):
    return render_template(request, "summarizer/summarize.html", {"form": {}, "user": user})

@router.post("/summarize")
async def summarize_post(
    request: Request,
    title: Optional[str] = Form(""),
    original_text: Optional[str] = Form(""),
    compression_ratio: float = Form(0.3),
    method: str = Form("hybrid"),
    file: Optional[UploadFile] = File(None),
    user: Optional[User] = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.headers.get("HX-Request") == "true"

    file_content_str = None
    if file and file.filename:
        try:
            content_bytes = await file.read()
            file_content_str = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            err_msg = lang("Unable to read file. Please ensure it's a valid UTF-8 text file.")
            if is_ajax:
                return JSONResponse({"success": False, "error": err_msg}, status_code=400)
            add_flash_message(request, err_msg, "danger")
            return render_template(request, "summarizer/summarize.html", {"user": user})

    is_valid, err_msg = validate_input_edge_cases(
        title=title or "",
        text=original_text or "",
        has_file=bool(file and file.filename),
        file_content=file_content_str
    )
    if not is_valid:
        if is_ajax:
            return JSONResponse({"success": False, "error": err_msg}, status_code=400)
        add_flash_message(request, err_msg, "danger")
        return render_template(request, "summarizer/summarize.html", {"user": user})

    final_title = title or ""
    final_text = original_text or ""

    if file and file.filename and file_content_str:
        try:
            parsed_title, parsed_text = parse_uploaded_file_content(file_content_str)
            final_title = parsed_title
            final_text = parsed_text
        except ValueError as e:
            if is_ajax:
                return JSONResponse({"success": False, "error": str(e)}, status_code=400)
            add_flash_message(request, str(e), "danger")
            return render_template(request, "summarizer/summarize.html", {"form": {"title": title or "", "original_text": original_text or ""}, "user": user})

    try:
        validate_text_content(final_text)
    except ValueError as e:
        if is_ajax:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)
        add_flash_message(request, str(e), "danger")
        return render_template(request, "summarizer/summarize.html", {"user": user})

    # Offload heavy ML pipeline execution to worker thread pool using anyio
    try:
        if method == "traditional":
            result = await anyio.to_thread.run_sync(
                lambda: summarize_traditional(text=final_text, title=final_title, compression_ratio=compression_ratio, stream=False)
            )
            summary_text = result.get("summary", "") if isinstance(result, dict) else ""
            entities = []
            if not final_title and isinstance(result, dict) and result.get("effective_title"):
                final_title = result["effective_title"]
        else:
            result = await anyio.to_thread.run_sync(
                lambda: predict_and_summarize(text=final_text, title=final_title, compression_ratio=compression_ratio, stream=False)
            )
            summary_text = result.get("summary", "") if isinstance(result, dict) else ""
            entities = result.get("entities", []) if isinstance(result, dict) else []
            if not final_title and isinstance(result, dict) and result.get("effective_title"):
                final_title = result["effective_title"]

        if not final_title:
            words = final_text.split()
            final_title = " ".join(words[:5]) + "..." if len(words) > 5 else final_text

    except Exception as e:
        err_str = lang(f"Error during summarization: {str(e)}")
        if is_ajax:
            return JSONResponse({"success": False, "error": err_str}, status_code=500)
        add_flash_message(request, err_str, "danger")
        return render_template(request, "summarizer/summarize.html", {"user": user})

    new_summary = None
    if user:
        new_summary = Summary(
            user_id=user.id,
            title=final_title,
            original_text=final_text,
            summary_text=summary_text,
            compression_ratio=compression_ratio,
            method=method,
            word_count_original=len(final_text.split()),
            word_count_summary=len(summary_text.split())
        )
        new_summary.entities = entities
        session.add(new_summary)
        session.commit()
        session.refresh(new_summary)

    response_data = {
        "success": True,
        "title": final_title,
        "original_text": final_text,
        "summary_text": summary_text,
        "compression_ratio": compression_ratio,
        "entities": entities,
        "method": method,
        "word_count_original": len(final_text.split()),
        "word_count_summary": len(summary_text.split()),
        "summary_id": new_summary.id if new_summary else None
    }

    if is_ajax:
        return JSONResponse(response_data)

    if new_summary:
        return RedirectResponse(url=f"/summary/{new_summary.id}", status_code=status.HTTP_302_FOUND)

    return render_template(request, "summarizer/summary_detail.html", {"summary": response_data, "user": user})

@router.get("/summary/{pk}", response_class=HTMLResponse)
def summary_detail(
    pk: int,
    request: Request,
    user: User = Depends(require_current_user),
    session: Session = Depends(get_session)
):
    summary_obj = session.get(Summary, pk)
    if not summary_obj or summary_obj.user_id != user.id:
        add_flash_message(request, lang("Summary not found."), "danger")
        return RedirectResponse(url="/history", status_code=status.HTTP_302_FOUND)

    return render_template(
        request,
        "summarizer/summary_detail.html",
        {"summary": summary_obj, "entities_by_type": summary_obj.get_entities_by_type(), "user": user}
    )

@router.get("/history", response_class=HTMLResponse)
def history(
    request: Request,
    search: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("-created_at"),
    user: User = Depends(require_current_user),
    session: Session = Depends(get_session)
):
    query = select(Summary).where(Summary.user_id == user.id)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Summary.title.like(term),
                Summary.original_text.like(term),
                Summary.summary_text.like(term)
            )
        )

    if method in ["hybrid", "traditional"]:
        query = query.where(Summary.method == method)

    if sort_by == "created_at":
        query = query.order_by(asc(Summary.created_at))
    elif sort_by == "title":
        query = query.order_by(asc(Summary.title))
    elif sort_by == "-title":
        query = query.order_by(desc(Summary.title))
    elif sort_by == "word_count_original":
        query = query.order_by(asc(Summary.word_count_original))
    elif sort_by == "-word_count_original":
        query = query.order_by(desc(Summary.word_count_original))
    else:
        query = query.order_by(desc(Summary.created_at))

    summaries = session.exec(query).all()

    return render_template(
        request,
        "summarizer/history.html",
        {
            "summaries": summaries,
            "filter_form": {"search": search or "", "method": method or "", "sort_by": sort_by or "-created_at"},
            "user": user
        }
    )

@router.get("/charts", response_class=HTMLResponse)
def charts_view(
    request: Request,
    user: User = Depends(require_current_user),
    session: Session = Depends(get_session)
):
    summaries = session.exec(
        select(Summary).where(Summary.user_id == user.id).order_by(desc(Summary.created_at))
    ).all()

    total_count = len(summaries)
    hybrid_count = sum(1 for s in summaries if s.method == "hybrid")
    traditional_count = sum(1 for s in summaries if s.method == "traditional")

    avg_compression = 0.0
    if total_count > 0:
        avg_compression = sum(s.actual_compression for s in summaries) / total_count

    return render_template(
        request,
        "summarizer/charts.html",
        {
            "summaries": summaries,
            "stats": {
                "total_count": total_count,
                "hybrid_count": hybrid_count,
                "traditional_count": traditional_count,
                "avg_compression": round(avg_compression * 100, 1)
            },
            "user": user
        }
    )

@router.get("/comparison", response_class=HTMLResponse)
def comparison_get(request: Request, user: Optional[User] = Depends(get_current_user)):
    return render_template(request, "summarizer/comparison.html", {"form": {}, "user": user})

@router.post("/comparison")
async def comparison_post(
    request: Request,
    title: str = Form(...),
    text: str = Form(...),
    compression_ratio: float = Form(0.3),
    user: Optional[User] = Depends(get_current_user)
):
    try:
        validate_text_content(text)
    except ValueError as e:
        add_flash_message(request, str(e), "danger")
        return render_template(request, "summarizer/comparison.html", {"form": {"title": title, "text": text}, "user": user})

    # Run both methods concurrently in threads
    async with anyio.create_task_group() as tg:
        hybrid_res = {}
        trad_res = {}

        async def run_hybrid():
            nonlocal hybrid_res
            hybrid_res = await anyio.to_thread.run_sync(
                lambda: predict_and_summarize(text=text, title=title, compression_ratio=compression_ratio, stream=False)
            )

        async def run_trad():
            nonlocal trad_res
            trad_res = await anyio.to_thread.run_sync(
                lambda: summarize_traditional(text=text, title=title, compression_ratio=compression_ratio, stream=False)
            )

        tg.start_soon(run_hybrid)
        tg.start_soon(run_trad)

    return render_template(
        request,
        "summarizer/comparison.html",
        {
            "title": title,
            "text": text,
            "hybrid_result": hybrid_res,
            "traditional_result": trad_res,
            "compression_ratio": compression_ratio,
            "user": user
        }
    )

@router.get("/export/{pk}")
def export_summary(
    pk: int,
    format: str = Query("txt"),
    user: User = Depends(require_current_user),
    session: Session = Depends(get_session)
):
    summary_obj = session.get(Summary, pk)
    if not summary_obj or summary_obj.user_id != user.id:
        return JSONResponse({"error": "Summary not found"}, status_code=404)

    if format == "json":
        data = {
            "title": summary_obj.title,
            "original_text": summary_obj.original_text,
            "summary_text": summary_obj.summary_text,
            "method": summary_obj.method,
            "compression_ratio": summary_obj.compression_ratio,
            "created_at": summary_obj.created_at.isoformat(),
            "entities": summary_obj.entities
        }
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="summary_{pk}.json"'}
        )

    # Default TXT export format
    content = f"TITLE: {summary_obj.title}\n"
    content += f"METHOD: {summary_obj.method}\n"
    content += f"DATE: {summary_obj.created_at}\n\n"
    content += f"SUMMARY:\n{summary_obj.summary_text}\n\n"
    content += f"ORIGINAL TEXT:\n{summary_obj.original_text}\n"

    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="summary_{pk}.txt"'}
    )

@router.post("/add-to-dataset/{pk}")
def add_to_dataset_endpoint(
    pk: int,
    user: User = Depends(require_current_user),
    session: Session = Depends(get_session)
):
    summary_obj = session.get(Summary, pk)
    if not summary_obj or summary_obj.user_id != user.id:
        return JSONResponse({"success": False, "error": "Summary not found"}, status_code=404)

    if summary_obj.added_to_dataset:
        return JSONResponse({"success": False, "error": "Summary already added to dataset."})

    try:
        add_to_indosum_dataset(summary_obj.title, summary_obj.original_text, summary_obj.summary_text)
        summary_obj.added_to_dataset = True
        session.add(summary_obj)
        session.commit()
        return JSONResponse({"success": True, "message": "Added to Indosum dataset successfully!"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@router.get("/download-template")
def download_template():
    content = (
        "TITLE=Sample Document Title Here\n"
        "TEXT=Paste your full document text here after the TEXT= marker. "
        "The system will automatically extract the title and text for summarization."
    )
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": 'attachment; filename="indogist_template.txt"'}
    )

@router.get("/task-status/{task_id}")
def task_status(task_id: str):
    return JSONResponse({"task_id": task_id, "status": "completed"})
