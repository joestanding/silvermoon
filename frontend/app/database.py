from mongoengine import connect

def init_db(app):
    settings = app.config['MONGODB_SETTINGS']
    connect(
        db=settings['db'],
        host=settings['host'],
        port=settings['port']
    )
