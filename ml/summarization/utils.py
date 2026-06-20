import numpy as np
import nltk
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
from ml.ner.loader import stemmer, stopword_remover


def tokens_to_text(token_lists):
    if not isinstance(token_lists, list):
        return ""
    return " ".join([" ".join(map(str, sentence)) for sentence in token_lists])


def text_to_sentences(full_text):
    return nltk.tokenize.sent_tokenize(full_text)


def preprocess_tfidf(sentences):
    processed_sents = []
    for sent in sentences:
        stemmed = stemmer.stem(sent)
        stopwords_removed = stopword_remover.remove(stemmed)
        processed_sents.append(stopwords_removed)
    return processed_sents

def extract_tf_query(tfidf_matrix, vectorizer, top_n=10):
    """fitur tf-based query"""
    sum_scores = np.asarray(tfidf_matrix.sum(axis=0)).ravel()
    top_indices = sum_scores.argsort()[::-1][:top_n]
    features = vectorizer.get_feature_names_out()
    return " ".join([features[i] for i in top_indices])


def add_to_indosum_dataset(title, text, summary, user):
    """
    - paragraphs: [[['word', 'word'], ['sentence2']], [['para2']]]
    - summary: ['sentence1', 'sentence2']
    - category: 'user-submission'
    """
    
    dataset_dir = os.path.join(str(BASE_DIR), 'data', 'indosum')
    if not os.path.exists(dataset_dir):
        os.makedirs(dataset_dir)
        
    target_file = os.path.join(dataset_dir, 'user_fold.jsonl')
    
    raw_paragraphs = text.split('\n\n')
    structured_paragraphs = []
    
    for p in raw_paragraphs:
        clean_p = p.strip()
        if not clean_p:
            continue
            
        sents = nltk.tokenize.sent_tokenize(clean_p)
        tokenized_sents = [nltk.tokenize.word_tokenize(s) for s in sents]
        structured_paragraphs.append(tokenized_sents)
        
    summary_sentences = nltk.tokenize.sent_tokenize(summary)
    new_id = f"user-{uuid.uuid4().hex[:10]}"

    entry = {
        "id": new_id,
        "paragraphs": structured_paragraphs,
        "summary": summary_sentences,
        "gold_labels": [],
        "category": "user-contribution",
        "source": str(user),
        "source_url": "",
        "title": title,
        "created_at": datetime.now().isoformat()
    }
    
    try:
        with open(target_file, 'a', encoding='utf-8') as f:
            json_str = json.dumps(entry, ensure_ascii=False)
            f.write(json_str + '\n')
            
        print(f"[INFO] Added summary {entry['id']} to dataset.")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to save to dataset: {e}")
        raise e