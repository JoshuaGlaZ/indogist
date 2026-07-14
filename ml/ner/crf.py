import tensorflow as tf
import keras


def crf_log_norm(emissions, transitions, mask):
    """
    Computes log-partition function log Z(P) using forward log-space dynamic programming with tf.while_loop.
    emissions: (B, T, K)
    transitions: (K, K)
    mask: (B, T) boolean tensor
    """
    alpha = emissions[:, 0, :]  # (B, K)
    seq_len = tf.shape(emissions)[1]
    
    def condition(t, alpha):
        return t < seq_len
        
    def body(t, alpha):
        emit_t = tf.expand_dims(emissions[:, t, :], axis=1)  # (B, 1, K)
        alpha_exp = tf.expand_dims(alpha, axis=2)  # (B, K, 1)
        trans_exp = tf.expand_dims(transitions, axis=0)  # (1, K, K)
        
        # score[b, i, j] = alpha[b, i] + transitions[i, j] + emissions[b, t, j]
        scores = alpha_exp + trans_exp + emit_t  # (B, K, K)
        alpha_next = tf.reduce_logsumexp(scores, axis=1)  # (B, K)
        
        mask_t = tf.expand_dims(mask[:, t], axis=-1)  # (B, 1)
        alpha = tf.where(mask_t, alpha_next, alpha)
        return (t + 1, alpha)

    _, alpha_final = tf.while_loop(
        condition,
        body,
        loop_vars=(tf.constant(1), alpha),
        maximum_iterations=seq_len,
    )
    return tf.reduce_logsumexp(alpha_final, axis=-1)


def crf_sequence_score(emissions, y_true, transitions, mask):
    """
    Computes real path score s(P, y) for ground truth tag sequence y_true.
    emissions: (B, T, K)
    y_true: (B, T) int32 ground truth tag indices
    transitions: (K, K)
    mask: (B, T) boolean tensor
    """
    num_classes = tf.shape(emissions)[2]
    y_true_one_hot = tf.one_hot(y_true, depth=num_classes)
    mask_float = tf.cast(mask, tf.float32)
    
    emit_scores = tf.reduce_sum(emissions * y_true_one_hot, axis=-1) * mask_float
    total_emit = tf.reduce_sum(emit_scores, axis=-1)
    
    y_curr = y_true[:, :-1]
    y_next = y_true[:, 1:]
    trans_indices = tf.stack([y_curr, y_next], axis=-1)
    trans_scores = tf.gather_nd(transitions, trans_indices)
    
    trans_mask = mask_float[:, :-1] * mask_float[:, 1:]
    total_trans = tf.reduce_sum(trans_scores * trans_mask, axis=-1)
    
    return total_emit + total_trans


def viterbi_decode_sample(emissions_sample, transitions, seq_len):
    """
    Decodes single sequence using Viterbi dynamic programming.
    emissions_sample: (T, K)
    transitions: (K, K)
    seq_len: int
    """
    if seq_len == 0:
        return []
    
    viterbi = emissions_sample[0, :]
    backpointers = []
    
    for t in range(1, seq_len):
        emit_t = emissions_sample[t, :]
        scores = tf.expand_dims(viterbi, axis=-1) + transitions  # (K, K)
        max_score = tf.reduce_max(scores, axis=0)  # (K,)
        best_prev = tf.argmax(scores, axis=0, output_type=tf.int32)  # (K,)
        viterbi = max_score + emit_t
        backpointers.append(best_prev.numpy() if hasattr(best_prev, 'numpy') else best_prev)
        
    best_last_tag = int(tf.argmax(viterbi, output_type=tf.int32).numpy() if hasattr(viterbi, 'numpy') else tf.argmax(viterbi))
    best_path = [best_last_tag]
    curr_tag = best_last_tag
    for bp in reversed(backpointers):
        curr_tag = int(bp[curr_tag])
        best_path.append(curr_tag)
    best_path.reverse()
    return best_path


def viterbi_decode_batch(emissions, transitions, mask=None):
    """
    Batched Viterbi decoding. Returns (B, T) tensor of predicted tag IDs.
    """
    B = tf.shape(emissions)[0]
    T = tf.shape(emissions)[1]
    
    if mask is None:
        mask = tf.ones((B, T), dtype=tf.bool)
        
    paths = []
    emissions_np = emissions.numpy() if hasattr(emissions, 'numpy') else emissions
    transitions_np = transitions.numpy() if hasattr(transitions, 'numpy') else transitions
    mask_np = mask.numpy() if hasattr(mask, 'numpy') else mask
    
    for b in range(B.numpy() if hasattr(B, 'numpy') else B):
        seq_l = int(tf.reduce_sum(tf.cast(mask_np[b], tf.int32)))
        if seq_l == 0:
            paths.append([0] * int(T))
            continue
        p = viterbi_decode_sample(emissions_np[b], transitions_np, seq_l)
        if len(p) < int(T):
            p.extend([0] * (int(T) - len(p)))
        paths.append(p)
        
    return tf.constant(paths, dtype=tf.int32)


@keras.saving.register_keras_serializable(package="ml.ner", name="CRFLayer")
class CRFLayer(keras.layers.Layer):
    """
    Custom Keras 3 CRF Layer.
    Maintains trainable transitions matrix (num_classes, num_classes).
    Output tensor passes emissions concatenated with transitions parameters.
    """
    def __init__(self, num_classes, **kwargs):
        super().__init__(**kwargs)
        self.num_classes = num_classes

    def build(self, input_shape):
        self.transitions = self.add_weight(
            name="transitions",
            shape=(self.num_classes, self.num_classes),
            initializer="glorot_uniform",
            trainable=True,
        )
        super().build(input_shape)

    def call(self, inputs, mask=None):
        # inputs: (batch, seq_len, num_classes)
        trans_expanded = tf.reshape(self.transitions, (1, 1, self.num_classes * self.num_classes))
        batch_size = tf.shape(inputs)[0]
        seq_len = tf.shape(inputs)[1]
        trans_tiled = tf.tile(trans_expanded, [batch_size, seq_len, 1])
        return tf.concat([inputs, trans_tiled], axis=-1)

    def decode(self, emissions, mask=None):
        return viterbi_decode_batch(emissions, self.transitions, mask)

    def get_config(self):
        config = super().get_config()
        config.update({"num_classes": self.num_classes})
        return config

    @classmethod
    def from_config(cls, config):
        return cls(**config)


@keras.saving.register_keras_serializable(package="ml.ner", name="crf_loss")
def crf_loss(y_true, y_pred):
    """
    Sequence negative log-likelihood loss for CRF model.
    """
    total_dim = tf.shape(y_pred)[-1]
    total_dim_float = tf.cast(total_dim, tf.float32)
    num_classes = tf.cast((-1.0 + tf.sqrt(1.0 + 4.0 * total_dim_float)) / 2.0, tf.int32)
    
    emissions = y_pred[:, :, :num_classes]
    trans_flat = y_pred[:, 0, num_classes:]
    transitions = tf.reshape(trans_flat[0], (num_classes, num_classes))
    
    y_true_int = tf.cast(y_true, tf.int32)
    mask = tf.not_equal(y_true_int, 0)
    
    log_z = crf_log_norm(emissions, transitions, mask)
    seq_score = crf_sequence_score(emissions, y_true_int, transitions, mask)
    
    loss_sample = log_z - seq_score
    return tf.reduce_mean(loss_sample)


@keras.saving.register_keras_serializable(package="ml.ner", name="crf_accuracy")
def crf_accuracy(y_true, y_pred):
    """
    Masked token accuracy metric ignoring PAD (index 0).
    """
    total_dim = tf.shape(y_pred)[-1]
    total_dim_float = tf.cast(total_dim, tf.float32)
    num_classes = tf.cast((-1.0 + tf.sqrt(1.0 + 4.0 * total_dim_float)) / 2.0, tf.int32)
    
    emissions = y_pred[:, :, :num_classes]
    y_true_int = tf.cast(y_true, tf.int32)
    preds = tf.argmax(emissions, axis=-1, output_type=tf.int32)
    
    mask = tf.cast(tf.not_equal(y_true_int, 0), tf.float32)
    matches = tf.cast(tf.equal(y_true_int, preds), tf.float32) * mask
    
    return tf.reduce_sum(matches) / (tf.reduce_sum(mask) + 1e-12)
