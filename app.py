import os
import asyncio
from flask import Flask, request, jsonify, render_template, send_from_directory
from clases import ProyectoAudio, Cancion, Pista
from procesamiento_audio import separate_stems, mix_tracks

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
proyecto.cargar_estado()

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
        proyecto.guardar_estado()
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

    # localizar la Cancion en el proyecto
    cancion = proyecto.encontrar_cancion_por_archivo(nombre_archivo)
    if not cancion:
        return jsonify({"error": "Canción no registrada en el proyecto"}), 404

    try:
        # Procesamiento asíncrono: separate_stems sigue existiendo (alias)
        stems = await ejecutar_async(separate_stems, ruta_archivo, app.config["OUTPUT_FOLDER"])

        # stems viene como dict nombre -> ruta (si usas Demucs)
        # o puede venir como lista: adaptamos a dict simple si hace falta
        if isinstance(stems, dict):
            items = stems.items()
        elif isinstance(stems, (list, tuple)):
            # si es lista de rutas, generamos nombres base
            items = []
            for p in stems:
                name = os.path.splitext(os.path.basename(p))[0]
                items.append((name, p))
        else:
            return jsonify({"error": "Formato de stems inesperado"}), 500

        # Añadir cada pista a la Cancion
        for name, path in items:
            pista = Pista(name, path)
            cancion.agregar_pista(pista)

        proyecto.guardar_estado()
        # Devolver lista/ dict con pistas para el frontend
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

    if not pistas or not isinstance(pistas, (list, tuple)):
        return jsonify({"error": "No se proporcionaron pistas en formato lista"}), 400

    if len(pistas) < 2:
        return jsonify({"error": "Se requieren al menos 2 pistas: vocal y acompañamiento"}), 400

    # Construimos rutas absolutas
    rutas_pistas = [os.path.join(app.config["OUTPUT_FOLDER"], p) for p in pistas]

    # Tomamos las dos primeras (si quieres lógica más sólida, puedes buscar 'vocals' en el nombre)
    vocal_path = rutas_pistas[0]
    accomp_path = rutas_pistas[1]

    ruta_salida = os.path.join(app.config["OUTPUT_FOLDER"], "mezcla_final.wav")

    try:
        # Ahora llamamos a mix_tracks en el formato esperado (vocal, accomp, out)
        await ejecutar_async(mix_tracks, vocal_path, accomp_path, ruta_salida)
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
