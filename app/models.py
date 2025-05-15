from app import db
from datetime import datetime, timezone,timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.sql import func

variant_id = db.Column(db.Integer, db.ForeignKey('dish_variants.id'), nullable=False)
variant = db.relationship('DishVariant')
modifiers = db.relationship('OrderItemModifier', backref='order_item', cascade="all, delete-orphan")

dish_tags_table = db.Table('dish_tags', db.Model.metadata,
    db.Column('dish_id', db.Integer, db.ForeignKey('dishes.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)
class PasswordResetOTP(db.Model):
    __tablename__ = 'password_reset_otps'

    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), nullable=False, index=True)
    otp_code = db.Column(db.String(10), nullable=False) 
    created_at = db.Column(db.DateTime(timezone = True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime(timezone = True), nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)

    def __init__(self, phone_number, otp_code, expires_in_seconds):
        self.phone_number = phone_number
        self.otp_code = otp_code
        now_utc = datetime.now(timezone.utc)
        self.created_at = now_utc
        self.expires_at = now_utc + timedelta(seconds=expires_in_seconds)

    def is_valid(self, provided_otp):
        now_utc = datetime.now(timezone.utc)
        if self.expires_at.tzinfo is None:
            expires_at = self.expires_at.replace(tzinfo=timezone.utc)
        else:
            expires_at = self.expires_at
            
        return not self.used and expires_at > now_utc and self.otp_code == provided_otp

    def mark_as_used(self):
        self.used = True

class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False) # Назва тегу (spicy, meat, etc.)

    def __repr__(self):
        return self.name
    def __str__(self):
        return self.name

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=False, nullable=True)
    email = db.Column(db.String(120), unique=False, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    phone_number = db.Column(db.String(20), unique = True, nullable = False)
    is_admin = db.Column(db.Boolean, default=False)  # Потенційне адмін меню

    orders = db.relationship('Order', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.phone_number}>'

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

dish_modifier_groups_table = db.Table('dish_modifier_groups', db.Model.metadata,
    db.Column('dish_id', db.Integer, db.ForeignKey('dishes.id'), primary_key=True),
    db.Column('modifier_group_id', db.Integer, db.ForeignKey('modifier_groups.id'), primary_key=True)
)

class ModifierOption(db.Model):
    __tablename__ = 'modifier_options'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('modifier_groups.id'), nullable=False, index=True) # Зв'язок з групою
    name = db.Column(db.String(100), nullable=False)
    price_modifier = db.Column(db.Numeric(10, 2), nullable=False, default=0.00) # Зміна ціни
    is_default = db.Column(db.Boolean, default=False, nullable=False)

    group = db.relationship('ModifierGroup', back_populates='options')

    def __repr__(self):
        return f'<ModifierOption {self.name} (+{self.price_modifier})>'

class ModifierGroup(db.Model):
    __tablename__ = 'modifier_groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True) 
    description = db.Column(db.Text, nullable=True)
    is_required = db.Column(db.Boolean, default=True, nullable=False) 
    selection_type = db.Column(db.Enum('single', 'multiple', name='selection_type_enum'), default='single', nullable=False)

    options = db.relationship(
        'ModifierOption',
        back_populates='group',
        cascade='all, delete-orphan',
        lazy='select'
    )

    def __repr__(self):
        return f'<ModifierGroup "{self.name}" (ID: {self.id})>'

class OrderItemModifier(db.Model):
    __tablename__ = 'order_item_modifiers'
    id = db.Column(db.Integer, primary_key=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey('order_items.id'), nullable=False)
    modifier_option_id = db.Column(db.Integer, db.ForeignKey('modifier_options.id'), nullable=False)
    modifier_option = db.relationship('ModifierOption')

class DishVariant(db.Model):
    __tablename__ = 'dish_variants'
    id = db.Column(db.Integer, primary_key=True)
    dish_id = db.Column(db.Integer, db.ForeignKey('dishes.id'), nullable=False) 
    size_label = db.Column(db.String(100), nullable=False) # Текстове позначення (L, XL, 360г, чорний чай)
    weight_grams = db.Column(db.Integer, nullable=True) # Вага (опціонально)
    volume_ml = db.Column(db.Integer, nullable=True) # Об'єм (опціонально)
    price = db.Column(db.Numeric(10, 2), nullable=False) 
    is_default = db.Column(db.Boolean, default=False, nullable=False) # Чи це варіант за замовчуванням

    dish = db.relationship('Dish', back_populates='variants')

    def __repr__(self):
        return f'<DishVariant {self.size_label} for Dish ID {self.dish_id}>'

class Dish(db.Model):
    __tablename__ = 'dishes'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    detailed_description = db.Column(db.Text)
    image_url = db.Column(db.String(255))  # URL зображення
    category = db.Column(db.String(50))  # Категорія страви (наприклад, "Кофе", "Десерти")
    is_available = db.Column(db.Boolean, default=True)  # Чи доступна страва зараз

    variants = db.relationship(
        'DishVariant', back_populates='dish', cascade='all, delete-orphan', lazy='select'
    )
    tags = db.relationship(
        'Tag', secondary=dish_tags_table, backref=db.backref('dishes', lazy='dynamic'), lazy='select'
    )
    modifier_groups = db.relationship( 
        'ModifierGroup',
        secondary=dish_modifier_groups_table, 
        backref=db.backref('dishes_associated', lazy='dynamic'), 
        lazy='select' 
    )
    
    def __repr__(self):
        return f'<Dish {self.name}>'
    
class News(db.Model):
    __tablename__ = 'news'
    # Мабуть додати новинам перевірку на дату і якщо дата більше за потрібну вони самі вимикаються
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
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

    items = db.relationship(
    'OrderItem',
    back_populates='order',
    cascade='all, delete-orphan',
    lazy='joined'
    )

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
    variant_id = db.Column(db.Integer, db.ForeignKey('dish_variants.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Numeric(10, 2))

    order = db.relationship('Order', back_populates='items')
    dish = db.relationship('Dish')
    variant = db.relationship('DishVariant')

    modifiers = db.relationship(
        'OrderItemModifier',
        backref='order_item',
        cascade="all, delete-orphan",
        lazy='joined'
    )

    def __repr__(self):
        return f'<OrderItem {self.quantity}x Dish {self.dish_id} (Variant {self.variant_id})>'

class Table(db.Model):
    __tablename__ = 'tables'
    # Столикам взагалі треба змінити логіку, займусь цим потім. (Або додати метод який буде виступати в ролі календаря?)

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

    reservation_start_time = db.Column(db.DateTime, nullable=False, index=True)
    reservation_end_time = db.Column(db.DateTime, nullable=False, index=True) 

    reservation_date = db.Column(db.DateTime, nullable=False)
    guest_count = db.Column(db.Integer, nullable=False)
    comments = db.Column(db.Text)
    status = db.Column(db.String, default='Підтверджено')
    phone_number = db.Column(db.String(20), nullable=True) #Ця строка потрібна щоб гость міг подати запит на цей рут лише з номером телефона та отримати свій гостьовий профіль

    user = db.relationship('User')

    def __repr__(self):
        if self.user_id:
            return f'<Reservation for Table {self.table_id} by User {self.user_id} on {self.reservation_date}>'
        else:
            return f'<Reservation for Table {self.table_id} by Guest {self.guest_id} on {self.reservation_date}>'
        

