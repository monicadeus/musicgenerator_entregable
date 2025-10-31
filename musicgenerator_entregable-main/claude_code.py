from flask import Flask, request, send_file, jsonify
import os
from datetime import datetime
import torch
from demucs import pretrained
from demucs.apply import apply_model
from demucs.audio import AudioFile, save_audio
from audiocraft.models import MusicGen
import torchaudio
import zipfile
import shutil

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = "uploads"
SEPARATED_FOLDER = "separated"
REMIX_FOLDER = "remixes"
ALLOWED_EXTENSIONS = {"mp3", "wav", "flac", "ogg"}

for folder in [UPLOAD_FOLDER, SEPARATED_FOLDER, REMIX_FOLDER]:
    os.makedirs(folder, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB max file size

# Load models (do this once at startup)
print("Loading Demucs model...")
demucs_model = pretrained.get_model('htdemucs')
device = 'cuda' if torch.cuda.is_available() else 'cpu'
demucs_model.to(device)

print("Loading MusicGen model...")
musicgen_model = MusicGen.get_pretrained('facebook/musicgen-small')


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_info(filepath):
    size = os.path.getsize(filepath)
    size_kb = round(size / 1024, 2)
    return {
        'size_bytes': size,
        'size_kb': size_kb,
        'upload_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def separate_audio(audio_path, output_folder):
    """Separate audio into stems using Demucs"""
    print(f"Separating audio: {audio_path}")

    # Load audio
    wav = AudioFile(audio_path).read(streams=0, samplerate=demucs_model.samplerate,
                                     channels=demucs_model.audio_channels)
    wav = torch.from_numpy(wav).to(device)
    ref = wav.mean(0)
    wav = (wav - ref.mean()) / ref.std()

    # Apply model
    sources = apply_model(demucs_model, wav[None], device=device)[0]
    sources = sources * ref.std() + ref.mean()

    # Save separated stems
    stem_files = {}
    stems = ['drums', 'bass', 'other', 'vocals']

    os.makedirs(output_folder, exist_ok=True)

    for i, stem in enumerate(stems):
        stem_path = os.path.join(output_folder, f"{stem}.wav")
        save_audio(sources[i], stem_path, samplerate=demucs_model.samplerate)
        stem_files[stem] = stem_path
        print(f"Saved {stem} to {stem_path}")

    return stem_files


def create_remix(stem_files, prompt, output_path, duration=30):
    """Create a remix using MusicGen with reference stems"""
    print(f"Creating remix with prompt: {prompt}")

    # Set generation parameters
    musicgen_model.set_generation_params(
        duration=duration,
        temperature=1.0,
        top_k=250,
        top_p=0.9,
        cfg_coef=3.0
    )

    # Generate music based on prompt
    # You can also use stems as conditioning
    wav = musicgen_model.generate([prompt])

    # Save generated audio
    audio_write(output_path, wav[0].cpu(), musicgen_model.sample_rate, strategy="loudness")

    return output_path + ".wav"


def audio_write(stem_name, wav, sample_rate, strategy="loudness"):
    """Helper function to write audio files"""
    import numpy as np
    from scipy.io import wavfile

    # Convert to numpy and ensure correct shape
    if isinstance(wav, torch.Tensor):
        wav = wav.detach().cpu().numpy()

    # Normalize
    if strategy == "loudness":
        wav = wav / (np.abs(wav).max() + 1e-8)
        wav = wav * 0.9

    # Ensure correct shape (channels, samples)
    if wav.ndim == 1:
        wav = wav.reshape(1, -1)

    # Save
    wavfile.write(f"{stem_name}.wav", sample_rate, wav.T)


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Audio Remixer - Demucs + MusicGen</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                padding: 30px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }
            .container {
                background: white;
                padding: 40px;
                border-radius: 12px;
                max-width: 800px;
                margin: 0 auto;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            }
            h1 {
                color: #333;
                margin-bottom: 10px;
            }
            .subtitle {
                color: #666;
                margin-bottom: 30px;
            }
            .message {
                padding: 15px;
                margin: 15px 0;
                border-radius: 6px;
                animation: slideIn 0.3s ease;
            }
            @keyframes slideIn {
                from { opacity: 0; transform: translateY(-10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            .success { 
                background: #d4edda; 
                color: #155724; 
                border: 1px solid #c3e6cb;
            }
            .error { 
                background: #f8d7da; 
                color: #721c24; 
                border: 1px solid #f5c6cb;
            }
            .info {
                background: #d1ecf1;
                color: #0c5460;
                border: 1px solid #bee5eb;
            }
            .file-info {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
                border-left: 4px solid #667eea;
            }
            .stems-list {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 10px;
                margin: 15px 0;
            }
            .stem-item {
                background: white;
                padding: 10px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-weight: bold;
                color: #667eea;
            }
            input[type="file"], input[type="text"], textarea {
                width: 100%;
                padding: 12px;
                margin: 10px 0;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                box-sizing: border-box;
                font-size: 14px;
            }
            textarea {
                min-height: 80px;
                resize: vertical;
                font-family: Arial, sans-serif;
            }
            button {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 14px 30px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 16px;
                font-weight: bold;
                width: 100%;
                margin-top: 10px;
                transition: transform 0.2s;
            }
            button:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            }
            button:active {
                transform: translateY(0);
            }
            .download-link {
                display: inline-block;
                background: #28a745;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 6px;
                margin: 10px 5px;
                font-weight: bold;
            }
            .download-link:hover {
                background: #218838;
            }
            label {
                font-weight: bold;
                color: #333;
                display: block;
                margin-top: 15px;
            }
            .loader {
                display: none;
                text-align: center;
                padding: 20px;
            }
            .spinner {
                border: 4px solid #f3f3f3;
                border-top: 4px solid #667eea;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 0 auto;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎵 Audio Remixer</h1>
            <p class="subtitle">Upload audio → Separate stems with Demucs → Create remix with MusicGen</p>
    '''

    if request.method == 'POST':
        if 'audio_file' not in request.files:
            html += '<div class="message error">❌ No file selected</div>'
        else:
            file = request.files['audio_file']

            if file.filename == '':
                html += '<div class="message error">❌ Empty filename</div>'
            elif not allowed_file(file.filename):
                html += '<div class="message error">❌ File type not allowed. Use: mp3, wav, flac, ogg</div>'
            else:
                try:
                    # Save uploaded file
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    base_name = os.path.splitext(file.filename)[0]
                    safe_name = f"{base_name}_{timestamp}"

                    filepath = os.path.join(UPLOAD_FOLDER, f"{safe_name}.wav")
                    file.save(filepath)

                    info = get_file_info(filepath)

                    html += f'''
                    <div class="message success">✅ File uploaded successfully</div>
                    <div class="file-info">
                        <h3>📁 File Information:</h3>
                        <p><strong>Name:</strong> {file.filename}</p>
                        <p><strong>Size:</strong> {info['size_kb']} KB</p>
                        <p><strong>Upload time:</strong> {info['upload_time']}</p>
                    </div>
                    '''

                    # Separate audio
                    html += '<div class="message info">🔄 Separating audio into stems...</div>'
                    separated_folder = os.path.join(SEPARATED_FOLDER, safe_name)
                    stem_files = separate_audio(filepath, separated_folder)

                    html += f'''
                    <div class="message success">✅ Audio separated successfully!</div>
                    <div class="file-info">
                        <h3>🎼 Separated Stems:</h3>
                        <div class="stems-list">
                            <div class="stem-item">🥁 Drums</div>
                            <div class="stem-item">🎸 Bass</div>
                            <div class="stem-item">🎹 Other</div>
                            <div class="stem-item">🎤 Vocals</div>
                        </div>
                        <p style="margin-top: 15px;">
                            <a href="/download_stems/{safe_name}" class="download-link">📦 Download All Stems</a>
                        </p>
                    </div>
                    '''

                    # Get remix prompt
                    remix_prompt = request.form.get('remix_prompt', 'upbeat electronic music with strong drums')
                    duration = int(request.form.get('duration', 30))

                    html += '<div class="message info">🎨 Creating remix with MusicGen...</div>'

                    remix_path = os.path.join(REMIX_FOLDER, safe_name)
                    remix_file = create_remix(stem_files, remix_prompt, remix_path, duration)

                    html += f'''
                    <div class="message success">✅ Remix created successfully!</div>
                    <div class="file-info">
                        <h3>🎧 Your Remix:</h3>
                        <p><strong>Prompt used:</strong> "{remix_prompt}"</p>
                        <p><strong>Duration:</strong> {duration} seconds</p>
                        <audio controls style="width: 100%; margin: 15px 0;">
                            <source src="/play_remix/{safe_name}" type="audio/wav">
                        </audio>
                        <p>
                            <a href="/download_remix/{safe_name}" class="download-link">⬇️ Download Remix</a>
                        </p>
                    </div>
                    '''

                except Exception as e:
                    html += f'<div class="message error">❌ Error: {str(e)}</div>'

    html += '''
            <form method="POST" enctype="multipart/form-data" id="uploadForm">
                <label>🎵 Select Audio File:</label>
                <input type="file" name="audio_file" accept=".mp3,.wav,.flac,.ogg" required>

                <label>✨ Remix Prompt (describe the style you want):</label>
                <textarea name="remix_prompt" placeholder="e.g., upbeat electronic music with strong drums and energetic bass">upbeat electronic music with strong drums</textarea>

                <label>⏱️ Duration (seconds):</label>
                <input type="number" name="duration" value="30" min="5" max="60">

                <button type="submit">🚀 Upload & Create Remix</button>
            </form>

            <div class="loader" id="loader">
                <div class="spinner"></div>
                <p>Processing... This may take a few minutes</p>
            </div>
        </div>

        <script>
            document.getElementById('uploadForm').onsubmit = function() {
                document.getElementById('loader').style.display = 'block';
            };
        </script>
    </body>
    </html>
    '''

    return html


@app.route('/download_stems/<folder_name>')
def download_stems(folder_name):
    """Download all stems as a ZIP file"""
    separated_folder = os.path.join(SEPARATED_FOLDER, folder_name)
    zip_path = os.path.join(SEPARATED_FOLDER, f"{folder_name}_stems.zip")

    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for stem in ['drums', 'bass', 'other', 'vocals']:
            stem_file = os.path.join(separated_folder, f"{stem}.wav")
            if os.path.exists(stem_file):
                zipf.write(stem_file, f"{stem}.wav")

    return send_file(zip_path, as_attachment=True)


@app.route('/download_remix/<file_name>')
def download_remix(file_name):
    """Download the remix file"""
    remix_path = os.path.join(REMIX_FOLDER, f"{file_name}.wav")
    return send_file(remix_path, as_attachment=True)


@app.route('/play_remix/<file_name>')
def play_remix(file_name):
    """Stream the remix for playback"""
    remix_path = os.path.join(REMIX_FOLDER, f"{file_name}.wav")
    return send_file(remix_path, mimetype='audio/wav')


if __name__ == '__main__':
    app.run(debug=True, port=5000)