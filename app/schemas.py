from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field
from app.models import *
from marshmallow import fields, ValidationError, validates, Schema
from app import db

class UserSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = True  # Створювати об'єкт моделі при десеріалізації
        include_relationships = False
        include_fk = False
        fields = ('id', 'phone_number', 'first_name', 'last_name', 'is_admin', 'password') # Певно ще й is_admin треба прибрати, але він поки не заважає
        load_only = ('password',)
        
    phone_number = auto_field(required=True)
    password = fields.String(load_only=True, required=True) # Отримуємо пароль, но не видаємо його в JSON

    @validates('phone_number')
    def validate_phone_number(self, value):
        if not value:
            raise ValidationError('Номер телефону є обов\'язковим.')
        # Мейбі додати складнішу перевірку по типу регіонального номеру
        if len(value) < 10: # Проста перевірка довжини
             raise ValidationError('Номер телефону має містити мінімум 10 символів')

        if User.query.filter_by(phone_number=value).first():
            raise ValidationError('Цей номер телефону вже зареєстрований.')

    
class GuestSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Guest
        load_instance = True
        include_relationships = False

    @validates('phone_number')
    def validate_phone_number(self, value):
        if not value or len(value) < 10:
            raise ValidationError('Номер телефону має містити менше 10 символів')

       
class ModifierOptionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ModifierOption
        load_instance = True
        include_fk = False
        exclude = ("group",)
        fields = ('id', 'name', 'price_modifier', 'is_default', 'group_id')

    price_modifier = fields.Float(as_string=False)

class ModifierOptionSimpleSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ModifierOption
        load_instance = True
        include_fk = True  
    price_modifier = fields.Float(as_string=False)

class ModifierGroupSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ModifierGroup
        load_instance = True
        include_fk = False
        fields = ('id', 'name', 'description', 'is_required', 'selection_type', 'options')

        
    options = fields.Nested(ModifierOptionSchema, many=True) 
class DishVariantSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = DishVariant
        load_instance = True
        include_fk = True 
        fields = ('id', 'dish_id', 'size_label', 'weight_grams', 'volume_ml', 'price', 'is_default')
    dish_id = auto_field()
    price = fields.Float() 

class TagSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Tag
        load_instance = True

class DishSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Dish
        load_instance = True
        include_relationships = True 

        fields = ('id', 'name', 'description', 'detailed_description', 'image_url',
                  'category', 'is_available', 'variants', 'tags', 'modifier_groups')

    variants = fields.Nested(DishVariantSchema, many=True, required=True)
    tags = fields.Nested(TagSchema, many=True, only=("id", "name")) # Повертаємо ID і name тегу
    modifier_groups = fields.Nested(ModifierGroupSchema, many=True) # Повертаємо повну структуру груп

class NewsSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = News
        load_instance = True
        include_fk = True

class OrderItemModifierSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = OrderItemModifier
        load_instance = True
        include_fk = True

    modifier_option = fields.Nested(ModifierOptionSimpleSchema)

class OrderItemSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = OrderItem
        sqla_session = db.session
        load_instance = True
        include_relationships = True
        include_fk = True
        exclude = ('order',)

    dish_id = auto_field()
    dish = fields.Nested(DishSchema, only=('id','name'))
    variant = fields.Nested(DishVariantSchema)
    modifiers = fields.Nested(OrderItemModifierSchema, many=True)
    price = fields.Float(dump_only=True)

class OrderSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Order
        sqla_session = db.session
        load_instance = True
        include_relationships = True
        include_fk = True
        fields = ('id', 'user_id', 'guest_id', 'order_date', 'status', 'total_price',
                 'delivery_address', 'comments', 'phone_number', 'items', 'user', 'guest')

    items = fields.Nested(OrderItemSchema, many=True) 
    user = fields.Nested('UserSchema', only=('id', 'phone_number', 'first_name', 'last_name'), dump_only=True)
    guest = fields.Nested('GuestSchema', only=('id', 'phone_number', 'name'), dump_only=True)
    total_price = fields.Float(dump_only=True) # Тільки для читання
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
        
    user = fields.Nested('UserSchema', only=('id', 'phone_number', 'first_name', 'last_name'), dump_only=True)
    guest = fields.Nested('GuestSchema', only=('id', 'phone_number', 'name'), dump_only=True)
    table = fields.Nested('TableSchema', only=('id', 'table_number'))
    reservation_date = fields.DateTime(format='%Y-%m-%d %H:%M:%S')