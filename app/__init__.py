from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_restful import Api
from config import config

db = SQLAlchemy()
migrate = Migrate()
api = Api()

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    db.init_app(app)
    migrate.init_app(app, db)

    api = Api(app)

    from app.routes import initialize_routes
    initialize_routes(api)

    return app