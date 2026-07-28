import io

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Summary, User

# ==========================================
# TIER 1: FEATURE COVERAGE (HAPPY PATHS)
# ==========================================


def test_upload_valid_template_file(client: TestClient):
    """Tier 1: Uploading a valid template text file with TITLE= and TEXT= processes correctly."""
    file_content = (
        "TITLE=Transformasi Pelayanan Publik Digital\n\n"
        "TEXT=Pemerintah Indonesia merilis sistem pelayanan publik terpadu untuk mempermudah perizinan usaha. "
        "Program ini akan mengintegrasikan seluruh basis data kementerian di pusat dan daerah. "
        "Diharapkan layanan ini dapat memotong birokrasi dan mempercepat proses administrasi bagi warga negara."
    )
    files = {
        "file": ("template_sample.txt", io.BytesIO(file_content.encode("utf-8")), "text/plain")
    }
    data = {"method": "hybrid", "compression_ratio": "0.3"}
    response = client.post("/summarize/", data=data, files=files)
    assert response.status_code == 200
    assert len(response.text.strip()) > 0


# ==========================================
# TIER 2: BOUNDARY & CORNER CASES
# ==========================================


def test_upload_invalid_template_format(client: TestClient):
    """Tier 2: Uploading a text file missing TITLE= or TEXT= markers returns format validation error."""
    invalid_content = (
        "Ini adalah teks biasa tanpa marker TITLE atau TEXT yang disyaratkan oleh template sistem."
    )
    files = {
        "file": ("invalid_format.txt", io.BytesIO(invalid_content.encode("utf-8")), "text/plain")
    }
    data = {"method": "hybrid"}
    response = client.post("/summarize/", data=data, files=files)
    assert response.status_code in (200, 400)
    assert (
        "Format file tidak sesuai" in response.text
        or "template" in response.text.lower()
        or "alert-danger" in response.text
    )


def test_upload_non_utf8_binary_file(client: TestClient):
    """Tier 2: Uploading a non-UTF8 binary file handles UnicodeDecodeError without server crash."""
    binary_content = b"\x80\x81\x82\xff\xfe\xfd\x00\x01\x02"
    files = {"file": ("corrupted.bin", io.BytesIO(binary_content), "application/octet-stream")}
    data = {"method": "hybrid"}
    response = client.post("/summarize/", data=data, files=files)
    assert response.status_code in (200, 400)
    assert (
        "UTF-8" in response.text
        or "Unable to read file" in response.text
        or "alert-danger" in response.text
    )


# ==========================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# ==========================================


def test_upload_authenticated_persists_summary(
    auth_client: TestClient, db_session: Session, test_user: User
):
    """Tier 3: Uploading template file while authenticated saves Summary record to DB."""
    title = "File Upload Persistent Test"
    file_content = (
        f"TITLE={title}\n\n"
        "TEXT=Kementerian Pendidikan meluncurkan beasiswa baru untuk mahasiswa sains dan teknologi. "
        "Beasiswa ini mencakup biaya kuliah penuh serta uang saku bulanan selama masa studi. "
        "Pendaftaran akan dibuka secara daring melalui portal resmi nasional mulai bulan depan."
    )
    files = {"file": ("beasiswa.txt", io.BytesIO(file_content.encode("utf-8")), "text/plain")}
    data = {"method": "traditional", "compression_ratio": "0.3"}

    response = auth_client.post("/summarize/", data=data, files=files)
    assert response.status_code == 200

    summary = (
        db_session.query(Summary)
        .filter(Summary.title == title, Summary.user_id == test_user.id)
        .first()
    )
    assert summary is not None
    assert summary.method == "traditional"


# ==========================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS
# ==========================================


def test_upload_large_multiparagraph_document(client: TestClient):
    """Tier 4: Uploading a large multi-paragraph document template executes tokenization and summarization."""
    paragraph1 = "Kementerian Kesehatan mengumumkan perluasan cakupan imunisasi nasional untuk anak-anak sekolah dasar. Program ini akan dilaksanakan serentak di 38 provinsi di seluruh wilayah Indonesia."
    paragraph2 = "Menteri Kesehatan menyampaikan bahwa ketersediaan vaksin telah dipastikan aman dan terdistribusi hingga ke fasilitas kesehatan tingkat pertama di pelosok daerah."
    paragraph3 = "Masyarakat dihimbau untuk berpartisipasi aktif dalam menyukseskan kegiatan imunisasi demi menjaga kekebalan kelompok dan kesehatan generasi muda Indonesia."

    file_content = (
        f"TITLE=Program Imunisasi Nasional\n\nTEXT={paragraph1}\n\n{paragraph2}\n\n{paragraph3}"
    )
    files = {"file": ("imunisasi_doc.txt", io.BytesIO(file_content.encode("utf-8")), "text/plain")}
    data = {"method": "hybrid", "compression_ratio": "0.4"}

    response = client.post("/summarize/", data=data, files=files)
    assert response.status_code == 200
    assert len(response.text.strip()) > 0
