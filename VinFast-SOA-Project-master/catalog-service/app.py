# catalog-service/app.py

from flask import Flask, request, jsonify, Response
from database import db, CarModel, Inventory 
import os
import json
from sqlalchemy import func
from flask_cors import CORS 

app = Flask(__name__)
CORS(app) 

# Đảm bảo sử dụng tên DB mới để tránh xung đột
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///catalog_service_v3.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app) 

# --- DỮ LIỆU DEMO MỚI (Giữ nguyên) ---
CARS_DATA_DEMO = [
    {
        "model_name": "VinFast VF 9", "base_price": 1499000000, 
        "description": "SUV điện hạng E, 7 chỗ. Flagship của VinFast.", 
        "specs": json.dumps({"motor_type": "Điện", "range": "438 km", "color": "Trắng"}), 
        "image_url": "https://giaxeoto.vn/admin/upload/images/resize/640-gia-xe-Vinfast-VF9.jpg", 
        "inventory_HN": 5, "inventory_HCM": 10
    },
    {
        "model_name": "VinFast VF 8", "base_price": 1057000000, 
        "description": "SUV điện hạng D, 5 chỗ. Mẫu xe chủ lực toàn cầu.", 
        "specs": json.dumps({"motor_type": "Điện", "range": "420 km", "color": "Đỏ"}),
        "image_url": "https://danchoioto.vn/wp-content/uploads/2022/08/gia-xe-vinfast-vf8.jpg", 
        "inventory_HN": 15, "inventory_HCM": 30
    },
    {
        "model_name": "VinFast VF 7", "base_price": 850000000, 
        "description": "SUV điện hạng C, phong cách Coupe, thiết kế hiện đại.", 
        "specs": json.dumps({"motor_type": "Điện", "range": "400 km", "color": "Xanh"}),
        "image_url": "https://giaxeoto.vn/admin/upload/images/resize/640-Vinfast-VF7-gia-xe.jpg", 
        "inventory_HN": 20, "inventory_HCM": 25
    },
    {
        "model_name": "VinFast VF 6", "base_price": 675000000, 
        "description": "SUV điện hạng B, nhỏ gọn và linh hoạt, giá dễ tiếp cận.", 
        "specs": json.dumps({"motor_type": "Điện", "range": "399 km", "color": "Vàng"}),
        "image_url": "https://giaxeoto.vn/admin/upload/images/resize/640-Vinfast-VF6-ban-thuong-mai-gia-xe.jpg", 
        "inventory_HN": 30, "inventory_HCM": 20
    },
    {
        "model_name": "VinFast VF 5 Plus", "base_price": 458000000, 
        "description": "SUV điện hạng A, dành cho đô thị.", 
        "specs": json.dumps({"motor_type": "Điện", "range": "326 km", "color": "Trắng"}),
        "image_url": "https://giaxeoto.vn/admin/upload/images/resize/640-Vinfast-VF5-plus-gia-xe.jpg", 
        "inventory_HN": 40, "inventory_HCM": 50
    },
    {
        "model_name": "VinFast LUX A2.0", "base_price": 1115000000, 
        "description": "Sedan hạng E, động cơ xăng turbo. Thiết kế Ý đẳng cấp.", 
        "specs": json.dumps({"motor_type": "Xăng", "engine": "2.0L", "cylinder": "4"}),
        "image_url": "https://vinfastdongsaigon.com/content/VINFAST/san-pham/lux-a20.jpg", 
        "inventory_HN": 10, "inventory_HCM": 5
    },
    {
        "model_name": "VinFast LUX SA2.0", "base_price": 1550000000, 
        "description": "SUV hạng E, động cơ xăng turbo. Mạnh mẽ và sang trọng.", 
        "specs": json.dumps({"motor_type": "Xăng", "engine": "2.0L", "cylinder": "4"}),
        "image_url": "https://danchoioto.vn/wp-content/uploads/2020/09/vinfast-lux-sa2-0.jpg", 
        "inventory_HN": 10, "inventory_HCM": 5
    },
    {
        "model_name": "VinFast Fadil", "base_price": 425000000, 
        "description": "Hatchback hạng A, xe đô thị nhỏ gọn, tiện lợi.", 
        "specs": json.dumps({"motor_type": "Xăng", "engine": "1.4L", "color": "Bạc"}),
        "image_url": "https://autopro8.mediacdn.vn/134505113543774208/2023/1/29/vinfast-fadil-23-16434695001991234174472-16749685067641882387245-1674974414975-16749744151041515512318.jpg", 
        "inventory_HN": 20, "inventory_HCM": 15
    }
]

def create_demo_data(data):
    """Tạo DB và chèn dữ liệu demo."""
    db.create_all()
    
    CarModel.query.delete() 
    Inventory.query.delete()

    for item in data:
        car = CarModel(
            model_name=item['model_name'], 
            base_price=item['base_price'],
            description=item['description'],
            specs=item['specs'],
            image_url=item['image_url']
        )
        db.session.add(car)
        
        db.session.commit() 
        car_id = car.id
        
        db.session.add(Inventory(car_model_id=car_id, dealer_location="Hà Nội", stock_quantity=item['inventory_HN']))
        db.session.add(Inventory(car_model_id=car_id, dealer_location="TP. HCM", stock_quantity=item['inventory_HCM']))

    db.session.commit() 
    print("Đã khởi tạo DB Danh mục & Kho với dữ liệu mới thành công.")


# --- API ENDPOINTS (Giữ nguyên) ---

@app.route('/api/v1/catalog/cars', methods=['GET'])
def get_all_cars():
    cars = CarModel.query.all()
    data = [car.to_dict() for car in cars]
    json_output = app.json.dumps(data, ensure_ascii=False)
    return Response(json_output, mimetype='application/json', status=200)

@app.route('/api/v1/catalog/cars/<int:car_id>', methods=['GET'])
def get_car_details(car_id):
    car = CarModel.query.get(car_id)
    if car:
        data = car.to_dict()
        json_output = app.json.dumps(data, ensure_ascii=False)
        return Response(json_output, mimetype='application/json', status=200)
    return jsonify({"message": "Mẫu xe không tồn tại"}), 404

@app.route('/api/v1/inventory/check', methods=['POST'])
def check_inventory():
    data = request.json
    car_id = data.get('car_id')
    required_quantity = data.get('quantity', 1)
    
    if not car_id:
        return jsonify({"message": "Thiếu ID mẫu xe"}), 400

    total_stock = db.session.query(func.sum(Inventory.stock_quantity)).filter(
        Inventory.car_model_id == car_id
    ).scalar() or 0
    
    is_available = total_stock >= required_quantity
    
    return jsonify({
        "car_id": car_id,
        "is_available": is_available,
        "available_stock": total_stock,
        "required": required_quantity
    }), 200 

if __name__ == '__main__':
    # THỰC HIỆN XÓA FILE DB VÀ TẠO MỚI TRONG APPLICATION CONTEXT
    with app.app_context():
        db_path = 'catalog_service_v3.db'
        
        # Xóa file DB cũ
        if os.path.exists(db_path):
             os.remove(db_path) 
             
        # Tạo DB và dữ liệu mới
        create_demo_data(CARS_DATA_DEMO)
            
    print("Catalog Service đang khởi động trên cổng 5002...")
    app.run(port=5002, debug=True)