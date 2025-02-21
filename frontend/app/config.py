import os

class Config:
    DEBUG = True
    MONGODB_SETTINGS = {
        'db': os.getenv('DB_NAME', 'silvermoon'),
        'host': os.getenv('MONGO_HOST', 'database'),
        'port': int(os.getenv('MONGO_PORT', 27017))
    }
