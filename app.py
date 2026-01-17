from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import json
import os
from datetime import datetime, timedelta
from config import GEMINI_API_KEY, SECRET_KEY
import google.genai as genai
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///science_assistant.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/pdfs'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configure Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

# ==================== MODELS ====================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'user' or 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ChatLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user_message = db.Column(db.Text, nullable=False)
    bot_answer = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    session_id = db.Column(db.String(100))
    response_time = db.Column(db.Float)  # in seconds

class DownloadLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class FAQ(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    keywords = db.Column(db.Text)  # JSON string of keywords
    category = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255))
    category = db.Column(db.String(100))
    file_path = db.Column(db.String(500))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    download_count = db.Column(db.Integer, default=0)

# ==================== LOGIN MANAGER ====================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== DECORATORS ====================

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'admin':
            flash('คุณไม่มีสิทธิ์เข้าถึงหน้านี้', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== ROUTES ====================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('ชื่อผู้ใช้นี้มีอยู่แล้ว', 'error')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('อีเมลนี้มีอยู่แล้ว', 'error')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('ลงทะเบียนสำเร็จ! กรุณาเข้าสู่ระบบ', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('เข้าสู่ระบบสำเร็จ!', 'success')
            
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home'))
        
        flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'error')
    
    return render_template('login.html')

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash('ออกจากระบบสำเร็จ', 'success')
    return redirect(url_for('home'))

@app.route("/chat")
def chat():
    return render_template("chat.html")

@app.route("/downloads")
def downloads():
    documents = Document.query.filter_by().order_by(Document.category, Document.filename).all()
    
    # Group by category
    categories = {}
    for doc in documents:
        if doc.category not in categories:
            categories[doc.category] = []
        categories[doc.category].append(doc)
    
    return render_template("downloads.html", categories=categories)

@app.route("/download/<int:doc_id>")
def download_file(doc_id):
    doc = Document.query.get_or_404(doc_id)
    
    # Log download
    log = DownloadLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        filename=doc.filename,
        category=doc.category
    )
    db.session.add(log)
    
    # Increment download count
    doc.download_count += 1
    db.session.commit()
    
    return send_from_directory(
        os.path.dirname(doc.file_path),
        os.path.basename(doc.file_path),
        as_attachment=True,
        download_name=doc.original_filename
    )

# ==================== API ROUTES ====================

@app.route("/api/chat", methods=["POST"])
def chat_api():
    start_time = datetime.utcnow()
    user_message = request.json.get("message", "").strip()
    
    if not user_message:
        return jsonify({"error": "กรุณาพิมพ์ข้อความ"}), 400
    
    # Search in FAQ first
    faqs = FAQ.query.filter_by(is_active=True).all()
    for faq in faqs:
        keywords = json.loads(faq.keywords) if faq.keywords else []
        if any(kw.lower() in user_message.lower() for kw in keywords):
            answer = faq.answer
            
            # Log chat
            response_time = (datetime.utcnow() - start_time).total_seconds()
            log = ChatLog(
                user_id=current_user.id if current_user.is_authenticated else None,
                user_message=user_message,
                bot_answer=answer,
                session_id=session.get('chat_session_id'),
                response_time=response_time
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({"response": answer, "source": "faq"})
    
    # Use Gemini AI
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=user_message
        )
        answer = response.text
        
        # Log chat
        response_time = (datetime.utcnow() - start_time).total_seconds()
        log = ChatLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            user_message=user_message,
            bot_answer=answer,
            session_id=session.get('chat_session_id'),
            response_time=response_time
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({"response": answer, "source": "ai"})
    
    except Exception as e:
        return jsonify({"error": "เกิดข้อผิดพลาดในการประมวลผล"}), 500

@app.route("/api/search_pdf", methods=["POST"])
def search_pdf():
    keyword = request.json.get("keyword", "").lower()
    
    documents = Document.query.filter(
        Document.filename.ilike(f'%{keyword}%') |
        Document.original_filename.ilike(f'%{keyword}%') |
        Document.category.ilike(f'%{keyword}%')
    ).all()
    
    results = [{
        "id": doc.id,
        "filename": doc.original_filename or doc.filename,
        "category": doc.category,
        "download_count": doc.download_count
    } for doc in documents]
    
    return jsonify(results)

# ==================== ADMIN ROUTES ====================

@app.route("/admin")
@admin_required
def admin_dashboard():
    # Statistics
    total_users = User.query.count()
    total_chats = ChatLog.query.count()
    total_downloads = DownloadLog.query.count()
    total_documents = Document.query.count()
    
    # Recent activity
    recent_chats = ChatLog.query.order_by(ChatLog.timestamp.desc()).limit(10).all()
    recent_downloads = DownloadLog.query.order_by(DownloadLog.timestamp.desc()).limit(10).all()
    
    # Chat statistics by date (last 7 days)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    daily_chats = db.session.query(
        db.func.date(ChatLog.timestamp).label('date'),
        db.func.count(ChatLog.id).label('count')
    ).filter(ChatLog.timestamp >= seven_days_ago).group_by(
        db.func.date(ChatLog.timestamp)
    ).all()
    
    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        total_chats=total_chats,
        total_downloads=total_downloads,
        total_documents=total_documents,
        recent_chats=recent_chats,
        recent_downloads=recent_downloads,
        daily_chats=daily_chats
    )

@app.route("/admin/faqs")
@admin_required
def admin_faqs():
    faqs = FAQ.query.order_by(FAQ.category, FAQ.created_at.desc()).all()
    return render_template('admin/faqs.html', faqs=faqs)

@app.route("/admin/faq/add", methods=['POST'])
@admin_required
def add_faq():
    question = request.form.get('question')
    answer = request.form.get('answer')
    keywords = request.form.get('keywords')  # comma-separated
    category = request.form.get('category')
    
    faq = FAQ(
        question=question,
        answer=answer,
        keywords=json.dumps([k.strip() for k in keywords.split(',')]),
        category=category
    )
    
    db.session.add(faq)
    db.session.commit()
    
    flash('เพิ่ม FAQ สำเร็จ', 'success')
    return redirect(url_for('admin_faqs'))

@app.route("/admin/documents")
@admin_required
def admin_documents():
    documents = Document.query.order_by(Document.upload_date.desc()).all()
    return render_template('admin/documents.html', documents=documents)

@app.route("/admin/users")
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

# ==================== INITIALIZATION ====================

@app.before_request
def before_request_func():
    """Function to run before each request"""
    if 'chat_session_id' not in session:
        session['chat_session_id'] = os.urandom(16).hex()

def init_database():
    """Initialize database and create default admin"""
    with app.app_context():
        db.create_all()
        
        # Create default admin if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', email='admin@science.ku.th', role='admin')
            admin.set_password('admin1234')  # Change this in production!
            db.session.add(admin)
            db.session.commit()
            print("✅ Default admin created: username='admin', password='admin1234'")

if __name__ == "__main__":
    # Initialize database before running
    init_database()
    app.run(debug=True, host='0.0.0.0', port=5000)