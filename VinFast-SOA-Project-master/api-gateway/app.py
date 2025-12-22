from flask import Flask, request, jsonify, Response
import requests
from flask_cors import CORS
import os
import jwt
from flask_socketio import SocketIO

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Cấu hình SocketIO hỗ trợ WebSocket cho cả Admin và Customer
socketio = SocketIO(app, cors_allowed_origins="*")

JWT_SECRET = os.environ.get('JWT_SECRET_KEY', 'vinfast_secret_key_mac_dinh_123')

SERVICES = {
    "users": os.environ.get("USER_SERVICE_URL", "http://users:5001/api/v1"),
    "catalog": os.environ.get("CATALOG_SERVICE_URL", "http://catalog:5002/api/v1"),
    "orders": os.environ.get("ORDER_SERVICE_URL", "http://orders:5003/api/v1"),
    "chat": os.environ.get("CHAT_SERVICE_URL", "http://chat:5005/api/v1")
}

@app.route('/<service>/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def gateway_router(service, path):
    if service not in SERVICES:
        return jsonify({"error": "Dịch vụ không tồn tại"}), 404
    
    base_url = SERVICES[service].rstrip('/')
    clean_path = path.lstrip('/')
    target_url = f"{base_url.replace('/api/v1', '')}/{clean_path}" if "api/v1" in clean_path else f"{base_url}/{clean_path}"
    
    headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
    
    public_paths = ['users/login', 'users/register', 'catalog/cars']
    is_public = any(p in f"{service}/{path}" for p in public_paths)

    if not is_public:
        auth_header = request.headers.get('Authorization')
        if not auth_header: return jsonify({"message": "Vui lòng đăng nhập"}), 401
        try:
            token = auth_header.split(" ")[1]
            decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            headers['X-User-Id'] = str(decoded.get('user_id'))
            headers['X-User-Role'] = decoded.get('role')
        except: return jsonify({"message": "Phiên làm việc hết hạn"}), 401

    try:
        response = requests.request(
            method=request.method, url=target_url, headers=headers, data=request.get_data(), timeout=10
        )
        
        # SỬA LỖI QUAN TRỌNG: Trả về JSON chuẩn để Customer hiện được danh sách đơn hàng
        try:
            return jsonify(response.json()), response.status_code
        except:
            return response.content, response.status_code
            
    except Exception as e:
        return jsonify({"error": str(e)}), 503

if __name__ == '__main__':
    # Chạy bằng socketio.run để không làm treo các yêu cầu HTTP khác
    socketio.run(app, host='0.0.0.0', port=8000, debug=True, allow_unsafe_werkzeug=True)
