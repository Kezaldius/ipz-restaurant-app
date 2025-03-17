from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field
from app.models import User, Dish, Order, OrderItem, Table, Reservation
from marshmallow import fields, ValidationError, validates

class UserSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = True  # Створювати об'єкт моделі при десеріалізації
        exclude = ('password_hash',)  # Виключаємо password_hash з виводу
    
    #Процес валідації даних
    @validates('email')
    def validate_email(self, value):
        if User.query.filter_by(email=value).first():
            raise ValidationError('Цей email вже використовується.')
            
    @validates('username')
    def validate_username(self, value):
       if User.query.filter_by(username=value).first():
           raise ValidationError('Це ім\'я користувача вже зайняте.')

class DishSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Dish
        load_instance = True
        include_relationships = True 

class OrderItemSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = OrderItem
        load_instance = True
        include_fk = True  
    
    dish = fields.Nested(DishSchema, only=('id','name', 'price')) # Вкладений об'єкт Dish (тільки id та name)
    price = auto_field(dump_only=True) # Тільки для читання


class OrderSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Order
        load_instance = True
        include_relationships = True

    items = fields.Nested(OrderItemSchema, many=True)
    user = fields.Nested(UserSchema, only=('id', 'username', 'email'))  # Вкладений об'єкт User
    total_price = auto_field(dump_only=True) # Тільки для читання
    order_date = auto_field(dump_only=True)


class TableSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Table
        load_instance = True

class ReservationSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Reservation
        load_instance = True
        include_fk = True
        
    user = fields.Nested(UserSchema, only=('id', 'username', 'email'))
    table = fields.Nested(TableSchema, only=('id', 'table_number'))
    reservation_date = fields.DateTime(format='%Y-%m-%d %H:%M:%S')