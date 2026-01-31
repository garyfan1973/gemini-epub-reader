import os
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import traceback

app = Flask(__name__)

# 設定上傳目錄
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'epub'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 設定 Gemini API
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # 改用更穩定的 gemini-1.5-flash
        model = genai.GenerativeModel('gemini-1.5-flash')
        print("Gemini API configured successfully with gemini-1.5-flash")
    except Exception as e:
        print(f"Error configuring Gemini: {e}")
        model = None
else:
    print("Warning: GEMINI_API_KEY not found in environment variables")
    model = None

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({'url': f'/static/uploads/{filename}', 'filename': filename})
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/api/translate', methods=['POST'])
def translate_text():
    if not GEMINI_API_KEY:
         return jsonify({'error': 'Server Error: GEMINI_API_KEY not set in env'}), 500

    if not model:
        return jsonify({'error': 'Server Error: Gemini model failed to initialize'}), 500
    
    data = request.json
    text = data.get('text', '')
    if not text:
        return jsonify({'error': 'No text provided'}), 400

    try:
        print(f"Translating text: {text[:50]}...")
        prompt = f"Translate the following text to Traditional Chinese (Taiwan). Only output the translation, nothing else.\n\nText:\n{text}"
        
        response = model.generate_content(prompt)
        
        if response.text:
            return jsonify({'translation': response.text})
        else:
            return jsonify({'error': 'Empty response from Gemini (Safety block?)'}), 500

    except Exception as e:
        error_msg = str(e)
        print(f"Translation Error: {traceback.format_exc()}")
        return jsonify({'error': f"Gemini Error: {error_msg}"}), 500

@app.route('/api/define', methods=['POST'])
def define_word():
    if not model:
        return jsonify({'error': 'Gemini API not configured'}), 500
    
    data = request.json
    word = data.get('word', '')
    context = data.get('context', '')
    
    if not word:
        return jsonify({'error': 'No word provided'}), 400

    try:
        print(f"Defining word: {word}")
        prompt = f"""
        Explain the word "{word}" in Traditional Chinese.
        Context: "{context}"
        
        Format as HTML:
        <p><b>{word}</b> [IPA if possible] (part of speech)</p>
        <p>Meaning in context...</p>
        <ul>
            <li>Example 1 (En/Zh)</li>
            <li>Example 2 (En/Zh)</li>
        </ul>
        """
        response = model.generate_content(prompt)
        return jsonify({'definition': response.text})
    except Exception as e:
        print(f"Definition Error: {traceback.format_exc()}")
        return jsonify({'error': f"Gemini Error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
