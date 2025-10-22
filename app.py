from flask import Flask, request, render_template, flash, redirect
import os

app = Flask(__name__)
app.secret_key = "clave_secreta"  # Necesario para mostrar mensajes temporales

# Carpeta donde se guardan los archivos
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"mp3", "wav", "flac", "ogg"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Crear la carpeta si no existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Verifica que la extensión sea válida."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        # Comprobamos si el formulario tiene un archivo
        if "music_file" not in request.files:
            flash("No seleccionaste ningún archivo.")
            return redirect(request.url)

        file = request.files["music_file"]

        if file.filename == "":
            flash("Nombre de archivo vacío.")
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            file.save(filepath)
            flash(f"Archivo '{file.filename}' subido correctamente.")
            return redirect(request.url)
        else:
            flash("Tipo de archivo no permitido. (Usa mp3, wav, flac u ogg)")
            return redirect(request.url)

    return render_template("upload.html")

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8080)