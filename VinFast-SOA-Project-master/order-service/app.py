# app.py

from flask import Flask, request, jsonify, Response
from database import db, Order, OrderItem
from datetime import datetime
import os
import requests 
from flask_cors import CORS # ĐÃ THÊM

app = Flask(__name__)
CORS(app) # KÍCH HOẠT CORS CHO PHÉP FRONTEND TRUY CẬP

# Cấu hình Flask và DB (sử dụng cổng 5003)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///order_service.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# --- KHAI BÁO ENDPOINT CÁC DỊCH VỤ KHÁC ---
USER_SERVICE_URL = "http://127.0.0.1:5001"
CATALOG_SERVICE_URL = "http://127.0.0.1:5002"

def initialize_db():
    """Tạo DB khi khởi động."""
    with app.app_context():
        db_path = 'order_service.db'
        if os.path.exists(db_path):
             os.remove(db_path) 
        db.create_all()
        print("Đã khởi tạo DB Đơn hàng thành công.")

@app.before_request
def setup_data():
    """Khởi tạo DB chỉ một lần khi server khởi động."""
    if not hasattr(app, 'db_initialized'):
        initialize_db()
        app.db_initialized = True

# --- HÀM HỖ TRỢ TÍCH HỢP DỊCH VỤ ---

def check_user_exists(user_id):
    """Gọi User Service (T1) để kiểm tra người dùng."""
    try:
        response = requests.get(f"{USER_SERVICE_URL}/api/v1/users/{user_id}")
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        print("Lỗi kết nối T1: Đảm bảo User Service đang chạy!")
        return False

def get_car_info_and_check_inventory(car_id, quantity):
    """
    Gọi Catalog Service (T2) để lấy giá và kiểm tra tồn kho.
    """
    try:
        # 1. Kiểm tra tồn kho
        inventory_check = requests.post(
            f"{CATALOG_SERVICE_URL}/api/v1/inventory/check",
            json={"car_id": car_id, "quantity": quantity}
        )
        if inventory_check.status_code != 200:
            return None, False

        inventory_data = inventory_check.json()
        is_available = inventory_data.get('is_available', False)

        if not is_available:
            return None, False

        # 2. Lấy chi tiết xe để lấy giá
        car_details = requests.get(f"{CATALOG_SERVICE_URL}/api/v1/catalog/cars/{car_id}")
        
        if car_details.status_code != 200:
            return None, False 

        base_price = car_details.json().get('base_price')
        
        return base_price, is_available
        
    except requests.exceptions.ConnectionError:
        print("Lỗi kết nối T2: Đảm bảo Catalog Service đang chạy!")
        return None, False

# --- API ENDPOINTS ---

@app.route('/api/v1/orders', methods=['POST'])
def create_order():
    """Tạo đơn hàng mới (Tích hợp T1 và T2)."""
    
    data = request.json
    
    # SỬA LỖI 400: Kiểm tra an toàn và xử lý chuyển đổi kiểu dữ liệu
    if data is None:
        return jsonify({"message": "Thiếu dữ liệu JSON. Kiểm tra Content-Type!"}), 400
        
    user_id_raw = data.get('user_id')
    items = data.get('items', [])
    
    # Ép kiểu user_id và kiểm tra tính hợp lệ
    try:
        user_id = int(user_id_raw)
    except (ValueError, TypeError):
        return jsonify({"message": "User ID phải là số nguyên hợp lệ."}), 400
    
    if not items or not isinstance(items, list):
        return jsonify({"message": "Thiếu chi tiết mặt hàng hoặc định dạng không hợp lệ."}), 400


    # 1. KIỂM TRA NGƯỜI DÙNG TỒN TẠI (GỌI T1)
    if not check_user_exists(user_id):
        return jsonify({"message": "Người dùng không hợp lệ (ID không tồn tại trong User Service)"}), 404

    new_order = Order(user_id=user_id, status='Pending', total_amount=0)
    db.session.add(new_order)
    
    calculated_total = 0
    
    # 2. KIỂM TRA TỒN KHO VÀ GIÁ (GỌI T2)
    for item_data in items:
        # Ép kiểu an toàn cho car_id và quantity
        try:
            car_id = int(item_data.get('car_id'))
            quantity = int(item_data.get('quantity', 1))
        except (ValueError, TypeError):
             db.session.rollback()
             return jsonify({"message": "ID xe và số lượng phải là số nguyên."}), 400

        base_price, is_available = get_car_info_and_check_inventory(car_id, quantity)
        
        if not is_available:
            # Hủy giao dịch nếu hết hàng
            db.session.rollback()
            return jsonify({"message": f"Mẫu xe ID {car_id} không đủ tồn kho hoặc không tồn tại."}), 409 # Conflict

        # Thêm Item vào đơn hàng
        subtotal = base_price * quantity
        calculated_total += subtotal
        
        order_item = OrderItem(
            order=new_order,
            car_model_id=car_id,
            quantity=quantity,
            unit_price=base_price
        )
        db.session.add(order_item)

    # 3. HOÀN TẤT VÀ LƯU ĐƠN HÀNG
    new_order.total_amount = calculated_total
    new_order.status = 'Confirmed'
    db.session.commit()

    return jsonify(new_order.to_dict()), 201 # Created

@app.route('/api/v1/orders/<int:order_id>', methods=['GET'])
def get_order_details(order_id):
    """Lấy chi tiết đơn hàng theo ID."""
    order = Order.query.get(order_id)
    if order:
        return jsonify(order.to_dict()), 200
    return jsonify({"message": "Đơn hàng không tồn tại"}), 404

@app.route('/api/v1/orders', methods=['GET'])
def get_all_orders():
    """API để Frontend (T4) lấy tất cả đơn hàng."""
    orders = Order.query.all()
    return jsonify([order.to_dict() for order in orders]), 200

if __name__ == '__main__':
    # Khởi tạo DB khi chạy ứng dụng
    with app.app_context():
        initialize_db()
        
    print("Order Service đang khởi động trên cổng 5003...")
    app.run(port=5003, debug=True)