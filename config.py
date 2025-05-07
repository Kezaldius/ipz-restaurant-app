import os
import decimal
from dotenv import load_dotenv

load_dotenv()

class Config:
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    OTP_EXPIRATION_SECONDS = 1800 # Час життя OTP у секундах. Для тестів використаємо 30 хвилин. 
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') 
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 299, # Коли з'єднання становиться старше за 299 секунд, то пул перестворює з'єднання
        'pool_pre_ping': True # Пінгуємо БД перед з'єднанням
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    RESTFUL_JSON = {'ensure_ascii': False,  'separators': (', ', ': '), 'indent': 2, 'sort_keys':True,
                    'default': lambda o: float(o) if isinstance(o, decimal.Decimal) else o
                    }
    
class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

