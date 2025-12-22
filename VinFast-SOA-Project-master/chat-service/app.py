from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# Khởi tạo SocketIO đồng bộ với Gateway cổng 8000
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=None)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///chat_service.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, nullable=False)
    sender_role = db.Column(db.String(20))
    sender_name = db.Column(db.String(100))
    content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=db.func.now())

    def to_dict(self):
        return {
            "order_id": self.order_id, "role": self.sender_role,
            "name": self.sender_name, "content": self.content,
            "time": self.timestamp.strftime("%H:%M")
        }

with app.app_context():
    db.create_all()

@socketio.on('join')
def on_join(data):
    if 'order_id' in data:
        room = str(data['order_id'])
        join_room(room)

@socketio.on('send_message')
def handle_message(data):
    if 'order_id' not in data: return
    room = str(data['order_id'])
    try:
        new_msg = Message(
            order_id=data['order_id'],
            sender_role=data.get('role', 'customer'),
            sender_name=data.get('name', 'Khách hàng'),
            content=data['content']
        )
        db.session.add(new_msg)
        db.session.commit()
        # Bắn tin nhắn tới toàn bộ phòng để Admin và Customer cùng thấy
        emit('receive_message', new_msg.to_dict(), room=room)
    except:
        db.session.rollback()

@app.route('/api/v1/chat/<int:order_id>', methods=['GET'])
def get_history(order_id):
    # API phục hồi tin nhắn cũ khi Customer tải lại trang
    messages = Message.query.filter_by(order_id=order_id).order_by(Message.timestamp.asc()).all()
    return jsonify([m.to_dict() for m in messages]), 200

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5005, allow_unsafe_werkzeug=True)