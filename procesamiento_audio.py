import os
import subprocess
import argparse
from pathlib import Path
import numpy as np
import torch
import librosa
import soundfile as sf
from abc import ABC, abstractmethod

from demucs.apply import apply_model
from modelos import get_demucs_model, get_musicgen

# =========================
# GLOBAL SETTINGS
# =========================
SAMPLE_RATE = 32000
VOCAL_GAIN = 0.85
ACC_GAIN = 0.65
MODEL_DEMUCS = "htdemucs"
MODEL_MUSICGEN = "facebook/musicgen-small"

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
torch.set_default_device(DEVICE)

# CARGAR MODELOS UNA SOLA VEZ (al importar el módulo)
print("Cargando modelos de IA...")
demucs_model = get_demucs_model()
musicgen_processor, musicgen_model = get_musicgen()
print("Modelos cargados exitosamente")


# =========================
# UTILS
# =========================
def log(msg: str):
    """Print to console and write to remix.log"""
    print(msg, flush=True)
    try:
        with open("remix.log", "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception as e:
        print(f"No se pudo escribir en log: {e}")


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def load_audio(path, sr=SAMPLE_RATE, mono=False):
    """Carga un archivo de audio con librosa"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Archivo no encontrado: {path}")

    y, r = librosa.load(path, sr=sr, mono=mono)
    if y.ndim == 1:
        y = np.expand_dims(y, 0)
    return y, r


def save_audio(path, audio, sr=SAMPLE_RATE):
    """Guarda audio en formato WAV"""
    if audio.ndim > 1:
        audio = audio.T
    sf.write(path, audio, sr)
    log(f"Audio guardado: {path}")


# =========================
# CLASE BASE
# =========================
class AudioProcessor(ABC):
    """Clase abstracta para procesadores de audio"""

    @abstractmethod
    def process(self, *args, **kwargs):
        pass


# =========================
# SUBCLASE 1: SEPARACIÓN DE STEMS
# =========================
class DemucsSeparator(AudioProcessor):
    """Separa un audio en stems usando Demucs"""

    def process(self, input_audio, out_dir):
        log(f"Separando stems de: {input_audio}")
        ensure_dir(out_dir)

        # Verificar que el archivo existe
        if not os.path.exists(input_audio):
            raise FileNotFoundError(f"Archivo no encontrado: {input_audio}")

        # Cargar audio
        log("Cargando audio...")
        wav, _ = load_audio(input_audio, sr=SAMPLE_RATE, mono=False)
        wav_t = torch.tensor(wav, dtype=torch.float32).unsqueeze(0).to(DEVICE)

        # Aplicar modelo Demucs
        log("Procesando con Demucs (esto puede tardar)...")
        with torch.no_grad():
            sources = apply_model(
                demucs_model,
                wav_t,
                device=DEVICE,
                split=True,
                overlap=0.25,
                shifts=1
            )[0]

        # Guardar cada stem
        stems = demucs_model.sources
        paths = {}

        log(f"Guardando {len(stems)} stems...")
        for i, name in enumerate(stems):
            out_path = Path(out_dir) / f"{name}.wav"
            save_audio(out_path, sources[i].cpu().numpy(), SAMPLE_RATE)
            log(f"{name} → {out_path}")
            paths[name] = str(out_path)

        log("Separación completada exitosamente")
        return paths


# =========================
# SUBCLASE 2: GENERACIÓN DE ACOMPAÑAMIENTO
# =========================
class MusicGenGenerator(AudioProcessor):
    """Genera acompañamiento musical con MusicGen"""

    def process(self, style_prompt, out_path, duration=30):
        prompt = f"background music in {style_prompt} style"
        log(f"Generando acompañamiento: {prompt}")

        inputs = musicgen_processor(
            text=prompt,
            return_tensors="pt",
            padding=True
        ).to(DEVICE)

        log("Generando audio con MusicGen...")
        with torch.no_grad():
            audio = musicgen_model.generate(
                **inputs,
                max_new_tokens=int(duration * SAMPLE_RATE / 256)
            )

        # Normalizar y guardar
        arr = audio[0, 0].cpu().numpy()
        arr = arr / (np.max(np.abs(arr)) + 1e-9)
        save_audio(out_path, arr, SAMPLE_RATE)
        log(f"Acompañamiento generado → {out_path}")
        return out_path


# =========================
# SUBCLASE 3: MEZCLA
# =========================
class Mixer(AudioProcessor):
    """Mezcla vocal con acompañamiento"""

    def process(self, vocal_wav, accomp_wav, out_path):
        log("Mezclando vocal + acompañamiento...")

        # Cargar pistas
        v, _ = librosa.load(vocal_wav, sr=SAMPLE_RATE, mono=True)
        a, _ = librosa.load(accomp_wav, sr=SAMPLE_RATE, mono=True)

        # Igualar longitudes
        L = min(len(v), len(a))
        mix = VOCAL_GAIN * v[:L] + ACC_GAIN * a[:L]

        # Normalizar
        mix = mix / (np.max(np.abs(mix)) + 1e-9)
        save_audio(out_path, mix, SAMPLE_RATE)
        log(f"Mezcla final → {out_path}")
        return out_path


# =========================
# FUNCIONES PÚBLICAS (para compatibilidad con app.py)
# =========================
def separate_stems(input_audio, out_dir):
    """
    Separa un audio en stems usando Demucs CLI (bloqueante y confiable).

    Args:
        input_audio (str): ruta del archivo de audio
        out_dir (str): carpeta donde guardar los stems

    Returns:
        dict: {'drums': path, 'bass': path, 'other': path, 'vocals': path}
    """

    if not os.path.exists(input_audio):
        raise FileNotFoundError(f"El archivo no existe: {input_audio}")

    os.makedirs(out_dir, exist_ok=True)

    # Ruta del comando demucs
    # Usa el modelo htdemucs que da mejor calidad
    command = [
        "demucs",
        "-n", "htdemucs",
        "-o", out_dir,
        input_audio
    ]

    print("Ejecutando Demucs...")
    print("Comando:", " ".join(command))

    # Ejecutar bloqueante y CAPTURAR tudo
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    stdout, stderr = process.communicate()

    print("📤 STDOUT:")
    print(stdout)
    print("📥 STDERR:")
    print(stderr)

    if process.returncode != 0:
        raise RuntimeError(f"Demucs falló con código {process.returncode}:\n{stderr}")

    # Buscar carpeta generada por Demucs
    song_name = os.path.splitext(os.path.basename(input_audio))[0]
    demucs_output_dir = os.path.join(out_dir, "htdemucs", song_name)

    print(f"📂 Carpeta generada: {demucs_output_dir}")

    if not os.path.exists(demucs_output_dir):
        raise RuntimeError("Demucs terminó, pero no generó la carpeta esperada.")

    stems = {
        "drums": os.path.join(demucs_output_dir, "drums.wav"),
        "bass": os.path.join(demucs_output_dir, "bass.wav"),
        "other": os.path.join(demucs_output_dir, "other.wav"),
        "vocals": os.path.join(demucs_output_dir, "vocals.wav")
    }

    # Validar cada archivo
    stems_validos = {}

    for name, path in stems.items():
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            stems_validos[name] = path
        else:
            print(f"⚠️ WARNING: '{name}' está vacío o no existe ({path})")

    if not stems_validos:
        raise RuntimeError("Demucs ejecutó pero todos los stems salieron vacíos.")

    print("🎉 Separación completada correctamente")
    return stems_validos


def generate_accompaniment(style_prompt, out_path, duration=30):
    """
    Genera un acompañamiento musical

    Args:
        style_prompt: estilo musical (ej: "electronic", "lo-fi")
        out_path: dónde guardar el audio
        duration: duración en segundos

    Returns:
        str: ruta al archivo generado
    """
    try:
        return MusicGenGenerator().process(style_prompt, out_path, duration)
    except Exception as e:
        log(f"❌ Error en generación: {e}")
        raise


def mix_tracks(vocal_wav, accomp_wav, out_path):
    """
    Mezcla dos pistas de audio

    Args:
        vocal_wav: ruta al archivo de vocal
        accomp_wav: ruta al acompañamiento
        out_path: dónde guardar la mezcla

    Returns:
        str: ruta al archivo mezclado
    """
    try:
        return Mixer().process(vocal_wav, accomp_wav, out_path)
    except Exception as e:
        log(f"❌ Error en mezcla: {e}")
        raise


# =========================
# MAIN PIPELINE (para uso desde línea de comandos)
# =========================
def main():
    parser = argparse.ArgumentParser(description="🎛️ AI Remix: Demucs + MusicGen")
    parser.add_argument("--input", required=True, help="Input audio file (.mp3 or .wav)")
    parser.add_argument("--style", required=True, help="Style prompt for MusicGen")
    parser.add_argument("--duration", type=int, default=30, help="Duration in seconds")
    parser.add_argument("--output_dir", default="output_remix", help="Output directory")
    args = parser.parse_args()

    log("=" * 50)
    log("🎛️ Iniciando AI Remix Pipeline")
    log(f"🎚 Device: {DEVICE}")
    log("=" * 50)

    ensure_dir(args.output_dir)

    # Pipeline completo
    separator = DemucsSeparator()
    generator = MusicGenGenerator()
    mixer = Mixer()

    # 1. Separar stems
    stems = separator.process(args.input, args.output_dir)
    vocal_path = stems.get("vocals")

    # 2. Generar acompañamiento
    accomp_path = os.path.join(args.output_dir, "accompaniment_generated.wav")
    generator.process(args.style, accomp_path, duration=args.duration)

    # 3. Mezclar
    final_mix = os.path.join(args.output_dir, "final_remix.wav")
    mixer.process(vocal_path, accomp_path, final_mix)

    log("=" * 50)
    log(f"✅ ¡Remix completado! → {final_mix}")
    log("=" * 50)

# Evitar ejecución automática cuando Flask recarga
if __name__ == "__main__" and os.getenv("WERKZEUG_RUN_MAIN") == "true":
    if os.name == "nt":
        os.system("chcp 65001 >NUL")
    main()
