import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .utils import text_to_sentences, preprocess_tfidf, extract_tf_query
from ml.ner.loader import stemmer, stopword_remover


def summarize_traditional(text, title, compression_ratio=0.3, stream=False):
    """
    If stream=True, acts as a generator yielding progress steps: {'step': N}
    until the final {'step': 4, 'result': ...}.
    Otherwise, returns the final summary text directly.
    """
    def _generator():
        # --- Step 1: Preprocessing ---
        yield {'step': 1}

        sentences = text_to_sentences(text)
        n_sentences = len(sentences)

        processed_sents = preprocess_tfidf(sentences)
        processed_title = stopword_remover.remove(stemmer.stem(title))

        tfidf_vectorizer = TfidfVectorizer()
        tfidf_matrix = tfidf_vectorizer.fit_transform(processed_sents)

        # --- Step 2: Analyzing ---
        yield {'step': 2}

        effective_processed_title = ""
        effective_title = title
        if title and title.strip():
            effective_processed_title = stopword_remover.remove(stemmer.stem(title))
        else:
            effective_title = extract_tf_query(tfidf_matrix, tfidf_vectorizer)
            effective_processed_title = effective_title

        title_scores = np.zeros(n_sentences)
        if effective_processed_title:
            title_tfidf_vector = tfidf_vectorizer.transform([effective_processed_title])
            title_scores = cosine_similarity(
                tfidf_matrix, title_tfidf_vector).flatten()

        location_scores = np.array(
            [((n_sentences - i) / n_sentences) for i in range(n_sentences)])
        frequency_scores = np.asarray(tfidf_matrix.sum(axis=1)).ravel()

        similarity_matrix = cosine_similarity(tfidf_matrix, tfidf_matrix)
        np.fill_diagonal(similarity_matrix, 0)
        aggregation_scores = similarity_matrix.sum(axis=1)

        # --- Step 3: Scoring & Selection ---
        yield {'step': 3}

        def normalize(arr):
            if arr.max() > arr.min():
                return (arr - arr.min()) / (arr.max() - arr.min())
            return np.zeros_like(arr)

        final_scores = title_scores + location_scores + \
            (normalize(frequency_scores) * normalize(aggregation_scores))

        num_summary_sentences = max(1, round(n_sentences * compression_ratio))
        top_indices = np.argsort(final_scores)[-num_summary_sentences:]
        sorted_indices = sorted(top_indices)

        summary = " ".join([sentences[i] for i in sorted_indices])

        # --- Step 4: Done ---
        yield {
            'step': 4,
            'result': {
                'summary': summary,
                'entities': [],
                'effective_title': effective_title
            }
        }

    if stream:
        return _generator()
    else:
        # Run the generator to exhaustion and return just the summary string
        # for backwards compatibility with non-streamed calls
        result_text = ""
        for step_data in _generator():
            if step_data.get('step') == 4 and 'result' in step_data:
                result_text = step_data['result']['summary']
        return result_text
