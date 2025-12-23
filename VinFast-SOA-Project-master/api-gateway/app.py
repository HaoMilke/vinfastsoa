from flask import Flask, request, jsonify, Response
import requests
from flask_cors import CORS
import os
import jwt
from flask_socketio import SocketIO, emit
import socketio as socketio_client  # Sử dụng client để forward sang chat-service

app = Flask(__name__)
# Cấu hình CORS cho phép Frontend truy cập vào tất cả các route
CORS(app, resources={r"/*": {"origins": "*"}})

# Cấu hình SocketIO tại Gateway (Cổng 8000)
# Sử dụng async_mode='eventlet' để chạy ổn định trong môi trường Docker
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

JWT_SECRET = os.environ.get('JWT_SECRET_KEY', 'vinfast_secret_key_mac_dinh_123')

# Định nghĩa danh sách các service nội bộ
SERVICES = {
    "users": os.environ.get("USER_SERVICE_URL", "http://users:5001/api/v1"),
    "catalog": os.environ.get("CATALOG_SERVICE_URL", "http://catalog:5002/api/v1"),
    "orders": os.environ.get("ORDER_SERVICE_URL", "http://orders:5003/api/v1"),
    "chat": os.environ.get("CHAT_SERVICE_URL", "http://chat:5005/api/v1")
}

# --- KẾT NỐI SOCKET NỘI BỘ SANG CHAT SERVICE ---
chat_internal_url = os.environ.get("CHAT_INTERNAL_URL", "http://chat:5005")
sio_to_chat = socketio_client.Client()

def connect_to_chat_service():
    """Hàm tự động kết nối lại tới Chat Service nếu mất kết nối"""
    try:
        if not sio_to_chat.connected:
            sio_to_chat.connect(chat_internal_url)
            print("✅ Gateway đã kết nối thành công tới Chat Service Socket.")
    except Exception as e:
        print(f"❌ Lỗi kết nối tới Chat Service Socket: {str(e)}")

# Khởi tạo kết nối lần đầu
connect_to_chat_service()

# --- LOGIC WEBSOCKET PROXY (Forwarding) ---

@socketio.on('join')
def handle_join_proxy(data):
    """Chuyển tiếp sự kiện join phòng từ Client sang Chat Service"""
    connect_to_chat_service()
    if sio_to_chat.connected:
        sio_to_chat.emit('join', data)

@socketio.on('send_message')
def handle_send_message_proxy(data):
    """Chuyển tiếp tin nhắn từ Client sang Chat Service"""
    connect_to_chat_service()
    if sio_to_chat.connected:
        sio_to_chat.emit('send_message', data)

@sio_to_chat.on('receive_message')
def handle_receive_from_chat(data):
    """Nhận tin nhắn từ Chat Service và bắn ngược về cho Frontend"""
    # Ép kiểu order_id về chuỗi để đảm bảo SocketIO nhận diện đúng Room
    room_id = str(data.get('order_id'))
    socketio.emit('receive_message', data, room=room_id)

# --- LOGIC HTTP ROUTER ---

@app.route('/<service>/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def gateway_router(service, path):
    """Định tuyến tất cả các yêu cầu HTTP tới các service tương ứng"""
    if service not in SERVICES:
        return jsonify({"error": "Dịch vụ không tồn tại"}), 404
    
    base_url = SERVICES[service].rstrip('/')
    clean_path = path.lstrip('/')
    
    # SỬA LỖI ĐỊNH TUYẾN: Kiểm tra nếu path gửi tới đã có api/v1 thì không nhân đôi
    if "api/v1" in clean_path:
        target_url = f"{base_url.replace('/api/v1', '')}/{clean_path}"
    else:
        target_url = f"{base_url}/{clean_path}"
    
    # Loại bỏ header 'host' để tránh xung đột proxy
    headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
    
    # Các API công khai không cần kiểm tra JWT
    public_paths = ['users/login', 'users/register', 'catalog/cars']
    is_public = any(p in f"{service}/{path}" for p in public_paths)

    if not is_public:
        auth_header = request.headers.get('Authorization')
        if not auth_header: 
            return jsonify({"message": "Vui lòng đăng nhập"}), 401
        try:
            token = auth_header.split(" ")[1]
            decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            # Đính kèm User Info vào header để các service nội bộ sử dụng
            headers['X-User-Id'] = str(decoded.get('user_id'))
            headers['X-User-Role'] = decoded.get('role')
        except Exception: 
            return jsonify({"message": "Phiên làm việc hết hạn"}), 401

    try:
        # Thực hiện chuyển tiếp request
        response = requests.request(
            method=request.method, 
            url=target_url, 
            headers=headers, 
            data=request.get_data(), 
            timeout=10
        )
        
        # Trả về kết quả JSON hoặc Content thô
        try:
            return jsonify(response.json()), response.status_code
        except Exception:
            return response.content, response.status_code
            
    except Exception as e:
        return jsonify({"error": f"Lỗi kết nối tới {service}: {str(e)}"}), 503

if __name__ == '__main__':
    # Quan trọng: Sử dụng socketio.run để hỗ trợ song song HTTP và WebSocket
    socketio.run(app, host='0.0.0.0', port=8000, debug=True, allow_unsafe_werkzeug=True)