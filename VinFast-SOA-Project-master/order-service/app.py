# order-service/app.py
from flask import Flask, request, jsonify
from database import db, Order, OrderItem
import os
import requests 
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Cấu hình Flask và DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///order_service.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# FIX: Sử dụng tên service "catalog" để khớp với docker-compose networks
CATALOG_SERVICE_URL = os.environ.get("CATALOG_SERVICE_URL", "http://catalog:5002/api/v1")

def initialize_db():
    """Khởi tạo cơ sở dữ liệu."""
    with app.app_context():
        db.create_all()

@app.before_request
def setup_data():
    """Đảm bảo DB được tạo khi nhận request đầu tiên."""
    if not hasattr(app, 'db_initialized'):
        initialize_db()
        app.db_initialized = True

# --- API 1: TẠO ĐƠN HÀNG (Trạng thái ban đầu: Pending) ---
@app.route('/api/v1/orders', methods=['POST'])
def create_order():
    data = request.json
    user_id_raw = request.headers.get('X-User-Id')
    
    if not user_id_raw:
        return jsonify({"message": "Yêu cầu phải qua Gateway"}), 401
    
    try:
        user_id = int(user_id_raw)
        items = data.get('items', [])
        
        # Bước 1 trong workflow: Tạo đơn với trạng thái Pending
        new_order = Order(user_id=user_id, status='Pending', total_amount=0)
        db.session.add(new_order)
        db.session.flush() # Để lấy được new_order.id

        total_confirmed_amount = 0
        for item_data in items:
            car_id = item_data.get('car_id')
            qty = item_data.get('quantity', 1)

            # Gọi Catalog Service thực hiện Saga (trừ kho) sử dụng URL nội bộ Docker
            try:
                response = requests.post(
                    f"{CATALOG_SERVICE_URL}/inventory/reduce",
                    json={"car_id": car_id, "quantity": qty},
                    timeout=5
                )
                
                if response.status_code != 200:
                    error_info = response.json().get('message', 'Hết hàng hoặc lỗi Catalog')
                    db.session.rollback()
                    return jsonify({"message": f"Thất bại: {error_info}"}), 400

                res_data = response.json()
                unit_price = res_data.get('unit_price', 0)
                total_confirmed_amount += unit_price * qty
                
                db.session.add(OrderItem(
                    order_id=new_order.id, 
                    car_model_id=car_id, 
                    quantity=qty, 
                    unit_price=unit_price
                ))
            except requests.exceptions.RequestException as e:
                db.session.rollback()
                return jsonify({"message": f"Lỗi kết nối Catalog Service: {str(e)}"}), 503

        new_order.total_amount = total_confirmed_amount
        db.session.commit()
        
        # Trả về dữ liệu đầy đủ bao gồm ID để Frontend không bị undefined
        return jsonify(new_order.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Lỗi xử lý đơn hàng: {str(e)}"}), 500

# --- API 2: XÁC NHẬN THANH TOÁN (Chuyển sang trạng thái Paid) ---
@app.route('/api/v1/orders/<int:order_id>/pay', methods=['PUT'])
def process_payment(order_id):
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"message": "Không tìm thấy đơn hàng"}), 404
    
    order.status = 'Paid'
    db.session.commit()
    return jsonify({
        "message": "Thanh toán thành công", 
        "status": "Paid",
        "order_id": order.id
    }), 200

# --- API 3: ADMIN HẸN LỊCH (Chuyển sang trạng thái Scheduled) ---
@app.route('/api/v1/orders/<int:order_id>/confirm', methods=['PUT'])
def confirm_order(order_id):
    role = request.headers.get('X-User-Role')
    if role != 'admin':
        return jsonify({"message": "Chỉ Admin mới có quyền thực hiện"}), 403

    order = Order.query.get(order_id)
    if not order:
        return jsonify({"message": "Không tìm thấy đơn hàng"}), 404
    
    order.status = 'Scheduled' 
    db.session.commit()
    return jsonify({"message": "Đã xác nhận lịch hẹn thành công", "status": "Scheduled"}), 200

# --- API 4: LẤY DANH SÁCH ĐƠN HÀNG (Dành cho Dashboard) ---
@app.route('/api/v1/orders', methods=['GET'])
def get_all_orders():
    try:
        orders = Order.query.all()
        return jsonify([order.to_dict() for order in orders]), 200
    except Exception as e:
        return jsonify({"message": f"Lỗi lấy dữ liệu: {str(e)}"}), 500

if __name__ == '__main__':
    initialize_db()
    app.run(host='0.0.0.0', port=5003)