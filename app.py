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
        # 強制使用 HTML 結構的 Prompt
        prompt = f"""
        Act as a professional linguistic expert. Analyze the word "{word}" in the context: "{context}".
        
        Output valid HTML code using this EXACT structure (do not use markdown blocks):
        
        <div class="dict-card">
            <div class="dict-header">
                <span class="dict-word">{word}</span>
                <span class="dict-cn">Traditional Chinese Translation</span>
                <span class="dict-ipa">[IPA Pronunciation]</span>
                <span class="dict-pos">part of speech</span>
            </div>
            
            <div class="dict-section context-meaning">
                <h4>🎯 上下文精準釋義</h4>
                <p>Explain the precise meaning of "{word}" in this specific sentence. Translate the explanation to Traditional Chinese.</p>
            </div>

            <div class="dict-section">
                <h4>📚 詳細定義</h4>
                <ul>
                    <li><strong>English:</strong> Standard definition.</li>
                    <li><strong>Chinese:</strong> Traditional Chinese translation.</li>
                </ul>
            </div>

            <div class="dict-section examples">
                <h4>🗣️ 雙語例句</h4>
                <ul>
                    <li>
                        <p class="en">Example sentence 1.</p>
                        <p class="zh">Chinese translation.</p>
                    </li>
                    <li>
                        <p class="en">Example sentence 2.</p>
                        <p class="zh">Chinese translation.</p>
                    </li>
                </ul>
            </div>
            
            <div class="dict-section footer">
                <p>💡 <span class="dict-note">Synonyms: synonym1, synonym2</span></p>
            </div>
        </div>
        """
        response = active_model.generate_content(prompt)
        # 清理可能跑出來的 markdown code block
        clean_text = response.text.replace('```html', '').replace('```', '')
        return jsonify({'definition': clean_text})
    except Exception as e:
        return jsonify({'error': f"API Error ({model_name}): {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
