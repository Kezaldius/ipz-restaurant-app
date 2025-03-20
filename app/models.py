from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.sql import func

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    phone_number = db.Column(db.String(20))
    is_admin = db.Column(db.Boolean, default=False)  # Потенційне адмін меню

    orders = db.relationship('Order', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Guest(db.Model):
    __tablename__ = 'guests'

    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), nullable=False, unique=True)
    name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=func.now())
    
    orders = db.relationship('Order', backref='guest', lazy='dynamic', 
                          foreign_keys='Order.guest_id')
    reservations = db.relationship('Reservation', backref='guest', lazy='dynamic',
                               foreign_keys='Reservation.guest_id')
    
    def __repr__(self):
        return f'<Guest {self.phone_number}>'



class Dish(db.Model):
    __tablename__ = 'dishes'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)  # Ціна 
    image_url = db.Column(db.String(255))  # URL зображення
    category = db.Column(db.String(50))  # Категорія страви (наприклад, "Кофе", "Десерти")
    is_available = db.Column(db.Boolean, default=True)  # Чи доступна страва зараз

    def __repr__(self):
        return f'<Dish {self.name}>'
    

class News(db.Model):
    __tablename__ = 'news'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(255))  # URL зображення
    is_actual = db.Column(db.Boolean, default=True)  # Чи актуальна новина

    def __repr__(self):
        return f'<News {self.name}>'


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    guest_id = db.Column(db.Integer, db.ForeignKey('guests.id'), nullable=True)
    order_date = db.Column(db.DateTime, default=func.now())
    status = db.Column(db.String(50), default='В обробці')  # Статус замовлення ("В обробці", "Готується", "Доставлено", інші статуси)
    total_price = db.Column(db.Numeric(10, 2))
    delivery_address = db.Column(db.String(255))
    comments = db.Column(db.Text) # Коментарі до замовлення
    phone_number = db.Column(db.String(20))

    items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade="all, delete-orphan")  # Зв'язок з елементами замовлення

    def __repr__(self):
        if self.user_id:
            return f'<Order {self.id} by User {self.user_id}>'
        else:
            return f'<Order {self.id} by Guest {self.guest_id}>'

class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    dish_id = db.Column(db.Integer, db.ForeignKey('dishes.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Numeric(10, 2)) # Ціна на момент замовлення

    dish = db.relationship('Dish') 

    def __repr__(self):
        return f'<OrderItem {self.quantity}x Dish {self.dish_id} in Order {self.order_id}>'



class Table(db.Model):
    __tablename__ = 'tables'

    id = db.Column(db.Integer, primary_key=True)
    table_number = db.Column(db.Integer, unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)  # Кількість місць на столік
    is_available = db.Column(db.Boolean, default=True) #Чи вільний столик

    reservations = db.relationship('Reservation', backref='table', lazy='dynamic')

    def __repr__(self):
        return f'<Table {self.table_number}>'

class Reservation(db.Model):
    __tablename__ = 'reservations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    guest_id = db.Column(db.Integer, db.ForeignKey('guests.id'), nullable=True)
    table_id = db.Column(db.Integer, db.ForeignKey('tables.id'), nullable=False)
    reservation_date = db.Column(db.DateTime, nullable=False)
    guest_count = db.Column(db.Integer, nullable=False)
    comments = db.Column(db.Text)
    status = db.Column(db.String, default='Підтверджено')
    phone_number = db.Column(db.String(20), nullable=True)

    user = db.relationship('User')

    def __repr__(self):
        if self.user_id:
            return f'<Reservation for Table {self.table_id} by User {self.user_id} on {self.reservation_date}>'
        else:
            return f'<Reservation for Table {self.table_id} by Guest {self.guest_id} on {self.reservation_date}>'