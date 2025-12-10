# gateway_app.py

from flask import Flask, request, jsonify
import requests
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app) # Cho phép Frontend truy cập Gateway

# Định nghĩa URL của các dịch vụ Back-end (Luôn dùng cổng 500x)
SERVICES = {
    "users": os.environ.get("USER_SERVICE_URL", "http://127.0.0.1:5001/api/v1"),
    "catalog": os.environ.get("CATALOG_SERVICE_URL", "http://127.0.0.1:5002/api/v1"),
    "orders": os.environ.get("ORDER_SERVICE_URL", "http://127.0.0.1:5003/api/v1")
}

@app.route('/<service>/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def gateway_router(service, path):
    """Định tuyến yêu cầu từ Frontend đến đúng dịch vụ."""
    
    if service not in SERVICES:
        return jsonify({"error": "Service not found"}), 404
    
    # 1. Xây dựng URL đích
    # Ví dụ: /catalog/cars/1 -> http://127.0.0.1:5002/api/v1/catalog/cars/1
    target_url = f"{SERVICES[service]}/{path}"
    
    # 2. Chuyển tiếp yêu cầu (Forward the request)
    try:
        response = requests.request(
            method=request.method,
            url=target_url,
            # Giữ nguyên Content-Type và Body từ Frontend
            headers={"Content-Type": request.headers.get("Content-Type", "application/json")},
            data=request.get_data(),
            timeout=10
        )
        
        # 3. Trả về phản hồi từ Back-end
        # Sử dụng Response thay vì jsonify để tránh lỗi encoding
        return response.content, response.status_code, response.headers.items()

    except requests.exceptions.RequestException as e:
        print(f"Lỗi Gateway khi kết nối đến {service}: {e}")
        return jsonify({"error": f"Gateway failed to connect to {service}"}), 503

if __name__ == '__main__':
    print("API Gateway đang khởi động trên cổng 8000...")
    # THÊM host='0.0.0.0'
    app.run(host='0.0.0.0', port=8000, debug=True)