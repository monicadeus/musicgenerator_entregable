from flask import Flask, request, render_template, flash, redirect
'''
Flask - crea la aplicación web
request - permite acceder a los archivos que el usuario envía
render_template - carga un archivo HTML desde la carpeta "templates"
flash - muestra mensajes temporales
redirect - redirije al usuario a otra ruta
'''

import os  #sirve para manejar rutas y archivos en el sistema operativo

app = Flask(__name__)  #crea la app
app.secret_key = "clave_secreta"  # Necesario para mostrar mensajes temporales

# Carpeta donde se guardan los archivos
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"mp3", "wav", "flac", "ogg"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER #guarda la configuración para oder usarla luego

# Crear la carpeta si no existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

#Validación de los archivos
def allowed_file(filename):
    """Verifica que la extensión sea válida."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/", methods=["GET", "POST"])
#se ejecuta cada vez que alguien entre a la web (GET) o suba un archivo (POST)
def upload_file():
    if request.method == "POST":
        # Comprobamos si el formulario tiene un archivo
        if "music_file" not in request.files:
            flash("No seleccionaste ningún archivo.")
            return redirect(request.url)

        file = request.files["music_file"]
        #también avisa si no se selecciona ningún archivo
        if file.filename == "":
            flash("Nombre de archivo vacío.")
            return redirect(request.url)

        #guardar el archivo en uploads si es válido
        if file and allowed_file(file.filename):
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            file.save(filepath)
            flash(f"Archivo '{file.filename}' subido correctamente.")
            return redirect(request.url)
        else:
            flash("Tipo de archivo no permitido. (Usa mp3, wav, flac u ogg)")
            return redirect(request.url)

    #si el metodo es GET, carga el HTML
    return render_template("upload.html")

#activa el modo debug, haciendo que se reinicie automáticamente cuando cambias el código
if __name__ == "__main__":
    app.run(debug=True)