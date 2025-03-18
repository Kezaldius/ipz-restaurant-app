from flask import request, jsonify
from flask_restful import Resource, reqparse
from app import db
from app.models import User, Dish, Order, OrderItem, Table, Reservation
from app.schemas import UserSchema, DishSchema, OrderSchema, OrderItemSchema, TableSchema, ReservationSchema
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy.exc import IntegrityError, OperationalError
from marshmallow import ValidationError



def get_object_or_404(model, id):
    obj = model.query.get(id)
    if obj is None:
        return {'message': f'{model.__name__} not found'}, 404
    return obj, 200


#  Реєстрація користувача
class UserRegistration(Resource):
    def post(self):
        user_schema = UserSchema()
        try:
            new_user = user_schema.load(request.get_json(), session=db.session)
        except ValidationError as e:
             return {'message': 'Помилка валідації даних', 'errors': e.messages}, 400

        # Перевірка на унікальність email та username вже є в схемі UserSchema (Оптимізувати)
        if 'password' in request.get_json():
            new_user.set_password(request.get_json()['password'])  # Хешуємо пароль
        db.session.add(new_user)

        try:
            db.session.commit()
            return user_schema.dump(new_user), 201  # Повертаємо створеного користувача
        except IntegrityError:  
            db.session.rollback()
            return {'message': 'Помилка при створенні користувача', 'error': str(e)}, 500



#  Вхід користувача 
class UserLogin(Resource):
     def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('username', type=str, required=True, help="Ім'я користувача обов'язкове")
        parser.add_argument('password', type=str, required=True, help='Пароль обов\'язковий')
        args = parser.parse_args()

        user = User.query.filter_by(username=args['username']).first()
        if user and user.check_password(args['password']):

            return {'message': 'Успішний вхід', 'user_id': user.id}, 200
        else:
            return {'message': 'Невірне ім\'я користувача або пароль'}, 401


# CRUD для страв
class DishList(Resource):
    def get(self):
        dishes = Dish.query.all()
        dish_schema = DishSchema(many=True)
        return dish_schema.dump(dishes), 200

    def post(self):
        dish_schema = DishSchema()
        try:
            new_dish = dish_schema.load(request.get_json(), session=db.session)
            
            db.session.add(new_dish)
            db.session.commit()
            
            return dish_schema.dump(new_dish), 201
            
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

class DishResource(Resource):
    def get(self, dish_id):
        dish, status_code = get_object_or_404(Dish, dish_id)
        if status_code == 404: return dish, status_code 
        dish_schema = DishSchema()
        return dish_schema.dump(dish), 200

    def put(self, dish_id):
        dish, status_code = get_object_or_404(Dish, dish_id)
        if status_code == 404: return dish, status_code

        dish_schema = DishSchema()
        try:
           data = dish_schema.load(request.get_json(), session=db.session)
           new_dish = Dish(**data)
           db.session.add(new_dish)
           db.session.commit()
           return dish_schema.dump(new_dish), 201
        except ValidationError as e:
             db.session.rollback()
             return {'message': 'Помилка валідації', 'errors': e.messages}, 400
        except Exception as e: 
             db.session.rollback()
             print(str(e))
             return {'message': 'Помилка створення страви'}, 500


    def delete(self, dish_id):
         dish, status_code = get_object_or_404(Dish, dish_id)
         if status_code == 404: return dish, status_code
         db.session.delete(dish)
         db.session.commit()
         return {'message': 'Страву видалено'}, 200


# CRUD для замовлень

class OrderList(Resource):

   
    def post(self):

        try:
            data = request.get_json()
           # data['user_id'] = user_id # Додаємо id користувача до даних замовлення.
        except:
            return {'message': 'Некоректні данні'}, 400
        
        # Валідація даних
        if not data or 'items' not in data or not data['items']:
             return {'message': "Необхідно вказати список страв"}, 400
        
        # Перевірка наявності юзера
        user, status_code = get_object_or_404(User, data['user_id'])
        if status_code == 404: return user, status_code
        
        # Створення замовлення
        order = Order(user_id=data['user_id'], delivery_address = data.get('delivery_address'), comments=data.get('comments'))

        total_price = 0
        # Обробка елементів замовлення (страв)
        for item_data in data['items']:
            dish, status_code = get_object_or_404(Dish, item_data['dish_id'])
            if status_code == 404:
                return dish, status_code 

            if not dish.is_available:
                return {'message': f'Страва "{dish.name}" недоступна'}, 400

            if item_data['quantity'] <= 0:
                 return {'message': "Кількість страв має бути більше нуля"}, 400

            order_item = OrderItem(dish=dish, quantity=item_data['quantity'], price=dish.price)
            order.items.append(order_item)
            total_price += dish.price * item_data['quantity']

        order.total_price = total_price
        db.session.add(order)

        try:
            db.session.commit()
            order_schema = OrderSchema()
            return order_schema.dump(order), 201  # Повертаємо створене замовлення
        except Exception as e:
            db.session.rollback()
            return {'message': 'Помилка створення замовлення', 'error': str(e)}, 500

class OrderResource(Resource):

    def get(self, order_id):
        order, status_code = get_object_or_404(Order, order_id)
        if status_code == 404: return order, status_code


        order_schema = OrderSchema()
        return order_schema.dump(order), 200

    def put(self, order_id):
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


    def delete(self, order_id):
        order, status_code = get_object_or_404(Order, order_id)
        if status_code == 404: return order, status_code

  

        db.session.delete(order)
        db.session.commit()
        return {'message': 'Замовлення видалено'}, 200


#Отримання замовлень для конкретного користувача
class UserOrders(Resource):
    def get(self, user_id):
  
        
        user, status_code = get_object_or_404(User, user_id)
        if status_code == 404: return user, status_code

        orders = Order.query.filter_by(user_id=user_id).all()
        order_schema = OrderSchema(many=True)
        return order_schema.dump(orders), 200


# CRUD для столиків
class TableList(Resource):
    def get(self):
        tables = Table.query.all()
        table_schema = TableSchema(many=True)
        return table_schema.dump(tables), 200
    
    def post(self):

        
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
        

class TableResource(Resource):
    def get(self, table_id):
       table, status_code = get_object_or_404(Table, table_id)
       if status_code == 404: return table, status_code
       table_schema = TableSchema()
       return table_schema.dump(table), 200

    def put(self, table_id):
        table, status_code = get_object_or_404(Table, table_id)
        if status_code == 404: return table, status_code


        table_schema = TableSchema()
        try:
           updated_table = table_schema.load(request.get_json(), instance=table, partial=True)
        except Exception as e:
              return {'message': 'Помилка валідації', 'errors': e.messages}, 400

        db.session.commit()
        return table_schema.dump(updated_table), 200

    def delete(self, table_id):
        table, status_code = get_object_or_404(Table, table_id)
        if status_code == 404: return table, status_code


        db.session.delete(table)
        db.session.commit()
        return {'message': 'Столик видалено'}, 200


# CRUD для бронювань
class ReservationList(Resource):
    def post(self):
        reservation_schema = ReservationSchema()
        try:
            data = request.get_json()
            
            # Перевірка на наявність столика
            table, status_code = get_object_or_404(Table, data['table_id'])
            if status_code == 404: 
                return table, status_code
                
            # Перевірка на справжність юзера (Змінити логіку коли додам можливість гостевих користувачей)
            user, status_code = get_object_or_404(User, data['user_id'])
            if status_code == 404: 
                return user, status_code
            
            new_reservation = Reservation(
                user_id=data['user_id'],
                table_id=data['table_id'],
                reservation_date=datetime.strptime(data['reservation_date'], '%Y-%m-%d %H:%M:%S'),
                guest_count=data['guest_count'],
                comments=data.get('comments'),
                status=data.get('status', 'Підтверджено')
            )
            
            db.session.add(new_reservation)
            db.session.commit()
            
            return reservation_schema.dump(new_reservation), 201
            
        except ValidationError as e:
            return {'message': 'Помилка валідації', 'errors': e.messages}, 400
        except IntegrityError as e:
            db.session.rollback()
            return {'message': 'Помилка цілісності даних', 'error': str(e)}, 400
        except KeyError as e:
            return {'message': f'Відсутнє обов\'язкове поле: {str(e)}'}, 400
        except Exception as e:
            db.session.rollback()
            return {'message': 'Помилка створення бронювання', 'error': str(e)}, 500

class ReservationResource(Resource):
    def get(self, reservation_id):
        reservation, status_code = get_object_or_404(Reservation, reservation_id)
        if status_code == 404: return reservation, status_code

        reservation_schema = ReservationSchema()
        return reservation_schema.dump(reservation), 200

    def put(self, reservation_id):
        reservation, status_code = get_object_or_404(Reservation, reservation_id)
        if status_code == 404: return reservation, status_code



        reservation_schema = ReservationSchema()
        try:
           updated_reservation = reservation_schema.load(request.get_json(), instance=reservation, partial=True)
        except Exception as e:
            return {'message':'Помилка валідації', 'errors':e.messages}, 400

        db.session.commit()
        return reservation_schema.dump(updated_reservation), 200
    
    def delete(self, reservation_id):
        reservation, status_code = get_object_or_404(Reservation, reservation_id)
        if status_code == 404: return reservation, status_code
        
  

        db.session.delete(reservation)
        db.session.commit()
        return {'message': 'Бронювання видалено'}, 200

#Отримання бронювань для конкретного користувача
class UserReservations(Resource):
    def get(self, user_id):
        user, status_code = get_object_or_404(User, user_id)
        if status_code == 404: return user, status_code
        
        reservations = Reservation.query.filter_by(user_id=user_id).all()
        reservation_schema = ReservationSchema(many=True)
        return reservation_schema.dump(reservations), 200
    
def initialize_routes(api):
    print("API маршрути запускаються")
    api.add_resource(UserRegistration, '/api/register')
    api.add_resource(UserLogin, '/api/login')
    api.add_resource(DishList, '/api/dishes')
    api.add_resource(DishResource, '/api/dishes/<int:dish_id>')
    api.add_resource(OrderList, '/api/orders')
    api.add_resource(OrderResource, '/api/orders/<int:order_id>')
    api.add_resource(UserOrders, '/api/users/<int:user_id>/orders')
    api.add_resource(TableList, '/api/tables')
    api.add_resource(TableResource, '/api/tables/<int:table_id>')
    api.add_resource(ReservationList, '/api/reservations')
    api.add_resource(ReservationResource, '/api/reservations/<int:reservation_id>')
    api.add_resource(UserReservations, '/api/users/<int:user_id>/reservations')
    print("API маршрути запущені") # Видалити дебаг прінти при деплої