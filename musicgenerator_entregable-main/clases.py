# clases.py
# Contiene los modelos: Cancion, Pista y ProyectoAudio
# Objetivo: separar la lógica de datos (modelo) del servidor (app.py)

import os
from procesamiento_audio.py import separate_stems, generate_accompaniment, mix_tracks
from datetime import datetime
from typing import List, Optional

class Pista:
    """
    Representa una pista (stem) individual de audio.
    Por ejemplo: voz, guitarra, bajo, batería...
    """
    def __init__(self, nombre: str, archivo_ruta: str, duracion_seg: Optional[float] = None):
        self.nombre = nombre
        self.archivo_ruta = archivo_ruta  # ruta al archivo físico en disco
        self.duracion_seg = duracion_seg  # duración en segundos (si se conoce)
        self.metadatos = {}               # diccionario libre para tags adicionales

    def __repr__(self):
        return f"Pista(nombre={self.nombre}, archivo={os.path.basename(self.archivo_ruta)})"


class Cancion:
    """
    Representa un archivo de canción subido por el usuario.
    Mantiene metadatos básicos y referencia a pistas (si se separó en stems).
    """
    def __init__(self, titulo: str, archivo_ruta: str, formato: Optional[str] = None):
        self.titulo = titulo
        self.archivo_ruta = archivo_ruta
        self.formato = formato or self._infer_format()
        self.tamanio_bytes = self._get_size_bytes()
        self.hora_subida = datetime.now()
        self.pistas: List[Pista] = []  # listas de Pista asociadas tras separación
        self.metadatos = {}            # por ejemplo artista, album, bpm, etc.

    def _infer_format(self) -> Optional[str]:
        """Extrae la extensión del archivo como formato (mp3, wav, ...)."""
        parts = os.path.basename(self.archivo_ruta).rsplit(".", 1)
        return parts[1].lower() if len(parts) == 2 else None

    def _get_size_bytes(self) -> int:
        """Devuelve el tamaño del archivo en bytes (0 si no existe)."""
        try:
            return os.path.getsize(self.archivo_ruta)
        except Exception:
            return 0

    def agregar_pista(self, pista: Pista):
        """Añade una pista a la canción (por ejemplo tras separar stems)."""
        self.pistas.append(pista)

    def info_simple(self) -> dict:
        """Devuelve información resumen de la canción (útil para la UI)."""
        return {
            "titulo": self.titulo,
            "archivo": os.path.basename(self.archivo_ruta),
            "formato": self.formato,
            "tam_kb": int(self.tamanio_bytes / 1024),
            "hora_subida": self.hora_subida.isoformat(),
            "num_pistas": len(self.pistas)
        }

    def __repr__(self):
        return f"Cancion(titulo={self.titulo}, archivo={os.path.basename(self.archivo_ruta)})"


class ProyectoAudio:
    """
    Representa un proyecto que puede contener varias canciones y el estado del
    procesamiento (separación, mezcla, exportación).
    """
    def __init__(self, nombre_proyecto: str):
        self.nombre = nombre_proyecto
        self.canciones: List[Cancion] = []
        self.created_at = datetime.now()
        self.outputs_dir = "outputs_remix"  # carpeta por defecto para resultados
        os.makedirs(self.outputs_dir, exist_ok=True)

    def agregar_cancion(self, cancion: Cancion):
        """Añade una Cancion al proyecto."""
        self.canciones.append(cancion)

    def encontrar_cancion_por_archivo(self, filename: str) -> Optional[Cancion]:
        """Busca una canción por nombre de archivo (basename)."""
        for c in self.canciones:
            if os.path.basename(c.archivo_ruta) == filename:
                return c
        return None

    def listar_canciones(self) -> List[dict]:
        """Devuelve una lista con información simple de las canciones del proyecto."""
        return [c.info_simple() for c in self.canciones]

    # Métodos placeholder que la app puede llamar (se recomienda implementar en otro módulo)
    def separar_stems(self):
        return separate_stems(self.cancion.ruta_archivo, self.output_dir)

    def generar_acompanamiento(self, estilo, duracion=30):
        out_path = os.path.join(self.output_dir, "accompaniment_generated.wav")
        return generate_accompaniment(estilo, out_path, duracion)

    def mezclar(self, vocal_wav, accomp_wav):
        out_path = os.path.join(self.output_dir, "final_mix.wav")
        return mix_tracks(vocal_wav, accomp_wav, out_path)