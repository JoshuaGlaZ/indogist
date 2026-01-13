import os
import json
import joblib
import pickle
from django.conf import settings
from tensorflow.keras.models import load_model
from tensorflow.keras.layers import TextVectorization
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
import nltk
import tensorflow as tf
import numpy as np

# --- Custom Keras Objects ---
def masked_sparse_cce(y_true, y_pred):
    """Custom loss function that ignores padded tokens."""
    loss_obj = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=False, reduction='none')
    loss = loss_obj(y_true, y_pred)
    mask = tf.cast(tf.not_equal(y_true, 0), dtype=loss.dtype) # PAD_INDEX 0
    loss *= mask
    return tf.reduce_sum(loss) / (tf.reduce_sum(mask) + 1e-12)

def masked_accuracy(y_true, y_pred):
    """Custom accuracy metric that ignores padded tokens."""
    preds = tf.argmax(y_pred, axis=-1, output_type=y_true.dtype)
    matches = tf.cast(tf.equal(y_true, preds), tf.float32)
    mask = tf.cast(tf.not_equal(y_true, 0), tf.float32) # PAD_INDEX 0
    return tf.reduce_sum(matches * mask) / (tf.reduce_sum(mask) + 1e-12)

class NLPService:
    """
    Singleton service to handle loading heavy NLP models once.
    This prevents memory leaks and repeated loading overhead.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NLPService, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return
            
        self.ner_model = None
        self.vectorizer = None
        self.idx_to_tag = None
        self.max_len = 256
        self.stemmer = None
        self.stopword_remover = None
        
        # Load models immediately upon instantiation
        self.load_models()
        self.initialized = True

    def load_models(self):
        print("NLPService: Initializing models...")
        
        # 1. Initialize Lightweight Tools (Sastrawi/NLTK)
        self.stemmer = StemmerFactory().create_stemmer()
        self.stopword_remover = StopWordRemoverFactory().create_stop_word_remover()
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)

        # 2. Load Deep Learning Models (Heavy)
        model_dir = os.path.join(settings.BASE_DIR, 'ml', 'models', 'ner_experiment_30-November-2025_13.35')
        model_path = os.path.join(model_dir, "best_model_by_f1.keras")
        
        # Fallback to standard name if best_model doesn't exist
        if not os.path.exists(model_path):
             model_path = os.path.join(model_dir, "model.keras")

        try:
            if os.path.exists(model_path):
                self.ner_model = load_model(
                    model_path,
                    custom_objects={'masked_sparse_cce': masked_sparse_cce, 'masked_accuracy': masked_accuracy}
                )
            
                vect_path = os.path.join(model_dir, "vectorizer.pkl")
                if os.path.exists(vect_path):
                    with open(vect_path, "rb") as f:
                        vect_data = pickle.load(f)
                    self.vectorizer = TextVectorization.from_config(vect_data['config'])
                    self.vectorizer.set_vocabulary(vect_data['vocabulary'])
                
                tag_to_idx = joblib.load(os.path.join(model_dir, "tag_to_idx.pkl"))
                self.idx_to_tag = {idx: tag for tag, idx in tag_to_idx.items()}

                # Load Config
                try:
                    with open(os.path.join(model_dir, "experiment_results.json"), 'r') as f:
                        res = json.load(f)
                        self.max_len = res.get('config', {}).get('max_cap_len', 256)
                except:
                    self.max_len = 256
                
                print("NLPService: Deep learning models loaded successfully.")
            else:
                print(f" NLPService Warning: Model file not found at {model_path}")

        except Exception as e:
            print(f"NLPService Error: {e}")

    def is_ready(self):
        return self.ner_model is not None and self.vectorizer is not None

nlp_service = NLPService()

ner_model = nlp_service.ner_model
vectorizer = nlp_service.vectorizer
idx_to_tag = nlp_service.idx_to_tag
max_len = nlp_service.max_len
stemmer = nlp_service.stemmer
stopword_remover = nlp_service.stopword_remover

def load_all_models():
    pass