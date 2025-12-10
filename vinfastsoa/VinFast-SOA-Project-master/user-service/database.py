# database.py

from flask_sqlalchemy import SQLAlchemy
from passlib.context import CryptContext

# Khởi tạo đối tượng SQLAlchemy
db = SQLAlchemy()

# Khởi tạo công cụ băm mật khẩu (Dùng thuật toán an toàn)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

class User(db.Model):
    """Định nghĩa mô hình User cho dịch vụ này."""
    
    # Định nghĩa tên bảng
    __tablename__ = 'users' 
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    # Lưu mật khẩu đã băm (hash), không bao giờ lưu mật khẩu gốc!
    password_hash = db.Column(db.String(128), nullable=False) 
    role = db.Column(db.String(20), default='customer') # customer, admin, dealer

    def set_password(self, password):
        """Hàm băm và lưu mật khẩu"""
        self.password_hash = pwd_context.hash(password)

    def verify_password(self, password):
        """Hàm kiểm tra mật khẩu nhập vào có khớp không"""
        return pwd_context.verify(password, self.password_hash)

    def to_dict(self):
        """Trả về User dưới dạng Dict để tạo JSON Response"""
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role
        }