import numpy as np
import pandas as pd
import os
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .utils import text_to_sentences, preprocess_tfidf, extract_tf_query
from ml.ner.loader import stemmer, stopword_remover
import Sastrawi.Stemmer.Filter.TextNormalizer as normalizer

def summarize_traditional(text, title, compression_ratio=0.3, progress_callback=None):
    """
    Traditional extractive summarization with full step logging and Excel documentation.

    Args:
        text: Input document text.
        title: Document title.
        compression_ratio: Fraction of sentences to include in summary.
        progress_callback: Optional callable(event_dict) for SSE progress events.
                           Events emitted:
                             {'type': 'step', 'step': 'step1', 'status': 'active', 'label': '...'}
                             {'type': 'step', 'step': 'step1', 'status': 'done'}
    """
    def emit(event):
        if progress_callback:
            progress_callback(event)

    # Inisialisasi Excel Writer
    excel_file = "dokumentasi_tradisional.xlsx"
    writer = pd.ExcelWriter(excel_file, engine='openpyxl')

    # =========================================================================
    # [STEP 1] TAHAP INPUT DATA - Gambar 6.11
    # =========================================================================
    emit({'type': 'step', 'step': 'step1', 'status': 'active', 'label': 'Tokenizing sentences...'})

    print("\n" + "="*80)
    print("LOG SISTEM: TRADITIONAL SUMMARIZATION PIPELINE")
    print("="*80)
    print(f"[STEP 1] Tahap Input Data - Gambar 6.11")
    print(f"Judul Input    : {title}")
    print(f"Jumlah Karakter: {len(text)}")

    # =========================================================================
    # [STEP 2] PREPROCESSING 1: SENTENCE TOKENIZATION - Gambar 6.12
    # =========================================================================
    sentences = text_to_sentences(text)
    n_sentences = len(sentences)
    print(f"\n[STEP 2] Preprocessing 1: Sentence Tokenization - Gambar 6.12")
    print(f"Total Kalimat Terdeteksi: {n_sentences}")
    for i, s in enumerate(sentences):
        print(f"  S{i+1}: {s}")

    emit({'type': 'step', 'step': 'step1', 'status': 'done'})

    # =========================================================================
    # [STEP 3 & 6] PREPROCESSING 2 & 4: STEMMING & STOPWORD REMOVAL - Gambar 6.16
    # =========================================================================
    emit({'type': 'step', 'step': 'step2', 'status': 'active', 'label': 'Building TF-IDF matrix...'})

    print(f"\n[STEP 3 & 6] Preprocessing: Stemming & Stopword Removal - Gambar 6.16")
    preprocessing_data = []
    processed_sents = []

    for i in range(len(sentences)):
        s_original = sentences[i]
        s_norm = normalizer.normalize_text(s_original)
        s_stemmed = stemmer.stem(s_norm)
        s_final = stopword_remover.remove(s_stemmed)

        processed_sents.append(s_final)
        preprocessing_data.append({
            'ID': f"S{i+1}",
            'Original': s_original,
            'Stemmed': s_stemmed,
            'Final_Clean': s_final
        })

        print(f"S{i+1}")
        print(f"  [RAW]  : {s_original[:100]}...")
        print(f"  [STEM] : {s_stemmed[:100]}...")
        print(f"  [FINAL]: {s_final[:100]}...\n")

    pd.DataFrame(preprocessing_data).to_excel(writer, sheet_name='1_Preprocessing', index=False)

    # =========================================================================
    # [STEP 7] TF-IDF MATRIX & COMPONENTS (TF, IDF) - Gambar 6.17
    # =========================================================================
    count_vectorizer = CountVectorizer()
    tf_matrix_sents = count_vectorizer.fit_transform(processed_sents)
    feature_names = count_vectorizer.get_feature_names_out()

    tfidf_vectorizer = TfidfVectorizer()
    tfidf_mat_sents = tfidf_vectorizer.fit_transform(processed_sents)
    idf_values = tfidf_vectorizer.idf_

    raw_tfidf_sents = tf_matrix_sents.toarray() * idf_values

    effective_title = title
    if not effective_title or not effective_title.strip():
        effective_title = extract_tf_query(tfidf_mat_sents, tfidf_vectorizer)
        print(f"\n[INFO] Judul kosong. Menggunakan TF-Query: '{effective_title}'")

    processed_title = stopword_remover.remove(stemmer.stem(effective_title))
    processed_title = stopword_remover.remove(stemmer.stem(title)) if title else ""
    title_tf_vec = count_vectorizer.transform([processed_title]) if processed_title else None
    title_tfidf_vec = tfidf_vectorizer.transform([processed_title]) if processed_title else None

    raw_tfidf_title = title_tf_vec.toarray() * idf_values if title_tf_vec is not None else None

    print("\n" + "="*60)
    print("[STEP 7] TF & IDF COMPONENTS LOG - Gambar 6.17")
    print("-" * 60)
    print(f"Jumlah Fitur (Vocab): {len(feature_names)}")
    print("\nSampel Nilai IDF (Top 5 Kata):")
    for i in range(min(5, len(feature_names))):
        print(f"  - {feature_names[i]}: {idf_values[i]:.4f}")

    print("\nSampel Matriks TF-IDF Hasil fit_transform (S1):")
    if n_sentences > 0:
        s1_vector = tfidf_mat_sents.getrow(0).toarray()[0]
        print(f"  S1 = {list(np.round(s1_vector[s1_vector > 0], 4))} (Non-zero values)")
    print("="*60)

    components_data = []
    r_idx, c_idx = tf_matrix_sents.nonzero()
    for r, c in zip(r_idx, c_idx):
        components_data.append({
            'Source': f"S{r+1}",
            'Term': feature_names[c],
            'TF': tf_matrix_sents[r, c],
            'IDF': round(idf_values[c], 4),
            'Raw_TFIDF': round(raw_tfidf_sents[r, c], 4),
            'Final_TFIDF_Norm': round(tfidf_mat_sents[r, c], 4)
        })
    pd.DataFrame(components_data).to_excel(writer, sheet_name='2_TF_IDF_Components', index=False)

    df_dense = pd.DataFrame(raw_tfidf_sents, columns=feature_names, index=[f"S{i+1}" for i in range(n_sentences)])
    if raw_tfidf_title is not None:
        df_title = pd.DataFrame(raw_tfidf_title, columns=feature_names, index=["TITLE"])
        df_dense = pd.concat([df_title, df_dense])
    df_dense.to_excel(writer, sheet_name='3_Raw_TFIDF_Matrix')

    emit({'type': 'step', 'step': 'step2', 'status': 'done'})

    # =========================================================================
    # [STEP 8] FEATURE EXTRACTION (STATISTICAL) - Gambar 6.18
    # =========================================================================
    emit({'type': 'step', 'step': 'step3', 'status': 'active', 'label': 'Extracting statistical features...'})

    print("\n" + "="*60)
    print("[STEP 8] Statistical Feature Extraction - Gambar 6.18")

    title_scores = cosine_similarity(tfidf_mat_sents, title_tfidf_vec).flatten() if title_tfidf_vec is not None else np.zeros(n_sentences)

    loc_scores_raw = np.array([((n_sentences - i) / n_sentences) for i in range(n_sentences)])

    freq_scores = np.asarray(tfidf_mat_sents.sum(axis=1)).ravel()

    sim_mat = cosine_similarity(tfidf_mat_sents, tfidf_mat_sents)
    np.fill_diagonal(sim_mat, 0)
    agg_scores = sim_mat.sum(axis=1)

    def normalize(arr):
        if arr.max() > arr.min():
            return (arr - arr.min()) / (arr.max() - arr.min())
        return np.zeros_like(arr)

    freq_norm = normalize(freq_scores)
    agg_norm = normalize(agg_scores)

    feature_matrix_df = pd.DataFrame({
        'TS_Score': title_scores,
        'Loc_Raw': loc_scores_raw,
        'Freq_Norm': freq_norm,
        'Agg_Norm': agg_norm
    }, index=[f"S{i+1}" for i in range(n_sentences)])

    print("\nNormalized Feature Matrix (Preview):")
    print(feature_matrix_df.round(4).to_string())

    feature_matrix_df.to_excel(writer, sheet_name='4_Feature_Matrix')

    emit({'type': 'step', 'step': 'step3', 'status': 'done'})

    # =========================================================================
    # [STEP 9] FINAL SCORING - Gambar 6.19
    # =========================================================================
    emit({'type': 'step', 'step': 'step4', 'status': 'active', 'label': 'Scoring & selecting sentences...'})

    # Rumus: TS + Loc + (Freq_Norm * Agg_Norm)
    final_scores = title_scores + loc_scores_raw + (freq_norm * agg_norm)

    print("\n" + "="*60)
    print("[STEP 9] Final Scoring (Traditional Formula) - Gambar 6.19")
    ranking_data = []
    for i, s in enumerate(final_scores):
        print(f"  Skor S{i+1}: {s:.4f}")
        ranking_data.append({
            'ID': f"S{i+1}",
            'Final_Score': round(s, 4),
            'Content': sentences[i]
        })

    # =========================================================================
    # [STEP 10] SELECTION & RECONSTRUCTION - Gambar 6.20
    # =========================================================================
    num_select = max(1, round(n_sentences * compression_ratio))
    top_indices = np.argsort(final_scores)[-num_select:]
    sorted_indices = sorted(top_indices)

    for entry in ranking_data:
        idx = int(entry['ID'][1:]) - 1
        entry['Is_Summary'] = "YES" if idx in top_indices else "NO"
    pd.DataFrame(ranking_data).to_excel(writer, sheet_name='5_Final_Ranking', index=False)

    summary_result = " ".join([sentences[i] for i in sorted_indices])

    print(f"\n[STEP 10] Selection & Summary Reconstruction - Gambar 6.20")
    print(f"Indices Kalimat Terpilih: {[idx + 1 for idx in sorted_indices]}")
    print("-" * 50)
    print(f"RINGKASAN AKHIR: {summary_result[:150]}...")
    print("-" * 50)

    writer.close()
    print(f"\n[INFO] Dokumentasi Excel Selesai: {excel_file}")

    emit({'type': 'step', 'step': 'step4', 'status': 'done'})

    return {'summary': summary_result, 'effective_title': title if title else "Indikator Utama"}
