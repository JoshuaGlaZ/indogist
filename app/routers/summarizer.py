import asyncio
import hashlib
import json
import os
from datetime import datetime
from functools import lru_cache

from cachetools import TTLCache
from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlmodel import Session, asc, desc, func, or_, select

from app.auth import add_flash_message, get_current_user
from app.config import settings
from app.database import get_session
from app.i18n import lang
from app.models import Summary, User
from app.schemas import (
    parse_uploaded_file_content,
    validate_input_edge_cases,
    validate_text_content,
)
from ml.summarization.hybrid import predict_and_summarize
from ml.summarization.traditional import summarize_traditional
from ml.summarization.utils import add_to_indosum_dataset

router = APIRouter(tags=["summarizer"])


limiter = Limiter(
    key_func=get_remote_address,
    enabled=os.getenv("TESTING", "False").lower() not in ("true", "1"),
)


SUMMARY_CACHE = TTLCache(maxsize=256, ttl=3600)


def render_template(request: Request, name: str, context: dict | None = None):
    return request.app.state.render_template(request, name, context)


@router.get("/", response_class=HTMLResponse)
def home_get(
    request: Request,
    user: User | None = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    recent_summaries = []
    if user:
        statement = (
            select(Summary)
            .where(Summary.user_id == user.id)
            .order_by(desc(Summary.created_at))
            .limit(5)
        )
        recent_summaries = session.exec(statement).all()
    return render_template(
        request,
        "summarizer/home.html",
        {"recent_summaries": recent_summaries, "user": user},
    )


@router.get("/summarize/", response_class=HTMLResponse)
def summarize_get(request: Request, user: User | None = Depends(get_current_user)):
    return render_template(request, "summarizer/summarize.html", {"form": {}, "user": user})


@router.post("/summarize/")
@limiter.limit("10/minute")
async def summarize_post(
    request: Request,
    title: str | None = Form(""),
    original_text: str | None = Form(""),
    text: str | None = Form(""),
    compression_ratio: float = Form(0.3),
    method: str = Form("hybrid"),
    hybrid_variant: str = Form("pos_ner"),
    traditional_variant: str = Form("sentence_rank"),
    file: UploadFile | None = File(None),
    user: User | None = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    is_ajax = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.headers.get("HX-Request") == "true"
    )
    raw_input = original_text or text or ""

    file_content_str = None
    if file and file.filename:
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        content_bytes = await file.read()
        if len(content_bytes) > max_bytes:
            err_msg = lang(
                request,
                f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB.",
            )
            if is_ajax:
                return JSONResponse({"success": False, "error": err_msg}, status_code=413)
            add_flash_message(request, err_msg, "danger")
            return render_template(request, "summarizer/summarize.html", {"user": user})
        try:
            file_content_str = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            err_msg = lang(
                request,
                "Unable to read file. Please ensure it is a valid UTF-8 text file.",
            )

            if is_ajax:
                return JSONResponse({"success": False, "error": err_msg}, status_code=400)
            add_flash_message(request, err_msg, "danger")
            return render_template(request, "summarizer/summarize.html", {"user": user})

    is_valid, err_msg = validate_input_edge_cases(
        title=title or "",
        text=raw_input,
        has_file=bool(file and file.filename),
        file_content=file_content_str,
        request=request,
    )
    if not is_valid:
        if is_ajax:
            return HTMLResponse(
                f'<div class="alert alert-danger mb-0">{err_msg}</div>', status_code=400
            )
        add_flash_message(request, err_msg, "danger")
        return render_template(request, "summarizer/summarize.html", {"user": user})

    final_title = title or ""
    final_text = raw_input

    if file and file.filename and file_content_str:
        try:
            parsed_title, parsed_text = parse_uploaded_file_content(
                file_content_str, request=request
            )
            final_title = parsed_title
            final_text = parsed_text
        except ValueError as e:
            if is_ajax:
                return HTMLResponse(
                    f'<div class="alert alert-danger mb-0">{e!s}</div>',
                    status_code=400,
                )
            add_flash_message(request, str(e), "danger")
            return render_template(
                request,
                "summarizer/summarize.html",
                {
                    "form": {"title": title or "", "original_text": raw_input},
                    "user": user,
                },
            )

    try:
        validate_text_content(final_text, request=request)
    except ValueError as e:
        if is_ajax:
            return HTMLResponse(
                f'<div class="alert alert-danger mb-0">{e!s}</div>', status_code=400
            )

    variant_key = hybrid_variant if method == "hybrid" else traditional_variant
    cache_key = hashlib.sha256(
        f"{final_text}:{method}:{variant_key}:{compression_ratio}".encode()
    ).hexdigest()
    entities_list = []
    pos_tokens = []
    if cache_key in SUMMARY_CACHE:
        cached = SUMMARY_CACHE[cache_key]
        summary_result = cached["summary"]
        entities_list = cached.get("entities", [])
        pos_tokens = cached.get("pos_tokens", [])
    else:
        if method == "traditional":
            res = await asyncio.to_thread(
                summarize_traditional,
                final_text,
                title=final_title,
                compression_ratio=compression_ratio,
                stream=False,
            )
            if isinstance(res, dict):
                summary_result = res.get("summary", "")
                entities_list = res.get("entities", [])
                pos_tokens = res.get("pos_tokens", [])
            else:
                summary_result = res
        else:
            res = await asyncio.to_thread(
                predict_and_summarize,
                final_text,
                title=final_title,
                compression_ratio=compression_ratio,
            )
            if isinstance(res, dict):
                summary_result = res.get("summary", "")
                entities_list = res.get("entities", [])
                pos_tokens = res.get("pos_tokens", [])
            else:
                summary_result = res

        SUMMARY_CACHE[cache_key] = {
            "summary": summary_result,
            "entities": entities_list,
            "pos_tokens": pos_tokens,
        }

    if user:
        summary_obj = Summary(
            user_id=user.id,
            title=final_title or final_text[:50],
            original_text=final_text,
            summary_text=summary_result,
            method=method,
            compression_ratio=compression_ratio,
            created_at=datetime.utcnow(),
            word_count_original=len(final_text.split()),
            word_count_summary=len(summary_result.split()),
            entities_json=json.dumps(entities_list) if entities_list else "[]",
        )
        session.add(summary_obj)
        session.commit()
        session.refresh(summary_obj)

    if is_ajax:
        # Determine capabilities based on method + variant
        has_ner = method == "hybrid"
        has_pos = method == "hybrid" and variant_key in (
            "tfidf_ner_pos",
            "tfidf_ner_pos_crf",
        )

        # Zero-out data that this method/variant doesn't provide
        ner_data = entities_list if has_ner else []
        pos_data = pos_tokens if has_pos else []

        # Build entity chips (only if method provides NER)
        if has_ner and ner_data:
            chips = []
            for ent in ner_data:
                conf_val = float(
                    ent.get(
                        "confidence",
                        ent.get("confidence_percent", ent.get("score", 0.9)),
                    )
                )
                score = round(conf_val * 100) if conf_val <= 1.0 else round(conf_val)
                text = ent.get("text", "")
                label = ent.get("label", "ENTITY")
                chips.append(
                    f'<span class="entity-chip show"><span>{text}</span><span class="e-type">{label}</span><span class="e-score">{score}%</span></span>'
                )
            entity_chips_html = "".join(chips)
        elif has_ner:
            entity_chips_html = f'<span class="output-placeholder">{lang(request, "No named entities detected in this text.")}</span>'
        else:
            entity_chips_html = f'<span class="output-placeholder">{lang(request, "This method does not perform entity detection.")}</span>'

        # Build NER + POS data as JSON for client-side rendering
        import json as _json

        entities_json = (
            _json.dumps(
                [{"text": e.get("text", ""), "label": e.get("label", "ENTITY")} for e in ner_data]
            )
            if ner_data
            else "[]"
        )
        pos_json = _json.dumps(pos_data) if pos_data else "[]"

        summary_html = summary_result.strip()

        # Build dynamic toggle bar via OOB swap
        toggle_btns = (
            '<button type="button" class="btn btn-ghost active" style="padding:2px 8px;font-size:11.5px;" onclick="switchOutputMode(this,\'outputArea\',\'plain\')">'
            + lang(request, "Plain")
            + "</button>"
        )
        if has_ner:
            toggle_btns += (
                '<button type="button" class="btn btn-ghost" style="padding:2px 8px;font-size:11.5px;" onclick="switchOutputMode(this,\'outputArea\',\'ner\')">'
                + lang(request, "NER Highlights")
                + "</button>"
            )
        if has_pos:
            toggle_btns += (
                '<button type="button" class="btn btn-ghost" style="padding:2px 8px;font-size:11.5px;" onclick="switchOutputMode(this,\'outputArea\',\'pos\')">'
                + lang(request, "POS Tagging")
                + "</button>"
            )

        return HTMLResponse(
            f"{summary_html}"
            f'<div id="entityWrap" hx-swap-oob="true">{entity_chips_html}</div>'
            f'<div id="viewModeToggle" hx-swap-oob="true" class="view-mode-toggle" style="display:flex;gap:4px;">{toggle_btns}</div>'
            f'<div id="entitySection" hx-swap-oob="true" class="entity-section" style="display:{"block" if has_ner else "none"}">'
            f'<p class="field-label" style="margin-bottom:0;">{lang(request, "Detected entities")}</p>'
            f'<div class="entity-wrap" id="entityWrap">{entity_chips_html}</div></div>'
            f"<script>window.__nerEntities={entities_json};window.__posData={pos_json};window.__posActiveFilters=null;"
            f"window.__hasNer={'true' if has_ner else 'false'};window.__hasPos={'true' if has_pos else 'false'};"
            f'if(window.OUTPUT_TEXT_CACHE)delete window.OUTPUT_TEXT_CACHE["outputArea"];</script>'
        )

    context = {
        "summary": {"summary_text": summary_result},
        "entities_list": entities_list,
        "user": user,
    }
    return render_template(request, "summarizer/summarize.html", context)


@router.get("/history/", response_class=HTMLResponse)
def history_get(
    request: Request,
    q: str | None = Query(""),
    method: str | None = Query(""),
    sort: str | None = Query("-created_at"),
    page: int = Query(1, ge=1),
    user: User | None = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    PAGE_SIZE = 10
    is_ajax = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.headers.get("HX-Request") == "true"
    )
    summaries = []
    total_count = 0
    if user:
        statement = select(Summary).where(Summary.user_id == user.id)
        if q:
            statement = statement.where(
                or_(Summary.title.contains(q), Summary.summary_text.contains(q))
            )
        if method:
            statement = statement.where(Summary.method == method)

        count_stmt = select(func.count(Summary.id)).where(Summary.user_id == user.id)
        if q:
            count_stmt = count_stmt.where(
                or_(Summary.title.contains(q), Summary.summary_text.contains(q))
            )
        if method:
            count_stmt = count_stmt.where(Summary.method == method)
        total_count = session.exec(count_stmt).one()

        if sort == "created_at":
            statement = statement.order_by(asc(Summary.created_at))
        elif sort == "title":
            statement = statement.order_by(asc(Summary.title))
        else:
            statement = statement.order_by(desc(Summary.created_at))

        statement = statement.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
        summaries = session.exec(statement).all()

    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)

    context = {
        "summaries": summaries,
        "search_query": q,
        "method_filter": method,
        "sort_by": sort,
        "user": user,
        "current_page": page,
        "total_pages": total_pages,
        "total_count": total_count,
    }

    if is_ajax:
        return render_template(request, "summarizer/history_list.html", context)

    return render_template(request, "summarizer/history.html", context)


@lru_cache(maxsize=1)
def _load_chart_metrics_cache():
    import base64
    from pathlib import Path

    models_dir = Path(__file__).resolve().parent.parent.parent / "ml" / "models"
    chart_image_b64 = ""
    for img_name in [
        "training_history.png",
        "training_metrics.png",
        "entity_f1_metrics.png",
    ]:
        found_imgs = list(models_dir.glob(f"**/{img_name}"))
        if found_imgs:
            try:
                with open(found_imgs[0], "rb") as f:
                    chart_image_b64 = base64.b64encode(f.read()).decode("utf-8")
                break
            except Exception:
                pass
    if not chart_image_b64:
        chart_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    report_table = []
    report_files = list(models_dir.glob("**/classification_report.txt"))
    if report_files:
        try:
            with open(report_files[0]) as f:
                lines = f.readlines()
            for line in lines[2:]:
                parts = line.strip().split()
                if len(parts) == 5:
                    report_table.append(
                        {
                            "class": parts[0],
                            "precision": parts[1],
                            "recall": parts[2],
                            "f1-score": parts[3],
                            "support": parts[4],
                        }
                    )
                elif len(parts) == 6 and parts[0] in ("macro", "weighted"):
                    report_table.append(
                        {
                            "class": f"{parts[0]} {parts[1]}",
                            "precision": parts[2],
                            "recall": parts[3],
                            "f1-score": parts[4],
                            "support": parts[5],
                        }
                    )
        except Exception:
            pass

    if not report_table:
        report_table = [
            {
                "class": "B-LOC",
                "precision": "0.74",
                "recall": "0.86",
                "f1-score": "0.80",
                "support": "103",
            },
            {
                "class": "B-ORG",
                "precision": "0.91",
                "recall": "0.81",
                "f1-score": "0.86",
                "support": "401",
            },
            {
                "class": "B-PER",
                "precision": "0.94",
                "recall": "0.50",
                "f1-score": "0.65",
                "support": "515",
            },
            {
                "class": "I-LOC",
                "precision": "0.53",
                "recall": "0.74",
                "f1-score": "0.62",
                "support": "82",
            },
            {
                "class": "I-ORG",
                "precision": "0.60",
                "recall": "0.81",
                "f1-score": "0.69",
                "support": "247",
            },
            {
                "class": "I-PER",
                "precision": "0.82",
                "recall": "0.58",
                "f1-score": "0.68",
                "support": "222",
            },
            {
                "class": "weighted avg",
                "precision": "0.94",
                "recall": "0.94",
                "f1-score": "0.93",
                "support": "10588",
            },
        ]

    return chart_image_b64, report_table


@router.get("/charts/", response_class=HTMLResponse)
def charts_get(request: Request, user: User | None = Depends(get_current_user)):
    chart_image_b64, report_table = _load_chart_metrics_cache()
    return render_template(
        request,
        "summarizer/charts.html",
        {"user": user, "chart_image": chart_image_b64, "report_table": report_table},
    )


@router.get("/comparison/", response_class=HTMLResponse)
@router.post("/comparison/", response_class=HTMLResponse)
async def comparison(
    request: Request,
    text: str | None = Form(""),
    model_a: str | None = Form("traditional"),
    model_b: str | None = Form("hybrid"),
    user: User | None = Depends(get_current_user),
):
    is_ajax = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.headers.get("HX-Request") == "true"
    )
    summary_a = ""
    summary_b = ""
    if text:

        def _run_model(model_name: str):
            if model_name == "traditional":
                res = summarize_traditional(text, title="", compression_ratio=0.3, stream=False)
                return res.get("summary", "") if isinstance(res, dict) else res
            else:
                res = predict_and_summarize(text, title="", compression_ratio=0.3)
                return res.get("summary", "") if isinstance(res, dict) else res

        res_a_task = asyncio.to_thread(_run_model, model_a)
        res_b_task = asyncio.to_thread(_run_model, model_b)
        summary_a, summary_b = await asyncio.gather(res_a_task, res_b_task)

    context = {
        "source_text": text,
        "traditional_summary": summary_a,
        "hybrid_summary": summary_b,
        "model_a": model_a,
        "model_b": model_b,
        "user": user,
    }

    if is_ajax and text:
        has_ner_a = model_a == "hybrid"
        has_pos_a = model_a == "hybrid"
        has_ner_b = model_b == "hybrid"
        has_pos_b = model_b == "hybrid"

        def _t(msg):
            return lang(request, msg)

        toggle_a = (
            '<button type="button" class="btn btn-ghost active" style="padding:2px 8px;font-size:11.5px;" onclick="switchOutputMode(this,\'compareOutputA\',\'plain\')">'
            + _t("Plain")
            + "</button>"
        )
        if has_ner_a:
            toggle_a += (
                '<button type="button" class="btn btn-ghost" style="padding:2px 8px;font-size:11.5px;" onclick="switchOutputMode(this,\'compareOutputA\',\'ner\')">'
                + _t("NER Highlights")
                + "</button>"
            )
        if has_pos_a:
            toggle_a += (
                '<button type="button" class="btn btn-ghost" style="padding:2px 8px;font-size:11.5px;" onclick="switchOutputMode(this,\'compareOutputA\',\'pos\')">'
                + _t("POS Tagging")
                + "</button>"
            )

        toggle_b = (
            '<button type="button" class="btn btn-ghost active" style="padding:2px 8px;font-size:11.5px;" onclick="switchOutputMode(this,\'compareOutputB\',\'plain\')">'
            + _t("Plain")
            + "</button>"
        )
        if has_ner_b:
            toggle_b += (
                '<button type="button" class="btn btn-ghost" style="padding:2px 8px;font-size:11.5px;" onclick="switchOutputMode(this,\'compareOutputB\',\'ner\')">'
                + _t("NER Highlights")
                + "</button>"
            )
        if has_pos_b:
            toggle_b += (
                '<button type="button" class="btn btn-ghost" style="padding:2px 8px;font-size:11.5px;" onclick="switchOutputMode(this,\'compareOutputB\',\'pos\')">'
                + _t("POS Tagging")
                + "</button>"
            )

        lbl_output = _t("Output View")
        lbl_words = _t("Words")
        lbl_sentences = _t("Sentences")

        return HTMLResponse(f"""
        <div class="card">
          <div class="card-head">
            <p class="card-title">{_t("Model A")} ({model_a.upper()})</p>
            <span class="badge {model_a}">{model_a}</span>
          </div>
          <div class="card-body">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
              <span class="field-label" style="margin-bottom: 0;">{lbl_output}</span>
              <div class="view-mode-toggle" style="display: flex; gap: 4px;">{toggle_a}</div>
            </div>
            <div class="output-area" id="compareOutputA">{summary_a.strip()}</div>
            <div class="stats-grid" style="margin-top: 12px;">
              <div class="stat-card"><span class="s-label">{lbl_words}</span><span class="s-value">{len(summary_a.split()) if summary_a else 0}</span></div>
              <div class="stat-card accent"><span class="s-label">{lbl_sentences}</span><span class="s-value">{len(summary_a.split(".")) if summary_a else 0}</span></div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-head">
            <p class="card-title">{_t("Model B")} ({model_b.upper()})</p>
            <span class="badge {model_b}">{model_b}</span>
          </div>
          <div class="card-body">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
              <span class="field-label" style="margin-bottom: 0;">{lbl_output}</span>
              <div class="view-mode-toggle" style="display: flex; gap: 4px;">{toggle_b}</div>
            </div>
            <div class="output-area" id="compareOutputB">{summary_b.strip()}</div>
            <div class="stats-grid" style="margin-top: 12px;">
              <div class="stat-card"><span class="s-label">{lbl_words}</span><span class="s-value">{len(summary_b.split()) if summary_b else 0}</span></div>
              <div class="stat-card accent"><span class="s-label">{lbl_sentences}</span><span class="s-value">{len(summary_b.split(".")) if summary_b else 0}</span></div>
            </div>
          </div>
        </div>
        """)

    return render_template(request, "summarizer/comparison.html", context)


@router.get("/summary/{pk}/", response_class=HTMLResponse)
@router.get("/summary/{pk}", response_class=HTMLResponse)
def summary_detail(
    request: Request,
    pk: int,
    user: User | None = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    summary = session.get(Summary, pk)
    if not summary:
        return HTMLResponse(content=lang(request, "Summary not found"), status_code=404)
    if not user or summary.user_id != user.id:
        return HTMLResponse(content=lang(request, "Not authorized"), status_code=403)
    entities_list = summary.entities
    return render_template(
        request,
        "summarizer/summary_detail.html",
        {"summary": summary, "entities_list": entities_list, "user": user},
    )


@router.get("/export/{pk}")
@router.get("/export/{pk}/")
def export_summary(
    request: Request,
    pk: int,
    user: User | None = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    summary = session.get(Summary, pk)
    if not summary:
        return HTMLResponse(content=lang(request, "Summary not found"), status_code=404)
    if not user or summary.user_id != user.id:
        return HTMLResponse(content=lang(request, "Not authorized"), status_code=403)

    content = f"Title: {summary.title}\nDate: {summary.created_at}\nMethod: {summary.method}\n\nSummary:\n{summary.summary_text}\n\nOriginal Text:\n{summary.original_text}"
    headers = {"Content-Disposition": f'attachment; filename="summary_{pk}.txt"'}
    return Response(content=content, media_type="text/plain", headers=headers)


@router.post("/add-to-dataset/")
@router.post("/add-to-dataset")
def add_dataset_post(
    request: Request,
    summary_id: int = Form(...),
    user: User | None = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    summary = session.get(Summary, summary_id)
    if not summary:
        return JSONResponse(
            {"success": False, "error": lang(request, "Summary not found")},
            status_code=404,
        )
    if not user or summary.user_id != user.id:
        return JSONResponse(
            {"success": False, "error": lang(request, "Not authorized")},
            status_code=403,
        )
    username = user.username
    try:
        success = add_to_indosum_dataset(
            summary.title, summary.original_text, summary.summary_text, username
        )
        if success:
            summary.added_to_dataset = True
            session.add(summary)
            session.commit()
            return JSONResponse(
                {
                    "success": True,
                    "message": lang(request, "Added to dataset successfully"),
                }
            )
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
    return JSONResponse(
        {"success": False, "error": lang(request, "Failed to add to dataset")},
        status_code=500,
    )


@router.get("/download-template")
@router.get("/download-template/")
def download_template():
    content = "TITLE=Judul Artikel Berita\n\nTEXT=Teks lengkap artikel berita Bahasa Indonesia yang ingin diringkas...\n"
    headers = {"Content-Disposition": 'attachment; filename="indogist_template.txt"'}
    return Response(content=content, media_type="text/plain", headers=headers)
