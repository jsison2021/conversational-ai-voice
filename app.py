from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory
from werkzeug.utils import secure_filename
from google.cloud import speech, texttospeech_v1

import os

app = Flask(__name__)

# Configure upload folder
UPLOAD_STT = 'UPLOAD_STT'
UPLOAD_TTS = 'UPLOAD_TTS'
ALLOWED_EXTENSIONS = {'wav','txt'}
app.config['UPLOAD_STT'] = UPLOAD_STT
app.config['UPLOAD_TTS'] = UPLOAD_TTS

os.makedirs(UPLOAD_STT, exist_ok=True)
os.makedirs(UPLOAD_TTS, exist_ok=True)

# Google Cloud Speech-to-Text client
client_STT = speech.SpeechClient()

# Google Cloud Text-to-Speech client
client_TTS = texttospeech_v1.TextToSpeechClient()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_STT_files():
    files = []
    for filename in os.listdir(UPLOAD_STT):
        if allowed_file(filename):
            files.append(filename)
            print(filename)
    files.sort(reverse=True)
    return files

def get_TTS_files():
    files = []
    for filename in os.listdir(UPLOAD_TTS):
        if allowed_file(filename):
            files.append(filename)
            print(filename)
    files.sort(reverse=True)
    return files

@app.route('/')
def index():
    STT_files = get_STT_files()
    TTS_files = get_TTS_files()
    return render_template('index.html', STT_files=STT_files, TTS_files = TTS_files)

def sample_recognize(content):
    audio = speech.RecognitionAudio(content=content)

    config = speech.RecognitionConfig(
        language_code="en-US",
        model="latest_long",
        audio_channel_count=1,
        enable_word_confidence=True,
        enable_word_time_offsets=True,
    )

    operation = client_STT.long_running_recognize(config=config, audio=audio)
    response = operation.result(timeout=90)

    txt = ''
    for result in response.results:
        txt += result.alternatives[0].transcript + '\n'

    return txt

@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        flash('No audio data')
        return redirect(request.url)
    file = request.files['audio_data']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file:
        # Generate a filename with timestamp
        filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
        file_path = os.path.join(app.config['UPLOAD_STT'], filename)
        file.save(file_path)

        # Read the audio file content
        with open(file_path, 'rb') as f:
            audio_content = f.read()

        # Call the speech-to-text function
        transcript = sample_recognize(audio_content)

        # Save the transcript to a .txt file
        transcript_filename = filename.replace('.wav', '.txt')
        transcript_path = os.path.join(app.config['UPLOAD_STT'], transcript_filename)
        with open(transcript_path, 'w') as txt_file:
            txt_file.write(transcript)

    return redirect('/')  # Success, redirect to homepage

@app.route('/upload/<filename>')
def get_file(filename):
    return send_file(filename)

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

@app.route('/upload_text', methods=['POST'])
def upload_text():
    # Get the input text from the form
    text = request.form['text']
    
    if not text:
        flash('No text provided')
        return redirect(request.url)
    
    # Call the Text-to-Speech function
    audio_content = sample_synthesize_speech(text=text)
    
    # Generate a unique filename for the audio file
    filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
    file_path = os.path.join(app.config['UPLOAD_TTS'], filename)
    
    # Save the audio content to a .wav file
    with open(file_path, 'wb') as audio_file:
        audio_file.write(audio_content)
    
    return redirect('/')  # Success, redirect to the homepage


@app.route('/script.js',methods=['GET'])
def scripts_js():
    return send_file('./script.js')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    stt_path = os.path.join(app.config['UPLOAD_STT'], filename)
    tts_path = os.path.join(app.config['UPLOAD_TTS'], filename)
    
    if os.path.exists(stt_path):
        return send_from_directory(app.config['UPLOAD_STT'], filename)
    elif os.path.exists(tts_path):
        return send_from_directory(app.config['UPLOAD_TTS'], filename)
    else:
        return "File not found", 404

if __name__ == '__main__':
    server_port = os.environ.get('PORT', '8080')
    app.run(debug=False, port=server_port, host='0.0.0.0')