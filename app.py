import os
import asyncio
from flask import Flask, request, jsonify, render_template, send_from_directory
from clases import ProyectoAudio, Cancion

import clases
print("🔍 Cargando clases desde:", clases.__file__)
print("Tiene método agregar_cancion?:", hasattr(clases.ProyectoAudio, "agregar_cancion"))

from procesamiento_audio import separate_stems, mix_tracks

print("Tiene método agregar_cancion?:", hasattr(ProyectoAudio, "agregar_cancion"))

# -------------------------------------------------------
# Configuración general del servidor Flask
# -------------------------------------------------------
app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs_remix"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Proyecto principal de audio
proyecto = ProyectoAudio("Proyecto de Audio")

# -------------------------------------------------------
# Funciones auxiliares
# -------------------------------------------------------

async def ejecutar_async(funcion, *args, **kwargs):
    """
    Ejecuta funciones bloqueantes (como IA de audio) en un hilo aparte.
    Flask no es asíncrono nativo, pero asyncio.to_thread evita que se bloquee.
    """
    return await asyncio.to_thread(funcion, *args, **kwargs)

# -------------------------------------------------------
# Rutas del sistema
# -------------------------------------------------------

@app.route("/")
def index():
    """Página principal (interfaz del usuario)."""
    return render_template("upload.html")



@app.route("/upload", methods=["GET", "POST"])
def upload_file():
     """Sube un archivo musical y lo registra en el proyecto."""
     try:
        if request.method == "GET":
            return render_template("upload.html")

        if "file" not in request.files:
            return jsonify({"error": "No se envió ningún archivo"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "Nombre de archivo inválido"}), 400

        filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(filepath)
        # Crear objeto Cancion
        nueva_cancion = Cancion(file.filename, filepath, "audio")

        # Añadir al proyecto
        proyecto.agregar_cancion(nueva_cancion)
        return jsonify({"mensaje": "Archivo subido correctamente", "ruta": filepath})
     except Exception as e:
        return jsonify({"error": f"Error al subir archivo: {str(e)}"}), 500

@app.route("/separar", methods=["POST"])
async def separar():
    """
    Usa Demucs o Spleeter para separar una canción en stems.
    Se ejecuta de forma asíncrona para no bloquear la app.
    """
    data = request.get_json()
    nombre_archivo = data.get("nombre")

    if not nombre_archivo:
        return jsonify({"error": "Falta el nombre del archivo"}), 400

    ruta_archivo = os.path.join(app.config["UPLOAD_FOLDER"], nombre_archivo)

    try:
        # Procesamiento asíncrono
        stems = await ejecutar_async(separate_stems, ruta_archivo, app.config["OUTPUT_FOLDER"])
        proyecto.agregar_pista(stems)
        return jsonify({"mensaje": "Separación completada", "pistas": stems})
    except FileNotFoundError:
        return jsonify({"error": "Archivo no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": f"Error durante la separación: {str(e)}"}), 500

@app.route("/mezclar", methods=["POST"])
async def mezclar():
    """
    Mezcla pistas (stems) seleccionadas.
    También corre de forma asíncrona para evitar bloqueos.
    """
    data = request.get_json()
    pistas = data.get("pistas")

    if not pistas:
        return jsonify({"error": "No se proporcionaron pistas"}), 400

    rutas_pistas = [os.path.join(app.config["OUTPUT_FOLDER"], p) for p in pistas]
    ruta_salida = os.path.join(app.config["OUTPUT_FOLDER"], "mezcla_final.wav")

    try:
        await ejecutar_async(mix_tracks, rutas_pistas, ruta_salida)
        return jsonify({"mensaje": "Mezcla completada", "archivo_resultante": ruta_salida})
    except Exception as e:
        return jsonify({"error": f"Error durante la mezcla: {str(e)}"}), 500

@app.route("/output_remix/<path:filename>")
def resultados(filename):
    """Sirve los archivos generados (stems o mezclas)."""
    try:
        return send_from_directory(app.config["OUTPUT_FOLDER"], filename)
    except FileNotFoundError:
        return jsonify({"error": "Archivo no encontrado"}), 404

# -------------------------------------------------------
# Ejecución del servidor
# -------------------------------------------------------
if __name__ == "__main__":
    # En debug se mantiene autoreload, pero sin bloquear la IU durante procesos largos.
    app.run(debug=True)