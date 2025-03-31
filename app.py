from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory
from werkzeug.utils import secure_filename
from google.cloud import speech
import vertexai
from vertexai.generative_models import GenerativeModel, Part
import os

app = Flask(__name__)

# Configure upload folder
UPLOAD_STT = 'UPLOAD_STT'
ALLOWED_EXTENSIONS = {'wav', 'txt'}
app.config['UPLOAD_STT'] = UPLOAD_STT

os.makedirs(UPLOAD_STT, exist_ok=True)

vertexai.init(project = "js-conversational-ai", location = "us-central1")

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

def process_audio_with_vertexai(audio_content):    
    # Sentiment Analysis with Vertex AI
    model = GenerativeModel("gemini-1.5-flash-001")
    prompt = f"""
                Please provide an exact transcript for the audio, followed by sentiment analysis.
                
                Your reponse should follow the format:
                
                Text: USERS SPEECH TRANSCRIPTION

                SENTIMENT ANALYSIS: Positive | Neutral | Negative
                
            """
    contents = [Part.from_data(audio_content, mime_type="audio/wav"), prompt]
    
    result = model.generate_content(contents)
    print("Results:" + result.text)
    return result.text

@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        return redirect(request.url)
    
    file = request.files['audio_data']
    if file.filename == '':
        return redirect(request.url)
    
    if file:
        timestamp = datetime.now().strftime("%Y%m%d-%I%M%S%p")
        audio_filename = f"{timestamp}.wav"
        audio_file_path = os.path.join(app.config['UPLOAD_STT'], audio_filename)
        file.save(audio_file_path)

        with open(audio_file_path, 'rb') as audio_file:
            audio_content = audio_file.read()

        sentiment_result = process_audio_with_vertexai(audio_content)
        
        transcript_filename = f"{timestamp}_text.txt"
        transcript_path = os.path.join(app.config['UPLOAD_STT'], transcript_filename)
        with open(transcript_path, 'w') as transcript_file:
            transcript_file.write(sentiment_result)
    

    return redirect('/')

@app.route('/upload/<filename>')
def get_file(filename):
    return send_file(filename)

@app.route('/script.js', methods=['GET'])
def scripts_js():
    return send_file('./script.js')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    stt_path = os.path.join(app.config['UPLOAD_STT'], filename)
    
    if os.path.exists(stt_path):
        return send_from_directory(app.config['UPLOAD_STT'], filename)
    else:
        return "File not found", 404

if __name__ == '__main__':
    server_port = os.environ.get('PORT', '8085')
    app.run(debug=False, port=server_port, host='0.0.0.0')
