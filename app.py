from routes.public import public
from routes.auth import auth
from routes.admin import admin
from flask import Flask, render_template
from config import SECRET_KEY


app = Flask(__name__)
app.register_blueprint(public)
app.register_blueprint(auth)
app.register_blueprint(admin)
app.secret_key = SECRET_KEY


@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(error):
    return render_template("500.html"), 500


if __name__ == '__main__':
    app.run(debug=True)  