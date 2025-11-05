from flask import Flask, render_template, request, send_from_directory, jsonify
import os
import RemixAI

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    filename = file.filename
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)
    return jsonify({"filename": filename})

@app.route('/separate', methods=['POST'])
def separate():
    filename = request.json['filename']
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    output_path = os.path.join('outputs', 'separated')
    os.makedirs(output_path, exist_ok=True)

    # Call your backend to separate stems
    RemixAI.separate_stems(input_path, output_path)

    # List output files
    files = [f for f in os.listdir(output_path) if f.endswith('.wav')]
    download_links = [f"/download/separated/{f}" for f in files]

    return jsonify({
        "status": "ok",
        "message": "Stems separated successfully.",
        "files": download_links
    })

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    filename = data.get('filename')
    style_prompt = data.get('style_prompt', 'Hiphop, trap')  # default if none given
    output_path = os.path.join('outputs', 'generated')
    os.makedirs(output_path, exist_ok=True)

    # call backend correctly
    RemixAI.generate_accompaniment(style_prompt, output_path)

    # list output files to display or download later
    files = [f for f in os.listdir(output_path) if f.endswith('.wav')]
    download_links = [f"/download/generated/{f}" for f in files]

    return jsonify({
        "status": "ok",
        "message": "Acompañamiento generado con éxito.",
        "files": download_links
    })


@app.route('/mix', methods=['POST'])
def mix():
    RemixAI.mix_tracks()
    return jsonify({"status": "ok", "message": "Remix final listo"})

@app.route('/download/<path:filename>')
def download(filename):
    return send_from_directory('outputs', filename, as_attachment=True)

@app.route('/download/separated/<path:filename>')
def download_stem(filename):
    return send_from_directory('outputs/separated', filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
