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
    'phone_number': fields.String(required=True, description='Номер телефону'),
    'first_name': fields.String(description='Ім\'я'),
    'last_name': fields.String(description='Прізвище'),
    'is_admin': fields.Boolean(description='Чи є користувач адміністратором')
})

registration_model = api.model('UserRegistration', {
    'phone_number': fields.String(required=True, description='Номер телефону'),
    'password': fields.String(required=True, description='Пароль'), 
    'first_name': fields.String(description='Ім\'я'),
    'last_name': fields.String(description='Прізвище') # Видалив isadmin при регістрації, поки взагалі його не використовуємо
})

login_model = api.model('UserLogin' , {
    'phone_number': fields.String(required=True, description='Номер телефону для входу'),
    'password': fields.String(required=True, description='Пароль для входу')
})
verify_otp_and_reset_password_model = api.model('VerifyOTPAndResetPassword', {
    'phone_number': fields.String(required=True, description='Номер телефону користувача (E.164)'),
    'otp_code': fields.String(required=True, description='OTP-код, отриманий через SMS'),
    'new_password': fields.String(required=True, description='Новий пароль')
})
reset_password_model = api.model('VerifyOTPAndResetPassword', {
    'first_name': fields.String(required=True, description='Ім\'я'),
    'last_name': fields.String(required=True, description='Прізвище'),
    'phone_number': fields.String(required=True, description='Номер телефону користувача (E.164)'),
    'old_password': fields.String(required=True, description='Старий пароль'),
    'new_password': fields.String(required=True, description='Новий пароль'),
    'new_password_repeat': fields.String(required=True, description='Підтвердження нового паролю')
}) # Взагалі не зовсім зрозумів навіщо в зміні пароля ПІ, але Максим сказав значить хай буде

request_otp_model = api.model('RequestPasswordResetOTP', {
    'phone_number': fields.String(required=True, description='Номер телефону користувача (у форматі E.164, по типу +380991234567)')
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

modifier_option_model = api.model('ModifierOption', {
    'id': fields.Integer(readonly=True, description='ID опції модифікатора'),
    'name': fields.String(required=True, description='Назва опції (напр., "Мигдальне", "соєвє")'),
    'price_modifier': fields.Float(required=True, description='Зміна ціни при виборі цієї опції (напр., 5.00, 10.00, 0.00)'),
    'is_default': fields.Boolean(default=False, description='Чи вибрана ця опція за замовчуванням у групі')
})

modifier_group_model = api.model('ModifierGroup', {
    'id': fields.Integer(readonly=True, description='ID групи модифікаторів'),
    'name': fields.String(required=True, description='Назва групи (напр., "ОБОВ\'ЯЗКОВО вид молока", "Додати сироп?")'),
    'description': fields.String(description='Додатковий опис групи'),
    'is_required': fields.Boolean(default=True, description='Чи є вибір у цій групі обов\'язковим'),
    'selection_type': fields.String(enum=['single', 'multiple'], default='single', description='Тип вибору: один (single) чи декілька (multiple) опцій'),
    'options': fields.List( # Список опцій всередині групи
        fields.Nested(modifier_option_model),
        required=True,
        min_items=1, # Група має містити хоча б одну опцію
        description='Список доступних опцій у цій групі'
    )
})


dish_variant_model = api.model('DishVariant', {
    'id': fields.Integer(readonly=True, description='ID варіанту (опціонально, для внутрішньої логіки)'),
    'size_label': fields.String(required=True, description='Текстове позначення розміру/варіанту (напр., "L", "XL", "360г", "700г", "Чорний з лимоном")'),
    'weight_grams': fields.Integer(description='Вага варіанту в грамах (г)'),
    'volume_ml': fields.Integer(description='Об\'єм варіанту в мілілітрах (мл)'),
    'price': fields.Float(required=True, description='Базова (!) ціна цього варіанту страви/напою '),
    'is_default': fields.Boolean(default=False, description='Чи є цей варіант варіантом за замовчуванням (його ціна буде відображатись в картці)')
})


dish_model = api.model('Dish', {
    'id': fields.Integer(readonly=True, description='ID страви'),
    'name': fields.String(required=True, description='Назва страви'),
    'description': fields.String(description='Опис страви'),
    'detailed_description': fields.String(description = 'Детальний опис страви'),
    'image_url': fields.String(description='URL зображення'),
    'category': fields.String(description='Категорія страви'),
    'is_available': fields.Boolean(description='Чи доступна страва'),
    'tags': fields.List(
        fields.String,
        description = 'Список тегів/атрибутів (Приклад: spicy,salty,vegeterian,meat,fish,new,lactose)'
    ),
    'variants': fields.List(
        fields.Nested(dish_variant_model),
        required = True,
        min_items = 1,
        description = 'Список доступних варіантів страви (розміри,вага,інгрідієнти,смаки), кожен зі своєю ціною. Вибір є обов\'язковим, якщо їх >1' 
    ),
    'modifier_groups': fields.List( #Список груп модифікаторів
        fields.Nested(modifier_group_model),
        description='Список груп опцій, які можуть змінювати ціну (напр., вибір молока, топінги).'
    )
})

news_model = api.model('News', {
    'id': fields.Integer(readonly=True, description='ID страви'),
    'name': fields.String(required=True, description='Назва новини'),
    'description': fields.String(description='Опис новини'),
    'image_url': fields.String(description='URL зображення'),
    'is_actual': fields.Boolean(description='Чи актуальна новина')
})


order_item_model_input = api.model('OrderItemInput', { #це модель для ВХІДНИХ даних
    'dish_id': fields.Integer(required=True, description='ID базової страви'),
    'variant_id': fields.Integer(required=True, description='ID вибраного варіанту страви (розмір, смак тощо)'), 
    'quantity': fields.Integer(required=True, min=1, description='Кількість (має бути > 0)'),
    'modifier_option_ids': fields.List(fields.Integer, description='Список ID вибраних опцій модифікаторів (якщо є)') 
})

# Модель для ВІДПОВІДІ 
order_item_model_output = api.model('OrderItemOutput', {
    'id': fields.Integer(readonly=True, description='ID елемента замовлення'),
    'dish_id': fields.Integer(description='ID базової страви'),
    'variant_id': fields.Integer(description='ID вибраного варіанту'), 
    'quantity': fields.Integer(description='Кількість'),
    'price': fields.Float(description='Ціна за одиницю товару (з урахуванням варіанту та модифікаторів)'), 
    'dish_name': fields.String(attribute='dish.name', description='Назва страви'),
    'variant_label': fields.String(attribute='variant.size_label', description='Позначення варіанту'),
    'selected_modifier_options': fields.List(fields.Raw, description='Деталі вибраних модифікаторів') 
})

order_model = api.model('Order', {
    'id': fields.Integer(readonly=True, description='ID замовлення'),
    'user_id': fields.Integer(description='ID користувача (або null)'),
    'guest_id': fields.Integer(description='ID гостя (або null)'),
    'order_date': fields.DateTime(description='Дата замовлення'),
    'status': fields.String(description='Статус замовлення'),
    'total_price': fields.Float(description='Загальна сума замовлення'), 
    'delivery_address': fields.String(description='Адреса доставки'),
    'comments': fields.String(description='Коментарі'),
    'phone_number': fields.String(required=False, description='Номер телефону '), 
    'name': fields.String(description="Ім'я гостя (якщо не зареєстрований)"), 
    'items': fields.List(fields.Nested(order_item_model_input), required=True, min_items=1, description='Елементи замовлення')
})

# Модель відповіді для замовлення (використовує модель виводу для item)
order_model_output = api.model('OrderOutput', {
    'id': fields.Integer(readonly=True),
    'user_id': fields.Integer(allow_null=True),
    'guest_id': fields.Integer(allow_null=True),
    'order_date': fields.DateTime(),
    'status': fields.String(),
    'total_price': fields.Float(),
    'delivery_address': fields.String(),
    'comments': fields.String(),
    'phone_number': fields.String(),
    'items': fields.List(fields.Nested(order_item_model_output)) 
})

table_model = api.model('Table', {
    'id': fields.Integer(readonly=True, description='ID столика'),
    'table_number': fields.Integer(required=True, description='Номер столика'),
    'capacity': fields.Integer(required=True, description='Кількість місць'),
    'is_available': fields.Boolean(description='Чи вільний столик')
})

reservation_model = api.model('Reservation', {
    'id': fields.Integer(readonly=True, description='ID бронювання'),
    'user_id': fields.Integer(description='ID користувача', allow_null=True),
    'guest_id': fields.Integer(description='ID гостя', allow_null=True),
    'table_id': fields.Integer(required=True, description='ID столика'),
    'reservation_start_time': fields.DateTime(required=True, description='Дата та час початку бронювання', dt_format='iso8601'), 
    'reservation_end_time': fields.DateTime(required=True, description='Дата та час закінчення бронювання', dt_format='iso8601'), 
    'guest_count': fields.Integer(required=True, description='Кількість гостей'),
    'comments': fields.String(description='Коментарі'),
    'status': fields.String(description='Статус бронювання'),
    'phone_number': fields.String(description='Номер телефону'),

    'user': fields.Nested(user_model, description='Деталі користувача', allow_null=True, skip_none=True),
    'guest': fields.Nested(guest_model, description='Деталі гостя', allow_null=True, skip_none=True),
    'table': fields.Nested(table_model, description='Деталі столика', required=True)
})

reservation_input_model = api.model('ReservationInput', {
    'date': fields.String(required=True, description='Дата бронювання у форматі YYYY-MM-DD', example='2024-12-31'),
    'slot_start': fields.String(required=True, description='Час початку слоту у форматі HH:MM', example='14:00'),
    'table_id': fields.Integer(required=True, description='ID столика'),
    'guest_count': fields.Integer(required=True, description='Кількість гостей'),
    'user_id': fields.Integer(description='ID користувача (якщо зареєстрований)'),
    'phone_number': fields.String(description='Номер телефону (якщо гість або новий користувач)'),
    'name': fields.String(description="Ім'я гостя (якщо не зареєстрований)"),
    'comments': fields.String(description='Коментарі до бронювання')
})

time_slot_availability_model = api.model('TimeSlotAvailability', {
    'slot_start': fields.String(description='Час початку слоту HH:MM'),
    'slot_end': fields.String(description='Час кінця слоту HH:MM'),
    'is_available_for_booking': fields.Boolean(description='Чи доступний слот для бронювання')
})

date_slots_availability_response_model = api.model('DateSlotsAvailabilityResponse', {
    'date': fields.String(description='Дата у форматі YYYY-MM-DD'),
    'slots': fields.List(fields.Nested(time_slot_availability_model))
})

table_slot_availability_model = api.model('TableSlotAvailability', {
    'table_id': fields.Integer(),
    'table_number': fields.Integer(),
    'capacity': fields.Integer(),
    'is_available': fields.Boolean(),
    'reason_code': fields.String(allow_null=True),
    'reason_message': fields.String(allow_null=True)
})

users_ns = api.namespace('users', description='Операції з користувачами')
guests_ns = api.namespace('guests', description='Операції з гостями')
dishes_ns = api.namespace('dishes', description='Операції зі стравами')
orders_ns = api.namespace('orders', description='Операції з замовленнями')
tables_ns = api.namespace('tables', description='Операції зі столиками')
modifier_groups_ns = api.namespace('modifier-groups', description='Операції з групами модифікаторів')
reservations_ns = api.namespace('reservations', description='Операції з бронюваннями')
news_ns = api.namespace('news', description='Операції з новинами')

