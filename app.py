from routes.public import public
from routes.auth import auth
from routes.admin import admin
from routes.common import media_url
from flask import Flask, render_template, flash, redirect, request
from config import SECRET_KEY
from datetime import datetime


app = Flask(__name__)
app.register_blueprint(public)
app.register_blueprint(auth)
app.register_blueprint(admin)
app.secret_key = SECRET_KEY
# Total size of one request, so several project images can be uploaded at once
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024


@app.context_processor
def inject_globals():
    return {"current_year": datetime.now().year, "media_url": media_url}


@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(413)
def file_too_large(error):
    flash("Upload is too large. The total size must be under 32 MB.", "danger")
    return redirect(request.url)


@app.errorhandler(500)
def internal_server_error(error):
    return render_template("500.html"), 500


if __name__ == '__main__':
    app.run(debug=True)  