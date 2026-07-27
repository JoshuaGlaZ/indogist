import os
from pathlib import Path
from typing import Any

from ml.ner.loader import nlp_service

BASE_DIR = Path(__file__).resolve().parent.parent


def get_model_status() -> dict[str, Any]:
    """
    Scans the ML directory structure and returns a comprehensive status dictionary
    for model availability, loaded components, and inference readiness.
    """
    models_root = BASE_DIR / "ml" / "models"

    # 1. Discover Active Model Directory
    active_dir = None
    if models_root.exists():
        final_pos_dir = models_root / "ner_pos_final"
        if final_pos_dir.exists():
            active_dir = final_pos_dir
        else:
            pos_dirs = sorted(
                [
                    d
                    for d in os.listdir(models_root)
                    if (
                        d.startswith(("ner_pos_experiment_", "ner_experiment_pos_"))
                        or d == "ner_experiment_pos_10-May-2026_10.00"
                    )
                    and (models_root / d).is_dir()
                ],
                reverse=True,
            )
            if pos_dirs:
                active_dir = models_root / pos_dirs[0]

    if not active_dir:
        active_dir = models_root / "ner_experiment_30-November-2025_13.35"

    # 2. Check File Artifacts
    keras_path = active_dir / "best_model_by_f1.keras"
    if not keras_path.exists():
        keras_path = active_dir / "model.keras"

    tflite_path = active_dir / "optimized_model.tflite"
    vectorizer_path = active_dir / "vectorizer.pkl"
    tag_path = active_dir / "tag_to_idx.pkl"
    pos_path = active_dir / "pos_to_idx.pkl"
    exp_results_path = active_dir / "experiment_results.json"

    # 3. Singleton State
    svc_status = nlp_service.get_status()

    # 4. Evaluation Report Check
    report_files = list(models_root.glob("**/classification_report.txt"))
    chart_files = list(models_root.glob("**/*.png"))

    return {
        "models_root": str(models_root),
        "active_dir": str(active_dir) if active_dir.exists() else None,
        "active_dir_name": active_dir.name if active_dir.exists() else "None",
        "keras_available": keras_path.exists(),
        "keras_size_mb": round(os.path.getsize(keras_path) / (1024 * 1024), 2)
        if keras_path.exists()
        else 0.0,
        "tflite_available": tflite_path.exists(),
        "tflite_size_mb": round(os.path.getsize(tflite_path) / (1024 * 1024), 2)
        if tflite_path.exists()
        else 0.0,
        "vectorizer_available": vectorizer_path.exists(),
        "tags_available": tag_path.exists(),
        "pos_mapping_available": pos_path.exists(),
        "exp_config_available": exp_results_path.exists(),
        "evaluation_reports_count": len(report_files),
        "evaluation_charts_count": len(chart_files),
        "singleton": svc_status,
    }


def check_models(verbose: bool = True) -> int:
    """
    Renders a formatted rich terminal dashboard displaying ML model status and pipeline availability.
    Can be run via CLI (`uv run check-models`) or imported.
    Returns 0 if models are ready, 1 if warnings/missing components.
    """
    status = get_model_status()
    singleton = status["singleton"]

    try:
        from rich.align import Align
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        has_rich = True
    except ImportError:
        has_rich = False

    if not has_rich or not verbose:
        # Fallback Plain Text Terminal Output
        print("==================================================")
        print("           INDOGIST ML MODEL STATUS               ")
        print("==================================================")
        print(f"Active Model Dir : {status['active_dir_name']}")
        print(
            f"Keras Model      : {'READY' if status['keras_available'] else 'NOT FOUND'} ({status['keras_size_mb']} MB)"
        )
        print(
            f"TFLite Model     : {'READY' if status['tflite_available'] else 'NOT FOUND'} ({status['tflite_size_mb']} MB)"
        )
        print(f"Active Format    : {singleton['model_format']}")
        print(
            f"Vectorizer       : {'READY' if status['vectorizer_available'] else 'NOT FOUND'} (vocab={singleton['vocab_size']}, max_len={singleton['max_len']})"
        )
        print(f"POS Tagger       : {singleton['pos_tagger_status']}")
        print(f"Pipeline State   : {'READY' if singleton['is_ready'] else 'INCOMPLETE'}")
        print("==================================================")
        return 0 if singleton["is_ready"] else 1

    console = Console()

    # Table Construction
    table = Table(
        show_header=True,
        header_style="bold magenta",
        padding=(0, 1),
        expand=True,
        box=None,
    )
    table.add_column("Component", style="cyan", width=22)
    table.add_column("Status", width=14)
    table.add_column("Details & Metrics", style="dim")

    # Keras Row
    if status["keras_available"]:
        keras_badge = (
            "[bold black on green]  AVAILABLE  [/]"
            if singleton["model_format"] == "Keras"
            else "[bold green]AVAILABLE[/]"
        )
        keras_detail = f"[green]v2/v3 Saved Model format ({status['keras_size_mb']} MB)[/green]"
    else:
        keras_badge = "[bold red]MISSING[/]"
        keras_detail = "[yellow]Not found in model directory[/yellow]"
    table.add_row("Keras Model", keras_badge, keras_detail)

    # TFLite Row
    if status["tflite_available"]:
        tflite_badge = (
            "[bold black on green]  AVAILABLE  [/]"
            if singleton["model_format"] == "TFLite"
            else "[bold green]AVAILABLE[/]"
        )
        tflite_detail = f"[green]CPU Quantized FlatBuffer ({status['tflite_size_mb']} MB)[/green]"
    else:
        tflite_badge = "[bold red]MISSING[/]"
        tflite_detail = "[yellow]Not found in model directory[/yellow]"
    table.add_row("TFLite Model", tflite_badge, tflite_detail)

    # Active Format Row
    active_fmt_badge = (
        f"[bold green]{singleton['model_format']}[/]"
        if singleton["model_format"] != "None"
        else "[bold red]NONE[/]"
    )
    table.add_row(
        "Active Format",
        active_fmt_badge,
        f"Selected for live inference (is_keras={singleton['is_keras_model']})",
    )

    # Vectorizer Row
    vect_badge = (
        "[bold green]LOADED[/]" if status["vectorizer_available"] else "[bold red]MISSING[/]"
    )
    vect_detail = (
        f"Vocabulary Size: {singleton['vocab_size']:,} terms | Max Cap Len: {singleton['max_len']}"
    )
    table.add_row("Text Vectorizer", vect_badge, vect_detail)

    # NER Tags Row
    tags_badge = "[bold green]LOADED[/]" if status["tags_available"] else "[bold red]MISSING[/]"
    tags_detail = f"BIO Classes: {singleton['tag_count']} tags registered"
    table.add_row("NER Tag Set", tags_badge, tags_detail)

    # POS Tagger Row
    if "Stanza" in singleton["pos_tagger_status"]:
        pos_badge = "[bold green]STANZA CACHED[/]"
    elif "Zero-padded" in singleton["pos_tagger_status"]:
        pos_badge = "[bold yellow]FALLBACK[/]"
    else:
        pos_badge = "[bold dim]DISABLED[/]"
    table.add_row("POS Tagger Engine", pos_badge, singleton["pos_tagger_status"])

    # Extractive Summarization Row
    table.add_row(
        "Summarizer Engine",
        "[bold green]READY[/bold green]",
        "TF-IDF + Cosine Similarity + MMR (lambda=0.7)",
    )

    # Overall Pipeline Readiness
    is_ready = singleton["is_ready"]
    overall_status = (
        "[bold black on green]  PIPELINE READY  [/]"
        if is_ready
        else "[bold white on red]  PIPELINE INCOMPLETE  [/]"
    )

    panel_title = "[bold white]Indogist ML Model & Pipeline Availability[/bold white]"
    panel_subtitle = f"Active Directory: [cyan]{status['active_dir_name']}[/cyan]"

    main_panel = Panel(
        Align.center(table),
        title=panel_title,
        subtitle=panel_subtitle,
        border_style="bright_blue" if is_ready else "red",
        padding=(1, 2),
    )

    console.print()
    console.print(main_panel)
    console.print(Align.center(Text.from_markup(f"Status: {overall_status}")))
    console.print()

    return 0 if is_ready else 1


if __name__ == "__main__":
    import sys

    sys.exit(check_models())
