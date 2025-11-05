import os
import argparse
from pathlib import Path
import numpy as np
import torch
import librosa
import soundfile as sf

from demucs.pretrained import get_model
from demucs.apply import apply_model
from transformers import AutoProcessor, MusicgenForConditionalGeneration

# =========================
# GLOBAL SETTINGS
# =========================
SAMPLE_RATE = 32000
VOCAL_GAIN = 0.85
ACC_GAIN = 0.65
MODEL_DEMUCS = "htdemucs"
MODEL_MUSICGEN = "facebook/musicgen-small"

# detect device
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
torch.set_default_device(DEVICE)

# =========================
# UTILS
# =========================
def log(msg: str):
    """Print to console and write to remix.log"""
    print(msg, flush=True)
    with open("remix.log", "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def load_audio(path, sr=SAMPLE_RATE, mono=False):
    y, r = librosa.load(path, sr=sr, mono=mono)
    if y.ndim == 1:
        y = np.expand_dims(y, 0)
    return y, r


def save_audio(path, audio, sr=SAMPLE_RATE):
    if audio.ndim > 1:
        audio = audio.T
    sf.write(path, audio, sr)

# =========================
# 1️⃣ STEM SEPARATION
# =========================
_DEMUCS_MODEL = None
def separate_stems(input_audio, out_dir):
    """Separate stems using Demucs (CPU/GPU)"""
    global _DEMUCS_MODEL
    ensure_dir(out_dir)

    if _DEMUCS_MODEL is None:
        log("🔊 Loading Demucs model...")
        _DEMUCS_MODEL = get_model(MODEL_DEMUCS).to(DEVICE).eval()

    wav, _ = load_audio(input_audio, sr=SAMPLE_RATE, mono=False)
    wav_t = torch.tensor(wav, dtype=torch.float32).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        sources = apply_model(_DEMUCS_MODEL, wav_t, device=DEVICE,
                              split=True, overlap=0.25, shifts=1)[0]

    stems = _DEMUCS_MODEL.sources  # ['vocals','drums','bass','other']
    paths = {}
    for i, name in enumerate(stems):
        out_path = Path(out_dir) / f"{name}.wav"
        save_audio(out_path, sources[i].cpu().numpy(), SAMPLE_RATE)
        log(f"{name} stem saved → {out_path}")
        paths[name] = str(out_path)

    return paths

# =========================
# 2️⃣ AI ACCOMPANIMENT
# =========================
_MUSICGEN_MODEL = None
_MUSICGEN_PROC = None
def generate_accompaniment(style_prompt, out_path, duration=30):
    """Generate accompaniment using MusicGen"""
    global _MUSICGEN_MODEL, _MUSICGEN_PROC

    if _MUSICGEN_MODEL is None:
        log("Loading MusicGen model...")
        _MUSICGEN_PROC = AutoProcessor.from_pretrained(MODEL_MUSICGEN)
        _MUSICGEN_MODEL = MusicgenForConditionalGeneration.from_pretrained(MODEL_MUSICGEN).to(DEVICE)

    prompt = f"background music in {style_prompt} style"
    log(f"🎶 Generating accompaniment: {prompt}")
    inputs = _MUSICGEN_PROC(text=prompt, return_tensors="pt", padding=True).to(DEVICE)

    with torch.no_grad():
        audio = _MUSICGEN_MODEL.generate(**inputs, max_new_tokens=int(duration * SAMPLE_RATE / 256))

    arr = audio[0, 0].cpu().numpy()
    arr = arr / (np.max(np.abs(arr)) + 1e-9)
    save_audio(out_path, arr, SAMPLE_RATE)
    log(f"Accompaniment saved → {out_path}")
    return out_path

# =========================
# 3️⃣ MIXING
# =========================
def mix_tracks(vocal_wav, accomp_wav, out_path):
    """Combine vocal + AI accompaniment"""
    log("🎧 Mixing vocal + accompaniment...")
    v, _ = librosa.load(vocal_wav, sr=SAMPLE_RATE, mono=True)
    a, _ = librosa.load(accomp_wav, sr=SAMPLE_RATE, mono=True)

    L = min(len(v), len(a))
    mix = VOCAL_GAIN * v[:L] + ACC_GAIN * a[:L]
    mix = mix / (np.max(np.abs(mix)) + 1e-9)
    save_audio(out_path, mix, SAMPLE_RATE)
    log(f"Final remix saved → {out_path}")
    return out_path

# =========================
# 4️⃣ MAIN PIPELINE
# =========================
def main():
    parser = argparse.ArgumentParser(description="🎛️ AI Remix: Demucs + MusicGen")
    parser.add_argument("--input", required=True, help="Input audio file (.mp3 or .wav)")
    parser.add_argument("--style", required=True, help="Style prompt for MusicGen (e.g. 'electronic', 'lo-fi', 'acoustic')")
    parser.add_argument("--duration", type=int, default=30, help="Generated accompaniment duration in seconds")
    parser.add_argument("--output_dir", default="output_remix", help="Output directory")
    args = parser.parse_args()

    log("Starting Remix Franken 2.0")
    log(f"🎚 Device: {DEVICE}")

    ensure_dir(args.output_dir)
    stems = separate_stems(args.input, args.output_dir)
    vocal_path = stems.get("vocals")
    accomp_path = os.path.join(args.output_dir, "accompaniment_generated.wav")
    final_mix = os.path.join(args.output_dir, "final_remix.wav")

    generate_accompaniment(args.style, accomp_path, duration=args.duration)
    mix_tracks(vocal_path, accomp_path, final_mix)

    log(f"Done! Remix ready → {final_mix}")

if __name__ == "__main__":
    if os.name == "nt":
        os.system("chcp 65001 >NUL")  # Windows UTF-8 fix
    main()