import tensorflow as tf

def masked_sparse_cce(y_true, y_pred):
    """Custom loss function that ignores padded tokens (index 0)."""
    loss_obj = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=False, reduction='none')
    loss = loss_obj(y_true, y_pred)
    mask = tf.cast(tf.not_equal(y_true, 0), dtype=loss.dtype)  # PAD_INDEX 0
    loss *= mask
    return tf.reduce_sum(loss) / (tf.reduce_sum(mask) + 1e-12)

def masked_accuracy(y_true, y_pred):
    """Custom accuracy metric that ignores padded tokens (index 0)."""
    preds = tf.argmax(y_pred, axis=-1, output_type=y_true.dtype)
    matches = tf.cast(tf.equal(y_true, preds), tf.float32)
    mask = tf.cast(tf.not_equal(y_true, 0), tf.float32)  # PAD_INDEX 0
    return tf.reduce_sum(matches * mask) / (tf.reduce_sum(mask) + 1e-12)
