import base64
import os
import json
import re
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _, gettext_lazy as _lazy
from django_q.tasks import async_task, fetch
from config import settings
from ml.summarization.utils import add_to_indosum_dataset

from .models import Summary
from .forms import SummaryForm

from ml.summarization.hybrid import predict_and_summarize
from ml.summarization.traditional import summarize_traditional


def home(request):
    """Home page logic."""
    context = {}
    if request.user.is_authenticated:
        recent_summaries = Summary.objects.filter(user=request.user).order_by(
            "-created_at"
        )[:5]
        context["recent_summaries"] = recent_summaries
    return render(request, "summarizer/home.html", context)


def _parse_uploaded_file(uploaded_file):
    """Helper: Parse uploaded text file with template format."""
    try:
        content = uploaded_file.read().decode("utf-8")
        lines = content.split("\n")

        title = ""
        text = ""
        capture_text = False

        for i, line in enumerate(lines):
            if line.strip().startswith("TITLE="):
                title_on_line = line.split("TITLE=", 1)[1].strip()
                if title_on_line:
                    title = title_on_line
                else:
                    for next_line in lines[i + 1 :]:
                        if next_line.strip() and not next_line.strip().startswith(
                            "TEXT="
                        ):
                            title = next_line.strip()
                            break
            elif line.strip().startswith("TEXT="):
                text_on_line = line.split("TEXT=", 1)[1].strip()
                if text_on_line:
                    text = text_on_line + "\n"
                capture_text = True
                continue
            elif capture_text:
                text += line + "\n"

        text = text.strip()
        if not title or not text:
            raise ValueError(
                "File format invalid. Please ensure:\n"
                "1. TITLE= is present with a title\n"
                "2. TEXT= is present with text content\n"
                "Use the official template."
            )

        return title, text

    except UnicodeDecodeError:
        raise ValueError(
            "Unable to read file. Please ensure it's a valid UTF-8 text file."
        )


def _is_template_file(uploaded_file):
    """Check if uploaded file follows the template format."""
    try:
        content = uploaded_file.read().decode("utf-8")
        uploaded_file.seek(0)
        has_title_marker = "TITLE=" in content
        has_text_marker = "TEXT=" in content
        return has_title_marker and has_text_marker
    except Exception:
        return False


def _validate_input_edge_cases(title, original_text, uploaded_file):
    """
    Validate input edge cases before processing.

    Edge Cases:
    1. No title, no text, no file → FAIL
    2. Title only, no text, no file → FAIL
    3. Text only, no title, no file → PROCEED (ML will generate title)
    4. No title, no text, file uploaded (not template) → FAIL
    5. No title, no text, file uploaded (is template) → PROCEED

    Returns:
        tuple: (is_valid, error_message)
    """
    has_title = bool(title and title.strip())
    has_text = bool(original_text and original_text.strip())
    has_file = bool(uploaded_file)

    if not has_title and not has_text and not has_file:
        return (
            False,
            _lazy(
                "Please provide content to summarize. You must either:\n• Enter a title and text manually, OR\n• Upload a file using the template format"
            ),
        )

    if has_title and not has_text and not has_file:
        return (
            False,
            _lazy(
                "Title provided but no text content found. Please either:\n• Enter text in the 'Original Text' field, OR\n• Upload a file using the template format"
            ),
        )

    if not has_title and has_text and not has_file:
        return True, None

    if not has_title and not has_text and has_file:
        if not _is_template_file(uploaded_file):
            return (
                False,
                _lazy(
                    "Uploaded file does not follow the template format. Please:\n• Download the template file\n• Fill it with TITLE= and TEXT= markers\n• Upload the completed template"
                ),
            )
        return True, None

    return True, None


def _validate_text_content(text, min_words=10):
    """Validate that text has sufficient content for summarization."""
    if not text or not text.strip():
        raise ValueError(_lazy("Text content is empty."))
    words = text.split()
    word_count = len(words)
    if word_count < min_words:
        raise ValueError(
            _lazy(
                "Text is too short for summarization. "
                f"Please provide at least {min_words} words (currently: {word_count} words)."
            )
        )
    meaningful_words = [w for w in words if len(w) > 2]
    if len(meaningful_words) < min_words // 2:
        raise ValueError(
            _lazy(
                "Text contains insufficient meaningful content. "
                "Please provide more substantial text for summarization."
            )
        )
    return True


def _parse_and_validate_form(request):
    """
    Shared helper: parse, validate, and return cleaned form data.
    Returns (form_data_dict, error_response_or_None).
    error_response is a JsonResponse if there's an error, else None.
    """
    raw_title = request.POST.get("title", "").strip()
    raw_text = request.POST.get("original_text", "").strip()
    uploaded_file = request.FILES.get("file", None)

    is_valid, error_message = _validate_input_edge_cases(
        title=raw_title, original_text=raw_text, uploaded_file=uploaded_file
    )
    if not is_valid:
        return None, JsonResponse(
            {"success": False, "error": error_message}, status=400
        )

    post_data = request.POST.copy()
    if uploaded_file:
        try:
            file_title, file_text = _parse_uploaded_file(uploaded_file)
            post_data.update({"title": file_title, "original_text": file_text})
        except ValueError as e:
            return None, JsonResponse({"success": False, "error": str(e)}, status=400)

    form = SummaryForm(post_data, request.FILES)
    if not form.is_valid():
        error_messages = []
        for field, errors in form.errors.items():
            for error in errors:
                if field == "__all__":
                    error_messages.append(error)
                else:
                    field_name = (
                        form.fields[field].label if field in form.fields else field
                    )
                    error_messages.append(f"{field_name}: {error}")
        return None, JsonResponse(
            {"success": False, "error": " | ".join(error_messages)}, status=400
        )

    data = form.cleaned_data
    try:
        _validate_text_content(data["original_text"])
    except ValueError as e:
        return None, JsonResponse({"success": False, "error": str(e)}, status=400)

    return data, None


def summarize_view(request):
    """
    Main summarization view.
    - GET:  renders the form.
    - AJAX POST:  validates, then returns an SSE StreamingHttpResponse with
                  real-time step progress events.
    - Normal POST: legacy full-page form submission (non-JS fallback).
    """
    form = SummaryForm()

    if request.method != "POST":
        return render(request, "summarizer/summarize.html", {"form": form})

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # ── Validate input ────────────────────────────────────────────
    data, err = _parse_and_validate_form(request)
    if err:
        if is_ajax:
            return err  # already a JsonResponse
        messages.error(request, _lazy("Validation failed."))
        return render(request, "summarizer/summarize.html", {"form": form})

    try:
        _validate_text_content(data["original_text"])
    except ValueError as e:
        error_msg = str(e)
        if is_ajax:
            return JsonResponse({"success": False, "error": error_msg}, status=400)
        messages.error(request, error_msg)
        return render(request, "summarizer/summarize.html", {"form": form})

    # ── AJAX path → SSE streaming ─────────────────────────────────
    if is_ajax:
        return _summarize_sse(request, data)

    # ── Non-AJAX legacy form path ─────────────────────────────────
    try:
        if data["method"] == "hybrid":
            result = predict_and_summarize(
                text=data["original_text"],
                title=data["title"],
                compression_ratio=data["compression_ratio"],
            )
            entities = result.get("entities", [])
        else:
            result = summarize_traditional(
                text=data["original_text"],
                title=data["title"],
                compression_ratio=data["compression_ratio"],
                stream=False,
            )
            entities = []

        summary_text = result["summary"]
        effective_title = result.get("effective_title", data["title"])
        final_title = data["title"] if data["title"] else effective_title

        summary_id = None
        if request.user.is_authenticated:
            summary_obj = Summary.objects.create(
                user=request.user,
                title=final_title,
                original_text=data["original_text"],
                summary_text=summary_text,
                compression_ratio=data["compression_ratio"],
                entities=entities,
                method=data["method"],
            )
            summary_id = summary_obj.id

        messages.success(request, _lazy("✓ Summary generated successfully!"))
        return render(
            request,
            "summarizer/summarize.html",
            {
                "form": form,
                "result": {
                    "summary": summary_text,
                    "entities": entities,
                    "id": summary_id,
                    "title": final_title,
                },
            },
        )

    except Exception as e:
        error_msg = _lazy("Failed to generate summary: {error}").format(error=str(e))
        print(f"[ERROR] summarize_view: {e}")
        messages.error(request, error_msg)
        return render(request, "summarizer/summarize.html", {"form": form})


def _summarize_sse(request, data):
    task_data = {
        "method": data["method"],
        "original_text": data["original_text"],
        "title": data["title"],
        "compression_ratio": data["compression_ratio"],
        "user_id": request.user.id if request.user.is_authenticated else None,
    }
    task_id = async_task(
        "apps.summarizer.tasks.run_summarization",
        task_data,
    )

    def generate():
        step = 0
        while True:
            task = fetch(task_id)
            if task is None:
                import time

                time.sleep(1)
                continue

            if task.success:
                result = task.result
                if isinstance(result, dict) and result.get("success"):
                    if step < 3:
                        for s in range(step + 1, 4):
                            yield f"data: {json.dumps({'step': s})}\n\n"
                    yield f"data: {json.dumps(result)}\n\n"
                else:
                    error_msg = (
                        result.get("error", "Unknown error")
                        if isinstance(result, dict)
                        else str(result)
                    )
                    yield f"data: {json.dumps({'error': error_msg})}\n\n"
                break
            elif task.has_ended() and not task.success:
                yield f"data: {json.dumps({'error': str(task.result or 'Task failed')})}\n\n"
                break
            else:
                progress = task.progress() if hasattr(task, "progress") else {}
                if isinstance(progress, dict) and progress.get("step", 0) > step:
                    step = progress["step"]
                    yield f"data: {json.dumps({'step': step})}\n\n"
                import time

                time.sleep(1)

    response = StreamingHttpResponse(generate(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def task_status(request, task_id):
    task = fetch(task_id)
    if task is None:
        return JsonResponse({"status": "not_found"}, status=404)

    if task.has_ended():
        if task.success:
            return JsonResponse({"status": "done", "result": task.result})
        else:
            return JsonResponse(
                {"status": "error", "error": str(task.result or "Task failed")}
            )

    progress = task.progress() if hasattr(task, "progress") else {}
    return JsonResponse({"status": "running", "progress": progress})


@login_required
def summary_detail(request, pk):
    """Detail view for a single summary"""
    summary = get_object_or_404(Summary, pk=pk, user=request.user)

    entities_list = []
    if summary.entities and isinstance(summary.entities, list):
        for entity in summary.entities:
            if isinstance(entity, dict) and "confidence" in entity:
                entity["confidence_percent"] = f"{entity['confidence'] * 100:.0f}"
                entities_list.append(entity)

    context = {
        "summary": summary,
        "compression_display": f"{summary.compression_ratio * 100} %",
        "entities_list": entities_list,
        "entities_json": mark_safe(json.dumps(entities_list)),
        "actual_compression": summary.actual_compression * 100
        if summary.actual_compression
        else 0,
    }
    return render(request, "summarizer/summary_detail.html", context)


@login_required
def history(request):
    """View all summaries with search and filtering"""
    search_query = request.GET.get("q", "")
    method_filter = request.GET.get("method", "")
    sort_by = request.GET.get("sort", "-created_at")

    summaries = Summary.objects.filter(user=request.user)

    if search_query:
        summaries = summaries.filter(
            Q(title__icontains=search_query)
            | Q(original_text__icontains=search_query)
            | Q(summary_text__icontains=search_query)
        )

    if method_filter:
        summaries = summaries.filter(method=method_filter)

    if sort_by:
        summaries = summaries.order_by(sort_by)

    paginator = Paginator(summaries, 5)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "search_query": search_query,
        "method_filter": method_filter,
        "sort_by": sort_by,
    }
    return render(request, "summarizer/history.html", context)


@login_required
def charts_view(request):
    """Display model metrics from static files"""
    base_path = os.path.join(
        settings.BASE_DIR, "ml", "models", "ner2_tuningHYPERBAND_FINAL"
    )

    context = {
        "chart_image": None,
        "classification_report": [],
        "experiment_metrics": None,
        "file_error": None,
    }

    try:
        img_path = os.path.join(base_path, "training_history.png")
        if os.path.exists(img_path):
            with open(img_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
                context["chart_image"] = f"data:image/png;base64,{encoded_string}"

        report_path = os.path.join(base_path, "classification_report.txt")
        report_data = []
        if os.path.exists(report_path):
            with open(report_path, "r") as f:
                lines = f.readlines()
                for line in lines[2:]:
                    parts = line.split()
                    if not parts:
                        continue

                    if parts[0] == "accuracy":
                        report_data.append(
                            {
                                "label": "accuracy",
                                "precision": "",
                                "recall": "",
                                "f1": parts[1],
                                "support": parts[2] if len(parts) > 2 else "",
                            }
                        )
                    elif len(parts) >= 5:
                        if parts[1] == "avg":
                            label = f"{parts[0]} {parts[1]}"
                            scores = parts[2:]
                        else:
                            label = parts[0]
                            scores = parts[1:]
                        report_data.append(
                            {
                                "label": label,
                                "precision": scores[0],
                                "recall": scores[1],
                                "f1": scores[2],
                                "support": scores[3],
                            }
                        )
            context["classification_report"] = report_data

        json_path = os.path.join(base_path, "experiment_results.json")
        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                data = json.load(f)
                config = data.get("config", {})

                context["experiment_metrics"] = {
                    "Architecture": {
                        "Embedding Dim": config.get("embed_dim"),
                        "LSTM Units": config.get("lstm_units"),
                        "Layers": config.get("num_lstm_layers"),
                        "Dropout": config.get("dropout"),
                    },
                    "Training": {
                        "Epochs": config.get("epochs"),
                        "Batch Size": config.get("batch_size"),
                        "Patience": config.get("patience"),
                        "Learning Rate": config.get("learning_rate"),
                    },
                    "Performance": {
                        "Accuracy": f"{data.get('metrics', {}).get('accuracy', 0):.4f}",
                        "Timestamp": data.get("timestamp")[:10],
                    },
                }

    except Exception as e:
        context["file_error"] = str(e)

    return render(request, "summarizer/charts.html", context)


def comparison_view(request):
    """Compare traditional vs hybrid methods"""
    if request.method == "POST":
        text = request.POST.get("text", "").strip()
        title = request.POST.get("title", "").strip()
        try:
            compression_ratio = float(request.POST.get("compression_ratio", 0.3))
        except ValueError:
            compression_ratio = 0.3

        if not text:
            error_msg = _lazy("Please provide text for comparison")
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": error_msg}, status=400)
            messages.error(request, error_msg)
            return render(request, "summarizer/comparison.html")

        try:
            traditional_result = summarize_traditional(
                text=text,
                title=title,
                compression_ratio=compression_ratio,
                stream=False,
            )
            traditional_summary = traditional_result["summary"]
            final_title = (
                title
                if title
                else traditional_result.get("effective_title", "Untitled Comparison")
            )

            hybrid_result = predict_and_summarize(
                text=text, title=title, compression_ratio=compression_ratio
            )

            response_data = {
                "success": True,
                "title": final_title,
                "traditional": traditional_summary,
                "hybrid": hybrid_result["summary"],
                "traditional_words": len(traditional_summary.split()),
                "hybrid_words": len(hybrid_result["summary"].split()),
                "original_words": len(text.split()),
            }

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(response_data)

            return render(request, "summarizer/comparison.html", response_data)

        except Exception as e:
            error_msg = _lazy("Comparison failed: {error}").format(error=str(e))
            print(f"[ERROR] comparison_view: {e}")

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": error_msg}, status=500)
            messages.error(request, error_msg)

    return render(request, "summarizer/comparison.html")


@login_required
@require_http_methods(["POST"])
def add_to_dataset(request, pk):
    """Add summary to training dataset"""
    summary = get_object_or_404(Summary, pk=pk, user=request.user)

    if summary.added_to_dataset:
        return JsonResponse(
            {
                "success": False,
                "error": _lazy("This summary has already been added to the dataset"),
            },
            status=400,
        )

    try:
        add_to_indosum_dataset(
            title=summary.title,
            text=summary.original_text,
            summary=summary.summary_text,
            user=request.user.username,
        )

        summary.added_to_dataset = True
        summary.save()

        return JsonResponse(
            {"success": True, "message": _lazy("Successfully added to dataset!")}
        )

    except Exception as e:
        print(f"ERROR in add_to_dataset: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
def export_summary(request, pk):
    """Export summary as text file"""
    summary = get_object_or_404(Summary, pk=pk, user=request.user)

    response = HttpResponse(content_type="text/plain; charset=utf-8")
    filename = f"summary_{summary.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    content = f"""TITLE: {summary.title}

SUMMARY:
{summary.summary_text}

ORIGINAL TEXT:
{summary.original_text}
"""
    response.write(content)
    return response


def download_template(request):
    """Download template file for text upload"""
    response = HttpResponse(content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="summarizer_template.txt"'

    template = """IMPORTANT INSTRUCTIONS:
1. Do not remove the 'TITLE=' and 'TEXT=' lines
2. Write your title on the line after 'TITLE='
3. Write your entire text content on the lines after 'TEXT='

TITLE=
Kebijakan Ekonomi Digital Indonesia

TEXT=
Pemerintah Indonesia mengumumkan kebijakan baru untuk meningkatkan ekonomi digital di seluruh negeri. Program ini akan fokus pada tiga pilar utama: pengembangan infrastruktur internet berkecepatan tinggi, pelatihan sumber daya manusia di bidang teknologi informasi, dan pemberian insentif untuk startup lokal. 

Menteri Komunikasi dan Informatika menyatakan bahwa program ini diharapkan dapat menciptakan setidaknya satu juta lapangan kerja baru dalam lima tahun ke depan. Investasi pemerintah untuk program ini mencapai 50 triliun rupiah, dengan harapan dapat meningkatkan daya saing ekonomi Indonesia di kancah global.
"""
    response.write(template)
    return response
