import os
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import traceback

app = Flask(__name__)

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'epub'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL')

active_model = None
model_name = "Unknown"

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        available_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
            print(f"Available models: {available_models}")
        except Exception as e:
            print(f"Error listing models: {e}")

        target_model = None
        if GEMINI_MODEL:
            target_model = GEMINI_MODEL
        elif available_models:
            pros = [m for m in available_models if 'pro' in m.lower() and '1.5' in m]
            if pros: target_model = pros[0]
            else:
                flashs = [m for m in available_models if 'flash' in m.lower()]
                if flashs: target_model = flashs[0]
                else: target_model = available_models[0]
            
            if target_model.startswith('models/'):
                target_model = target_model.replace('models/', '')

        if not target_model: target_model = 'gemini-pro'

        print(f"Selected Model: {target_model}")
        model_name = target_model
        active_model = genai.GenerativeModel(target_model)
        
    except Exception as e:
        print(f"Error configuring Gemini: {e}")
else:
    print("Warning: GEMINI_API_KEY not found")

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({'url': f'/static/uploads/{filename}', 'filename': filename})
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/api/translate', methods=['POST'])
def translate_text():
    if not active_model: return jsonify({'error': 'Server Error: Model not initialized.'}), 500
    
    data = request.json
    text = data.get('text', '')
    if not text: return jsonify({'error': 'No text provided'}), 400

    try:
        print(f"Translating with {model_name}...")
        prompt = f"Translate the following text to Traditional Chinese (Taiwan). Only output the translation.\n\n{text}"
        response = active_model.generate_content(prompt)
        if response.text: return jsonify({'translation': response.text})
        else: return jsonify({'error': 'Empty response'}), 500
    except Exception as e:
        return jsonify({'error': f"API Error ({model_name}): {str(e)}"}), 500

@app.route('/api/define', methods=['POST'])
def define_word():
    if not active_model: return jsonify({'error': 'Model not initialized'}), 500
    
    data = request.json
    word = data.get('word', '')
    context = data.get('context', '')
    
    try:
        # Professional Dictionary Prompt 🎓
        prompt = f"""
        Act as a professional English-Chinese Dictionary (like Oxford or Longman).
        Analyze the word "{word}" based on this context: "{context}".
        
        Provide the output in clean HTML format (only inside body tags, no markdown blocks).
        
        Style Guide:
        - Use <h4 style="margin: 10px 0 5px; color: #db2777;"> for headers.
        - Use <b> for emphasis.
        - Use <ul style="padding-left: 20px; color: #4b5563;"> for lists.
        
        Structure:
        1. Word Header: Word + IPA + Part of Speech.
        2. Meaning in Context: Specific meaning in this sentence (Traditional Chinese).
        3. General Definition: English definition + Chinese meaning.
        4. Examples: 2-3 bilingual sentences.
        5. Synonyms/Antonyms: If relevant.
        """
        response = active_model.generate_content(prompt)
        return jsonify({'definition': response.text})
    except Exception as e:
        return jsonify({'error': f"API Error ({model_name}): {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
