# user-service/app.py

from flask import Flask, request, jsonify
from database import db, User
import jwt 
import datetime
import os
from flask_cors import CORS # Thêm CORS
from passlib.context import CryptContext
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

# --- Cấu hình DB và App (Cần giống database.py) ---
app = Flask(__name__)
CORS(app) # Kích hoạt CORS
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///user_service.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app) # Khởi tạo SQLAlchemy với app
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# Khai báo lại model ở đây để tránh lỗi Import (dù tốt nhất nên import từ database.py)
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

# --- KHỞI TẠO DỮ LIỆU DEMO ---

def initialize_db():
    with app.app_context():
        db_path = 'user_service.db'
        if os.path.exists(db_path):
             os.remove(db_path) 
             
        db.create_all()
        
        # Tạo Admin cố định
        admin_email = 'admin@vinfast.com'
        if not User.query.filter_by(email=admin_email).first():
            from faker import Faker
            fake = Faker('vi_VN')
            admin = User(name='Admin VinFast', email=admin_email, role='admin')
            admin.set_password('123456') 
            db.session.add(admin)

            # Tạo 3 user khách hàng demo
            for i in range(1, 4):
                user = User(name=f'Khách hàng Demo {i}', email=f'user{i}@test.com', role='customer')
                user.set_password('password') 
                db.session.add(user)

            db.session.commit()
            print("Đã khởi tạo DB Người dùng thành công.")

@app.before_request
def setup_data():
    if not hasattr(app, 'db_initialized'):
        initialize_db()
        app.db_initialized = True

# --- API ENDPOINTS ---

@app.route('/api/v1/users/register', methods=['POST'])
def register():
    # ... (Logic đăng ký giữ nguyên)
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
    
    return jsonify({"user_id": new_user.id, "message": "Đăng ký tài khoản thành công"}), 201

@app.route('/api/v1/users/login', methods=['POST'])
def login():
    # ... (Logic đăng nhập giữ nguyên)
    data = request.json
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()

    if user and user.verify_password(password):
        # Tạo JWT Token payload
        token_payload = {
            'user_id': user.id,
            'role': user.role,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }
        token = jwt.encode(token_payload, 'your_super_secret_key_for_jwt', algorithm='HS256')
        
        return jsonify({
            'message': 'Đăng nhập thành công',
            'token': token
        }), 200
    
    return jsonify({"message": "Email hoặc mật khẩu không chính xác"}), 401

@app.route('/api/v1/users/<int:user_id>', methods=['GET'])
def get_user_info(user_id):
    """API để T3 và T4 lấy thông tin người dùng."""
    user = User.query.get(user_id)
    if user:
        return jsonify(user.to_dict()), 200
    return jsonify({"message": "Người dùng không tồn tại"}), 404



# --- BỔ SUNG API CHO DASHBOARD (CÂU 2) ---
@app.route('/api/v1/reports/users/roles', methods=['GET'])
def get_user_role_stats():
    """API thống kê số lượng User theo Role cho biểu đồ"""
    try:
        # Query: Đếm số lượng user theo từng role
        stats = db.session.query(User.role, func.count(User.id)).group_by(User.role).all()

        # Chuẩn bị dữ liệu cho Chart.js
        labels = []
        data = []

        # Dịch tên role sang tiếng Việt cho đẹp
        role_map = {'admin': 'Quản trị viên', 'customer': 'Khách hàng', 'dealer': 'Đại lý'}

        for s in stats:
            role_name = s[0]
            count = s[1]
            labels.append(role_map.get(role_name, role_name))
            data.append(count)

        return jsonify({
            "chart_type": "pie",
            "data": {
                "labels": labels,
                "datasets": [{
                    "data": data,
                    "backgroundColor": ["#FF6384", "#36A2EB", "#FFCE56"]
                }]
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    
# --- CHẠY DỊCH VỤ ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Đảm bảo tables được tạo nếu chưa có
        
    print("User Service đang khởi động trên cổng 5001...")
    app.run(port=5001, debug=True)