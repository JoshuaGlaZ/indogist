import keras
import numpy as np
import tensorflow as tf
from ml.ner.crf import CRFLayer, crf_loss, crf_accuracy


def build_bilstm_crf_model(
    vocab_size: int,
    num_pos_tags: int,
    num_classes: int,
    embed_dim: int = 150,
    pos_embed_dim: int = 16,
    lstm_units: int = 128,
    dropout: float = 0.3,
    learning_rate: float = 0.005,
    embedding_matrix: np.ndarray = None,
    trainable_embeddings: bool = True,
    num_lstm_layers: int = 2,
) -> keras.Model:
    """
    Builds and compiles a dual-input BiLSTM-CRF Keras model incorporating Word & PoS Tag features.
    
    Inputs:
        word_input: Tensor of shape (Batch, Seq_Len) with word IDs.
        pos_input: Tensor of shape (Batch, Seq_Len) with PoS tag IDs.
    Output:
        CRFLayer tensor output of shape (Batch, Seq_Len, num_classes + num_classes^2).
    """
    word_input = keras.layers.Input(shape=(None,), dtype="int32", name="word_input")
    pos_input = keras.layers.Input(shape=(None,), dtype="int32", name="pos_input")

    if embedding_matrix is not None:
        word_emb = keras.layers.Embedding(
            input_dim=vocab_size,
            output_dim=embed_dim,
            embeddings_initializer=keras.initializers.Constant(embedding_matrix),
            trainable=trainable_embeddings,
            name="word_embedding",
        )(word_input)
    else:
        word_emb = keras.layers.Embedding(
            input_dim=vocab_size,
            output_dim=embed_dim,
            trainable=trainable_embeddings,
            name="word_embedding",
        )(word_input)

    pos_emb = keras.layers.Embedding(
        input_dim=num_pos_tags,
        output_dim=pos_embed_dim,
        name="pos_embedding",
    )(pos_input)

    x = keras.layers.Concatenate(axis=-1, name="concat_embeddings")([word_emb, pos_emb])

    for i in range(1, num_lstm_layers + 1):
        x = keras.layers.Bidirectional(
            keras.layers.LSTM(lstm_units, return_sequences=True),
            name=f"bilstm_{i}",
        )(x)
        if dropout > 0:
            x = keras.layers.Dropout(dropout, name=f"dropout_{i}")(x)

    emissions = keras.layers.Dense(num_classes, activation=None, name="ner_emitter")(x)
    outputs = CRFLayer(num_classes, name="crf_layer")(emissions)

    model = keras.Model(
        inputs=[word_input, pos_input],
        outputs=outputs,
        name="BiLSTM_CRF_PoS",
    )

    optimizer = keras.optimizers.Adam(learning_rate=learning_rate)
    model.compile(optimizer=optimizer, loss=crf_loss, metrics=[crf_accuracy])

    return model
