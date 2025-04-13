from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory
from werkzeug.utils import secure_filename
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.cloud import texttospeech_v1

import os

app = Flask(__name__)

# Configure upload folder
UPLOAD_STT = 'UPLOAD_STT'
ALLOWED_EXTENSIONS = {'wav', 'pdf'}
app.config['UPLOAD_STT'] = UPLOAD_STT

os.makedirs(UPLOAD_STT, exist_ok=True)

vertexai.init(project = "js-conversational-ai", location = "us-central1")

client_TTS = texttospeech_v1.TextToSpeechClient()

@app.route('/')
def index():
    STT_files = get_STT_files()
    return render_template('index.html', STT_files=STT_files)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_STT_files():
    files = [filename for filename in os.listdir(UPLOAD_STT) if allowed_file(filename)]
    files.sort(reverse=True)
    return files

def process_audio_and_pdf_with_vertexai(audio_content, pdf_content):    
    # Sentiment Analysis with Vertex AI
    model = GenerativeModel("gemini-1.5-flash-001")
    prompt = f"""
                Answer the user's query in the audio file based and use the PDF file as a reference.
                
            """
    contents = [Part.from_data(audio_content, mime_type="audio/wav"), Part.from_data(pdf_content, mime_type = "application/pdf"), prompt]
    
    result = model.generate_content(contents)
    print(result.text)
    return result.text


def sample_synthesize_speech(text=None, ssml=None):
    input = texttospeech_v1.SynthesisInput()
    if ssml:
      input.ssml = ssml
    else:
      input.text = text

    voice = texttospeech_v1.VoiceSelectionParams()
    voice.language_code = "en-UK"
    # voice.ssml_gender = "MALE"

    audio_config = texttospeech_v1.AudioConfig()
    audio_config.audio_encoding = "LINEAR16"

    request = texttospeech_v1.SynthesizeSpeechRequest(
        input=input,
        voice=voice,
        audio_config=audio_config,
    )

    response = client_TTS.synthesize_speech(request=request)

    return response.audio_content

@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    pdf = request.files.get('pdf_file')
    if pdf and pdf.filename != '':
        timestamp = datetime.now().strftime("%Y%m%d-%I%M%S%p")

        # Reset the STT folder
        for f in os.listdir(app.config['UPLOAD_STT']):
            file_path = os.path.join(app.config['UPLOAD_STT'], f)
            if os.path.isfile(file_path):
                os.remove(file_path)

        pdf_filename = f"{secure_filename(pdf.filename)}_{timestamp}.pdf"
        pdf_file_path = os.path.join(app.config['UPLOAD_STT'], pdf_filename)
        pdf.save(pdf_file_path)

    return redirect('/')

@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        return abort(400, "No audio file uploaded.")

    file = request.files['audio_data']
    if file.filename == '':
        return abort(400, "Empty audio file.")

    # Find latest PDF
    pdf_files = [f for f in os.listdir(app.config['UPLOAD_STT']) if f.lower().endswith('.pdf')]
    if not pdf_files:
        return abort(400, "No PDF uploaded yet.")
    pdf_files.sort(reverse=True)
    pdf_file_path = os.path.join(app.config['UPLOAD_STT'], pdf_files[0])
    pdf_filename = pdf_files[0]

    # Save audio
    timestamp = datetime.now().strftime("%Y%m%d-%I%M%S%p")
    audio_filename = f"question_{timestamp}.wav"
    audio_file_path = os.path.join(app.config['UPLOAD_STT'], audio_filename)
    file.save(audio_file_path)

    # Process
    with open(audio_file_path, 'rb') as audio_file:
        audio_content = audio_file.read()

    with open(pdf_file_path, 'rb') as pdf_file:
        pdf_content = pdf_file.read()

    sentiment_result = process_audio_and_pdf_with_vertexai(audio_content, pdf_content)
    audio_response_content = sample_synthesize_speech(text=sentiment_result)

    # Save response audio
    response_audio_filename = f"answer_{timestamp}.wav"
    response_audio_path = os.path.join(app.config['UPLOAD_STT'], response_audio_filename)
    with open(response_audio_path, 'wb') as audio_file:
        audio_file.write(audio_response_content)

    return redirect('/')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    stt_path = os.path.join(app.config['UPLOAD_STT'], filename)
    
    if os.path.exists(stt_path):
        return send_from_directory(app.config['UPLOAD_STT'], filename)
    else:
        return "File not found", 404

if __name__ == '__main__':
    server_port = os.environ.get('PORT', '8080')
    app.run(debug=False, port=server_port, host='0.0.0.0')
