from flask import Flask
from app.config import Config
from app.database import init_db
from app.routes import main

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['SECRET_KEY'] = 'ojwadawjdawdawd'

    init_db(app)

    app.register_blueprint(main)
    return app
