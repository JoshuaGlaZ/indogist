from fastapi.testclient import TestClient

SAMPLE_NEWS_TEXT = (
    "Bank Indonesia memutuskan untuk menaikkan suku bunga acuan sebesar 25 basis poin. "
    "Langkah ini diambil untuk mengendalikan tingkat inflasi dan menjaga stabilitas nilai tukar Rupiah. "
    "Gubernur BI menegaskan bahwa kebijakan moneter akan tetap pro-stabilitas dengan terus memantau dinamika ekonomi global."
)


# ==========================================
# TIER 1: FEATURE COVERAGE (HAPPY PATHS)
# ==========================================


def test_charts_get(client: TestClient):
    """Tier 1: Accessing charts page returns 200 OK."""
    response = client.get("/charts/")
    assert response.status_code == 200


def test_comparison_get(client: TestClient):
    """Tier 1: Accessing comparison studio page returns 200 OK."""
    response = client.get("/comparison/")
    assert response.status_code == 200


def test_comparison_post_happy_path(client: TestClient):
    """Tier 1: Submitting text for dual-model comparison renders side-by-side outputs."""
    payload = {"text": SAMPLE_NEWS_TEXT, "model_a": "traditional", "model_b": "hybrid"}
    response = client.post("/comparison/", data=payload)
    assert response.status_code == 200
    assert len(response.text.strip()) > 0


# ==========================================
# TIER 2: BOUNDARY & CORNER CASES
# ==========================================


def test_comparison_post_empty_text(client: TestClient):
    """Tier 2: Submitting empty text to comparison studio handles empty input gracefully."""
    payload = {"text": "", "model_a": "traditional", "model_b": "hybrid"}
    response = client.post("/comparison/", data=payload)
    assert response.status_code == 200


def test_comparison_post_same_models(client: TestClient):
    """Tier 2: Comparing identical models (traditional vs traditional) works cleanly."""
    payload = {"text": SAMPLE_NEWS_TEXT, "model_a": "traditional", "model_b": "traditional"}
    response = client.post("/comparison/", data=payload)
    assert response.status_code == 200


# ==========================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# ==========================================


def test_comparison_ajax_request(client: TestClient):
    """Tier 3: HTMX AJAX comparison request returns partial HTML cards for Model A and Model B."""
    payload = {"text": SAMPLE_NEWS_TEXT, "model_a": "traditional", "model_b": "hybrid"}
    headers = {"HX-Request": "true"}
    response = client.post("/comparison/", data=payload, headers=headers)
    assert response.status_code == 200
    assert "Model A" in response.text
    assert "Model B" in response.text
    assert "compareOutputA" in response.text
    assert "compareOutputB" in response.text


# ==========================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS
# ==========================================


def test_comparison_realworld_news_article(client: TestClient):
    """Tier 4: Compares Extractive vs Hybrid summarizers on multi-paragraph Indonesian financial article."""
    article = (
        "Kementerian Keuangan merilis laporan realisasi Anggaran Pendapatan dan Belanja Negara (APBN) semester pertama. "
        "Pendapatan negara tercatat mengalami pertumbuhan positif sebesar 12,5 persen dibandingkan periode tahun lalu, "
        "yang ditopang oleh penerimaan perpajakan dan PNBP sektor komoditas.\n\n"
        "Menteri Keuangan menyampaikan bahwa belanja negara juga terealisasi sesuai target, dengan prioritas pada sektor "
        "perlindungan sosial, kesehatan, dan pembangunan infrastruktur strategis nasional. "
        "Defisit anggaran terjaga pada tingkat aman di bawah 3 persen dari Produk Domestik Bruto (PDB)."
    )
    payload = {"text": article, "model_a": "traditional", "model_b": "hybrid"}
    response = client.post("/comparison/", data=payload)
    assert response.status_code == 200
    assert "traditional" in response.text.lower()
    assert "hybrid" in response.text.lower()


def test_charts_rendered_with_context_data(client: TestClient):
    """M3 Task 5: Verify charts_get renders chart_image and report_table conditional template blocks cleanly."""
    response = client.get("/charts/")
    assert response.status_code == 200
    assert (
        "Model Training Convergence" in response.text
        or "Training History" in response.text
        or "data:image/png;base64," in response.text
    )
    assert (
        "Detailed Performance Classification" in response.text
        or "Metric Class" in response.text
        or "Precision" in response.text
    )
