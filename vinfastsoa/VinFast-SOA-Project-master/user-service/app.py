# user-service/app.py

from flask import Flask, request, jsonify
from database import db, User
import jwt 
import datetime
import os 
from flask_cors import CORS 
from passlib.context import CryptContext
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

app = Flask(__name__)
CORS(app)

# --- CẤU HÌNH BẢO MẬT & DATABASE ---
# Lấy Key từ Docker Environment, nếu không có thì dùng key dự phòng
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'fallback_secret_key_123')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///user_service.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# --- MODEL USER ---
class User(db.Model):
    __tablename__ = 'users' 
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='customer') 

    def set_password(self, password):
        self.password_hash = pwd_context.hash(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role
        }

# --- KHỞI TẠO DỮ LIỆU ---
def initialize_db():
    with app.app_context():
        db_path = 'user_service.db'
        # Chỉ tạo lại nếu chưa tồn tại file DB để tránh mất dữ liệu khi restart
        if not os.path.exists(db_path):
             db.create_all()
             # Logic tạo user demo (nếu cần thiết có thể thêm lại ở đây)
             print("Đã khởi tạo DB mới.")

@app.before_request
def setup_data():
    if not hasattr(app, 'db_initialized'):
        # initialize_db() 
        app.db_initialized = True

# --- HÀM PHỤ TRỢ: LẤY USER TỪ TOKEN ---
def get_user_from_token():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None, "Thiếu Token xác thực"
    
    try:
        # Token format: "Bearer <token>"
        token = auth_header.split(" ")[1]
        # Giải mã bằng Key bảo mật từ biến môi trường
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        user_id = payload['user_id']
        user = User.query.get(user_id)
        if not user:
            return None, "User không tồn tại"
        return user, None
    except Exception:
        return None, "Token không hợp lệ hoặc đã hết hạn"

# --- API ENDPOINTS ---

@app.route('/api/v1/users/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not all([name, email, password]):
        return jsonify({"message": "Thiếu thông tin bắt buộc!"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Email đã tồn tại!"}), 409

    new_user = User(name=name, email=email)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({"user_id": new_user.id, "message": "Đăng ký thành công"}), 201

@app.route('/api/v1/users/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()

    if user and user.verify_password(password):
        token_payload = {
            'user_id': user.id,
            'role': user.role,
          'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
        }
        # Dùng JWT_SECRET_KEY động
        token = jwt.encode(token_payload, JWT_SECRET_KEY, algorithm='HS256')
        
        return jsonify({
            'message': 'Đăng nhập thành công',
            'token': token
        }), 200
    
    return jsonify({"message": "Email hoặc mật khẩu sai"}), 401

@app.route('/api/v1/users/<int:user_id>', methods=['GET'])
def get_user_info(user_id):
    user = User.query.get(user_id)
    if user:
        return jsonify(user.to_dict()), 200
    return jsonify({"message": "User không tồn tại"}), 404

# --- API MỚI 1: CẬP NHẬT THÔNG TIN ---
@app.route('/api/v1/users/update', methods=['PUT'])
def update_profile():
    user, error = get_user_from_token()
    if error:
        return jsonify({"message": error}), 401
    
    data = request.json
    new_name = data.get('name')
    new_email = data.get('email')

    if new_name:
        user.name = new_name
    
    if new_email and new_email != user.email:
        # Kiểm tra xem email mới có trùng với ai không
        if User.query.filter_by(email=new_email).first():
             return jsonify({"message": "Email này đã được sử dụng!"}), 409
        user.email = new_email

    db.session.commit()
    return jsonify({"message": "Cập nhật thành công!", "user": user.to_dict()}), 200

# --- API MỚI 2: ĐỔI MẬT KHẨU ---
@app.route('/api/v1/users/change-password', methods=['PUT'])
def change_password():
    user, error = get_user_from_token()
    if error:
        return jsonify({"message": error}), 401

    data = request.json
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if not old_password or not new_password:
        return jsonify({"message": "Vui lòng nhập mật khẩu cũ và mới"}), 400

    if not user.verify_password(old_password):
        return jsonify({"message": "Mật khẩu cũ không chính xác"}), 401

    user.set_password(new_password)
    db.session.commit()

    return jsonify({"message": "Đổi mật khẩu thành công!"}), 200

# --- API BÁO CÁO ---
@app.route('/api/v1/reports/users/roles', methods=['GET'])
def get_user_role_stats():
    try:
        stats = db.session.query(User.role, func.count(User.id)).group_by(User.role).all()
        labels = [s[0] for s in stats]
        data = [s[1] for s in stats]
        return jsonify({"chart_type": "pie", "data": {"labels": labels, "datasets": [{"data": data}]}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    print("User Service đang khởi động trên cổng 5001...")
    app.run(host='0.0.0.0', port=5001, debug=True)