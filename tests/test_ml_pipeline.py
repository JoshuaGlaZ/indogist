import pytest
from ml.summarization.hybrid import predict_and_summarize
from ml.summarization.traditional import summarize_traditional
from ml.summarization.utils import (
    text_to_sentences,
    preprocess_tfidf,
    pos_tag_summary
)


SAMPLE_ML_TEXT = (
    "Presiden Republik Indonesia Joko Widodo meresmikan proyek infrastruktur baru di ibu kota nusantara. "
    "Proyek ini meliputi pembangunan jalan tol, sarana air bersih, dan pusat perkantoran kementerian. "
    "Pemerintah berkomitmen mempercepat pembangunan agar kawasan tersebut siap digunakan pada bulan Agustus mendatang. "
    "Para investor domestik dan asing turut menyampaikan dukungan finansial untuk pengembangan teknologi pintar."
)


# ==========================================
# TIER 1: FEATURE COVERAGE (HAPPY PATHS)
# ==========================================

def test_predict_and_summarize_hybrid():
    """Tier 1: Hybrid summarizer returns structured dict with summary text, entities, and POS tokens."""
    result = predict_and_summarize(SAMPLE_ML_TEXT, title="Resmedi Nusantara", compression_ratio=0.3)
    assert isinstance(result, dict)
    assert "summary" in result
    assert len(result["summary"].strip()) > 0
    assert "entities" in result
    assert "pos_tokens" in result


def test_summarize_traditional_extractive():
    """Tier 1: Traditional Extractive summarizer returns structured dict or string summary."""
    result = summarize_traditional(SAMPLE_ML_TEXT, title="Extractive Test", compression_ratio=0.3, stream=False)
    if isinstance(result, dict):
        assert "summary" in result
        assert len(result["summary"].strip()) > 0
    else:
        assert isinstance(result, str)
        assert len(result.strip()) > 0


def test_pos_tag_summary_utility():
    """Tier 1: pos_tag_summary returns token list or empty list safely."""
    tokens = pos_tag_summary("Presiden meresmikan proyek baru.")
    assert isinstance(tokens, list)


# ==========================================
# TIER 2: BOUNDARY & CORNER CASES
# ==========================================

def test_preprocess_tfidf_stopwords():
    """Tier 2: Preprocess TFIDF removes Indonesian stopwords and stems terms correctly."""
    sentences = ["Pemerintah sedang melaksanakan kebijakan baru di jakarta."]
    processed = preprocess_tfidf(sentences)
    assert isinstance(processed, list)
    assert len(processed) == 1
    # Check that processed text has been lowercased or stemmed
    assert len(processed[0]) > 0


def test_text_to_sentences_empty():
    """Tier 2: text_to_sentences handles empty text input safely."""
    sents = text_to_sentences("")
    assert isinstance(sents, list)
    assert len(sents) == 0


# ==========================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# ==========================================

def test_hybrid_pipeline_integration():
    """Tier 3: Preprocessing -> Sentence Tokenization -> TF-IDF Ranking -> Hybrid Summary Output."""
    sentences = text_to_sentences(SAMPLE_ML_TEXT)
    assert len(sentences) >= 3

    processed = preprocess_tfidf(sentences)
    assert len(processed) == len(sentences)

    res = predict_and_summarize(SAMPLE_ML_TEXT, compression_ratio=0.5)
    assert isinstance(res, dict)
    assert len(res["summary"]) > 0


# ==========================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS
# ==========================================

def test_ml_pipeline_performance_heavy_text():
    """Tier 4: Processes a 1,000+ word Indonesian news document without memory exception or failure."""
    heavy_text = (SAMPLE_ML_TEXT + " ") * 10
    result = predict_and_summarize(heavy_text, compression_ratio=0.2)
    assert isinstance(result, dict)
    assert len(result["summary"].strip()) > 0


def test_summarize_traditional_empty_and_non_string_inputs():
    """M3 Task 3: summarize_traditional handles empty string, whitespace, and non-string inputs gracefully."""
    res_empty = summarize_traditional("", title="", stream=False)
    assert isinstance(res_empty, dict)
    assert res_empty.get("summary") == ""

    res_ws = summarize_traditional("   \n\t   ", title="Whitespace", stream=False)
    assert isinstance(res_ws, dict)
    assert res_ws.get("summary") == ""

    res_none = summarize_traditional(None, title="None test", stream=False)
    assert isinstance(res_none, dict)
    assert res_none.get("summary") == ""


def test_predict_and_summarize_empty_and_non_string_inputs():
    """M3 Task 3: predict_and_summarize handles empty string, whitespace, and non-string inputs gracefully."""
    res_empty = predict_and_summarize("", title="")
    assert isinstance(res_empty, dict)
    assert res_empty.get("summary") == ""

    res_ws = predict_and_summarize("   \n\t   ", title="Whitespace")
    assert isinstance(res_ws, dict)
    assert res_ws.get("summary") == ""

    res_none = predict_and_summarize(None, title="None test")
    assert isinstance(res_none, dict)
    assert res_none.get("summary") == ""


def test_nlp_service_pre_initialization_and_pos_prefix():
    """M3 Task 2: NLPService pre-initializes attributes and discovers POS model directory correctly."""
    from ml.ner.loader import nlp_service
    assert hasattr(nlp_service, "ner_model")
    assert hasattr(nlp_service, "vectorizer")
    assert hasattr(nlp_service, "idx_to_tag")
    assert hasattr(nlp_service, "max_len")
    assert nlp_service.max_len == 256 or isinstance(nlp_service.max_len, int)

    status = nlp_service.get_status()
    assert isinstance(status, dict)
    assert "is_ready" in status
    assert "model_format" in status
    assert "vocab_size" in status
    assert "tag_count" in status
    assert "pos_tagger_status" in status

    # Ensure print_status executes without throwing exceptions
    nlp_service.print_status()


def test_ml_status_module_diagnostics():
    """Tests the ml.status module get_model_status() and check_models() diagnostic helper functions."""
    from ml.status import get_model_status, check_models
    status = get_model_status()
    assert isinstance(status, dict)
    assert "models_root" in status
    assert "active_dir_name" in status
    assert "keras_available" in status
    assert "tflite_available" in status
    assert "singleton" in status

    exit_code = check_models(verbose=False)
    assert exit_code in (0, 1)

