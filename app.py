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
# 預設使用 gemini-2.0-flash-exp (夠新了吧！😤)
# 你可以在 Zeabur 環境變數設定 GEMINI_MODEL 來更換
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash-exp')

model = None

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        print(f"Gemini API configured with model: {GEMINI_MODEL}")
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
    if not model:
        return jsonify({'error': 'Server Error: Model not initialized. Check server logs.'}), 500
    
    data = request.json
    text = data.get('text', '')
    if not text: return jsonify({'error': 'No text provided'}), 400

    try:
        print(f"Translating with {GEMINI_MODEL}...")
        prompt = f"Translate the following text to Traditional Chinese (Taiwan). Only output the translation.\n\n{text}"
        response = model.generate_content(prompt)
        
        if response.text:
            return jsonify({'translation': response.text})
        else:
            return jsonify({'error': 'Empty response from Gemini'}), 500

    except Exception as e:
        # 將真正的錯誤回傳給前端！
        error_msg = str(e)
        print(f"Gemini Error: {error_msg}")
        return jsonify({'error': f"API Error: {error_msg}"}), 500

@app.route('/api/define', methods=['POST'])
def define_word():
    if not model: return jsonify({'error': 'Model not initialized'}), 500
    
    data = request.json
    word = data.get('word', '')
    context = data.get('context', '')
    
    try:
        prompt = f"""Explain "{word}" in Traditional Chinese. Context: "{context}". Format as HTML."""
        response = model.generate_content(prompt)
        return jsonify({'definition': response.text})
    except Exception as e:
        return jsonify({'error': f"API Error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
