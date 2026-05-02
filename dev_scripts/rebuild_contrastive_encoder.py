from pathlib import Path

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

BASE_DIR = Path(__file__).resolve().parent
ASSET_DIR = BASE_DIR / "assets"
LEGACY_PATH = ASSET_DIR / "contrastive_encoder.keras"
CLEAN_PATH = ASSET_DIR / "contrastive_encoder_clean.keras"


class L2Normalize(layers.Layer):
    def call(self, inputs):
        return tf.nn.l2_normalize(inputs, axis=1)

    def get_config(self):
        return super().get_config()


def build_clean_encoder(input_dim: int, embedding_dim: int = 128) -> keras.Sequential:
    model = keras.Sequential(
        [
            layers.Input(shape=(input_dim,)),
            layers.Dense(256, activation="relu"),
            layers.BatchNormalization(),
            layers.Dropout(0.4),
            layers.Dense(128, activation="relu"),
            layers.BatchNormalization(),
            layers.Dropout(0.3),
            layers.Dense(embedding_dim, activation=None),
            L2Normalize(),
        ],
        name="Contrastive_Encoder_Clean",
    )
    return model


def main() -> None:
    if not LEGACY_PATH.exists():
        raise FileNotFoundError(f"Legacy model not found: {LEGACY_PATH}")

    print(f"Loading legacy model from: {LEGACY_PATH}")
    legacy = keras.models.load_model(LEGACY_PATH, compile=False, safe_mode=False)

    legacy_weights = legacy.get_weights()
    if not legacy_weights:
        raise RuntimeError("Legacy model has no weights to infer architecture.")

    # Dense(256) kernel has shape (input_dim, 256); final Dense kernel has shape (128, embedding_dim)
    input_dim = int(legacy_weights[0].shape[0])
    embedding_dim = int(legacy_weights[12].shape[1])
    print(f"Detected input_dim={input_dim}, embedding_dim={embedding_dim}")

    clean = build_clean_encoder(input_dim=input_dim, embedding_dim=embedding_dim)
    clean.build((None, input_dim))

    print("Copying weights from legacy model to clean model...")
    clean.set_weights(legacy_weights)

    print(f"Saving clean model to: {CLEAN_PATH}")
    clean.save(CLEAN_PATH)
    print("Done.")


if __name__ == "__main__":
    main()
