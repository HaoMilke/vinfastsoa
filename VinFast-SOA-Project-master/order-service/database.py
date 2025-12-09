# database.py

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Order(db.Model):
    """Mô hình đơn hàng, liên kết với User Service (T1)."""
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    # user_id: Khóa ngoại giả định, liên kết với User Service (T1)
    user_id = db.Column(db.Integer, nullable=False) 
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='Pending') # Pending, Confirmed, Shipped, Cancelled
    total_amount = db.Column(db.Integer, default=0) # Tổng tiền
    
    # Mối quan hệ với các mặt hàng trong đơn hàng
    items = db.relationship('OrderItem', backref='order', lazy='dynamic')

    def to_dict(self):
        return {
            'order_id': self.id,
            'user_id': self.user_id,
            'order_date': self.order_date.isoformat(),
            'status': self.status,
            'total_amount': self.total_amount,
            # Lấy chi tiết các mặt hàng
            'items': [item.to_dict() for item in self.items.all()] 
        }

class OrderItem(db.Model):
    """Chi tiết từng mẫu xe được đặt trong một đơn hàng."""
    __tablename__ = 'order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    # car_model_id: Khóa ngoại giả định, liên kết với Catalog Service (T2)
    car_model_id = db.Column(db.Integer, nullable=False) 
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Integer, nullable=False) # Giá tại thời điểm đặt hàng
    
    def to_dict(self):
        return {
            'item_id': self.id,
            'car_model_id': self.car_model_id,
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'subtotal': self.quantity * self.unit_price
        }