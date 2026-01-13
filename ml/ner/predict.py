import numpy as np
from tensorflow.keras.preprocessing.sequence import pad_sequences
from ml.ner.loader import nlp_service

def extract_entities_from_tags(tokens, tags, confidences):
    """Extracts entity spans from BIO-tagged token sequences with confidences."""
    entities, current_entity = [], None
    for i, (token, tag, conf) in enumerate(zip(tokens, tags, confidences)):
        conf = float(conf)
        if tag.startswith("B-"):
            if current_entity:
                current_entity['confidence'] = float(
                    np.mean(current_entity['conf_scores']))
                del current_entity['conf_scores']
                entities.append(current_entity)
            current_entity = {"label": tag[2:],
                              "text": token, "conf_scores": [conf]}
        elif tag.startswith("I-") and current_entity and tag[2:] == current_entity["label"]:
            current_entity["text"] += " " + token
            current_entity["conf_scores"].append(conf)
        else:
            if current_entity:
                current_entity['confidence'] = float(
                    np.mean(current_entity['conf_scores']))
                del current_entity['conf_scores']
                entities.append(current_entity)
            current_entity = None

    if current_entity:
        current_entity['confidence'] = float(
            np.mean(current_entity['conf_scores']))
        del current_entity['conf_scores']
        entities.append(current_entity)
    return entities


def predict_entities(sentences):
    """Predicts entities on a list of sentences using the NLPService."""
    import re
    if not sentences:
        return []

    # Check via Singleton
    if not nlp_service.is_ready():
        print(" Warning: NER model components not initialized via NLPService.")
        return [{'sentence': s, 'tokens': s.split(), 'entities': []} for s in sentences]

    def clean_and_space_punctuation(text):
        import re
        """
        1. "(LSI)"        -> "(LSI)"      
        2. "21%"          -> "21%"         
        3. "non-kader"    -> "non-kader" 
        4. "22.61"        -> "22.61"     
        5. "Haposan,"     -> "Haposan ," 
        6. "terjadi."     -> "terjadi ." 
        7. "(Situbondo)," -> "(Situbondo) ,"
        """
        # whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # (Koma, Titik, Titik Dua, Titik Koma) 
        #    HANYA JIKA berada di AKHIR kata (diikuti spasi atau akhir string).
        #    Regex: (?<=\S)  = Lookbehind: Sebelumnya harus ada karakter (bukan spasi)
        #           ([,.:;?!]) = Group 1: Tanda baca target
        #           (?=\s|$) = Lookahead: Setelahnya harus spasi atau akhir kalimat
        #
        #    Ini menjaga "22.61" (karena setelah titik adalah angka '6', bukan spasi)
        #    Ini menjaga "Haposan," (karena setelah koma adalah spasi/akhir)
        text = re.sub(r'(?<=\S)([,.:;?!])(?=\s|$)', r' \1', text)
        return text

    try:
        # Tokenization
        tokenized_sents = [clean_and_space_punctuation(s).split() for s in sentences]

        # Token -> string
        text_inputs = [" ".join(s) for s in tokenized_sents]

        # Vectorize
        X_seq = nlp_service.vectorizer(text_inputs).numpy()

        # Padding
        X_padded = pad_sequences(
            X_seq, maxlen=nlp_service.max_len, padding="post", value=0)

        # Inference
        preds_probs = nlp_service.ner_model.predict(X_padded, verbose=0, batch_size=256)
        pred_ids = np.argmax(preds_probs, axis=-1)
        confidences = np.max(preds_probs, axis=-1)

        # Decoding (Map ID -> Tag -> Entity)
        results = []
        for i, (tokens, ids, confs) in enumerate(zip(tokenized_sents, pred_ids, confidences)):
            num_tokens = len(tokens)
            tags = [nlp_service.idx_to_tag.get(pid, "O") for pid in ids[:num_tokens]]
            token_confidences = confs[:num_tokens]

            entities = extract_entities_from_tags(
                tokens, tags, token_confidences)
            results.append({
                'sentence': sentences[i],
                'tokens': tokens,
                'entities': entities
            })

        return results
    except Exception as e:
        print(f"Error in predict_entities: {e}")
        return [{'sentence': s, 'tokens': s.split(), 'entities': []} for s in sentences]