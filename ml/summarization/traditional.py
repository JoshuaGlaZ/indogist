import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .utils import text_to_sentences, preprocess_tfidf, extract_tf_query
from ml.ner.loader import stemmer, stopword_remover


def summarize_traditional(text, title, compression_ratio=0.3):
    """
    Generates a summary using the traditional method without NER features.
    """
    sentences = text_to_sentences(text)
    n_sentences = len(sentences)
    # if n_sentences == 0: return ""

    processed_sents = preprocess_tfidf(sentences)
    processed_title = stopword_remover.remove(stemmer.stem(title))

    # if not any(processed_sents):
    #     return sentences[0] if sentences else ""

    tfidf_vectorizer = TfidfVectorizer()
    tfidf_matrix = tfidf_vectorizer.fit_transform(processed_sents)

    processed_title = ""
    if title and title.strip():
        processed_title = stopword_remover.remove(stemmer.stem(title))
    else:
        title = extract_tf_query(tfidf_matrix, tfidf_vectorizer)
        processed_title = title
    title_scores = np.zeros(n_sentences)
    if processed_title:
        title_tfidf_vector = tfidf_vectorizer.transform([processed_title])
        title_scores = cosine_similarity(
            tfidf_matrix, title_tfidf_vector).flatten()

    location_scores = np.array(
        [((n_sentences - i) / n_sentences) for i in range(n_sentences)])
    frequency_scores = np.asarray(tfidf_matrix.sum(axis=1)).ravel()

    similarity_matrix = cosine_similarity(tfidf_matrix, tfidf_matrix)
    np.fill_diagonal(similarity_matrix, 0) # kalimat terhadap dirinya sendiri
    aggregation_scores = similarity_matrix.sum(axis=1) # kalimat terhadap kalimat lain

    def normalize(arr):
        if arr.max() > arr.min():
            return (arr - arr.min()) / (arr.max() - arr.min())
        return np.zeros_like(arr)

    final_scores = title_scores + location_scores + \
        (normalize(frequency_scores) * normalize(aggregation_scores))

    num_summary_sentences = max(1, round(n_sentences * compression_ratio))
    top_indices = np.argsort(final_scores)[-num_summary_sentences:]
    sorted_indices = sorted(top_indices)

    return " ".join([sentences[i] for i in sorted_indices])
