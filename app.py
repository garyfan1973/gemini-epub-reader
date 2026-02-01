import os
from openai import OpenAI
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from dotenv import load_dotenv
import traceback

load_dotenv() # Load environment variables from .env file

app = Flask(__name__)

# --- Config ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-please-change')

# Database Config: Auto-detect PostgreSQL (Zeebur) or fallback to SQLite
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Mail Config (Environment Variables)
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', app.config['MAIL_USERNAME'])

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'epub'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Extensions ---
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
mail = Mail(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Database Creation (Ensure tables exist) ---
with app.app_context():
    db.create_all()

# --- Groq API Setup (免費方案) ---
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
model_name = GROQ_MODEL

if not GROQ_API_KEY:
    print("⚠️  WARNING: GROQ_API_KEY not set. Translation/Dictionary features will not work.")
    client = None
else:
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=GROQ_API_KEY
    )
    print(f"Using Groq with model: {model_name}")

# --- Helper Functions ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Auth Routes ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        try:
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']
            
            if User.query.filter_by(username=username).first():
                flash('Username already exists')
                return redirect(url_for('register'))
            if User.query.filter_by(email=email).first():
                flash('Email already registered')
                return redirect(url_for('register'))
                
            new_user = User(username=username, email=email)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('index'))
        except Exception as e:
            print("Register Error:")
            traceback.print_exc()
            flash(f"Error: {str(e)}")
            return render_template('register.html')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            token = serializer.dumps(email, salt='password-reset-salt')
            link = url_for('reset_password', token=token, _external=True)
            msg = Message('Password Reset Request', recipients=[email])
            msg.body = f'Click to reset your password: {link}'
            try:
                mail.send(msg)
                flash('Reset link sent to your email')
            except Exception as e:
                flash(f'Error sending email: {str(e)}')
        else:
            flash('Email not found')
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        flash('The token is invalid or expired.')
        return redirect(url_for('forgot_password'))
        
    if request.method == 'POST':
        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(request.form['password'])
            db.session.commit()
            flash('Password updated! Please login.')
            return redirect(url_for('login'))
    return render_template('reset_password.html')

# --- Main App Routes ---
@app.route('/')
@login_required
def index():
    return render_template('index.html', user=current_user)

@app.route('/upload', methods=['POST'])
@login_required
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
@login_required
def translate_text():
    if not client: return jsonify({'error': 'Server Error: GROQ_API_KEY not configured.'}), 500
    
    data = request.json
    text = data.get('text', '')
    if not text: return jsonify({'error': 'No text provided'}), 400

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a translator. Translate the user's text to Traditional Chinese (Taiwan). Only output the translation, nothing else."},
                {"role": "user", "content": text}
            ]
        )
        translation = response.choices[0].message.content
        if translation: return jsonify({'translation': translation})
        else: return jsonify({'error': 'Empty response'}), 500
    except Exception as e:
        return jsonify({'error': f"API Error ({model_name}): {str(e)}"}), 500

@app.route('/api/define', methods=['POST'])
@login_required
def define_word():
    if not client: return jsonify({'error': 'Server Error: GROQ_API_KEY not configured.'}), 500
    
    data = request.json
    word = data.get('word', '')
    context = data.get('context', '')
    
    try:
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
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a linguistic expert. Output only valid HTML code as instructed."},
                {"role": "user", "content": prompt}
            ]
        )
        result = response.choices[0].message.content
        clean_text = result.replace('```html', '').replace('```', '')
        return jsonify({'definition': clean_text})
    except Exception as e:
        return jsonify({'error': f"API Error ({model_name}): {str(e)}"}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8080)
