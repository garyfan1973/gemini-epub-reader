import os
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)

# 設定上傳目錄
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'epub'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 設定 Gemini API
# 在 Zeabur 上部署時，記得在環境變數設定 GEMINI_API_KEY
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # 使用 Gemini Pro 模型
    model = genai.GenerativeModel('gemini-pro')
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
        # 回傳檔案的 URL 供前端 epub.js 讀取
        return jsonify({'url': f'/static/uploads/{filename}', 'filename': filename})
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/api/translate', methods=['POST'])
def translate_text():
    if not model:
        return jsonify({'error': 'Gemini API not configured'}), 500
    
    data = request.json
    text = data.get('text', '')
    if not text:
        return jsonify({'error': 'No text provided'}), 400

    try:
        # Prompt Engineering: 要求 Gemini 翻譯
        prompt = f"請將以下英文段落翻譯成繁體中文，保持語氣通順：\n\n{text}"
        response = model.generate_content(prompt)
        return jsonify({'translation': response.text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/define', methods=['POST'])
def define_word():
    if not model:
        return jsonify({'error': 'Gemini API not configured'}), 500
    
    data = request.json
    word = data.get('word', '')
    context = data.get('context', '') # 傳入上下文可以讓定義更精準
    
    if not word:
        return jsonify({'error': 'No word provided'}), 400

    try:
        # Prompt Engineering: 要求 Gemini 提供定義、用法、例句
        prompt = f"""
        請針對單字 "{word}" 提供詳細解釋。
        上下文句子："{context}"
        
        請依序提供：
        1. 該單字在上下文中的中文含義
        2. 詞性與發音（KK音標）
        3. 英文定義
        4. 兩個中英文例句
        
        請用 HTML 格式回傳，方便直接顯示（使用 <b>, <ul>, <li> 等標籤）。
        """
        response = model.generate_content(prompt)
        return jsonify({'definition': response.text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
