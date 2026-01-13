import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .utils import text_to_sentences, preprocess_tfidf, extract_tf_query
from ..ner.predict import predict_entities

WEIGHTS = np.array([
    0.12,  # Title Similarity
    0.50,  # Location
    0.11,  # Term Frequency
    0.11,  # Aggregation
    0.03,  # Entity Count
    0.04,  # Entity Density
    0.09   # Entity Overlap
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
    if title:
        title_vec = vectorizer.transform([title])
        title_scores = cosine_similarity(tfidf_mat, title_vec).flatten()

    # Semantic Features (NER based)
    ent_counts = np.zeros(n)
    ent_densities = np.zeros(n)
    ent_overlaps = np.zeros(n)
    
    # Extract title entities for overlap calculation
    title_entities = set()
    if title:
        # Assuming title is processed as a single sentence input for NER
        t_res = predict_entities([title])
        if t_res and t_res[0].get('entities'):
            title_entities = {e['text'].lower() for e in t_res[0]['entities']}

    for i, res in enumerate(ner_results):
        entities = res.get('entities', [])
        tokens = res.get('tokens', [])
        count = len(entities)
        
        ent_counts[i] = count
        ent_densities[i] = count / len(tokens) if tokens else 0
        
        if title_entities and entities:
            sent_ents = {e['text'].lower() for e in entities}
            overlap = len(sent_ents.intersection(title_entities))
            ent_overlaps[i] = overlap / len(title_entities)

    # Matrix Construction (n_sentences x 7_features)
    feature_matrix = np.column_stack((
        title_scores,
        loc_scores,
        normalize_scores(freq_scores),
        normalize_scores(agg_scores),
        normalize_scores(ent_counts),
        normalize_scores(ent_densities),
        normalize_scores(ent_overlaps)
    ))

    return feature_matrix

def predict_and_summarize(text, title=None, compression_ratio=0.3):
    # Preprocessing
    raw_sentences = text_to_sentences(text)
    if not raw_sentences:
        return {'summary': '', 'entities': [], 'effective_title': ''}

    processed_sents = preprocess_tfidf(raw_sentences)
    if not any(processed_sents):
        return {'summary': raw_sentences[0], 'entities': [], 'effective_title': title}

    # TF-IDF & Title Handling
    vectorizer = TfidfVectorizer()
    tfidf_mat = vectorizer.fit_transform(processed_sents)
    
    effective_title = title
    if not effective_title or not effective_title.strip():
        effective_title = extract_tf_query(tfidf_mat, vectorizer)

    # Inference (NER)
    ner_results = predict_entities(raw_sentences)

    # Scoring & Ranking
    feature_matrix = compute_hybrid_scores(
        raw_sentences, effective_title, ner_results, tfidf_mat, vectorizer
    )
    
    final_scores = feature_matrix @ WEIGHTS
    
    # Selection
    n_select = max(1, int(len(raw_sentences) * compression_ratio))
    top_indices = np.argsort(final_scores)[-n_select:]
    top_indices.sort() 
    
    summary = " ".join([raw_sentences[i] for i in top_indices])

    # Entity Aggregation
    unique_entities = {}
    for idx in top_indices:
        for ent in ner_results[idx].get('entities', []):
            key = (ent['text'].lower(), ent['label'])
            if key not in unique_entities:
                # Ensure JSON serializable types
                clean_ent = {k: float(v) if isinstance(v, (np.floating, float)) else v 
                             for k, v in ent.items()}
                unique_entities[key] = clean_ent

    return {
        'summary': summary,
        'entities': list(unique_entities.values()),
        'effective_title': effective_title
    }