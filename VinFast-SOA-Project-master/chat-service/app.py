from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os

app = Flask(__name__)
# Cấu hình CORS mở rộng để đảm bảo Gateway và Frontend đều có thể kết nối
CORS(app, resources={r"/*": {"origins": "*"}})

# Cấu hình SocketIO
# async_mode='eventlet' thường ổn định nhất trong môi trường Docker
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=None)

# Kết nối Database SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///chat_service.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Message(db.Model):
    """Mô hình lưu trữ tin nhắn chat cho từng đơn hàng"""
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, nullable=False) # Gắn với mã đơn hàng
    sender_role = db.Column(db.String(20))           # 'admin', 'customer' hoặc 'system'
    sender_name = db.Column(db.String(100))
    content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=db.func.now())

    def to_dict(self):
        """Trả về dữ liệu dạng dictionary để truyền qua Socket/API"""
        return {
            "order_id": self.order_id, 
            "role": self.sender_role,
            "name": self.sender_name, 
            "content": self.content,
            "time": self.timestamp.strftime("%H:%M")
        }

# Khởi tạo bảng dữ liệu
with app.app_context():
    db.create_all()

@socketio.on('join')
def on_join(data):
    """Xử lý khi một người dùng tham gia vào phòng chat của đơn hàng"""
    if 'order_id' in data:
        # Luôn ép kiểu về String để tránh lệch Room với Gateway
        room = str(data['order_id'])
        join_room(room)
        print(f"✅ User joined room: {room}")

@socketio.on('send_message')
def handle_message(data):
    """Xử lý nhận tin nhắn mới và bắn tới các thành viên trong phòng"""
    if 'order_id' not in data or 'content' not in data: 
        return
        
    room = str(data['order_id'])
    try:
        # 1. Lưu tin nhắn vào Database
        new_msg = Message(
            order_id=data['order_id'],
            sender_role=data.get('role', 'customer'),
            sender_name=data.get('name', 'Khách hàng'),
            content=data['content']
        )
        db.session.add(new_msg)
        db.session.commit()
        
        # 2. Phát tin nhắn tới TOÀN BỘ những người trong phòng
        # Sử dụng socketio.emit để đảm bảo tin nhắn đi xuyên qua các tiến trình
        socketio.emit('receive_message', new_msg.to_dict(), room=room)
        
    except Exception as e:
        print(f"❌ Lỗi chat: {str(e)}")
        db.session.rollback()

@app.route('/api/v1/chat/<int:order_id>', methods=['GET'])
def get_history(order_id):
    """API lấy lại lịch sử tin nhắn khi load lại trang"""
    try:
        messages = Message.query.filter_by(order_id=order_id).order_by(Message.timestamp.asc()).all()
        return jsonify([m.to_dict() for m in messages]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v1/chat/system_notify', methods=['POST'])
def system_notify():
    """Endpoint nội bộ để các service khác (như Order) gửi tin nhắn thông báo"""
    data = request.json
    order_id = data.get('order_id')
    content = data.get('content')
    
    if order_id and content:
        room = str(order_id)
        new_msg = Message(
            order_id=order_id,
            sender_role='system',
            sender_name='Hệ thống',
            content=content
        )
        db.session.add(new_msg)
        db.session.commit()
        
        # Bắn thông báo real-time tới tất cả người dùng trong phòng
        socketio.emit('receive_message', new_msg.to_dict(), room=room)
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "failed"}), 400

if __name__ == '__main__':
    # Khởi chạy trên cổng 5005 nội bộ
    socketio.run(app, host='0.0.0.0', port=5005, allow_unsafe_werkzeug=True)