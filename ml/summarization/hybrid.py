import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .utils import text_to_sentences, preprocess_tfidf, extract_tf_query
from ..ner.predict import predict_entities

excel_file = "dokumentasi_hybrid.xlsx"
writer = pd.ExcelWriter(excel_file, engine='openpyxl')

WEIGHTS = np.array([
    0.16,  # Title Similarity
    0.29,  # Location
    0.21,  # Term Frequency
    0.09,  # Aggregation
    0.16,  # Entity Count
    0.09   # Entity Density
])

def normalize_scores(scores):
    min_val, max_val = scores.min(), scores.max()
    if max_val - min_val == 0:
        return np.zeros_like(scores)
    return (scores - min_val) / (max_val - min_val)

def compute_hybrid_scores(sentences, title, ner_results, tfidf_mat, vectorizer):
    n = len(sentences)
    print("\n" + "="*60)
    print("[STEP 8] Hybrid Feature Extraction (7 Features) - Gambar 6.18")
    # Statistical Features
    loc_scores = np.array([(n - i) / n for i in range(n)])
    
    freq_scores = np.asarray(tfidf_mat.sum(axis=1)).ravel()
    
    sim_mat = cosine_similarity(tfidf_mat, tfidf_mat)
    np.fill_diagonal(sim_mat, 0)
    agg_scores = sim_mat.sum(axis=1)

    effective_title = title if title and title.strip() else extract_tf_query(tfidf_mat, vectorizer)
    title_vec = vectorizer.transform([effective_title])
    title_scores = cosine_similarity(tfidf_mat, title_vec).flatten()

    # Semantic Features (NER based)
    ent_counts = np.array([len(res.get('entities', [])) for res in ner_results])
    ent_densities = np.array([len(res.get('entities', []))/len(res.get('tokens', [1])) for res in ner_results])

    # Matrix Construction (n_sentences x 6_features)
    feature_matrix = np.column_stack((
        title_scores,
        loc_scores,
        normalize_scores(freq_scores),
        normalize_scores(agg_scores),
        normalize_scores(ent_counts),
        normalize_scores(ent_densities),
    ))
    import pandas as pd
    feat_df = pd.DataFrame(feature_matrix, columns=['TS', 'Loc', 'Freq', 'Agg', 'EC', 'ED'])
    print(feat_df.round(4).to_string())
    print("="*60)
    hybrid_features = []
    for i in range(n):
        hybrid_features.append({
            'ID': f"S{i+1}",
            'TitleSim': title_scores[i],
            'Loc': loc_scores[i],
            'Freq_Raw': freq_scores[i],
            'Agg_Raw': agg_scores[i],
            'EntCount_Raw': ent_counts[i],
            'EntDens_Raw': ent_densities[i],
            'Freq_Norm': normalize_scores(freq_scores)[i],
            'Agg_Norm': normalize_scores(agg_scores)[i],
            'EC_Norm': normalize_scores(ent_counts)[i],
            'ED_Norm': normalize_scores(ent_densities)[i]
        })
    df_feat = pd.DataFrame(hybrid_features)
    df_feat.to_excel(writer, sheet_name='2_Hybrid_Features', index=False)

    return feature_matrix


def predict_and_summarize(text, title=None, compression_ratio=0.3, progress_callback=None):
    """
    Run hybrid summarization pipeline.

    Args:
        text: Input document text.
        title: Optional document title.
        compression_ratio: Fraction of sentences to keep.
        progress_callback: Optional callable(event_dict) for real-time SSE progress.
                           Events emitted:
                             {'type': 'step', 'step': 'step1', 'status': 'active', 'label': '...'}
                             {'type': 'step', 'step': 'step1', 'status': 'done'}
    """
    def emit(event):
        if progress_callback:
            progress_callback(event)

    # ------------------------------------------------------------------
    # STEP 1 — Input & Sentence Tokenization
    # ------------------------------------------------------------------
    emit({'type': 'step', 'step': 'step1', 'status': 'active', 'label': 'Tokenizing sentences...'})

    print("\n" + "="*80)
    print("LOG SISTEM: HYBRID SUMMARIZATION PIPELINE")
    print("="*80)
    print(f"[STEP 1] Tahap Input Data - Gambar 6.11")
    print(f"Judul Input: {title}")
    print(f"Karakter Konten: {len(text)}")

    raw_sentences = text_to_sentences(text)

    n = len(raw_sentences)
    print(f"\n[STEP 2] Preprocessing 1: Sentence Tokenization - Gambar 6.12")
    print(f"Kalimat Terdeteksi: {n}")
    for i in range(len(raw_sentences)):
        print(f"  S{i+1}: {raw_sentences[i]}")

    emit({'type': 'step', 'step': 'step1', 'status': 'done'})

    # ------------------------------------------------------------------
    # STEP 2 — Preprocessing & TF-IDF
    # ------------------------------------------------------------------
    emit({'type': 'step', 'step': 'step2', 'status': 'active', 'label': 'Building TF-IDF matrix...'})

    processed_sents = preprocess_tfidf(raw_sentences)

    from ml.ner.loader import stemmer, stopword_remover
    import Sastrawi.Stemmer.Filter.TextNormalizer as normalizer
    print(f"\n[STEP 6] Preprocessing 4: Stemming & Stopword Removal - Gambar 6.16")
    for i in range(len(raw_sentences)):
        s_original = raw_sentences[i]
        s_normalized = normalizer.normalize_text(s_original)
        s_stemmed = stemmer.stem(s_original)
        s_final = stopword_remover.remove(s_stemmed)
        print(f"S{i+1}")
        print(f"{s_original}")
        print(f"{s_normalized}")
        print(f"{s_stemmed}")
        print(f"{s_final}\n")

    # TF-IDF construction
    vectorizer = TfidfVectorizer()
    tfidf_mat = vectorizer.fit_transform(processed_sents)
    feature_names = vectorizer.get_feature_names_out()
    tfidf_matrix_dense = tfidf_mat.toarray()

    print(f"\n[STEP 7] TF-IDF Matrix Construction - Gambar 6.17")
    print(f"Matrix Dimension: {tfidf_mat.shape}")
    print("Feature Names:", feature_names)
    print("\nTF-IDF Matrix (dense form):\n", tfidf_matrix_dense)
    import pandas as pd
    df = pd.DataFrame(tfidf_matrix_dense, columns=feature_names)
    print("\nTF-IDF DataFrame:\n", df)

    tfidf_mat = vectorizer.fit_transform(processed_sents)

    effective_title = title
    if not effective_title or not effective_title.strip():
        effective_title = extract_tf_query(tfidf_mat, vectorizer)

    emit({'type': 'step', 'step': 'step2', 'status': 'done'})

    # ------------------------------------------------------------------
    # STEP 3 — NER Inference
    # ------------------------------------------------------------------
    emit({'type': 'step', 'step': 'step3', 'status': 'active', 'label': 'Running NER entity detection...'})

    ner_results = predict_entities(raw_sentences)
    entity_data = []
    for i, res in enumerate(ner_results):
        for ent in res.get('entities', []):
            entity_data.append({
                'Sentence_ID': f"S{i+1}",
                'Entity_Text': ent['text'],
                'Label': ent['label'],
                'Confidence': ent['confidence']
            })
    pd.DataFrame(entity_data).to_excel(writer, sheet_name='1_NER_Entities', index=False)

    emit({'type': 'step', 'step': 'step3', 'status': 'done'})

    # ------------------------------------------------------------------
    # STEP 4 — Scoring, Ranking & Summary Reconstruction
    # ------------------------------------------------------------------
    emit({'type': 'step', 'step': 'step4', 'status': 'active', 'label': 'Scoring & selecting sentences...'})

    feature_matrix = compute_hybrid_scores(
        raw_sentences, effective_title, ner_results, tfidf_mat, vectorizer
    )
    print(f"Feature Matrix: {feature_matrix}")

    final_scores = feature_matrix @ WEIGHTS
    print(f"\n[STEP 9] Final Scoring with Optimized Weights - Gambar 6.19")
    print(f"Bobot Digunakan: {WEIGHTS}")
    for i, s in enumerate(final_scores):
        print(f"  Skor S{i+1}: {s:.4f}")

    n_select = max(1, round(len(raw_sentences) * compression_ratio))
    print(n_select)
    top_indices = np.argsort(final_scores)[-n_select:]
    top_indices.sort()
    print(top_indices)

    summary = " ".join([raw_sentences[i] for i in top_indices])
    print(f"\n[STEP 10] Selection & Summary Reconstruction - Gambar 6.20")
    print(f"Kalimat Terpilih: {top_indices + 1}")
    print("-" * 50)
    print(f"RINGKASAN AKHIR: {summary}...")
    print("-" * 50)

    ranking_data = []
    for i, s in enumerate(final_scores):
        ranking_data.append({
            'ID': f"S{i+1}",
            'Score': s,
            'Selected': "YES" if i in top_indices else "NO",
            'Sentence': raw_sentences[i]
        })
    pd.DataFrame(ranking_data).to_excel(writer, sheet_name='3_Final_Ranking', index=False)

    writer.close()
    print(f"\n[INFO] Dokumentasi Hibrida disimpan di: {excel_file}")

    emit({'type': 'step', 'step': 'step4', 'status': 'done'})

    # Entity Aggregation
    unique_entities = {}
    for idx in top_indices:
        for ent in ner_results[idx].get('entities', []):
            key = (ent['text'].lower(), ent['label'])
            if key not in unique_entities:
                clean_ent = {k: float(v) if isinstance(v, (np.floating, float)) else v
                             for k, v in ent.items()}
                unique_entities[key] = clean_ent

    return {
        'summary': summary,
        'entities': list(unique_entities.values()),
        'effective_title': effective_title
    }
