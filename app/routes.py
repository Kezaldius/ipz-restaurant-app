from flask import request, jsonify,current_app
from flask_restx import Resource,  reqparse, fields 
from app import db, api 
from app.api import *
from app.models import *
from app.schemas import *
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import NotFound, BadRequest
from datetime import datetime, timedelta, date as py_date, time as py_time
from sqlalchemy.exc import IntegrityError, OperationalError
from marshmallow import ValidationError
from twilio.rest import Client
import re
import random
import string

def get_object_or_404(model, id):
    obj = model.query.get(id)
    if obj is None:
        return {'message': f'{model.__name__} not found'}, 404
    return obj, 200

slots_availability_parser = reqparse.RequestParser()
slots_availability_parser.add_argument('date', type=str, required=True, help='Дата у форматі YYYY-MM-DD', location='args')
slots_availability_parser.add_argument('guest_count', type=int, required=False, help='Кількість гостей', location='args')

tables_availability_parser = reqparse.RequestParser()
tables_availability_parser.add_argument('date', type=str, required=True, help='Дата у форматі YYYY-MM-DD', location='args')
tables_availability_parser.add_argument('slot_start', type=str, required=True, help='Час початку слоту у форматі HH:MM', location='args')
tables_availability_parser.add_argument('guest_count', type=int, required=False, help='Кількість гостей', location='args')

@users_ns.route('/register')
class UserRegistration(Resource):
    @users_ns.doc('create_new_user')
    @users_ns.expect(registration_model, validate=True)
    @users_ns.response(201, 'User created successfully', user_model)
    @users_ns.response(400, 'Validation Error or Phone number already exists')
    @users_ns.response(500, 'Internal Server Error')
    def post(self):
        """Реєстрація нового користувача."""
        user_schema = UserSchema()
        try:
            new_user = user_schema.load(request.get_json(), session=db.session)
        except ValidationError as e:
             return {'message': 'Помилка валідації даних', 'errors': e.messages}, 400

        if 'password' in request.get_json():
            new_user.set_password(request.get_json()['password'])
        else:
            return {'message': 'Пароль є обов\'язковим '}, 400 # Може щось змінювати буду нехай тут буде
        
        db.session.add(new_user)

        try:
            db.session.commit()
            return user_schema.dump(new_user), 201
        except IntegrityError as e:
            db.session.rollback()
            return {'message': 'Помилка при створенні користувача', 'error': str(e)}, 500


@users_ns.route('/login')
class UserLogin(Resource):
    @users_ns.doc('user_login')
    @users_ns.expect(user_model, validate=True)  
    @users_ns.response(200, 'Login successful')
    @users_ns.response(400, 'Bad Request')
    @users_ns.response(401, 'Invalid credentials')
    def post(self):
        """Вхід користувача."""
        data = request.get_json()
        phone_number = data.get('phone_number')
        password = data.get('password')

        if not phone_number or not password:
            return {'message': 'Номер телефону та пароль є обов\'язковими'}, 400

        user = User.query.filter_by(phone_number=phone_number).first()

        if user and user.check_password(password):
            return {'message': 'Успішний вхід', 'user_id': user.id}, 200
        else:
            return {'message': 'Неправильний номер телефону або пароль'}, 401

@users_ns.route('/<int:user_id>')
@users_ns.param('user_id', 'The user identifier')
class UserResource(Resource):
    @users_ns.doc('get_user_details')
    @users_ns.marshal_with(user_model) 
    @users_ns.response(404, 'Користувача не знайдено')
    def get(self, user_id):
        """Отримати детальну інформацію про користувача за ID."""
        user, status_code = get_object_or_404(User, user_id)
        if status_code == 404:
            return user, status_code 
        return user, 200 
    
    @users_ns.doc('partially_update_user')
    @users_ns.expect(user_patch_model)
    @users_ns.marshal_with(user_model)
    @users_ns.response(404, 'Користувача не знайдено')
    @users_ns.response(400, 'Помилка валідації')
    def patch(self, user_id):
        """Оновити інформацію про користувача за ID."""
        user_obj = User.query.get(user_id)
        if not user_obj:
            users_ns.abort(404, f"Користувача з ID {user_id} не знайдено.")
        data_to_update = users_ns.payload

        if not data_to_update:
            users_ns.abort(400, "Нема даних для оновлення")
        
        updated_fields_count = 0

        for key, value in data_to_update.items():
            if hasattr(user_obj, key) and key != 'id' :
                setattr(user_obj, key, value)
                updated_fields_count += 1
            else:
                current_app.logger.warning(f"Спроба оновити відстунє чи захищене поле '{key}' для користувача {user_id}")
        if updated_fields_count == 0:
            return {'message': 'Не було надано дійсних полів для оновлення або вказані поля не існують'}, 400
        try:
            db.session.commit()
            db.session.refresh(user_obj)
            current_app.logger.info(f"Користувача {user_id} успішно оновленно.")
            return user_obj, 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Помилка у БД при оновленні користувача {user_id}: {str(e)}")
            users_ns.abort(500, "Внутрішня помилка сервера при оновленні користувача")


@users_ns.route('/passwordreset') 
class RequestPasswordReset(Resource):
    @users_ns.doc('request_password_reset')
    @users_ns.expect(request_otp_model, validate=True)
    @users_ns.response(200, 'OTP успішно надіслано.')
    @users_ns.response(400, 'Невірний запит або помилка відправки OTP.')
    @users_ns.response(404, 'Користувача з таким номером телефону не знайдено.')
    @users_ns.response(500, 'Помилка на сервері Twilio')
    def post(self):
        """Запит на відправку OTP для скидання пароля."""
        data = request.get_json()
        phone_number = data.get('phone_number')

        if not phone_number:
            return {'message': 'Номер телефону є обов\'язковим.'}, 400
        
        user = User.query.filter_by(phone_number=phone_number).first()
        if not user:
            return {'message': 'Користувача з таким номером телефону не знайдено.'}, 404

        def normalize_number(number: str) -> str:
            cleaned = re.sub(r"[^\d+]", "", number)
            if re.fullmatch(r"0\d{9}", cleaned): # Якщо номер починається з 0 і має довжину в 10 цифр то додаємо код країни
                cleaned = "+380" + cleaned[1:]
            elif re.fullmatch(r"380\d{9}", cleaned): # Додаємо + якщо '380...'
                cleaned = "+" + cleaned
            return cleaned
        
        normalized_phonenumber = normalize_number(phone_number)
        
        def generate_otp(length=6):
            return "".join(random.choices(string.digits, k=length))
        
        otp_code = generate_otp()
        otp_expiration_seconds = current_app.config.get('OTP_EXPIRATION_SECONDS', 1800)

        PasswordResetOTP.query.filter_by(phone_number=phone_number, used=False).delete() # Видаляємо старі OTP при генерації нових 
        db.session.commit()

        new_otp_entry = PasswordResetOTP(
            phone_number=phone_number,
            otp_code=otp_code,
            expires_in_seconds=otp_expiration_seconds
        )
        db.session.add(new_otp_entry)
        db.session.commit()


        account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
        auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')

        if not all([account_sid, auth_token, normalized_phonenumber]):
            current_app.logger.error("Twilio credentials не налаштовані.")
            return {'message': 'Помилка конфігурації сервісу.'}, 500
        
        client = Client(account_sid, auth_token)
        message_body = f"Ваш код для скидання пароля: {otp_code}."
        
        try:
            message = client.messages.create(
                body=message_body,
                from_='+16183238656',
                to=normalized_phonenumber
            )
        except Exception as e:
            current_app.logger.error(f"Загальна помилка при відправці SMS для {phone_number}: {e}")
            return {'message': 'Внутрішня помилка сервера.'}, 500

@users_ns.route('/otpverify')
class VerifyOTPAndResetPassword(Resource):
    @users_ns.doc('verify_otp_and_reset_password')
    @users_ns.expect(verify_otp_and_reset_password_model, validate=True)
    @users_ns.response(200, 'Пароль успішно змінено.')
    @users_ns.response(400, 'Невірні вхідні дані - не всі поля заповнені.')
    @users_ns.response(401, 'Невірний або прострочений OTP-код.')
    @users_ns.response(404, 'Користувача з таким номером телефону не знайдено.')
    @users_ns.response(500, 'Внутрішня помилка сервера при спробі змінити пароль.')
    def post(self):
        """Запит на верифікацію OTP для скидання пароля."""
        data = request.get_json()
        phone_number = data.get('phone_number')
        provided_otp = data.get('otp_code')
        new_password = data.get('new_password')

        if not phone_number or not provided_otp or not new_password:
            return {'message': 'Номер телефону, OTP-код та новий пароль є обов\'язковими.'}, 400
        
        user = User.query.filter_by(phone_number=phone_number).first()
        if not user:
            current_app.logger.info(f"Спроба верифікації OTP для неіснуючого користувача: {phone_number}")
            return {'message': 'Користувача з таким номером телефону не знайдено.'}, 404
        
        otp_entry = PasswordResetOTP.query.filter_by(
            phone_number=phone_number,
            used=False
        ).order_by(PasswordResetOTP.created_at.desc()).first() # Беремо найостанніший пароль. Це важливо, якщо користувач міг кілька разів запитувати OTP

        if not otp_entry:
            current_app.logger.warning(f"Не знайдено активного OTP для {phone_number} при спробі верифікації.")
            return {'message': 'Для цього номеру телефону не було запитано OTP, або він вже використаний/прострочений.'}, 401
        
        if not otp_entry.is_valid(provided_otp):
            current_app.logger.warning(f"Невдала спроба верифікації OTP для {phone_number}. Надано: {provided_otp}, Очікувалось: {otp_entry.otp_code if otp_entry else 'N/A'}")
            # Якщо треба буде то можу зробити тут логіку таймаута після декількох невдалих спроб
            return {'message': 'Невірний або прострочений OTP-код.'}, 401
        
        user.set_password(new_password)
        otp_entry.mark_as_used() # Встановлюємо пароль та ставимо otp як використаний

        try:
            db.session.add(user) # Це для ясності зроблено, приберу за непотребою якщо багів не буде
            db.session.add(otp_entry) 
            db.session.commit() 
            current_app.logger.info(f"Пароль для користувача {phone_number} успішно змінено.")
            return {'message': 'Пароль успішно змінено.'}, 200
        except Exception as e:
            db.session.rollback() 
            current_app.logger.error(f"Помилка бази даних при зміні пароля для {phone_number} після валідації OTP: {str(e)}")
            return {'message': 'Внутрішня помилка сервера при спробі оновити пароль.'}, 500

@users_ns.route('/passwordresetclassic')
class ResetPasswordClassic(Resource):
    @users_ns.doc('reset_password')
    @users_ns.expect(reset_password_model, validate=True)
    @users_ns.response(200, 'Пароль успішно змінено.')
    @users_ns.response(400, 'Невірні вхідні дані - не всі поля правильно заповнені.')
    @users_ns.response(401, 'Помилка авторизації')
    @users_ns.response(404, 'Користувача з таким номером телефону не знайдено.')
    @users_ns.response(500, 'Внутрішня помилка сервера при спробі змінити пароль.')

    def post(self):
        """Запит на скидання пароля класичним методом"""
        data = request.get_json()
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        phone_number = data.get('phone_number')
        old_password = data.get('old_password')
        old_password_input = data.get('old_password')
        new_password = data.get('new_password')
        new_password_repeat = data.get('new_password_repeat')

        if not all([first_name,last_name,phone_number,old_password,new_password,new_password]):
            return {'message': 'Номер телефону, прізвище, ім\'я, поточний пароль та новий пароль з повтором є обов\'язковими.'}, 400
        user = User.query.filter_by(phone_number=phone_number).first()
        if not user:
            return {'message': 'Користувача з таким номером телефону не знайдено.'}, 404
    
        if new_password != new_password_repeat:
            return {'message': 'Введені паролі не збігаються. Будь ласка, переконайтеся, що обидва паролі однакові.'}, 400
        
        if not user.check_password(old_password_input):
            current_app.logger.warning(f"Невдала спроба зміни пароля для {phone_number}: невірний старий пароль.")
            return {'message': 'Невірний поточний пароль.'}, 401
        
        user.set_password(new_password)

        try:
            db.session.add(user) # Це для ясності зроблено, приберу за непотребою якщо багів не буде
            db.session.commit() 
            current_app.logger.info(f"Пароль для користувача {phone_number} успішно змінено.")
            return {'message': 'Пароль успішно змінено.'}, 200
        except Exception as e:
            db.session.rollback() 
            current_app.logger.error(f"Помилка бази даних при зміні пароля для {phone_number}: {str(e)}")
            return {'message': 'Внутрішня помилка сервера при спробі оновити пароль.'}, 500
        

@guests_ns.route('/')
class GuestResource(Resource):
    @guests_ns.doc('create_or_get_guest')
    @guests_ns.expect(guest_input_model, validate=True)
    @guests_ns.response(200, 'Guest found/created', guest_model)
    @guests_ns.response(400, 'Validation Error')
    def post(self):
        """Створення або отримання гостя за номером телефону."""
        try:
            data = request.get_json()

            if not data or 'phone_number' not in data:
                return {"message": "Потрібно вказати номер телефону"}, 400

            guest = Guest.query.filter_by(phone_number=data['phone_number']).first()

            if not guest:
                guest = Guest(
                    phone_number=data['phone_number'],
                    name=data.get('name', '')
                )
                db.session.add(guest)
                db.session.commit()

            guest_schema = GuestSchema()
            return guest_schema.dump(guest), 200

        except ValidationError as e:
            return {'message': 'Помилка валідації', 'errors': e.messages}, 400
        except Exception as e:
            db.session.rollback()
            return {'message': 'Помилка при обробці запиту', 'error': str(e)}, 500

@dishes_ns.route('/')
class DishList(Resource):

    @dishes_ns.doc('list_dishes')
    # Використовуємо єдину модель API для відповіді
    @dishes_ns.marshal_list_with(dish_model)
    def get(self):
        """Отримати список усіх страв."""
        dishes = Dish.query.all()
        return dishes 

    @dishes_ns.doc('create_dish')
    @dishes_ns.expect(dish_model) 
    # Повертаємо у форматі єдиної моделі API
    @dishes_ns.marshal_with(dish_model, code=201)
    def post(self):
        """Створити нову страву."""
        try:
            data = api.payload

            # Витягуємо дані для зв'язків ПЕРЕД створенням об'єкта Dish
            modifier_groups_input = data.pop('modifier_groups', [])
            tag_names = data.pop('tags', [])
            variants_data = data.pop('variants', [])

            # Валідація базових даних
            if not data.get('name'): api.abort(400, "Поле 'name' є обов'язковим.")
            if not variants_data: api.abort(400, "Поле 'variants' є обов'язковим.")

            # --- Обробка Modifier Groups ---
            linked_modifier_groups = []
            if modifier_groups_input:
                 group_ids_to_find = []
                 for group_data in modifier_groups_input:
                     group_id = group_data.get('id')
                     if group_id and isinstance(group_id, int): group_ids_to_find.append(group_id)
                     else: api.abort(400, f"Невірний формат modifier_groups: очікується [{'id': N}].")
                 if group_ids_to_find:
                     found_groups = ModifierGroup.query.filter(ModifierGroup.id.in_(group_ids_to_find)).all()
                     if len(found_groups) != len(set(group_ids_to_find)):
                          found_ids = {g.id for g in found_groups}; missing_ids = set(group_ids_to_find) - found_ids
                          api.abort(400, f"Групи модифікаторів з ID {missing_ids} не знайдено.")
                     linked_modifier_groups = found_groups

            # --- Обробка Tags ---
            linked_tags = []
            if tag_names:
                 for name in tag_names:
                     if not isinstance(name, str): api.abort(400, f"Теги повинні бути рядками.")
                     tag = Tag.query.filter_by(name=name).first();
                     if not tag: tag = Tag(name=name)
                     linked_tags.append(tag)

            # --- Створення основного об'єкта Dish ---
            dish_fields = {k: v for k, v in data.items() if hasattr(Dish, k)}
            new_dish = Dish(**dish_fields)

            # --- Створення та прив'язка Variants ---
            for variant_data in variants_data:
                 if not isinstance(variant_data, dict) or not all(k in variant_data for k in ('size_label', 'price')): api.abort(400, "Варіант має містити 'size_label' та 'price'.")
                 variant_fields = {k: v for k, v in variant_data.items() if hasattr(DishVariant, k)}
                 variant = DishVariant(**variant_fields)
                 new_dish.variants.append(variant)

            # --- Прив'язка знайдених груп та тегів ---
            new_dish.modifier_groups = linked_modifier_groups
            new_dish.tags = linked_tags

            # --- Збереження ---
            db.session.add(new_dish)
            db.session.commit()

            return new_dish, 201

        except IntegrityError as e: db.session.rollback(); return {'message': 'Помилка цілісності даних.', 'error': str(getattr(e, 'orig', e))}, 400
        except Exception as e: db.session.rollback(); print(f"Error: {e}"); return {'message': 'Внутрішня помилка сервера.', 'error': str(e)}, 500

@dishes_ns.route('/<int:dish_id>')
@dishes_ns.param('dish_id', 'The dish identifier')
class DishResource(Resource):
    @dishes_ns.doc('get_dish')
    # Використовуємо єдину модель API для відповіді
    @dishes_ns.marshal_with(dish_model)
    @dishes_ns.response(404, 'Dish not found')
    def get(self, dish_id):
        """Отримати страву за ID."""
        dish = Dish.query.get_or_404(dish_id)
        return dish

    @dishes_ns.doc('update_dish')
    @dishes_ns.expect(dish_model) 
    @dishes_ns.marshal_with(dish_model)
    @dishes_ns.response(400, 'Validation Error')
    @dishes_ns.response(404, 'Dish not found')
    def put(self, dish_id):
        """Оновити страву за ID."""
        dish = Dish.query.get_or_404(dish_id)
        try:
            data = api.payload

            # Витягуємо дані для зв'язків
            modifier_groups_input = data.pop('modifier_groups', None)
            tag_names = data.pop('tags', None)
            variants_data = data.pop('variants', None)

            # --- Оновлення Modifier Groups (якщо передано) ---
            if modifier_groups_input is not None:
                linked_modifier_groups = []
                if modifier_groups_input:
                    group_ids_to_find = []
                    for group_data in modifier_groups_input:
                         group_id = group_data.get('id');
                         if group_id and isinstance(group_id, int): group_ids_to_find.append(group_id)
                         else: api.abort(400, f"Невірний формат modifier_groups.")
                    if group_ids_to_find:
                        found_groups = ModifierGroup.query.filter(ModifierGroup.id.in_(group_ids_to_find)).all()
                        if len(found_groups) != len(set(group_ids_to_find)):
                             missing_ids = set(group_ids_to_find) - {g.id for g in found_groups}
                             api.abort(400, f"Групи модифікаторів з ID {missing_ids} не знайдено.")
                        linked_modifier_groups = found_groups
                dish.modifier_groups = linked_modifier_groups # Перезаписуємо

            # --- Оновлення Tags (якщо передано) ---
            if tag_names is not None:
                 linked_tags = []
                 for name in tag_names:
                     if not isinstance(name, str): api.abort(400, f"Теги повинні бути рядками.")
                     tag = Tag.query.filter_by(name=name).first();
                     if not tag: tag = Tag(name=name)
                     linked_tags.append(tag)
                 dish.tags = linked_tags # Перезаписуємо

            # --- Оновлення Variants (якщо передано) ---
            if variants_data is not None:
                 DishVariant.query.filter_by(dish_id=dish.id).delete(); db.session.flush()
                 if not variants_data: api.abort(400, "Поле 'variants' не може бути порожнім.")
                 new_variants = []
                 for variant_data in variants_data:
                      if not isinstance(variant_data, dict) or not all(k in variant_data for k in ('size_label', 'price')): api.abort(400, "Варіант має містити 'size_label' та 'price'.")
                      variant_fields = {k: v for k, v in variant_data.items() if hasattr(DishVariant, k)}
                      variant = DishVariant(**variant_fields)
                      new_variants.append(variant)
                 dish.variants = new_variants
            # --- Оновлення основних полів страви ---
            for key, value in data.items():
                if hasattr(dish, key) and key not in ['id', 'variants', 'tags', 'modifier_groups']:
                    setattr(dish, key, value)

            # --- Збереження ---
            db.session.commit()

            return dish
        except IntegrityError as e: db.session.rollback(); return {'message': 'Помилка цілісності даних.', 'error': str(getattr(e, 'orig', e))}, 400
        except Exception as e: db.session.rollback(); print(f"Error updating dish: {e}"); return {'message': 'Внутрішня помилка сервера.', 'error': str(e)}, 500

    @dishes_ns.doc('delete_dish')
    @dishes_ns.response(204, 'Dish deleted')
    @dishes_ns.response(404, 'Dish not found')
    def delete(self, dish_id):
        """Видалити страву за ID."""
        dish = Dish.query.get_or_404(dish_id)
        db.session.delete(dish)
        db.session.commit()
        return '', 204


@orders_ns.route('/')
class OrderList(Resource):
    @orders_ns.doc('create_order')
    @orders_ns.expect(order_model, validate=True)
    @orders_ns.response(201, 'Order created', order_model)
    @orders_ns.response(400, 'Bad Request')
    def post(self):
        """Створити нове замовлення."""
        try:
            data = request.get_json()
        except:
            return {'message': 'Некоректні дані'}, 400

        if not data or 'items' not in data or not data['items']:
            return {'message': "Необхідно вказати список страв"}, 400

        user_id = data.get('user_id')
        phone_number = data.get('phone_number')

        if not user_id and not phone_number:
            return {'message': "Потрібно вказати user_id або phone_number"}, 400

        guest_id = None
        if phone_number:
            guest = Guest.query.filter_by(phone_number=phone_number).first()
            if not guest:
                guest = Guest(phone_number=phone_number, name=data.get('name', ''))
                db.session.add(guest)
                db.session.flush()
            guest_id = guest.id

        elif user_id:
            user, status_code = get_object_or_404(User, user_id)
            if status_code == 404:
                return user, status_code

        order = Order(
            user_id=user_id,
            guest_id=guest_id,
            phone_number=phone_number,
            delivery_address=data.get('delivery_address'),
            comments=data.get('comments')
        )

        total_price = 0
        for item_data in data['items']:
            dish_id = item_data.get('dish_id')
            variant_id = item_data.get('variant_id')
            quantity = item_data.get('quantity')
            modifier_option_ids = item_data.get('modifier_option_ids', [])

            if not dish_id or not variant_id or not quantity:
                return {'message': 'Кожен item повинен мати dish_id, variant_id і quantity'}, 400

            dish, status_code = get_object_or_404(Dish, dish_id)
            if status_code == 404:
                return dish, status_code

            variant = DishVariant.query.filter_by(id=variant_id, dish_id=dish.id).first()
            if not variant:
                return {'message': f'Варіант страви не знайдено'}, 400

            if not dish.is_available:
                return {'message': f'Страва "{dish.name}" недоступна'}, 400

            if quantity <= 0:
                return {'message': "Кількість страв має бути більше нуля"}, 400

            # Ціна: базова з варіанту + сума модифікаторів
            item_price = float(variant.price)
            order_item = OrderItem(dish=dish, quantity=quantity, variant=variant)

            for mod_id in modifier_option_ids:
                modifier = ModifierOption.query.get(mod_id)
                if not modifier:
                    return {'message': f'Модифікатор з id {mod_id} не знайдено'}, 400
                order_item_modifier = OrderItemModifier(modifier_option=modifier)
                order_item.modifiers.append(order_item_modifier)
                item_price += float(modifier.price_modifier)

            order_item.price = item_price
            total_price += item_price * quantity
            order.items.append(order_item)
        
        order.total_price = total_price

        try:
            db.session.add(order)
            db.session.commit()
            db.session.refresh(order)
            order_schema = OrderSchema()
            return order_schema.dump(order), 201
        except Exception as e:
            db.session.rollback()
            return {'message': 'Помилка створення замовлення', 'error': str(e)}, 500
    def get(self):
        """Отримати всі замовлення"""
        orders = Order.query.all()  # Отримуємо всі замовлення
        order_schema = OrderSchema(many=True)
        return order_schema.dump(orders), 200    
    
@orders_ns.route('/<int:order_id>')
@orders_ns.param('order_id', 'The order identifier')
class OrderResource(Resource):
    @orders_ns.doc('get_order')
    @orders_ns.response(200, 'Success', order_model)
    @orders_ns.response(404, 'Order not found')
    def get(self, order_id):
        """Отримати замовлення за ID."""
        order, status_code = get_object_or_404(Order, order_id)
        if status_code == 404: return order, status_code

        order_schema = OrderSchema()
        return order_schema.dump(order), 200

    @orders_ns.doc('update_order_status')
    @orders_ns.expect(order_model, validate=False)  
    @orders_ns.response(200, 'Order updated', order_model)
    @orders_ns.response(400, 'Bad Request')
    @orders_ns.response(404, 'Order not found')
    def put(self, order_id):
        """Оновити статус замовлення."""
        order, status_code = get_object_or_404(Order, order_id)
        if status_code == 404: return order, status_code

        try:
            data = request.get_json()
        except:
            return{'message':'Некоректні данні'}, 400

        if 'status' in data:
              order.status = data['status']

        db.session.commit()
        order_schema = OrderSchema()
        return order_schema.dump(order), 200

    @orders_ns.doc('delete_order')
    @orders_ns.response(204, 'Order deleted')
    @orders_ns.response(404, 'Order not found')
    def delete(self, order_id):
        """Видалити замовлення за ID."""
        order, status_code = get_object_or_404(Order, order_id)
        if status_code == 404: return order, status_code

        db.session.delete(order)
        db.session.commit()
        return '', 204


@users_ns.route('/<int:user_id>/orders')
@users_ns.param('user_id', 'The user identifier')
class UserOrders(Resource):
    @users_ns.doc('get_user_orders')
    @users_ns.response(200, 'Success', order_model)
    @users_ns.response(404, 'User not found')
    def get(self, user_id):
        """Отримати замовлення користувача."""
        user, status_code = get_object_or_404(User, user_id)
        if status_code == 404: return user, status_code

        orders = Order.query.filter_by(user_id=user_id).all()
        order_schema = OrderSchema(many=True)
        return order_schema.dump(orders), 200

@guests_ns.route('/<string:phone_number>/orders')
@guests_ns.param('phone_number', 'Guest phone number')
class GuestOrders(Resource):
    @guests_ns.doc('get_guest_orders')
    @guests_ns.response(200, 'Success', order_model)
    @guests_ns.response(404, 'Guest not found')
    def get(self, phone_number):
        """Отримати замовлення гостя за номером телефону."""
        guest = Guest.query.filter_by(phone_number=phone_number).first()
        if not guest:
            return {'message': 'Гостя з таким номером не знайдено'}, 404

        orders = Order.query.filter_by(guest_id=guest.id).all()
        order_schema = OrderSchema(many=True)
        return order_schema.dump(orders), 200


@tables_ns.route('/')
class TableList(Resource):
    @tables_ns.doc('list_tables')
    @tables_ns.response(200, 'Success', table_model)
    def get(self):
        """Отримати список усіх столиків."""
        tables = Table.query.all()
        table_schema = TableSchema(many=True)
        return table_schema.dump(tables), 200

    @tables_ns.doc('create_table')
    @tables_ns.expect(table_model, validate=True)
    @tables_ns.response(201, 'Table created', table_model)
    @tables_ns.response(400, 'Validation Error')
    def post(self):
        """Створити новий столик."""
        table_schema = TableSchema()
        try:
            data = table_schema.load(request.get_json(), session=db.session)
            db.session.add(data)
            db.session.commit()

            return table_schema.dump(data), 201

        except ValidationError as e:
            db.session.rollback()
            return {'message': 'Помилка валідації', 'errors': e.messages}, 400
        except IntegrityError as e:
            db.session.rollback()
            return {'message': 'Помилка цілісності даних', 'error': str(e)}, 400
        except Exception as e:
            db.session.rollback()
            print(str(e))
            return {'message': 'Помилка створення страви', 'error': str(e)}, 500



@tables_ns.route('/<int:table_id>')
@tables_ns.param('table_id', 'The table identifier')
class TableResource(Resource):
    @tables_ns.doc('get_table')
    @tables_ns.response(200, 'Success', table_model)
    @tables_ns.response(404, 'Table not found')
    def get(self, table_id):
        """Отримати столик за ID."""
        table, status_code = get_object_or_404(Table, table_id)
        if status_code == 404: return table, status_code
        table_schema = TableSchema()
        return table_schema.dump(table), 200

    @tables_ns.doc('update_table')
    @tables_ns.expect(table_model, validate=True)
    @tables_ns.response(200, 'Table updated', table_model)
    @tables_ns.response(400, 'Validation Error')
    @tables_ns.response(404, 'Table not found')
    def put(self, table_id):
        """Оновити столик за ID."""
        table, status_code = get_object_or_404(Table, table_id)
        if status_code == 404: return table, status_code

        table_schema = TableSchema()
        try:
           updated_table = table_schema.load(request.get_json(), instance=table, partial=True, session=db.session)
           db.session.commit()
           return table_schema.dump(updated_table), 200
        except ValidationError as e:
              return {'message': 'Помилка валідації', 'errors': e.messages}, 400
        except Exception as e:
            db.session.rollback()
            return {'message': str(e)}, 500

    @tables_ns.doc('delete_table')
    @tables_ns.response(204, 'Table deleted')
    @tables_ns.response(404, 'Table not found')
    def delete(self, table_id):
        """Видалити столик за ID."""
        table, status_code = get_object_or_404(Table, table_id)
        if status_code == 404: return table, status_code

        db.session.delete(table)
        db.session.commit()
        return '', 204


@reservations_ns.route('/')
class ReservationList(Resource):


    @reservations_ns.doc('list_reservations', description='Отримати список усіх бронювань')
    @reservations_ns.marshal_list_with(reservation_model)
    def get(self):
        """Отримати всі бронювання""" 
        reservations = Reservation.query.all()
        return reservations, 200
    
    @reservations_ns.doc('create_reservation') 
    @reservations_ns.expect(reservation_input_model) 
    @reservations_ns.marshal_with(reservation_model, code=201) 
    def post(self):
        """Створити нове бронювання."""
        json_data = request.get_json()
        reservation_create_schema = ReservationCreateSchema()

        try:
            data = reservation_create_schema.load(json_data)
        except ValidationError as e:
            reservations_ns.abort(400, message="Помилка валідації вхідних даних.", errors=e.messages)

        requested_date_obj = data['date_str'] 
        slot_start_time_obj = data['time_slot_start_str']
        table_id = data['table_id']
        guest_count_val = data['guest_count']
        user_id_val = data.get('user_id')
        phone_number_val = data.get('phone_number')
        guest_name_val = data.get('name')
        comments_val = data.get('comments')

        slot_duration_hours = current_app.config.get('RESERVATION_SLOT_DURATION_HOURS', 1)
        reservation_start_dt = datetime.combine(requested_date_obj, slot_start_time_obj)
        reservation_end_dt = reservation_start_dt + timedelta(hours=slot_duration_hours)

        opening_hour = current_app.config.get('RESTAURANT_OPENING_HOUR', 10)
        if reservation_end_dt.time().hour < reservation_start_dt.time().hour and reservation_end_dt.time().hour < opening_hour :
             pass
        table = Table.query.get(table_id)

        if not table:
            raise NotFound(f"Столик з ID {table_id} не знайдено.")
        
        if not table.is_available: 
            reservations_ns.abort(400, message=f"Столик {table.table_number} тимчасово недоступний.")

        if table.capacity < guest_count_val:
            reservations_ns.abort(400, message=f"Столик {table.table_number} вміщує максимум {table.capacity} гостей.")

        conflicting = Reservation.query.filter(
            Reservation.table_id == table_id,
            Reservation.status == 'Підтверджено',
            Reservation.reservation_start_time < reservation_end_dt,
            Reservation.reservation_end_time > reservation_start_dt
        ).first()

        if conflicting:
            reservations_ns.abort(409, message=f"Cтолик {table.table_number} вже зайнятий на цей час. Будь ласка, оберіть інший час або столик.")
        
        final_user_id = None
        final_guest_id = None
        actual_phone_number = None

        if user_id_val:
            user = User.query.get(user_id_val)
            if not user:
                raise NotFound(f"Користувача з ID {user_id_val} не знайдено.")
            final_user_id = user.id
            actual_phone_number = user.phone_number
        elif phone_number_val:
            actual_phone_number = phone_number_val
            guest = Guest.query.filter_by(phone_number=phone_number_val).first()
            if not guest:
                guest = Guest(phone_number=phone_number_val, name=guest_name_val or f"Гість {phone_number_val}")
                db.session.add(guest)
                try:
                    db.session.flush() 
                except IntegrityError: 
                    db.session.rollback()
                    guest = Guest.query.filter_by(phone_number=phone_number_val).first()
                    if not guest: # Дуже малоймовірно, але менше дебажити треба буде
                         reservations_ns.abort(500, "Помилка при створенні/пошуку гостя.")
            final_guest_id = guest.id
        else:
            reservations_ns.abort(400, message="Необхідно вказати user_id або phone_number для бронювання.")
        
        new_reservation = Reservation(
            user_id=final_user_id,
            guest_id=final_guest_id,
            table_id=table_id,
            reservation_start_time=reservation_start_dt,
            reservation_end_time=reservation_end_dt,
            reservation_date = requested_date_obj,
            guest_count=guest_count_val,
            comments=comments_val,
            phone_number=actual_phone_number,
            status='Підтверджено' 
        )

        try:
            db.session.add(new_reservation)
            db.session.commit()
            return new_reservation, 201 
        except IntegrityError as err: 
            db.session.rollback()
            current_app.logger.error(f"Помилка IntegrityError при створенні бронювання: {err}")
            reservations_ns.abort(500, "Помилка бази даних при збереженні бронювання.")
        except Exception as e: 
            db.session.rollback()
            current_app.logger.error(f"Загальна помилка при створенні бронювання: {e}")
            reservations_ns.abort(500, "Не вдалося створити бронювання.")

@reservations_ns.route('/available-slots')
class AvailableSlots(Resource):
    @reservations_ns.expect(slots_availability_parser)
    @reservations_ns.marshal_with(date_slots_availability_response_model)

    def get(self):
        """Отримати список доступних часових слотів на обрану дату.
        Щоб правильно використовувати цей рут формат команди - /api/reservations/available-slots?date=2025-05-09&guest_count=2"""
        args = slots_availability_parser.parse_args()
        try:
            requested_date = datetime.strptime(args['date'], '%Y-%m-%d').date()
        except ValueError:
            reservations_ns.abort(400, "Невірний формат дати. Очікується YYYY-MM-DD.")
        
        guest_count = args.get('guest_count')

        opening_hour = current_app.config.get('RESTAURANT_OPENING_HOUR', 10)
        closing_hour = current_app.config.get('RESTAURANT_CLOSING_HOUR', 23)
        slot_duration_hours = current_app.config.get('RESERVATION_SLOT_DURATION_HOURS', 1)

        available_time_slots = []
        current_hour = opening_hour

        while current_hour < closing_hour:
            slot_start_time = py_time(current_hour, 0)
            # Розрахунок часу кінця слота
            end_hour_candidate = current_hour + slot_duration_hours
            slot_end_time = py_time(min(end_hour_candidate, closing_hour), 0)
            # Якщо тривалість слота робить його початок рівним або більшим за кінець (напр. closing_hour 22:30), пропускаємо
            if datetime.combine(py_date.min, slot_start_time) >= datetime.combine(py_date.min, slot_end_time) and slot_duration_hours > 0:
                current_hour += slot_duration_hours
                continue

            slot_start_dt = datetime.combine(requested_date, slot_start_time)
            slot_end_dt = datetime.combine(requested_date, slot_end_time)

            # Якщо slot_end_dt виходить на наступний день через closing_hour
            if slot_end_time.hour < slot_start_time.hour and slot_end_time.hour < opening_hour : 
                 slot_end_dt = datetime.combine(requested_date + timedelta(days=1), slot_end_time)

            query_tables = Table.query.filter(Table.is_available == True) # Перевірка на Table.is_available
            if guest_count and guest_count > 0:
                query_tables = query_tables.filter(Table.capacity >= guest_count)
            
            potential_tables = query_tables.all()
            is_any_table_available_in_slot = False

            if not potential_tables:
                is_any_table_available_in_slot = False
            else:
                for table in potential_tables:
                    conflicting_reservations = Reservation.query.filter(
                        Reservation.table_id == table.id,
                        Reservation.status == 'Підтверджено',
                        Reservation.reservation_start_time < slot_end_dt,
                        Reservation.reservation_end_time > slot_start_dt
                    ).count()

                    if conflicting_reservations == 0:
                        is_any_table_available_in_slot = True
                        break 
            available_time_slots.append({
                "slot_start": slot_start_time.strftime('%H:%M'), # Форматування для схеми
                "slot_end": slot_end_time.strftime('%H:%M'),   # Тут теж
                "is_available_for_booking": is_any_table_available_in_slot
            })
            current_hour += slot_duration_hours
            
        return {"date": requested_date.strftime('%Y-%m-%d'), "slots": available_time_slots}

@reservations_ns.route('/available-tables')
class AvailableTablesForSlot(Resource):
    @reservations_ns.expect(tables_availability_parser)
    @reservations_ns.marshal_list_with(table_slot_availability_model)
    def get(self):
        """Отримати список доступних столиків на обрану дату та часовий слот.
        Щоб правильно використовувати цей рут формат команди - /api/reservations/available-tables?date=2025-05-09&slot_start=20:00.
        Це стандартний формат, також можно додати guest_count = int s і буде /available-tables?date=2025-05-09&slot_start=20:00&guest_count=4"""
        args = tables_availability_parser.parse_args()
        try:
            requested_date = datetime.strptime(args['date'], '%Y-%m-%d').date()
            slot_start_time = datetime.strptime(args['slot_start'], '%H:%M').time()
        except ValueError:
            reservations_ns.abort(400, "Невірний формат дати або часу. Очікується YYYY-MM-DD та HH:MM.")

        guest_count = args.get('guest_count')
        slot_duration_hours = current_app.config.get('RESERVATION_SLOT_DURATION_HOURS', 1)
        requested_start_dt = datetime.combine(requested_date, slot_start_time)
        requested_end_dt = requested_start_dt + timedelta(hours=slot_duration_hours)

        # Якщо кінець слоту переходить на наступний день
        opening_hour = current_app.config.get('RESTAURANT_OPENING_HOUR', 10)
        if requested_end_dt.time().hour < requested_start_dt.time().hour and requested_end_dt.time().hour < opening_hour:
            pass
        all_tables = Table.query.all()
        result_tables_availability = []

        for table in all_tables:
            table_info = {
                "table_id": table.id,
                "table_number": table.table_number,
                "capacity": table.capacity,
                "is_available": True,
                "reason_code": None,
                "reason_message": None
            }

            # Перевірка, чи столик взагалі доступний 
            if not table.is_available:
                table_info["is_available"] = False
                table_info["reason_code"] = "TABLE_UNAVAILABLE"
                table_info["reason_message"] = "Столик тимчасово недоступний"
                result_tables_availability.append(table_info)
                continue

            # Перевірка вмістимості
            if guest_count and guest_count > 0 and table.capacity < guest_count:
                table_info["is_available"] = False
                table_info["reason_code"] = "NOT_ENOUGH_CAPACITY"
                table_info["reason_message"] = "Недостатньо місць"
                result_tables_availability.append(table_info)
                continue

            # Перевірка наявності конфліктуючих бронювань

            conflicting_reservations = Reservation.query.filter(
                Reservation.table_id == table.id,
                Reservation.status == 'Підтверджено',
                Reservation.reservation_start_time < requested_end_dt,
                Reservation.reservation_end_time > requested_start_dt
            )

            conflicting_reservations_list = conflicting_reservations.all()

            if conflicting_reservations_list:
                    current_app.logger.info(f"ЗНАЙДЕНО КОНФЛІКТ(И) для столика {table.id}:")
                    for res in conflicting_reservations_list:
                       current_app.logger.info(f"  - ID бронювання: {res.id}, Статус: {res.status}, Час: {res.reservation_start_time} - {res.reservation_end_time}")
                    table_info["is_available"] = False
                    table_info["reason_code"] = "BOOKED_IN_SLOT"
                    table_info["reason_message"] = "Заброньовано на цей час"
            else:
                  current_app.logger.info(f"Конфліктів для столика {table.id} НЕ знайдено в інтервалі {requested_start_dt} - {requested_end_dt}.")

            result_tables_availability.append(table_info)

        return result_tables_availability

@reservations_ns.route('/<int:reservation_id>')
@reservations_ns.param('reservation_id', 'The reservation identifier')
class ReservationResource(Resource):
    @reservations_ns.marshal_with(reservation_model)
    def get(self, reservation_id):
        """Отримати бронювання за ID."""
        reservation, status_code = get_object_or_404(Reservation, reservation_id)
        if status_code == 404: 
            reservation = Reservation.query.get_or_404(reservation_id, description=f"Бронювання з ID {reservation_id} не знайдено")
        return reservation
    
    @reservations_ns.expect(reservation_input_model) 
    @reservations_ns.marshal_with(reservation_model)
    def put(self, reservation_id):
        """Оновити бронювання за ID."""
        reservation = Reservation.query.get_or_404(reservation_id, description=f"Бронювання з ID {reservation_id} не знайдено")
        json_data = request.get_json()
        reservation_update_schema = ReservationCreateSchema(partial=True) # Дозволяємо часткове оновлення 
        try:
            data_to_update = reservation_update_schema.load(json_data)
        except ValidationError as err:
            reservations_ns.abort(400, message="Помилка валідації даних для оновлення.", errors=err.messages)

        allowed_to_update_simple = ['comments', 'status', 'phone_number'] # Можно змінити лише ці поля, якщо змінювати інші то треба додати повну перевірку доступності
        # Взагалі легше повністю видалити бронювання і створити нове, ніж додавати ту логіку
        needs_revalidation = False 
        if 'guest_count' in data_to_update:
            if data_to_update['guest_count'] > reservation.table.capacity:
                reservations_ns.abort(400, f"Нова кількість гостей ({data_to_update['guest_count']}) перевищує місткість столика ({reservation.table.capacity}).")
            reservation.guest_count = data_to_update['guest_count']
        for key, value in data_to_update.items():
            if key in allowed_to_update_simple:
                setattr(reservation, key, value)
        try:
            db.session.commit()
            return reservation
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Помилка при оновленні бронювання {reservation_id}: {e}")
            reservations_ns.abort(500, "Не вдалося оновити бронювання.")


@users_ns.route('/<int:user_id>/reservations')
@users_ns.param('user_id', 'The user identifier')
class UserReservations(Resource):
    @users_ns.doc('get_user_reservations')
    @users_ns.response(200, 'Success', reservation_model)
    @users_ns.response(404, 'User not found')
    def get(self, user_id):
        """Отримати бронювання користувача."""
        user, status_code = get_object_or_404(User, user_id)
        if status_code == 404: return user, status_code
        
        reservations = Reservation.query.filter_by(user_id=user_id).all()
        reservation_schema = ReservationSchema(many=True)
        return reservation_schema.dump(reservations), 200


@guests_ns.route('/<string:phone_number>/reservations')
@guests_ns.param('phone_number', 'Guest phone number')
class GuestReservations(Resource):
    @guests_ns.doc('get_guest_reservations')
    @guests_ns.response(200, 'Success', reservation_model)
    @guests_ns.response(404, 'Guest not found')
    def get(self, phone_number):
        """Отримати бронювання гостя за номером телефону."""
        guest = Guest.query.filter_by(phone_number=phone_number).first()
        if not guest:
            return {'message': 'Гостя з таким номером не знайдено'}, 404

        reservations = Reservation.query.filter_by(guest_id=guest.id).all()
        reservation_schema = ReservationSchema(many=True)
        return reservation_schema.dump(reservations), 200
    
@news_ns.route('')
class NewsList(Resource):
    @news_ns.doc('list_news')
    @news_ns.response(200, 'Success', news_model)
    @news_ns.response(400, 'Validation error')
    def get(self):
        """Отримати список усіх новин."""
        news = News.query.all()
        news_schema = NewsSchema(many=True)
        return news_schema.dump(news), 200
    
    @news_ns.doc('create_news')
    @news_ns.expect(news_model, validate=True)
    @news_ns.response(201, 'News created', news_model)
    @news_ns.response(400, 'Validation Error')
    def post(self):
        """Створити нову новину."""
        news_schema = NewsSchema()
        try:
            new_news = news_schema.load(request.get_json(), session=db.session)

            db.session.add(new_news)
            db.session.commit()

            return news_schema.dump(new_news), 201

        except ValidationError as e:
            db.session.rollback()
            return {'message': 'Помилка валідації', 'errors': e.messages}, 400
        except IntegrityError as e:
            db.session.rollback()
            return {'message': 'Помилка цілісності даних', 'error': str(e)}, 400
        except Exception as e:
            db.session.rollback()
            print(str(e))
            return {'message': 'Помилка створення новини', 'error': str(e)}, 500
        
@news_ns.route('/<int:news_id>')
@news_ns.param('news_id', 'The news identifier')
class NewsResource(Resource):
    @news_ns.doc('get_news')
    @news_ns.response(200, 'Success', news_model)
    @news_ns.response(404, 'News not found')
    @news_ns.response(500, 'Internal Server Error')
    def get(self, news_id):
        """Отримати новину за ID."""
        news_item, status_code = get_object_or_404(News, news_id)  #
        if status_code == 404:
            return news_item, status_code
        news_schema = NewsSchema()
        return news_schema.dump(news_item), 200

    @news_ns.doc('update_news')
    @news_ns.expect(news_model, validate=True)
    @news_ns.response(200, 'News updated', news_model)
    @news_ns.response(400, 'Validation Error')
    @news_ns.response(404, 'News not found')
    @news_ns.response(500, 'Internal Server Error')
    def put(self, news_id):
        """Оновити новину за ID."""
        news_item, status_code = get_object_or_404(News, news_id)
        if status_code == 404:
            return news_item, status_code

        news_schema = NewsSchema()
        try:
            updated_news = news_schema.load(
                request.get_json(), instance=news_item, partial=True, session=db.session
            )
            db.session.commit()
            return news_schema.dump(updated_news), 200
        except ValidationError as e:
            db.session.rollback()
            return {'message': 'Помилка валідації', 'errors': e.messages}, 400
        except Exception as e:
            db.session.rollback()
            return {'message': 'Помилка при оновленні новини', 'error': str(e)}, 500

    @news_ns.doc('delete_news')
    @news_ns.response(204, 'News deleted')
    @news_ns.response(404, 'News not found')
    @news_ns.response(500, 'Internal Server Error')
    def delete(self, news_id):
        """Видалити новину за ID."""
        news_item, status_code = get_object_or_404(News, news_id)
        if status_code == 404:
            return news_item, status_code
        try:
            db.session.delete(news_item)
            db.session.commit()
            return '', 204  # 204 Нема валідного контенту на видалення
        except Exception as e:
            db.session.rollback()
            return {'message':"Помилка при видаленні",  'error': str(e)}, 500
        
@modifier_groups_ns.route('/')
class ModifierGroupList(Resource):
    @modifier_groups_ns.doc('list_modifier_groups')
    @modifier_groups_ns.marshal_list_with(modifier_group_model) 
    def get(self):
        """Отримати список усіх груп модифікаторів."""
        groups = ModifierGroup.query.all()
        return groups

    @modifier_groups_ns.doc('create_modifier_group')
    @modifier_groups_ns.expect(modifier_group_model, validate=True)
    @modifier_groups_ns.marshal_with(modifier_group_model, code=201)

    def post(self):
        """Створити нову групу модифікаторів."""
        try:
            data = request.get_json()
            
            # Отримуємо дані для створення групи та опцій
            group_data = {
                'name': data.get('name'),
                'description': data.get('description'),
                'is_required': data.get('is_required', True),
                'selection_type': data.get('selection_type', 'single')
            }
            
            # Групу створюєм напряму без схеми
            new_group = ModifierGroup(**group_data)
            db.session.add(new_group)
            db.session.flush()  # отримуємо ID групи
            
            # Додаємо опції, якщо вони є
            options_data = data.get('options', [])
            for option_data in options_data:
                option = ModifierOption(
                    group_id=new_group.id,
                    name=option_data.get('name'),
                    price_modifier=option_data.get('price_modifier', 0.00),
                    is_default=option_data.get('is_default', False)
                )
                db.session.add(option)
            
            db.session.commit()
            return new_group, 201
        except ValidationError as e:
            db.session.rollback()
            return {'message': 'Помилка валідації даних', 'errors': e.messages}, 400
        except IntegrityError as e:
            db.session.rollback()
            return {'message': 'Помилка цілісності даних (можливо, група з такою назвою вже існує)', 'error': str(getattr(e, 'orig', e))}, 400
        except Exception as e:
            db.session.rollback()
            print(f"Error creating modifier group: {e}")
            return {'message': 'Внутрішня помилка сервера при створенні групи', 'error': str(e)}, 500

@modifier_groups_ns.route('/<int:group_id>')
@modifier_groups_ns.param('group_id', 'The modifier group identifier')
class ModifierGroupResource(Resource):

    @modifier_groups_ns.doc('get_modifier_group')
    @modifier_groups_ns.marshal_with(modifier_group_model)
    @modifier_groups_ns.response(404, 'Modifier Group not found')
    def get(self, group_id):
        """Отримати групу модифікаторів за ID."""
        group = ModifierGroup.query.get_or_404(group_id)
        return group

    @modifier_groups_ns.doc('update_modifier_group')
    @modifier_groups_ns.expect(modifier_group_model, validate=True)
    @modifier_groups_ns.marshal_with(modifier_group_model)
    @modifier_groups_ns.response(400, 'Validation Error')
    @modifier_groups_ns.response(404, 'Modifier Group not found')
    def put(self, group_id):
        """Оновити групу модифікаторів за ID."""
        group = ModifierGroup.query.get_or_404(group_id)
        try:
            data = request.get_json()
            
            # Оновлюємо базові поля групи
            if 'name' in data:
                group.name = data['name']
            if 'description' in data:
                group.description = data['description']
            if 'is_required' in data:
                group.is_required = data['is_required']
            if 'selection_type' in data:
                group.selection_type = data['selection_type']
            
            # Обробляємо опції, якщо вони передані
            if 'options' in data:
                # Видаляємо існуючі опції та створюємо нові
                ModifierOption.query.filter_by(group_id=group_id).delete()
                db.session.flush()
                
                for option_data in data.get('options', []):
                    option = ModifierOption(
                        group_id=group_id,
                        name=option_data.get('name'),
                        price_modifier=option_data.get('price_modifier', 0.00),
                        is_default=option_data.get('is_default', False)
                    )
                    db.session.add(option)
            
            db.session.commit()
            return group
            
        except ValidationError as e:
             db.session.rollback()
             return {'message': 'Помилка валідації', 'errors': e.messages}, 400
        except IntegrityError as e:
             db.session.rollback()
             return {'message': 'Помилка цілісності даних.', 'error': str(getattr(e, 'orig', e))}, 400
        except Exception as e:
             db.session.rollback()
             print(f"Error updating group {group_id}: {e}")
             return {'message': 'Внутрішня помилка сервера.', 'error': str(e)}, 500