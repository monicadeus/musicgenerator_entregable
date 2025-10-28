from flask import Flask, request
import os
from datetime import datetime

app = Flask(__name__)

# Configuracion
UPLOAD_FOLDER = "uploads"#Carpeta donde guarda los archivos
ALLOWED_EXTENSIONS = {"mp3", "wav", "flac", "ogg"} #Tipos de archivos permitidos
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)#crea una carpeta si no existe


# Verificar tipo de archivo permitido
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# Obtener informacion del archivo
def get_file_info(filepath):
    size = os.path.getsize(filepath)
    size_kb = round(size / 1024, 2)

    return {
        'size_bytes': size,
        'size_kb': size_kb,
        'upload_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    # HTML base
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Subir Audio</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                text-align: center; 
                padding: 50px; 
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 8px;
                display: inline-block;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                width: 400px;
            }
            .message {
                padding: 10px;
                margin: 10px 0;
                border-radius: 4px;
            }
            .success { 
                background: #e8f5e8; 
                color: #2d5016; 
                border: 1px solid #c3e6c3;
            }
            .error { 
                background: #f8d7da; 
                color: #721c24; 
                border: 1px solid #f5c6cb;
            }
            .file-info {
                text-align: left;
                background: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
                margin: 15px 0;
                border-left: 4px solid #007bff;
            }
            input[type="file"] {
                margin: 15px 0;
                padding: 8px;
            }
            button {
                background: #007bff;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
            }
            button:hover {
                background: #0056b3;
            }
        </style>
    </head>
    <body>
        <div class="container">
        <h1>Subir Archivo de Audio</h1>
    '''

    # Procesar archivo subido
    if request.method == 'POST':
        if 'audio_file' not in request.files:
            html += '<div class="message error">No se selecciono ningun archivo.</div>'
        else:
            file = request.files['audio_file']

            if file.filename == '':
                html += '<div class="message error">Nombre de archivo vacio.</div>'
            elif not allowed_file(file.filename):
                html += '<div class="message error">Tipo de archivo no permitido. Use: mp3, wav, flac, ogg</div>'
            else:
                # Guardar archivo
                filepath = os.path.join(UPLOAD_FOLDER, file.filename)
                file.save(filepath)

                # Obtener informacion
                info = get_file_info(filepath)

                html += f'''
                <div class="message success">Archivo subido correctamente</div>
                <div class="file-info">
                    <h3>Informacion del archivo:</h3>
                    <p><strong>Nombre:</strong> {file.filename}</p>
                    <p><strong>Tamaño:</strong> {info['size_kb']} KB</p>
                    <p><strong>Formato:</strong> {file.filename.rsplit('.', 1)[1].upper()}</p>
                    <p><strong>Hora de subida:</strong> {info['upload_time']}</p>
                </div>
                '''

    # Formulario
    html += '''
        <form method="POST" enctype="multipart/form-data">
            <input type="file" name="audio_file" accept=".mp3,.wav,.flac,.ogg" required>
            <br>
            <button type="submit">Subir Archivo</button>
        </form>
        </div>
    </body>
    </html>
    '''

    return html


if __name__ == '__main__':
    app.run(debug=True)
