# catalog-service/database.py

from flask_sqlalchemy import SQLAlchemy
import json

db = SQLAlchemy()

class CarModel(db.Model):
    """Mô hình chi tiết các mẫu xe VinFast."""
    __tablename__ = 'car_models'
    
    id = db.Column(db.Integer, primary_key=True) 
    model_name = db.Column(db.String(100), unique=True, nullable=False)
    base_price = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    specs = db.Column(db.Text) 
    image_url = db.Column(db.String(255), nullable=True) # <-- Trường ảnh mới
    
    inventory_items = db.relationship('Inventory', backref='car', lazy=True)

    def to_dict(self):
        """Trả về chi tiết xe dưới dạng Dict."""
        specs_dict = json.loads(self.specs) if self.specs else {} 
        return {
            'id': self.id,
            'model_name': self.model_name,
            'base_price': self.base_price,
            'description': self.description,
            'specs': specs_dict,
            'image_url': self.image_url # <-- Đảm bảo trường này được trả về
        }

class Inventory(db.Model):
    """Mô hình theo dõi tồn kho tại các đại lý/khu vực."""
    __tablename__ = 'inventory'
    
    id = db.Column(db.Integer, primary_key=True)
    car_model_id = db.Column(db.Integer, db.ForeignKey('car_models.id'), nullable=False) 
    dealer_location = db.Column(db.String(100), default='Hà Nội')
    stock_quantity = db.Column(db.Integer, default=0)