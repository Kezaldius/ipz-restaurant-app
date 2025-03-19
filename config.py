import os
import decimal
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'default-key-for-dev'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') 
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

