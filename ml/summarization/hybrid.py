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
    ent_counts = np.zeros(n)
    ent_densities = np.zeros(n)
    
    # Extract title entities for overlap calculation
    
    ent_counts = np.array([len(res.get('entities', [])) for res in ner_results])
    ent_densities = np.array([len(res.get('entities', []))/len(res.get('tokens', [1])) for res in ner_results])

    # Matrix Construction (n_sentences x 7_features)
    feature_matrix = np.column_stack((
        title_scores,
        loc_scores,
        normalize_scores(freq_scores),
        normalize_scores(agg_scores),
        normalize_scores(ent_counts),
        normalize_scores(ent_densities),
    ))

    return feature_matrix

def predict_and_summarize(text, title=None, compression_ratio=0.3, stream=False):
    """
    If stream=True, acts as a generator yielding progress steps: {'step': N}
    until the final {'step': 4, 'result': ...}.
    Otherwise, returns the final result dict directly.
    """
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

        # --- Step 2: NER Inference (the slow part) ---
        yield {'step': 2}

        ner_results = predict_entities(raw_sentences)

        # --- Step 3: Scoring & Selection ---
        yield {'step': 3}

        feature_matrix = compute_hybrid_scores(
            raw_sentences, effective_title, ner_results, tfidf_mat, vectorizer
        )
        final_scores = feature_matrix @ WEIGHTS

        n_select = max(1, round(len(raw_sentences) * compression_ratio))
        top_indices = np.argsort(final_scores)[-n_select:]
        top_indices.sort()

        summary = " ".join([raw_sentences[i] for i in top_indices])

        unique_entities = {}
        for idx in top_indices:
            for ent in ner_results[idx].get('entities', []):
                key = (ent['text'].lower(), ent['label'])
                if key not in unique_entities:
                    # Ensure JSON serializable types
                    clean_ent = {k: float(v) if isinstance(v, (np.floating, float)) else v 
                                 for k, v in ent.items()}
                    unique_entities[key] = clean_ent

        # --- Step 4: Done ---
        yield {
            'step': 4,
            'result': {
                'summary': summary,
                'entities': list(unique_entities.values()),
                'effective_title': effective_title
            }
        }

    if stream:
        return _generator()
    else:
        # Run the generator to exhaustion and return the final result
        result = None
        for step_data in _generator():
            if step_data.get('step') == 4 and 'result' in step_data:
                result = step_data['result']
        return result