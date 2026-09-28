from routes.public import public
from routes.auth import auth
from routes.admin import admin
from flask import Flask
from config import SECRET_KEY


app = Flask(__name__)
app.register_blueprint(public)
app.register_blueprint(auth)
app.register_blueprint(admin)
app.secret_key = SECRET_KEY


if __name__ == '__main__':
    app.run(debug=True)  