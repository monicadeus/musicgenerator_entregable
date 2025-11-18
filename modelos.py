# modelos.py
import torch
from demucs.pretrained import get_model
from transformers import AutoProcessor, MusicgenForConditionalGeneration

MODEL_DEMUCS = "htdemucs"
MODEL_MUSICGEN = "facebook/musicgen-small"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# -------------------------------------------------------
# CARGA DIFERIDA (lazy loading)
# Solo se cargan cuando se piden por primera vez.
# Después quedan en memoria.
# -------------------------------------------------------

_demucs_model = None
_musicgen_processor = None
_musicgen_model = None


def get_demucs_model():
    global _demucs_model
    if _demucs_model is None:
        print(" Cargando modelo Demucs (solo la primera vez)...")
        _demucs_model = get_model(MODEL_DEMUCS).to(DEVICE).eval()
    return _demucs_model


def get_musicgen():
    global _musicgen_processor, _musicgen_model

    if _musicgen_processor is None or _musicgen_model is None:
        print("Cargando modelo MusicGen (solo la primera vez)...")
        _musicgen_processor = AutoProcessor.from_pretrained(
            MODEL_MUSICGEN,
            force_download=False,      #No fuerza descargas cada vez
            local_files_only=False     # Usa primero cache local
        )
        _musicgen_model = MusicgenForConditionalGeneration.from_pretrained(
            MODEL_MUSICGEN,
            force_download=False,
            local_files_only=False
        ).to(DEVICE)
    return _musicgen_processor, _musicgen_model