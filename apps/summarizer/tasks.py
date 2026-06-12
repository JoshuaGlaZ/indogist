import logging
from ml.summarization.hybrid import predict_and_summarize
from ml.summarization.traditional import summarize_traditional

logger = logging.getLogger(__name__)


def run_summarization(task, data):
    try:
        task.set_progress({"step": 1, "message": "Starting summarization..."})

        method = data["method"]
        text = data["original_text"]
        title = data["title"]
        compression_ratio = data["compression_ratio"]
        user_id = data.get("user_id")

        task.set_progress({"step": 2, "message": "Processing text..."})

        if method == "hybrid":
            result = predict_and_summarize(
                text=text,
                title=title,
                compression_ratio=compression_ratio,
            )
            entities = result.get("entities", [])
        else:
            result = summarize_traditional(
                text=text,
                title=title,
                compression_ratio=compression_ratio,
                stream=False,
            )
            entities = []

        task.set_progress({"step": 3, "message": "Generating summary..."})

        summary_text = result["summary"]
        effective_title = result.get("effective_title", title)
        final_title = title if title else effective_title

        summary_id = None
        mode = "guest"
        if user_id:
            from apps.summarizer.models import Summary

            summary_obj = Summary.objects.create(
                user_id=user_id,
                title=final_title,
                original_text=text,
                summary_text=summary_text,
                compression_ratio=compression_ratio,
                entities=entities,
                method=method,
            )
            summary_id = summary_obj.id
            mode = "user"

        task.set_progress({"step": 4, "message": "Complete"})

        return {
            "success": True,
            "mode": mode,
            "summary": summary_text,
            "entities": entities,
            "summary_id": summary_id,
            "effective_title": final_title,
        }

    except Exception as e:
        logger.exception("run_summarization failed")
        return {"success": False, "error": str(e)}
