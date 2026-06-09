"""
Django signals for decoupled event-driven summarization.
"""

import django.dispatch
from django.db import transaction


summary_requested = django.dispatch.Signal(providing_args=["data", "user", "request"])

summary_completed = django.dispatch.Signal(providing_args=["summary", "result"])


def handle_summary_requested(sender, data, user, request, **kwargs):
    """
    Receiver for summary_requested signal.
    Processes the summarization request and returns the result.
    """
    from ml.summarization.hybrid import predict_and_summarize
    from ml.summarization.traditional import summarize_traditional
    from .models import Summary

    method = data.get("method", "hybrid")
    original_text = data.get("original_text", "")
    title = data.get("title", "")
    compression_ratio = data.get("compression_ratio", 0.3)

    try:
        if method == "hybrid":
            result = predict_and_summarize(
                text=original_text,
                title=title,
                compression_ratio=compression_ratio,
            )
            entities = result.get("entities", [])
        else:
            result = summarize_traditional(
                text=original_text,
                title=title,
                compression_ratio=compression_ratio,
                stream=False,
            )
            entities = []

        summary_text = result.get("summary", "")
        effective_title = result.get("effective_title", title)
        final_title = title if title else effective_title

        summary_obj = None
        if user and user.is_authenticated:
            summary_obj = Summary.objects.create(
                user=user,
                title=final_title,
                original_text=original_text,
                summary_text=summary_text,
                compression_ratio=compression_ratio,
                entities=entities,
                method=method,
            )

        result_data = {
            "summary": summary_text,
            "entities": entities,
            "effective_title": final_title,
            "method": method,
            "success": True,
        }

        summary_completed.send(
            sender=handle_summary_requested,
            summary=summary_obj,
            result=result_data,
        )

        return result_data

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def handle_summary_completed(sender, summary, result, **kwargs):
    """
    Receiver for summary_completed signal.
    Handles post-processing after summary creation.
    """
    if summary:
        print(f"[SIGNAL] Summary {summary.id} completed successfully")
    else:
        print("[SIGNAL] Guest summary completed (not saved)")


summary_requested.connect(
    handle_summary_requested, dispatch_uid="summary_requested_handler"
)
summary_completed.connect(
    handle_summary_completed, dispatch_uid="summary_completed_handler"
)

import django.dispatch


summary_requested = django.dispatch.Signal(providing_args=["data", "user", "request"])
"""
Signal dispatched when a user requests text summarization.

Args:
    sender: The view function that dispatched the signal
    data: dict containing:
        - title: str - Document title (optional)
        - original_text: str - Text to summarize
        - compression_ratio: float - Target compression ratio (0.1-0.5)
        - method: str - Summarization method ('hybrid' or 'traditional')
    user: User instance or None for anonymous users
    request: HttpRequest instance
"""


summary_completed = django.dispatch.Signal(providing_args=["summary", "result"])
"""
Signal dispatched after a summary is successfully created and saved.

Args:
    sender: The function that completed the summarization
    summary: Summary model instance (or None for guest users)
    result: dict containing:
        - summary: str - Generated summary text
        - entities: list - Extracted named entities (NER)
        - effective_title: str - Title used for the summary
        - method: str - Method used for summarization
"""
