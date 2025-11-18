import os
from flask import Flask, request, jsonify, render_template, send_from_directory, flash, redirect, url_for
from werkzeug.utils import secure_filename
from os.path import basename
from clases import ProyectoAudio, Cancion, Pista
from procesamiento_audio import separate_stems, mix_tracks

# -------------------------------------------------------
# Configuración general del servidor Flask
# -------------------------------------------------------
app = Flask(__name__)
app.secret_key = "tu_clave_secreta_aqui_12345"  #Necesario para flash()

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs_remix"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Proyecto principal de audio
proyecto = ProyectoAudio("Proyecto de Audio")
proyecto.cargar_estado()

print("Servidor Flask iniciado correctamente")


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
            flash("No se envió ningún archivo")
            return redirect(url_for("upload_file"))

        file = request.files["file"]
        if file.filename == "":
            flash("Nombre de archivo inválido")
            return redirect(url_for("upload_file"))

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        print(f"📁 Archivo guardado: {filepath}")

        # Crear objeto Cancion
        nueva_cancion = Cancion(filename, filepath, "audio")

        # Añadir al proyecto
        proyecto.agregar_cancion(nueva_cancion)
        proyecto.guardar_estado()

        print(f"Canción registrada: {filename}")

        # Redirigir al HTML de proyectos
        return redirect(url_for("proyecto_view", archivo=filename))

    except Exception as e:
        print(f"Error al subir archivo: {str(e)}")
        flash(f"Error al subir archivo: {str(e)}")
        return redirect(url_for("upload_file"))


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    """Sirve archivos subidos"""
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/proyecto")
def proyecto_view():
    """Muestra la vista del proyecto con la canción seleccionada"""
    nombre_archivo = request.args.get("archivo")
    print(f"🔍 Buscando canción: {nombre_archivo}")

    # Buscar canción en el proyecto
    cancion = proyecto.encontrar_cancion_por_archivo(nombre_archivo)

    if not cancion:
        flash("Canción no encontrada")
        return redirect(url_for("upload_file"))

    print(f"Canción encontrada: {cancion.titulo}")

    return render_template(
        "proyectos.html",
        cancion=cancion,
        archivo=basename(cancion.archivo_ruta)
    )


@app.route("/separar", methods=["POST"])
def separar():
    """
    Separa una canción en stems usando Demucs.
    """
    print("Endpoint /separar llamado")

    data = request.get_json()
    nombre_archivo = data.get("nombre")

    print(f"Data recibida: {data}")

    if not nombre_archivo:
        return jsonify({"error": "Falta el nombre del archivo"}), 400

    ruta_archivo = os.path.join(app.config["UPLOAD_FOLDER"], nombre_archivo)

    # Verificar que el archivo existe
    if not os.path.exists(ruta_archivo):
        print(f"Archivo no encontrado: {ruta_archivo}")
        return jsonify({"error": f"Archivo no encontrado: {nombre_archivo}"}), 404

    # Verificar que el archivo NO esté vacío (esta era una causa frecuente)
    size = os.path.getsize(ruta_archivo)
    print(f"Tamaño del archivo original: {size} bytes")

    if size == 0:
        return jsonify({"error": "El archivo subido está vacío"}), 400

    # Localizar la Cancion en el proyecto
    cancion = proyecto.encontrar_cancion_por_archivo(nombre_archivo)
    if not cancion:
        print(f"Canción no registrada: {nombre_archivo}")
        return jsonify({"error": "Canción no registrada en el proyecto"}), 404

    try:
        print(f"Iniciando separación de stems...")
        print(f"Archivo: {ruta_archivo}")
        print(f"Output: {app.config['OUTPUT_FOLDER']}")

        # FORZAMOS EJECUCIÓN SÍNCRONA Y BLOQUEANTE
        stems = separate_stems(ruta_archivo, app.config["OUTPUT_FOLDER"])

        # VALIDACIÓN CLAVE: asegurarse de que los stems existen y NO están vacíos
        stems_validos = {}
        for name, path in stems.items():
            if os.path.exists(path) and os.path.getsize(path) > 1000:
                stems_validos[name] = path
                print(f"Pista válida: {name} ({os.path.getsize(path)} bytes)")
            else:
                print(f" Pista inválida o vacía: {name} ({os.path.getsize(path) if os.path.exists(path) else 0} bytes)")

        if not stems_validos:
            return jsonify({
                "error": "La separación se ejecutó pero todos los stems están vacíos",
                "detalle": "Revisa separate_stems(): no está esperando a que Demucs escriba."
            }), 500

        # Añadir cada pista válida al proyecto
        for name, path in stems_validos.items():
            pista = Pista(name, path)
            cancion.agregar_pista(pista)
            print(f"Pista añadida al proyecto: {name}")

        proyecto.guardar_estado()

        # Convertimos las rutas REALES a rutas PÚBLICAS correctas
        pistas_publicas = {
            name: f"outputs_remix/{name}.wav"
            for name in stems_validos
        }

        return jsonify({
            "mensaje": "Separación completada exitosamente",
            "pistas": pistas_publicas
        })

    except Exception as e:
        import traceback
        print(f"ERROR DURANTE LA SEPARACIÓN:")
        print(traceback.format_exc())
        return jsonify({
            "error": f"Error durante la separación: {str(e)}",
            "detalle": traceback.format_exc()
        }), 500

@app.route('/outputs_remix/<path:filename>')
def serve_stems(filename):
    directorio = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs_remix")
    print("Sirviendo desde:", directorio)
    return send_from_directory(directorio, filename)

@app.route("/mezclar", methods=["POST"])
def mezclar():
    """
    Mezcla pistas (stems) seleccionadas.
    """
    print("Endpoint /mezclar llamado")

    data = request.get_json()
    pistas = data.get("pistas")

    if not pistas or not isinstance(pistas, (list, tuple)):
        return jsonify({"error": "No se proporcionaron pistas en formato lista"}), 400

    if len(pistas) < 2:
        return jsonify({"error": "Se requieren al menos 2 pistas"}), 400

    rutas_pistas = pistas
    print(f"Pistas recibidas: {pistas}")

    vocal_path = rutas_pistas[0]
    accomp_path = rutas_pistas[1]

    # Verificar que ambos archivos existen
    if not os.path.exists(vocal_path):
        return jsonify({"error": f"Pista vocal no encontrada: {pistas[0]}"}), 404
    if not os.path.exists(accomp_path):
        return jsonify({"error": f"Pista acompañamiento no encontrada: {pistas[1]}"}), 404

    ruta_salida = os.path.join(app.config["OUTPUT_FOLDER"], "mezcla_final.wav")

    try:
        print(f"   Iniciando mezcla...")
        print(f"   Vocal: {vocal_path}")
        print(f"   Accomp: {accomp_path}")
        print(f"   Output: {ruta_salida}")

        # Llamada SÍNCRONA (sin asyncio)
        mix_tracks(vocal_path, accomp_path, ruta_salida)

        print(f"Mezcla completada: {ruta_salida}")

        return jsonify({
            "mensaje": "Mezcla completada exitosamente",
            "archivo_resultante": basename(ruta_salida)
        })

    except Exception as e:
        import traceback
        print(f"ERROR DURANTE LA MEZCLA:")
        print(traceback.format_exc())
        return jsonify({
            "error": f"Error durante la mezcla: {str(e)}",
            "detalle": traceback.format_exc()
        }), 500


@app.route("/outputs_remix/<path:filename>")
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
    print("=" * 60)
    print("Servidor de Audio Remix")
    print("=" * 60)
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"Output folder: {OUTPUT_FOLDER}")
    print(f"Canciones en proyecto: {len(proyecto.canciones)}")
    print("=" * 60)

    # Ejecutar servidor
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=3838)
