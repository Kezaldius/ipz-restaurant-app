from flask import Blueprint
from flask_restx import Api, Resource, fields


api_bp = Blueprint('api', __name__)
api = Api(api_bp,
          title='Restaurant API',
          version='1.0',
          description='API для ресторанної системи',
          doc='/docs')


#Моделі для Swagger
user_model = api.model('User', {
    'id': fields.Integer(readonly=True, description='ID користувача'),
    'username': fields.String(required=True, description='Ім\'я користувача'),
    'email': fields.String(required=True, description='Email користувача'),
    'first_name': fields.String(description='Ім\'я'),
    'last_name': fields.String(description='Прізвище'),
    'phone_number': fields.String(description='Номер телефону'),
    'is_admin': fields.Boolean(description='Чи є користувач адміністратором')
})

registration_model = api.model('UserRegistration', {
    'username': fields.String(required=True, description='Ім\'я користувача'),
    'email': fields.String(required=True, description='Email користувача'),
    'password': fields.String(required=True, description='Пароль'), 
    'first_name': fields.String(description='Ім\'я'),
    'last_name': fields.String(description='Прізвище'),
    'phone_number': fields.String(description='Номер телефону'),
    'is_admin': fields.Boolean(description='Чи є користувач адміністратором')
})


guest_model = api.model('Guest', {
    'id': fields.Integer(readonly=True, description='ID гостя'),
    'phone_number': fields.String(required=True, description='Номер телефону'),
    'name': fields.String(description='Ім\'я гостя'),
    'created_at': fields.DateTime(description='Дата створення')
})

guest_input_model = api.model('GuestInput', {
    'phone_number': fields.String(required=True, description='Номер телефону'),
    'name': fields.String(required=False, description='Ім\'я гостя (необов\'язково)'),
})

dish_model = api.model('Dish', {
    'id': fields.Integer(readonly=True, description='ID страви'),
    'name': fields.String(required=True, description='Назва страви'),
    'description': fields.String(description='Опис страви'),
    'price': fields.Float(required=True, description='Ціна страви'),
    'image_url': fields.String(description='URL зображення'),
    'category': fields.String(description='Категорія страви'),
    'is_available': fields.Boolean(description='Чи доступна страва')
})

news_model = api.model('News', {
    'id': fields.Integer(readonly=True, description='ID страви'),
    'name': fields.String(required=True, description='Назва новини'),
    'description': fields.String(description='Опис новини'),
    'image_url': fields.String(description='URL зображення'),
    'is_actual': fields.Boolean(description='Чи актуальна новина')
})

order_item_model = api.model('OrderItem', {
    'id': fields.Integer(readonly=True, description='ID елемента замовлення'),
    'dish_id': fields.Integer(required=True, description='ID страви'),
    'quantity': fields.Integer(required=True, description='Кількість'),
    'price': fields.Float(description='Ціна на момент замовлення')
})

order_model = api.model('Order', {
    'id': fields.Integer(readonly=True, description='ID замовлення'),
    'user_id': fields.Integer(description='ID користувача'),
    'guest_id': fields.Integer(description='ID гостя'),
    'order_date': fields.DateTime(description='Дата замовлення'),
    'status': fields.String(description='Статус замовлення'),
    'total_price': fields.Float(description='Загальна сума'),
    'delivery_address': fields.String(description='Адреса доставки'),
    'comments': fields.String(description='Коментарі'),
    'phone_number': fields.String(description='Номер телефону'),
    'items': fields.List(fields.Nested(order_item_model), description='Елементи замовлення')
})

table_model = api.model('Table', {
    'id': fields.Integer(readonly=True, description='ID столика'),
    'table_number': fields.Integer(required=True, description='Номер столика'),
    'capacity': fields.Integer(required=True, description='Кількість місць'),
    'is_available': fields.Boolean(description='Чи вільний столик')
})

reservation_model = api.model('Reservation', {
    'id': fields.Integer(readonly=True, description='ID бронювання'),
    'user_id': fields.Integer(description='ID користувача'),
    'guest_id': fields.Integer(description='ID гостя'),
    'table_id': fields.Integer(required=True, description='ID столика'),
    'reservation_date': fields.DateTime(required=True, description='Дата бронювання'),
    'guest_count': fields.Integer(required=True, description='Кількість гостей'),
    'comments': fields.String(description='Коментарі'),
    'status': fields.String(description='Статус бронювання'),
    'phone_number': fields.String(description='Номер телефону')
})


users_ns = api.namespace('users', description='Операції з користувачами')
guests_ns = api.namespace('guests', description='Операції з гостями')
dishes_ns = api.namespace('dishes', description='Операції зі стравами')
orders_ns = api.namespace('orders', description='Операції з замовленнями')
tables_ns = api.namespace('tables', description='Операції зі столиками')
reservations_ns = api.namespace('reservations', description='Операції з бронюваннями')
news_ns = api.namespace('news', description='Операції з новинами')

