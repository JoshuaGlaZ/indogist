import hashlib
from collections import OrderedDict

import numpy as np
from tensorflow.keras.preprocessing.sequence import pad_sequences

from ml.ner.loader import nlp_service

_MAX_CACHE_SIZE = 1000
_ner_cache: OrderedDict = OrderedDict()


def extract_entities_from_tags(tokens, tags, confidences):
    """Extracts entity spans from BIO-tagged token sequences with confidences."""
    entities, current_entity = [], None
    for token, tag, conf in zip(tokens, tags, confidences, strict=False):
        conf = float(conf)

        if tag.startswith("B-"):
            if current_entity:
                current_entity["confidence"] = float(np.mean(current_entity["conf_scores"]))
                del current_entity["conf_scores"]
                entities.append(current_entity)
            current_entity = {"label": tag[2:], "text": token, "conf_scores": [conf]}
        elif tag.startswith("I-") and current_entity and tag[2:] == current_entity["label"]:
            current_entity["text"] += " " + token
            current_entity["conf_scores"].append(conf)
        else:
            if current_entity:
                current_entity["confidence"] = float(np.mean(current_entity["conf_scores"]))
                del current_entity["conf_scores"]
                entities.append(current_entity)
            current_entity = None

    if current_entity:
        current_entity["confidence"] = float(np.mean(current_entity["conf_scores"]))
        del current_entity["conf_scores"]
        entities.append(current_entity)
    return entities


def get_sentence_hash(sentence):
    """Generate a consistent hash for a sentence for caching purposes."""
    return hashlib.md5(sentence.encode("utf-8")).hexdigest()


def predict_entities(sentences):
    """Predicts entities on a list of sentences using the NLPService, with caching and optimizations."""
    import re

    if not sentences:
        return []

    # Check via Singleton
    if not nlp_service.is_ready():
        print(" Warning: NER model components not initialized via NLPService.")
        return [{"sentence": s, "tokens": s.split(), "entities": []} for s in sentences]

    def clean_and_space_punctuation(text):
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
        text = re.sub(r"\s+", " ", text).strip()
        # (Koma, Titik, Titik Dua, Titik Koma)
        #    HANYA JIKA berada di AKHIR kata (diikuti spasi atau akhir string).
        #    Regex: (?<=\S)  = Lookbehind: Sebelumnya harus ada karakter (bukan spasi)
        #           ([,.:;?!]) = Group 1: Tanda baca target
        #           (?=\s|$) = Lookahead: Setelahnya harus spasi atau akhir kalimat
        #
        #    Ini menjaga "22.61" (karena setelah titik adalah angka '6', bukan spasi)
        #    Ini menjaga "Haposan," (karena setelah koma adalah spasi/akhir)
        text = re.sub(r"(?<=\S)([,.:;?!])(?=\s|$)", r" \1", text)
        return text

    cached_results = []
    uncached_sentences = []
    uncached_indices = []

    for i, s in enumerate(sentences):
        s_hash = f"ner_sent_{get_sentence_hash(s)}"
        cached_result = _ner_cache.get(s_hash)
        if cached_result:
            cached_results.append((i, cached_result))
        else:
            uncached_sentences.append(s)
            uncached_indices.append(i)

    # Return immediately if everything is cached
    if not uncached_sentences:
        return [res for idx, res in sorted(cached_results, key=lambda x: x[0])]

    try:
        # Tokenization of uncached sentences
        tokenized_sents = [clean_and_space_punctuation(s).split() for s in uncached_sentences]

        # Token -> string
        text_inputs = [" ".join(s) for s in tokenized_sents]

        # Vectorize
        X_seq = nlp_service.vectorizer(text_inputs).numpy()

        # Find the max length in THIS batch, bounded by the model's absolute max length
        batch_max_len = min(nlp_service.max_len, max((len(seq) for seq in X_seq), default=0))
        # Ensure at least length 1 to avoid empty tensor errors
        batch_max_len = max(1, batch_max_len)

        # Padding (only up to batch_max_len instead of fully to 256)
        X_padded = pad_sequences(X_seq, maxlen=batch_max_len, padding="post", value=0)

        # Inference via Keras model or TFLite Interpreter
        if getattr(nlp_service, "is_keras_model", False):
            if nlp_service.pos_to_idx is not None:
                if nlp_service.pos_tagger is not None:
                    doc = nlp_service.pos_tagger(tokenized_sents)
                    pos_sequences = []
                    for sent in doc.sentences:
                        pos_tags = [w.upos for w in sent.words]
                        pos_ids = [nlp_service.pos_to_idx.get(tag, 0) for tag in pos_tags]
                        pos_sequences.append(pos_ids)
                    pos_padded = pad_sequences(
                        pos_sequences, maxlen=batch_max_len, padding="post", value=0
                    )
                else:
                    pos_padded = np.zeros_like(X_padded)
                preds_probs = nlp_service.ner_model([X_padded, pos_padded]).numpy()
            else:
                preds_probs = nlp_service.ner_model(X_padded).numpy()
        else:
            interpreter = nlp_service.ner_model
            input_details = interpreter.get_input_details()
            output_details = interpreter.get_output_details()[0]

            if (
                len(input_details) > 1
                and nlp_service.pos_to_idx is not None
                and nlp_service.pos_tagger is not None
            ):
                # POS Tagging via Stanza (pre-tokenized)
                doc = nlp_service.pos_tagger(tokenized_sents)
                pos_sequences = []
                for sent in doc.sentences:
                    pos_tags = [w.upos for w in sent.words]
                    pos_ids = [nlp_service.pos_to_idx.get(tag, 0) for tag in pos_tags]
                    pos_sequences.append(pos_ids)

                pos_padded = pad_sequences(
                    pos_sequences, maxlen=batch_max_len, padding="post", value=0
                )

                word_detail = next(
                    (d for d in input_details if "word" in d["name"]), input_details[0]
                )
                pos_detail = next(
                    (d for d in input_details if "pos" in d["name"]), input_details[1]
                )

                interpreter.resize_tensor_input(word_detail["index"], X_padded.shape)
                interpreter.resize_tensor_input(pos_detail["index"], pos_padded.shape)
                interpreter.allocate_tensors()

                interpreter.set_tensor(word_detail["index"], X_padded.astype(word_detail["dtype"]))
                interpreter.set_tensor(pos_detail["index"], pos_padded.astype(pos_detail["dtype"]))
            else:
                # Fallback for single-input baseline models
                detail = input_details[0]
                interpreter.resize_tensor_input(detail["index"], X_padded.shape)
                interpreter.allocate_tensors()
                interpreter.set_tensor(detail["index"], X_padded.astype(detail["dtype"]))

            interpreter.invoke()
            preds_probs = interpreter.get_tensor(output_details["index"])

        pred_ids = np.argmax(preds_probs, axis=-1)
        confidences = np.max(preds_probs, axis=-1)

        # Decoding (Map ID -> Tag -> Entity)
        results = []
        for i, (tokens, ids, confs) in enumerate(
            zip(tokenized_sents, pred_ids, confidences, strict=False)
        ):
            num_tokens = len(tokens)
            tags = [nlp_service.idx_to_tag.get(pid, "O") for pid in ids[:num_tokens]]
            token_confidences = confs[:num_tokens]

            entities = extract_entities_from_tags(tokens, tags, token_confidences)

            result = {
                "sentence": uncached_sentences[i],
                "tokens": tokens,
                "entities": entities,
            }
            results.append(result)

            s_hash = f"ner_sent_{get_sentence_hash(uncached_sentences[i])}"
            _ner_cache[s_hash] = result
            if len(_ner_cache) > _MAX_CACHE_SIZE:
                _ner_cache.popitem(last=False)

        # Reconstruct final list in original order
        final_results = [None] * len(sentences)
        for original_idx, res in cached_results:
            final_results[original_idx] = res
        for new_idx, res in zip(uncached_indices, results, strict=False):
            final_results[new_idx] = res

        return final_results

    except Exception as e:
        print(f"Error in predict_entities: {e}")
        # Fallback for errors to prevent complete failure
        fallback = [
            {"sentence": s, "tokens": s.split(), "entities": []} for s in uncached_sentences
        ]

        final_results = [None] * len(sentences)
        for original_idx, res in cached_results:
            final_results[original_idx] = res
        for new_idx, res in zip(uncached_indices, fallback, strict=False):
            final_results[new_idx] = res

        return final_results
