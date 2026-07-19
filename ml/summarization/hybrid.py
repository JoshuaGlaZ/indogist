import time
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .utils import text_to_sentences, preprocess_tfidf, extract_tf_query
from ..ner.predict import predict_entities

WEIGHTS = np.array([
    0.16,  # Title Similarity
    0.29,  # Location
    0.21,  # Term Frequency
    0.09,  # Aggregation
    0.16,  # Entity Count
    0.09   # Entity Density
])

def normalize_scores(scores):
    scores = np.asarray(scores, dtype=np.float64)
    min_val, max_val = scores.min(), scores.max()
    if max_val - min_val == 0:
        return np.zeros_like(scores)
    return (scores - min_val) / (max_val - min_val)

def compute_hybrid_scores(sentences, title, ner_results, tfidf_mat, vectorizer):
    n = len(sentences)
    
    # Statistical Features
    loc_scores = np.array([(n - i) / n for i in range(n)])
    
    freq_scores = np.asarray(tfidf_mat.sum(axis=1)).ravel()
    
    sim_mat = cosine_similarity(tfidf_mat, tfidf_mat)
    np.fill_diagonal(sim_mat, 0)
    agg_scores = sim_mat.sum(axis=1)

    title_scores = np.zeros(n)
    effective_title = title if title and title.strip() else extract_tf_query(tfidf_mat, vectorizer)
    title_vec = vectorizer.transform([effective_title])
    title_scores = cosine_similarity(tfidf_mat, title_vec).flatten()

    # Semantic Features (NER based)
    ent_counts = np.array([len(res.get('entities', [])) for res in ner_results])
    ent_densities = np.array([
        len(res.get('entities', [])) / len(res.get('tokens', [1])) if len(res.get('tokens', [])) > 0 else 0
        for res in ner_results
    ])

    # Matrix Construction (n_sentences x 6_features)
    feature_matrix = np.column_stack((
        title_scores,
        loc_scores,
        normalize_scores(freq_scores),
        normalize_scores(agg_scores),
        normalize_scores(ent_counts),
        normalize_scores(ent_densities),
    ))

    return feature_matrix

def predict_and_summarize(text, title=None, compression_ratio=0.3, stream=False, progress_callback=None):
    """
    Summarize text using hybrid NER-enhanced method.
    """
    _start_time = time.time()

    def _generator():
        # --- Step 1: Preprocessing ---
        yield {'step': 1}

        raw_sentences = text_to_sentences(text)
        if not raw_sentences:
            yield {'step': 4, 'result': {'summary': '', 'entities': [], 'effective_title': ''}}
            return

        processed_sents = preprocess_tfidf(raw_sentences)
        if not any(processed_sents):
            yield {'step': 4, 'result': {'summary': raw_sentences[0], 'entities': [], 'effective_title': title}}
            return

        vectorizer = TfidfVectorizer()
        tfidf_mat = vectorizer.fit_transform(processed_sents)

        effective_title = title
        if not effective_title or not effective_title.strip():
            effective_title = extract_tf_query(tfidf_mat, vectorizer)

        # --- Step 2: NER Inference ---
        yield {'step': 2}

        ner_results = predict_entities(raw_sentences)

        # --- Step 3: Scoring & Selection ---
        yield {'step': 3}

        feature_matrix = compute_hybrid_scores(
            raw_sentences, effective_title, ner_results, tfidf_mat, vectorizer
        )
        final_scores = feature_matrix @ WEIGHTS

        n_select = max(1, round(len(raw_sentences) * compression_ratio))
        
        # --- Maximal Marginal Relevance (MMR) Selection ---
        selected_indices = []
        unselected_indices = list(range(len(raw_sentences)))
        
        sim_matrix = cosine_similarity(tfidf_mat, tfidf_mat)
        lambda_param = 0.7  # 0.7 relevance vs 0.3 diversity

        for _ in range(min(n_select, len(raw_sentences))):
            if not selected_indices:
                best_idx = max(unselected_indices, key=lambda i: final_scores[i])
            else:
                def mmr_score(i):
                    max_sim = max(sim_matrix[i, j] for j in selected_indices)
                    return lambda_param * final_scores[i] - (1 - lambda_param) * max_sim
                best_idx = max(unselected_indices, key=mmr_score)
            selected_indices.append(best_idx)
            unselected_indices.remove(best_idx)

        top_indices = sorted(selected_indices)

        summary = " ".join([raw_sentences[i] for i in top_indices])

        unique_entities = {}
        for idx in top_indices:
            for ent in ner_results[idx].get('entities', []):
                key = (ent['text'].lower(), ent['label'])
                if key not in unique_entities:
                    clean_ent = {k: float(v) if isinstance(v, (np.floating, float)) else v 
                                 for k, v in ent.items()}
                    conf_val = float(clean_ent.get("confidence", clean_ent.get("score", 0.9)))
                    clean_ent["confidence_percent"] = round(conf_val * 100) if conf_val <= 1.0 else round(conf_val)
                    unique_entities[key] = clean_ent

        # --- Step 4: Done ---
        elapsed = time.time() - _start_time
        print(f"[TIMING] Hybrid summarization completed in {elapsed:.3f}s")
        yield {
            'step': 4,
            'result': {
                'summary': summary,
                'entities': list(unique_entities.values()),
                'effective_title': effective_title,
                'elapsed_time': elapsed
            }
        }

    # Mode 1: progress_callback
    if progress_callback is not None:
        result = None
        for step_data in _generator():
            if step_data.get('step') == 4 and 'result' in step_data:
                result = step_data['result']
            else:
                progress_callback(step_data)
        return result

    # Mode 2: stream
    if stream:
        return _generator()

    # Mode 3: non-stream
    result = None
    for step_data in _generator():
        if step_data.get('step') == 4 and 'result' in step_data:
            result = step_data['result']
    return result