import os

import tensorflow as tf


def masked_sparse_cce(y_true, y_pred):
    """Custom loss function that ignores padded tokens."""
    loss_obj = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=False, reduction="none")
    loss = loss_obj(y_true, y_pred)
    mask = tf.cast(tf.not_equal(y_true, 0), dtype=loss.dtype)  # PAD_INDEX 0
    loss *= mask
    return tf.reduce_sum(loss) / (tf.reduce_sum(mask) + 1e-12)


def masked_accuracy(y_true, y_pred):
    """Custom accuracy metric that ignores padded tokens."""
    preds = tf.argmax(y_pred, axis=-1, output_type=y_true.dtype)
    matches = tf.cast(tf.equal(y_true, preds), tf.float32)
    mask = tf.cast(tf.not_equal(y_true, 0), tf.float32)  # PAD_INDEX 0
    return tf.reduce_sum(matches * mask) / (tf.reduce_sum(mask) + 1e-12)


def convert_to_tflite():
    base_dir = os.path.abspath(os.path.dirname(__file__))
    model_dir = os.path.join(base_dir, "models", "ner_experiment_30-November-2025_13.35")

    model_path = os.path.join(model_dir, "best_model_by_f1.keras")
    if not os.path.exists(model_path):
        model_path = os.path.join(model_dir, "model.keras")
        if not os.path.exists(model_path):
            print(f"Error: Could not find keras model in {model_dir}")
            return

    print(f"Loading keras model from {model_path}...")
    model = tf.keras.models.load_model(
        model_path,
        custom_objects={
            "masked_sparse_cce": masked_sparse_cce,
            "masked_accuracy": masked_accuracy,
        },
    )

    print("Converting to TFLite (with CPU quantization)...")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)

    # Enable dynamic range quantization for massive CPU speedup and size reduction
    converter.optimizations = [tf.lite.Optimize.DEFAULT]

    # Required for LSTM/RNNs with dynamic shapes
    converter.target_spec.supported_ops = [
        tf.lite.OpsSet.TFLITE_BUILTINS,
        tf.lite.OpsSet.SELECT_TF_OPS,
    ]
    converter._experimental_lower_tensor_list_ops = False

    tflite_model = converter.convert()

    out_path = os.path.join(model_dir, "optimized_model.tflite")
    with open(out_path, "wb") as f:
        f.write(tflite_model)

    print(f"Successfully saved TFLite model to {out_path}")
    print(f"Original size: {os.path.getsize(model_path) / (1024 * 1024):.2f} MB")
    print(f"TFLite size: {os.path.getsize(out_path) / (1024 * 1024):.2f} MB")


if __name__ == "__main__":
    convert_to_tflite()
