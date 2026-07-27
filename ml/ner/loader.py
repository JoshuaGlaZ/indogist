import json
import os
import pickle
from pathlib import Path

import joblib
import nltk
import tensorflow as tf
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
from tensorflow.keras.layers import TextVectorization

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _safe_load_keras_model(keras_path, custom_objects=None):
    import zipfile

    from tensorflow import keras

    try:
        return keras.models.load_model(keras_path, custom_objects=custom_objects)
    except Exception as e:
        err_msg = str(e)
        if "quantization_config" in err_msg or "deserialized" in err_msg:
            try:
                with zipfile.ZipFile(keras_path, "r") as z_in:
                    if "config.json" in z_in.namelist():
                        cfg = json.loads(z_in.read("config.json").decode("utf-8"))

                        def remove_key(d, key):
                            if isinstance(d, dict):
                                d.pop(key, None)
                                for v in d.values():
                                    remove_key(v, key)
                            elif isinstance(d, list):
                                for item in d:
                                    remove_key(item, key)

                        remove_key(cfg, "quantization_config")
                        tmp_path = keras_path + ".tmp.keras"
                        try:
                            with zipfile.ZipFile(tmp_path, "w") as z_out:
                                for item in z_in.infolist():
                                    data = z_in.read(item.filename)
                                    if item.filename == "config.json":
                                        data = json.dumps(cfg).encode("utf-8")
                                    z_out.writestr(item, data)
                            model = keras.models.load_model(tmp_path, custom_objects=custom_objects)
                            print(
                                "NLPService: Loaded Keras model successfully after stripping incompatible deserialization keys."
                            )
                            return model
                        finally:
                            if os.path.exists(tmp_path):
                                os.remove(tmp_path)
            except Exception as inner_e:
                print(f"NLPService Warning: Secondary Keras load attempt failed: {inner_e}")
        raise


def _log_service(msg: str, level: str = "info"):
    try:
        from rich.console import Console

        console = Console()
        if level == "info":
            console.print(f"[bold cyan][NLPService][/bold cyan] {msg}")
        elif level == "warning":
            console.print(f"[bold yellow][NLPService Warning][/bold yellow] {msg}")
        elif level == "error":
            console.print(f"[bold red][NLPService Error][/bold red] {msg}")
        elif level == "success":
            console.print(f"[bold green][NLPService][/bold green] {msg}")
    except Exception:
        print(f"NLPService [{level.upper()}]: {msg}")


class NLPService:
    """
    Singleton service to handle loading heavy NLP models once.
    This prevents memory leaks and repeated loading overhead.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return

        self.ner_model = None
        self.vectorizer = None
        self.idx_to_tag = {}
        self.max_len = 256
        self.pos_to_idx = None
        self.pos_tagger = None
        self.stemmer = None
        self.stopword_remover = None
        self.is_keras_model = False

        # Load models immediately upon instantiation
        self.load_models()
        self.initialized = True

    def load_models(self):
        _log_service("Initializing ML models & text processing pipelines...")

        # 1. Initialize Lightweight Tools (Sastrawi/NLTK)
        self.stemmer = StemmerFactory().create_stemmer()
        self.stopword_remover = StopWordRemoverFactory().create_stop_word_remover()
        try:
            nltk.data.find("tokenizers/punkt")
        except LookupError:
            nltk.download("punkt", quiet=True)

        # 2. Locate Best Model Directory (POS model prioritized over baseline)
        models_root = os.path.join(str(BASE_DIR), "ml", "models")
        model_dir = None

        if os.path.exists(models_root):
            final_pos_dir = os.path.join(models_root, "ner_pos_final")
            if os.path.exists(final_pos_dir):
                model_dir = final_pos_dir
            else:
                pos_dirs = sorted(
                    [
                        d
                        for d in os.listdir(models_root)
                        if (
                            d.startswith(("ner_pos_experiment_", "ner_experiment_pos_"))
                            or d == "ner_experiment_pos_10-May-2026_10.00"
                        )
                        and os.path.isdir(os.path.join(models_root, d))
                    ],
                    reverse=True,
                )
                if pos_dirs:
                    model_dir = os.path.join(models_root, pos_dirs[0])

        if not model_dir:
            model_dir = os.path.join(models_root, "ner_experiment_30-November-2025_13.35")

        tflite_path = os.path.join(model_dir, "optimized_model.tflite")
        _log_service(f"Loading model artifacts from [cyan]{os.path.basename(model_dir)}[/cyan]")

        try:
            if os.path.exists(tflite_path):
                # Check for Keras model first to avoid Flex op TFLite interpreter issues
                keras_path = os.path.join(model_dir, "best_model_by_f1.keras")
                model_loaded = False
                if os.path.exists(keras_path):
                    try:
                        from ml.ner.utils import masked_accuracy, masked_sparse_cce

                        self.ner_model = _safe_load_keras_model(
                            keras_path,
                            custom_objects={
                                "masked_sparse_cce": masked_sparse_cce,
                                "masked_accuracy": masked_accuracy,
                            },
                        )
                        self.is_keras_model = True
                        model_loaded = True
                        _log_service("Keras model loaded successfully.", level="success")
                    except Exception as keras_err:
                        _log_service(
                            f"Failed to load Keras model ({keras_err}). Falling back to TFLite.",
                            level="warning",
                        )

                if not model_loaded:
                    self.ner_model = tf.lite.Interpreter(model_path=tflite_path)
                    self.ner_model.allocate_tensors()
                    self.is_keras_model = False
                    _log_service("TFLite model loaded successfully.", level="success")

                vect_path = os.path.join(model_dir, "vectorizer.pkl")
                if os.path.exists(vect_path):
                    with open(vect_path, "rb") as f:
                        vect_data = pickle.load(f)
                    self.vectorizer = TextVectorization.from_config(vect_data["config"])
                    self.vectorizer.set_vocabulary(vect_data["vocabulary"])

                tag_to_idx = joblib.load(os.path.join(model_dir, "tag_to_idx.pkl"))
                self.idx_to_tag = {idx: tag for tag, idx in tag_to_idx.items()}

                # Load POS artifacts if present
                pos_path = os.path.join(model_dir, "pos_to_idx.pkl")
                if os.path.exists(pos_path):
                    self.pos_to_idx = joblib.load(pos_path)
                    try:
                        import stanza

                        self.pos_tagger = stanza.Pipeline(
                            "id",
                            processors="tokenize,pos",
                            tokenize_pretokenized=True,
                            download_method=None,
                            verbose=False,
                        )
                        _log_service(
                            "Stanza POS tagger initialized from local cache.",
                            level="success",
                        )
                    except Exception as e:
                        self.pos_tagger = None
                        _log_service(
                            f"Stanza POS tagger disabled ({e}). Using default zero-padded POS embeddings.",
                            level="info",
                        )

                # Load Config
                try:
                    with open(os.path.join(model_dir, "experiment_results.json")) as f:
                        res = json.load(f)
                        self.max_len = res.get("config", {}).get("max_cap_len", 256)
                except Exception:
                    self.max_len = 256

                _log_service("Model initialization complete.", level="success")
            else:
                _log_service(f"TFLite model not found at {tflite_path}", level="error")

        except Exception as e:
            _log_service(f"Error during model load: {e}", level="error")

    def is_ready(self):
        return self.ner_model is not None and self.vectorizer is not None

    def get_status(self) -> dict:
        """
        Returns a dictionary representing the in-memory singleton state of loaded models and pipelines.
        """
        model_fmt = (
            "Keras" if self.is_keras_model else ("TFLite" if self.ner_model is not None else "None")
        )

        vocab_len = 0
        if self.vectorizer is not None:
            try:
                vocab_len = len(self.vectorizer.get_vocabulary())
            except Exception:
                vocab_len = 0

        pos_status = "Disabled"
        if self.pos_tagger is not None:
            pos_status = "Stanza (Local Cache)"
        elif self.pos_to_idx is not None:
            pos_status = "Zero-padded (Fallback)"

        return {
            "is_ready": self.is_ready(),
            "model_format": model_fmt,
            "is_keras_model": self.is_keras_model,
            "has_ner_model": self.ner_model is not None,
            "has_vectorizer": self.vectorizer is not None,
            "vocab_size": vocab_len,
            "max_len": self.max_len,
            "tag_count": len(self.idx_to_tag),
            "pos_tagger_status": pos_status,
            "has_stemmer": self.stemmer is not None,
            "has_stopword_remover": self.stopword_remover is not None,
        }

    def print_status(self) -> None:
        """Prints rich formatted model availability status to terminal."""
        try:
            from ml.status import check_models

            check_models(verbose=True)
        except Exception:
            st = self.get_status()
            print(
                f"[NLPService] Readiness: {st['is_ready']} | Format: {st['model_format']} | Vocab: {st['vocab_size']}"
            )


nlp_service = NLPService()

ner_model = nlp_service.ner_model
vectorizer = nlp_service.vectorizer
idx_to_tag = nlp_service.idx_to_tag
pos_to_idx = nlp_service.pos_to_idx
pos_tagger = nlp_service.pos_tagger
max_len = nlp_service.max_len
stemmer = nlp_service.stemmer
stopword_remover = nlp_service.stopword_remover
